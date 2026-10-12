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

public sealed class ApiTests : IClassFixture<ApiFactory>
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web)
    {
        Converters = { new JsonStringEnumConverter() },
    };

    private readonly ApiFactory _factory;
    private readonly HttpClient _client;

    public ApiTests(ApiFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
        factory.Ai.Failure = null;
        factory.Ai.OnQuery = null;
    }

    private static MultipartFormDataContent PdfUpload(string name = "protokoll.pdf", string? body = null)
    {
        var bytes = Encoding.ASCII.GetBytes(body ?? "%PDF-1.4 fake pdf content");
        return new MultipartFormDataContent { { new ByteArrayContent(bytes), "file", name } };
    }

    private async Task<DocumentDto> UploadAsync(string name = "protokoll.pdf")
    {
        var response = await _client.PostAsync("/api/documents", PdfUpload(name));
        response.StatusCode.Should().Be(HttpStatusCode.Accepted);
        return (await response.Content.ReadFromJsonAsync<DocumentDto>(Json))!;
    }

    private async Task<DocumentDto> WaitForStatusAsync(Guid id, DocumentStatus status)
    {
        for (var i = 0; i < 100; i++)
        {
            var doc = await _client.GetFromJsonAsync<DocumentDto>($"/api/documents/{id}", Json);
            if (doc!.Status == status) return doc;
            await Task.Delay(50);
        }
        throw new TimeoutException($"Document {id} never reached {status}");
    }

    [Fact]
    public async Task Uploaded_pdf_is_processed_in_the_background_and_becomes_ready()
    {
        var uploaded = await UploadAsync();
        uploaded.Status.Should().Be(DocumentStatus.Queued);

        var ready = await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);

        ready.PageCount.Should().Be(3);
        ready.ChunkCount.Should().Be(7);
        _factory.Ai.Ingested.Should().Contain(uploaded.Id);
    }

    [Fact]
    public async Task Non_pdf_content_is_rejected_even_with_pdf_extension()
    {
        var content = new MultipartFormDataContent { { new ByteArrayContent("hello world"u8.ToArray()), "file", "evil.pdf" } };

        var response = await _client.PostAsync("/api/documents", content);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        (await response.Content.ReadAsStringAsync()).Should().Contain("PDF");
    }

    [Fact]
    public async Task Oversized_upload_is_rejected_with_413()
    {
        var response = await _client.PostAsync("/api/documents", PdfUpload(body: "%PDF-" + new string('x', 3000)));

        response.StatusCode.Should().Be(HttpStatusCode.RequestEntityTooLarge);
    }

    [Fact]
    public async Task Document_rejected_by_ai_service_is_marked_failed_with_the_reason()
    {
        _factory.Ai.Failure = new AiServiceRejectedException(HttpStatusCode.UnprocessableEntity, "PDF:en är skannad.");

        var uploaded = await UploadAsync();
        var failed = await WaitForStatusAsync(uploaded.Id, DocumentStatus.Failed);

        failed.Error.Should().Be("PDF:en är skannad.");
    }

    [Fact]
    public async Task Failed_document_can_be_retried_once_the_ai_service_is_back()
    {
        _factory.Ai.Failure = new AiServiceUnavailableException("nere");
        var uploaded = await UploadAsync();
        var failed = await WaitForStatusAsync(uploaded.Id, DocumentStatus.Failed);
        failed.Error.Should().Contain("inte tillgänglig");

        _factory.Ai.Failure = null;
        var retry = await _client.PostAsync($"/api/documents/{uploaded.Id}/retry", null);
        retry.StatusCode.Should().Be(HttpStatusCode.Accepted);

        await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);
    }

    [Fact]
    public async Task Retry_on_a_ready_document_is_a_conflict()
    {
        var uploaded = await UploadAsync();
        await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);

        var response = await _client.PostAsync($"/api/documents/{uploaded.Id}/retry", null);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    }

    [Fact]
    public async Task Delete_removes_vectors_row_and_file()
    {
        var uploaded = await UploadAsync();
        await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);

        var response = await _client.DeleteAsync($"/api/documents/{uploaded.Id}");

        response.StatusCode.Should().Be(HttpStatusCode.NoContent);
        _factory.Ai.Deleted.Should().Contain(uploaded.Id);
        (await _client.GetAsync($"/api/documents/{uploaded.Id}")).StatusCode.Should().Be(HttpStatusCode.NotFound);
        (await _client.GetAsync($"/api/documents/{uploaded.Id}/file")).StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task Delete_keeps_the_document_if_vectors_could_not_be_removed()
    {
        var uploaded = await UploadAsync();
        await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);
        _factory.Ai.Failure = new AiServiceUnavailableException("nere");

        var response = await _client.DeleteAsync($"/api/documents/{uploaded.Id}");

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        (await _client.GetAsync($"/api/documents/{uploaded.Id}")).StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Uploaded_file_can_be_downloaded_again()
    {
        var uploaded = await UploadAsync("mitt-dokument.pdf");

        var response = await _client.GetAsync($"/api/documents/{uploaded.Id}/file");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/pdf");
        (await response.Content.ReadAsStringAsync()).Should().StartWith("%PDF-");
    }

    [Fact]
    public async Task Chat_returns_answer_with_file_names_and_stores_history()
    {
        var uploaded = await UploadAsync("skolskjuts.pdf");
        await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);
        _factory.Ai.OnQuery = (_, _) => new QueryResult(
            "Skolskjuts införs [1].", Grounded: true, [new AiSource(uploaded.Id, Page: 2, ChunkIndex: 4, "utdrag", 0.91)]);

        var response = await _client.PostAsJsonAsync("/api/chat", new ChatRequest("Vad beslutades?", null));

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var answer = (await response.Content.ReadFromJsonAsync<ChatAnswerDto>(Json))!;
        answer.Grounded.Should().BeTrue();
        answer.Sources.Should().ContainSingle().Which.Should().BeEquivalentTo(
            new ChatSourceDto(uploaded.Id, "skolskjuts.pdf", 2, "utdrag", 0.91));

        var history = await _client.GetFromJsonAsync<List<ChatAnswerDto>>("/api/chat/history", Json);
        history.Should().Contain(m => m.Id == answer.Id && m.Sources.Count == 1);
    }

    [Fact]
    public async Task Chat_returns_503_problem_when_the_llm_is_offline()
    {
        _factory.Ai.Failure = new AiServiceUnavailableException("gpu offline");

        var response = await _client.PostAsJsonAsync("/api/chat", new ChatRequest("Hej?", null));

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        (await response.Content.ReadAsStringAsync()).Should().Contain("ai_unavailable");
    }

    [Theory]
    [InlineData(null)]
    [InlineData("   ")]
    public async Task Chat_rejects_empty_question(string? question)
    {
        var response = await _client.PostAsJsonAsync("/api/chat", new ChatRequest(question, null));

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Malformed_json_is_a_400_not_a_500()
    {
        var body = new StringContent("{ not json", Encoding.UTF8, "application/json");

        var response = await _client.PostAsync("/api/chat", body);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Chat_rejects_unknown_document_ids()
    {
        var response = await _client.PostAsJsonAsync("/api/chat", new ChatRequest("Hej?", [Guid.NewGuid()]));

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task Health_reports_database_and_ai_service()
    {
        var response = await _client.GetAsync("/health");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("\"database\":true").And.Contain("\"aiService\":true");
    }
}
