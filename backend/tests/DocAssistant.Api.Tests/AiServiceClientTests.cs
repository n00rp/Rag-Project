using System.Net;
using System.Text;
using System.Text.Json;
using DocAssistant.Api.Services;
using FluentAssertions;

namespace DocAssistant.Api.Tests;

/// <summary>Å, Ä and Ö must survive the hop to and from the Python service unchanged.</summary>
public sealed class AiServiceClientTests
{
    private const string Swedish = "Östra Ängby: åk 1–6 får skolskjuts – ÅÄÖ åäö";

    private sealed class CapturingHandler(Func<HttpResponseMessage> respond) : HttpMessageHandler
    {
        public string? Body { get; private set; }
        public Uri? Url { get; private set; }

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
        {
            Url = request.RequestUri;
            Body = request.Content is null ? null : await request.Content.ReadAsStringAsync(ct);
            return respond();
        }
    }

    private static AiServiceClient ClientFor(CapturingHandler handler) =>
        new(new HttpClient(handler) { BaseAddress = new Uri("http://ai/") });

    private static HttpResponseMessage Utf8Json(string json) =>
        new(HttpStatusCode.OK) { Content = new StringContent(json, Encoding.UTF8, "application/json") };

    [Fact]
    public async Task Query_sends_the_question_as_exact_utf8_json_with_snake_case_names()
    {
        var handler = new CapturingHandler(() => Utf8Json("""{"answer":"x","grounded":false,"sources":[]}"""));

        await ClientFor(handler).QueryAsync("demo", Swedish, [Guid.Parse("11111111-1111-1111-1111-111111111111")], default);

        using var sent = JsonDocument.Parse(handler.Body!);
        sent.RootElement.GetProperty("question").GetString().Should().Be(Swedish);
        sent.RootElement.GetProperty("owner_id").GetString().Should().Be("demo");
        sent.RootElement.GetProperty("document_ids").GetArrayLength().Should().Be(1);
    }

    [Fact]
    public async Task Query_reads_swedish_answers_and_snippets_without_mangling()
    {
        var json = JsonSerializer.Serialize(new
        {
            answer = Swedish,
            grounded = true,
            sources = new[]
            {
                new { document_id = Guid.NewGuid(), page = 1, chunk_index = 0, snippet = Swedish, score = 0.9 },
            },
        });
        var handler = new CapturingHandler(() => Utf8Json(json));

        var result = await ClientFor(handler).QueryAsync("demo", "fråga", null, default);

        result.Answer.Should().Be(Swedish);
        result.Sources.Single().Snippet.Should().Be(Swedish);
    }

    [Fact]
    public async Task Ingest_sends_a_swedish_file_name_in_a_standards_compliant_encoded_form()
    {
        var handler = new CapturingHandler(() => Utf8Json(
            $$"""{"document_id":"{{Guid.NewGuid()}}","pages":1,"chunks":1}"""));
        await using var file = new MemoryStream("%PDF-1.4"u8.ToArray());

        await ClientFor(handler).IngestAsync("demo", Guid.NewGuid(), file, "Östra Ängby – protokoll.pdf", default);

        // RFC 5987 / 6266: non-ASCII file names go in filename*=UTF-8''<percent-encoded>.
        handler.Body.Should().Contain("filename*=utf-8''%C3%96stra%20%C3%84ngby");
    }

    [Fact]
    public async Task Delete_url_encodes_the_owner_id()
    {
        var handler = new CapturingHandler(() => new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent("{}") });

        await ClientFor(handler).DeleteAsync("ägare åäö", Guid.NewGuid(), default);

        handler.Url!.Query.Should().Be("?owner_id=%C3%A4gare%20%C3%A5%C3%A4%C3%B6");
    }
}
