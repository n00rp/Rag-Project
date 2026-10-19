using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using DocAssistant.Api.Contracts;
using DocAssistant.Api.Domain;
using DocAssistant.Api.Services;
using DocAssistant.Api.Tests.TestSupport;
using FluentAssertions;

namespace DocAssistant.Api.Tests;

public sealed class StreamingTests : IClassFixture<ApiFactory>
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web)
    {
        Converters = { new JsonStringEnumConverter() },
    };

    private readonly ApiFactory _factory;
    private readonly HttpClient _client;

    public StreamingTests(ApiFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
        factory.Ai.Failure = null;
        factory.Ai.OnStream = null;
    }

    private async Task<DocumentDto> ReadyDocumentAsync(string name = "protokoll.pdf")
    {
        var form = new MultipartFormDataContent
        {
            { new ByteArrayContent(Encoding.ASCII.GetBytes("%PDF-1.4 fake pdf content")), "file", name },
        };
        var response = await _client.PostAsync("/api/documents", form);
        var doc = (await response.Content.ReadFromJsonAsync<DocumentDto>(Json))!;
        for (var i = 0; i < 100; i++)
        {
            doc = (await _client.GetFromJsonAsync<DocumentDto>($"/api/documents/{doc.Id}", Json))!;
            if (doc.Status == DocumentStatus.Ready) return doc;
            await Task.Delay(50);
        }
        throw new TimeoutException("document never became ready");
    }

    private static async IAsyncEnumerable<AiStreamEvent> Events(params AiStreamEvent[] events)
    {
        foreach (var e in events) yield return e;
        await Task.CompletedTask;
    }

    private async Task<HttpResponseMessage> PostStreamAsync(string question, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/api/chat/stream")
        {
            Content = JsonContent.Create(new ChatRequest(question, null)),
        };
        return await _client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
    }

    private static async Task<List<JsonElement>> ReadEventsAsync(HttpResponseMessage response)
    {
        var events = new List<JsonElement>();
        using var reader = new StreamReader(await response.Content.ReadAsStreamAsync());
        while (await reader.ReadLineAsync() is { } line)
            if (line.Length > 0) events.Add(JsonDocument.Parse(line).RootElement.Clone());
        return events;
    }

    private async Task<List<ChatAnswerDto>> HistoryAsync() =>
        (await _client.GetFromJsonAsync<List<ChatAnswerDto>>("/api/chat/history", Json))!;

    [Fact]
    public async Task Answer_is_streamed_with_file_names_and_saved_when_it_is_done()
    {
        var doc = await ReadyDocumentAsync("skolskjuts.pdf");
        _factory.Ai.OnStream = (_, _, _) => Events(
            new AiSourcesEvent([new AiSource(doc.Id, Page: 2, ChunkIndex: 4, "utdrag", 0.91)]),
            new AiTokenEvent("Skolskjuts "),
            new AiTokenEvent("införs [1]."),
            new AiDoneEvent("Skolskjuts införs [1].", Grounded: true));

        var response = await PostStreamAsync("Vad beslutades?");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/x-ndjson");
        var events = await ReadEventsAsync(response);
        events.Select(e => e.GetProperty("type").GetString()).Should().Equal("sources", "token", "token", "done");
        events[0].GetProperty("sources")[0].GetProperty("fileName").GetString().Should().Be("skolskjuts.pdf");
        events[3].GetProperty("message").GetProperty("answer").GetString().Should().Be("Skolskjuts införs [1].");

        var saved = (await HistoryAsync()).Single(m => m.Id == events[3].GetProperty("message").GetProperty("id").GetGuid());
        saved.Interrupted.Should().BeFalse();
        saved.Sources.Should().ContainSingle().Which.FileName.Should().Be("skolskjuts.pdf");
    }

    [Fact]
    public async Task Support_level_and_the_overview_flag_are_forwarded_and_saved()
    {
        await ReadyDocumentAsync();
        _factory.Ai.OnStream = (_, _, _) => Events(
            new AiSupportEvent("delvis"),
            new AiTokenEvent("Summan saknas."),
            new AiDoneEvent("Summan saknas.", Grounded: true, Support: "delvis", Broad: true));

        var events = await ReadEventsAsync(await PostStreamAsync("Hur stor var budgeten?"));

        events.Select(e => e.GetProperty("type").GetString()).Should().Equal("support", "token", "done");
        events[0].GetProperty("level").GetString().Should().Be("delvis");
        var message = events[2].GetProperty("message");
        message.GetProperty("support").GetString().Should().Be("delvis");
        message.GetProperty("broad").GetBoolean().Should().BeTrue();
        var saved = (await HistoryAsync()).Single(m => m.Id == message.GetProperty("id").GetGuid());
        (saved.Support, saved.Broad).Should().Be(("delvis", true));
    }

    [Fact]
    public async Task A_refusal_is_saved_without_sources_even_though_they_were_announced()
    {
        var doc = await ReadyDocumentAsync();
        _factory.Ai.OnStream = (_, _, _) => Events(
            new AiSourcesEvent([new AiSource(doc.Id, 1, 0, "utdrag", 0.9)]),
            new AiTokenEvent("Jag hittar inget stöd för det i dokumenten."),
            new AiDoneEvent("Jag hittar inget stöd för det i dokumenten.", Grounded: false));

        var events = await ReadEventsAsync(await PostStreamAsync("Något utan stöd?"));

        var message = events[^1].GetProperty("message");
        message.GetProperty("grounded").GetBoolean().Should().BeFalse();
        message.GetProperty("sources").GetArrayLength().Should().Be(0);
    }

    [Fact]
    public async Task Model_unreachable_before_the_first_event_is_a_normal_503()
    {
        _factory.Ai.Failure = new AiServiceUnavailableException("nere");

        var response = await PostStreamAsync("Hej?");

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        (await response.Content.ReadAsStringAsync()).Should().Contain("ai_unavailable");
    }

    [Fact]
    public async Task A_failure_in_the_middle_ends_with_an_error_event_and_keeps_what_was_written()
    {
        await ReadyDocumentAsync();
        _factory.Ai.OnStream = (_, _, _) => Failing();
        static async IAsyncEnumerable<AiStreamEvent> Failing()
        {
            yield return new AiTokenEvent("Halva svaret");
            await Task.CompletedTask;
            throw new AiServiceUnavailableException("bröts");
        }

        var events = await ReadEventsAsync(await PostStreamAsync("Fråga som avbryts?"));

        events.Select(e => e.GetProperty("type").GetString()).Should().Equal("token", "error");
        events[1].GetProperty("code").GetString().Should().Be("ai_unavailable");
        var saved = (await HistoryAsync()).Single(m => m.Question == "Fråga som avbryts?");
        saved.Answer.Should().Be("Halva svaret");
        saved.Interrupted.Should().BeTrue();
    }

    [Fact]
    public async Task Stopping_the_answer_saves_the_partial_text_as_interrupted()
    {
        await ReadyDocumentAsync();
        _factory.Ai.OnStream = (_, _, ct) => Slow(ct);
        static async IAsyncEnumerable<AiStreamEvent> Slow([System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
        {
            yield return new AiTokenEvent("Det här hann ");
            yield return new AiTokenEvent("skrivas.");
            await Task.Delay(Timeout.Infinite, ct); // the model keeps going until the client gives up
        }
        using var stop = new CancellationTokenSource();

        using var response = await PostStreamAsync("Fråga som stoppas?", stop.Token);
        using var reader = new StreamReader(await response.Content.ReadAsStreamAsync());
        await reader.ReadLineAsync(); // both tokens have arrived once the second line is read
        await reader.ReadLineAsync();
        stop.Cancel();
        reader.Dispose();

        ChatAnswerDto? saved = null;
        for (var i = 0; i < 100 && saved is null; i++)
        {
            await Task.Delay(50);
            saved = (await HistoryAsync()).SingleOrDefault(m => m.Question == "Fråga som stoppas?");
        }
        saved.Should().NotBeNull();
        saved!.Answer.Should().Be("Det här hann skrivas.");
        saved.Interrupted.Should().BeTrue();
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public async Task Empty_question_is_rejected_before_streaming_starts(string question)
    {
        var response = await PostStreamAsync(question);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }
}
