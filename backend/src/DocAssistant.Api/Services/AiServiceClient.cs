using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace DocAssistant.Api.Services;

public record IngestResult(Guid DocumentId, int Pages, int Chunks);

public record AiSource(Guid DocumentId, int Page, int ChunkIndex, string Snippet, double Score);

public record QueryResult(string Answer, bool Grounded, List<AiSource> Sources);

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
