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
    public async Task Partial_support_and_the_overview_flag_are_stored_with_the_answer()
    {
        var uploaded = await UploadAsync("budget.pdf");
        await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);
        _factory.Ai.OnQuery = (_, _) => new QueryResult("Summan saknas.", Grounded: true, [], Support: "delvis", Broad: true);

        var response = await _client.PostAsJsonAsync("/api/chat", new ChatRequest("Hur stor var budgeten?", null));

        var answer = (await response.Content.ReadFromJsonAsync<ChatAnswerDto>(Json))!;
        (answer.Support, answer.Broad).Should().Be(("delvis", true));
        var stored = (await _client.GetFromJsonAsync<List<ChatAnswerDto>>("/api/chat/history", Json))!.Single(m => m.Id == answer.Id);
        (stored.Support, stored.Broad).Should().Be(("delvis", true));
    }

    [Fact]
    public async Task A_follow_up_question_is_sent_with_the_conversation_so_far_and_a_new_conversation_starts_empty()
    {
        await _client.DeleteAsync("/api/chat/history");
        _factory.Ai.OnQuery = (q, _) => new QueryResult($"Svar på {q}", Grounded: true, []);

        await _client.PostAsJsonAsync("/api/chat", new ChatRequest("Vad är uppsägningstiden?", null));
        _factory.Ai.LastHistory.Should().BeEmpty();

        await _client.PostAsJsonAsync("/api/chat", new ChatRequest("Och för en 45-åring?", null));
        _factory.Ai.LastHistory.Should().ContainSingle()
            .Which.Should().Be(new ChatTurn("Vad är uppsägningstiden?", "Svar på Vad är uppsägningstiden?"));

        await _client.DeleteAsync("/api/chat/history");
        await _client.PostAsJsonAsync("/api/chat", new ChatRequest("Ny fråga", null));
        _factory.Ai.LastHistory.Should().BeEmpty();
    }

    [Fact]
    public async Task Clearing_history_removes_the_chat_but_keeps_documents()
    {
        var uploaded = await UploadAsync("skolskjuts.pdf");
        await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);
        _factory.Ai.OnQuery = (_, _) => new QueryResult("Svar.", Grounded: true, []);
        await _client.PostAsJsonAsync("/api/chat", new ChatRequest("Fråga?", null));

        var response = await _client.DeleteAsync("/api/chat/history");

        response.StatusCode.Should().Be(HttpStatusCode.NoContent);
        (await _client.GetFromJsonAsync<List<ChatAnswerDto>>("/api/chat/history", Json)).Should().BeEmpty();
        (await _client.GetFromJsonAsync<List<DocumentDto>>("/api/documents", Json)).Should().Contain(d => d.Id == uploaded.Id);
    }

    private async Task<ChatAnswerDto> AskAsync()
    {
        var uploaded = await UploadAsync();
        await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);
        _factory.Ai.OnQuery = (_, _) => new QueryResult("Svar.", Grounded: true, []);
        var response = await _client.PostAsJsonAsync("/api/chat", new ChatRequest("Fråga?", null));
        return (await response.Content.ReadFromJsonAsync<ChatAnswerDto>(Json))!;
    }

    [Fact]
    public async Task An_answer_can_be_rated_with_a_comment_and_the_rating_withdrawn()
    {
        var answer = await AskAsync();
        answer.Rating.Should().BeNull();

        var down = await _client.PutAsJsonAsync($"/api/chat/{answer.Id}/feedback", new FeedbackRequest("down", "  Fel belopp  "));
        down.StatusCode.Should().Be(HttpStatusCode.OK);
        var rated = (await down.Content.ReadFromJsonAsync<ChatAnswerDto>(Json))!;
        rated.Rating.Should().Be("down");
        rated.FeedbackComment.Should().Be("Fel belopp");

        var stored = (await _client.GetFromJsonAsync<List<ChatAnswerDto>>("/api/chat/history", Json))!.Single(m => m.Id == answer.Id);
        stored.Rating.Should().Be("down");
        stored.FeedbackComment.Should().Be("Fel belopp");

        var up = await (await _client.PutAsJsonAsync($"/api/chat/{answer.Id}/feedback", new FeedbackRequest("up", null)))
            .Content.ReadFromJsonAsync<ChatAnswerDto>(Json);
        up!.Rating.Should().Be("up");
        up.FeedbackComment.Should().BeNull();

        var withdrawn = await (await _client.PutAsJsonAsync($"/api/chat/{answer.Id}/feedback", new FeedbackRequest(null, "ignoreras")))
            .Content.ReadFromJsonAsync<ChatAnswerDto>(Json);
        withdrawn!.Rating.Should().BeNull();
        withdrawn.FeedbackComment.Should().BeNull();
    }

    [Fact]
    public async Task Feedback_with_an_unknown_rating_or_a_far_too_long_comment_is_rejected()
    {
        var answer = await AskAsync();

        (await _client.PutAsJsonAsync($"/api/chat/{answer.Id}/feedback", new FeedbackRequest("great", null)))
            .StatusCode.Should().Be(HttpStatusCode.BadRequest);
        (await _client.PutAsJsonAsync($"/api/chat/{answer.Id}/feedback", new FeedbackRequest("down", new string('x', 1001))))
            .StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Feedback_on_an_answer_that_does_not_exist_is_404()
    {
        var response = await _client.PutAsJsonAsync($"/api/chat/{Guid.NewGuid()}/feedback", new FeedbackRequest("up", null));

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task Swedish_characters_survive_upload_chat_and_history()
    {
        const string fileName = "Östra Ängby – protokoll åk 1–6.pdf";
        const string question = "Vad beslutades om skolskjuts i Östra Ängby för åk 1–6? ÅÄÖ åäö";
        var uploaded = await UploadAsync(fileName);
        uploaded.FileName.Should().Be(fileName);
        await WaitForStatusAsync(uploaded.Id, DocumentStatus.Ready);
        _factory.Ai.OnQuery = (_, _) => new QueryResult(
            "Nämnden beslutade om skolskjuts [1].", Grounded: true,
            [new AiSource(uploaded.Id, 1, 0, "Överenskommelsen gäller älvdalen.", 0.9)]);

        var response = await _client.PostAsJsonAsync("/api/chat", new ChatRequest(question, null));
        var answer = (await response.Content.ReadFromJsonAsync<ChatAnswerDto>(Json))!;

        answer.Question.Should().Be(question);
        answer.Answer.Should().Be("Nämnden beslutade om skolskjuts [1].");
        answer.Sources.Single().FileName.Should().Be(fileName);
        answer.Sources.Single().Snippet.Should().Be("Överenskommelsen gäller älvdalen.");

        var history = await _client.GetFromJsonAsync<List<ChatAnswerDto>>("/api/chat/history", Json);
        var stored = history!.Single(m => m.Id == answer.Id);
        stored.Question.Should().Be(question);
        stored.Sources.Single().Snippet.Should().Be("Överenskommelsen gäller älvdalen.");
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
