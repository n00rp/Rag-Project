using System.Net;
using System.Runtime.CompilerServices;
using System.Net.Http.Json;
using System.Text.Json;

namespace DocAssistant.Api.Services;

public record IngestResult(Guid DocumentId, int Pages, int Chunks);

public record AiSource(Guid DocumentId, int Page, int ChunkIndex, string Snippet, double Score);

public record QueryResult(string Answer, bool Grounded, List<AiSource> Sources);

/// <summary>One event of a streamed answer: sources once, tokens while the model writes, then done.</summary>
public abstract record AiStreamEvent;

public sealed record AiSourcesEvent(List<AiSource> Sources) : AiStreamEvent;

public sealed record AiTokenEvent(string Text) : AiStreamEvent;

/// <summary>The whole answer. If <paramref name="Grounded"/> is false the announced sources must not be shown.</summary>
public sealed record AiDoneEvent(string Answer, bool Grounded) : AiStreamEvent;

/// <summary>The AI service (or the LLM behind it) can't be reached right now.</summary>
public class AiServiceUnavailableException(string message, Exception? inner = null) : Exception(message, inner);

/// <summary>The AI service understood the request but refused it (bad file, scanned PDF, ...).</summary>
public class AiServiceRejectedException(HttpStatusCode status, string message) : Exception(message)
{
    public HttpStatusCode Status { get; } = status;
}

public interface IAiServiceClient
{
    Task<IngestResult> IngestAsync(string ownerId, Guid documentId, Stream file, string fileName, CancellationToken ct);
    Task<QueryResult> QueryAsync(string ownerId, string question, IReadOnlyList<Guid>? documentIds, CancellationToken ct);

    /// <summary>Same question, but the answer arrives as it is written. Throws <see cref="AiServiceUnavailableException"/>
    /// if the model cannot be reached, before the first event or in the middle of the stream.</summary>
    IAsyncEnumerable<AiStreamEvent> QueryStreamAsync(string ownerId, string question, IReadOnlyList<Guid>? documentIds, CancellationToken ct);
    Task DeleteAsync(string ownerId, Guid documentId, CancellationToken ct);
    Task<bool> IsHealthyAsync(CancellationToken ct);
}

public sealed class AiServiceClient(HttpClient http) : IAiServiceClient
{
    // The Python service speaks snake_case.
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web)
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    };

    public async Task<IngestResult> IngestAsync(string ownerId, Guid documentId, Stream file, string fileName, CancellationToken ct)
    {
        using var form = new MultipartFormDataContent
        {
            { new StringContent(ownerId), "owner_id" },
            { new StringContent(documentId.ToString()), "document_id" },
            { new StreamContent(file), "file", fileName },
        };
        return await SendAsync<IngestResult>(() => http.PostAsync("ingest", form, ct), ct);
    }

    public async Task<QueryResult> QueryAsync(string ownerId, string question, IReadOnlyList<Guid>? documentIds, CancellationToken ct)
    {
        var body = new { ownerId, question, documentIds };
        return await SendAsync<QueryResult>(() => http.PostAsJsonAsync("query", body, Json, ct), ct);
    }

    public async IAsyncEnumerable<AiStreamEvent> QueryStreamAsync(
        string ownerId, string question, IReadOnlyList<Guid>? documentIds,
        [EnumeratorCancellation] CancellationToken ct)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "query/stream")
        {
            Content = JsonContent.Create(new { ownerId, question, documentIds }, options: Json),
        };
        // ResponseHeadersRead: hand over events as they arrive instead of waiting for the whole body.
        using var response = await SendRawAsync(() => http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct));
        await EnsureSuccessAsync(response, ct);

        using var reader = new StreamReader(await response.Content.ReadAsStreamAsync(ct));
        while (true)
        {
            string? line;
            try
            {
                line = await reader.ReadLineAsync(ct);
            }
            catch (Exception ex) when (ex is IOException or HttpRequestException)
            {
                throw new AiServiceUnavailableException("Anslutningen till AI-tjänsten bröts.", ex);
            }
            if (line is null) yield break;
            if (line.Length == 0) continue;
            yield return ParseEvent(line);
        }
    }

    private static AiStreamEvent ParseEvent(string line)
    {
        try
        {
            using var doc = JsonDocument.Parse(line);
            var root = doc.RootElement;
            switch (root.GetProperty("type").GetString())
            {
                case "sources":
                    return new AiSourcesEvent(root.GetProperty("sources").Deserialize<List<AiSource>>(Json) ?? []);
                case "token":
                    return new AiTokenEvent(root.GetProperty("text").GetString() ?? "");
                case "done":
                    return new AiDoneEvent(root.GetProperty("answer").GetString() ?? "", root.GetProperty("grounded").GetBoolean());
                case "error":
                    var message = root.TryGetProperty("message", out var m) ? m.GetString() : null;
                    throw new AiServiceUnavailableException(message ?? "AI-tjänsten rapporterade ett fel.");
            }
        }
        catch (Exception ex) when (ex is JsonException or KeyNotFoundException or InvalidOperationException)
        {
            throw new AiServiceUnavailableException("AI-tjänsten skickade ett oläsligt svar.", ex);
        }
        throw new AiServiceUnavailableException("AI-tjänsten skickade en okänd händelse.");
    }

    public async Task DeleteAsync(string ownerId, Guid documentId, CancellationToken ct)
    {
        using var response = await SendRawAsync(
            () => http.DeleteAsync($"documents/{documentId}?owner_id={Uri.EscapeDataString(ownerId)}", ct));
        await EnsureSuccessAsync(response, ct);
    }

    public async Task<bool> IsHealthyAsync(CancellationToken ct)
    {
        try
        {
            using var response = await http.GetAsync("health", ct);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return false;
        }
    }

    private async Task<T> SendAsync<T>(Func<Task<HttpResponseMessage>> send, CancellationToken ct)
    {
        using var response = await SendRawAsync(send);
        await EnsureSuccessAsync(response, ct);
        return (await response.Content.ReadFromJsonAsync<T>(Json, ct))
               ?? throw new AiServiceUnavailableException("AI-tjänsten returnerade ett tomt svar.");
    }

    private static async Task<HttpResponseMessage> SendRawAsync(Func<Task<HttpResponseMessage>> send)
    {
        try
        {
            return await send();
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            throw new AiServiceUnavailableException("AI-tjänsten kan inte nås.", ex);
        }
    }

    private static async Task EnsureSuccessAsync(HttpResponseMessage response, CancellationToken ct)
    {
        if (response.IsSuccessStatusCode) return;

        var detail = await ReadDetailAsync(response, ct);
        if ((int)response.StatusCode >= 500)
            throw new AiServiceUnavailableException(detail ?? $"AI-tjänsten svarade {(int)response.StatusCode}.");
        throw new AiServiceRejectedException(response.StatusCode, detail ?? "Begäran avvisades av AI-tjänsten.");
    }

    private static async Task<string?> ReadDetailAsync(HttpResponseMessage response, CancellationToken ct)
    {
        try
        {
            using var doc = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(ct), cancellationToken: ct);
            return doc.RootElement.TryGetProperty("detail", out var d) && d.ValueKind == JsonValueKind.String
                ? d.GetString()
                : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
