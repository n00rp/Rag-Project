using System.Text;
using System.Text.Json;
using DocAssistant.Api.Contracts;
using DocAssistant.Api.Data;
using DocAssistant.Api.Domain;
using DocAssistant.Api.Services;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;

namespace DocAssistant.Api.Endpoints;

public static class ChatEndpoints
{
    private const int MaxQuestionLength = 2000;
    private const int MaxCommentLength = 1000;
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    public static void MapChatEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/chat").WithTags("Chat");

        group.MapPost("/", Ask);
        group.MapPost("/stream", Stream);

        group.MapGet("/history", async (AppDbContext db, ICurrentUser user, CancellationToken ct, int limit = 50) =>
        {
            var rows = await db.ChatMessages
                .Where(m => m.OwnerId == user.OwnerId)
                .OrderByDescending(m => m.CreatedAt)
                .Take(Math.Clamp(limit, 1, 200))
                .ToListAsync(ct);
            return rows.AsEnumerable().Reverse().Select(ToDto);
        });

        group.MapPut("/{id:guid}/feedback", async Task<Results<Ok<ChatAnswerDto>, NotFound, ProblemHttpResult>> (
            Guid id, FeedbackRequest request, AppDbContext db, ICurrentUser user, CancellationToken ct) =>
        {
            if (request.Rating is not (null or "up" or "down"))
                return TypedResults.Problem("Betyget måste vara 'up', 'down' eller tomt.", statusCode: StatusCodes.Status400BadRequest);
            if (request.Comment is { Length: > MaxCommentLength })
                return TypedResults.Problem($"Kommentaren är för lång (max {MaxCommentLength} tecken).", statusCode: StatusCodes.Status400BadRequest);

            var message = await db.ChatMessages.FirstOrDefaultAsync(m => m.Id == id && m.OwnerId == user.OwnerId, ct);
            if (message is null) return TypedResults.NotFound();

            message.Rating = request.Rating;
            // A comment only makes sense together with a rating, and is dropped when the rating is withdrawn.
            message.FeedbackComment = request.Rating is null ? null : request.Comment?.Trim() is { Length: > 0 } c ? c : null;
            await db.SaveChangesAsync(ct);
            return TypedResults.Ok(ToDto(message));
        });

        group.MapDelete("/history", async (AppDbContext db, ICurrentUser user, CancellationToken ct) =>
        {
            await db.ChatMessages.Where(m => m.OwnerId == user.OwnerId).ExecuteDeleteAsync(ct);
            return TypedResults.NoContent();
        });
    }

    /// <summary>A validated question and the documents it is about (with their file names).</summary>
    private sealed record Prepared(string Question, List<Guid>? DocumentIds, Dictionary<Guid, string> Names);

    private static async Task<(Prepared? Ready, ProblemHttpResult? Problem)> PrepareAsync(
        ChatRequest request, AppDbContext db, ICurrentUser user, CancellationToken ct)
    {
        var question = request.Question?.Trim();
        if (string.IsNullOrEmpty(question))
            return (null, TypedResults.Problem("Frågan får inte vara tom.", statusCode: StatusCodes.Status400BadRequest));
        if (question.Length > MaxQuestionLength)
            return (null, TypedResults.Problem($"Frågan är för lång (max {MaxQuestionLength} tecken).", statusCode: StatusCodes.Status400BadRequest));

        var documentIds = request.DocumentIds?.Distinct().ToList();
        Dictionary<Guid, string> names;
        if (documentIds is { Count: > 0 })
        {
            names = await db.Documents
                .Where(d => d.OwnerId == user.OwnerId && documentIds.Contains(d.Id))
                .ToDictionaryAsync(d => d.Id, d => d.FileName, ct);
            if (names.Count != documentIds.Count)
                return (null, TypedResults.Problem("Ett eller flera dokument hittades inte.", statusCode: StatusCodes.Status404NotFound));
        }
        else
        {
            documentIds = null;
            names = await db.Documents
                .Where(d => d.OwnerId == user.OwnerId && d.Status == DocumentStatus.Ready)
                .ToDictionaryAsync(d => d.Id, d => d.FileName, ct);
        }
        return (new Prepared(question, documentIds, names), null);
    }

    private static List<ChatSourceDto> ToSourceDtos(IEnumerable<AiSource> sources, Dictionary<Guid, string> names) =>
        sources
            .Select(s => new ChatSourceDto(s.DocumentId, names.GetValueOrDefault(s.DocumentId, "okänt dokument"), s.Page, s.Snippet, s.Score))
            .ToList();

    private static async Task<ChatMessage> SaveAsync(
        AppDbContext db, ICurrentUser user, string question, string answer, bool grounded,
        List<ChatSourceDto> sources, bool interrupted, string support, bool broad, CancellationToken ct)
    {
        var message = new ChatMessage
        {
            Id = Guid.NewGuid(),
            OwnerId = user.OwnerId,
            Question = question,
            Answer = answer,
            Grounded = grounded,
            Interrupted = interrupted,
            Support = support,
            Broad = broad,
            SourcesJson = JsonSerializer.Serialize(grounded ? sources : [], Json),
        };
        db.ChatMessages.Add(message);
        await db.SaveChangesAsync(ct);
        return message;
    }

    private static async Task<Results<Ok<ChatAnswerDto>, ProblemHttpResult>> Ask(
        ChatRequest request,
        AppDbContext db,
        ICurrentUser user,
        IAiServiceClient ai,
        CancellationToken ct)
    {
        var (ready, problem) = await PrepareAsync(request, db, user, ct);
        if (problem is not null) return problem;

        QueryResult result;
        try
        {
            result = await ai.QueryAsync(user.OwnerId, ready!.Question, ready.DocumentIds, ct);
        }
        catch (AiServiceUnavailableException)
        {
            return TypedResults.Problem(
                "AI-modellen är inte tillgänglig just nu. Försök igen om en stund.",
                statusCode: StatusCodes.Status503ServiceUnavailable,
                extensions: new Dictionary<string, object?> { ["code"] = "ai_unavailable" });
        }

        var message = await SaveAsync(db, user, ready.Question, result.Answer, result.Grounded,
            ToSourceDtos(result.Sources, ready.Names), interrupted: false, result.Support, result.Broad, ct);
        return TypedResults.Ok(ToDto(message));
    }

    /// <summary>
    /// The same question and answer, but streamed as application/x-ndjson, one JSON event per line:
    /// <c>sources</c> (once, with file names), <c>token</c> (while the model writes), then <c>done</c> with the saved
    /// message, or <c>error</c> if the model fails mid-answer. If the model cannot be reached before anything was
    /// sent this is an ordinary 503. A stopped or failed answer is saved as it was (Interrupted), so it is still
    /// there after a reload.
    /// </summary>
    private static async Task<IResult> Stream(
        ChatRequest request,
        AppDbContext db,
        ICurrentUser user,
        IAiServiceClient ai,
        CancellationToken ct)
    {
        var (ready, problem) = await PrepareAsync(request, db, user, ct);
        if (problem is not null) return problem;

        return Results.Stream(async body =>
        {
            var started = false;
            var answer = new StringBuilder();
            var sources = new List<ChatSourceDto>();
            var support = "fullt";
            var broad = false;

            async Task Send(object evt)
            {
                started = true;
                await body.WriteAsync(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(evt, Json) + "\n"), ct);
                await body.FlushAsync(ct);
            }

            async Task SavePartialAsync()
            {
                if (answer.Length > 0)
                    await SaveAsync(db, user, ready!.Question, answer.ToString().Trim(), grounded: true, sources,
                        interrupted: true, support, broad, CancellationToken.None);
            }

            try
            {
                AiDoneEvent? done = null;
                await foreach (var evt in ai.QueryStreamAsync(user.OwnerId, ready!.Question, ready.DocumentIds, ct))
                {
                    switch (evt)
                    {
                        case AiSourcesEvent s:
                            sources = ToSourceDtos(s.Sources, ready.Names);
                            await Send(new { type = "sources", sources });
                            break;
                        case AiSupportEvent u:
                            support = u.Level;
                            await Send(new { type = "support", level = u.Level });
                            break;
                        case AiTokenEvent t:
                            answer.Append(t.Text);
                            await Send(new { type = "token", text = t.Text });
                            break;
                        case AiDoneEvent d:
                            done = d;
                            support = d.Support;
                            broad = d.Broad;
                            break;
                    }
                }

                if (done is null) throw new AiServiceUnavailableException("AI-tjänsten avslutade svaret i förtid.");
                var message = await SaveAsync(db, user, ready.Question, done.Answer, done.Grounded, sources,
                    interrupted: false, done.Support, done.Broad, ct);
                await Send(new { type = "done", message = ToDto(message) });
            }
            catch (AiServiceUnavailableException) when (!started)
            {
                throw; // nothing sent yet: becomes the usual 503 problem response
            }
            catch (AiServiceUnavailableException ex)
            {
                await SavePartialAsync();
                await Send(new { type = "error", code = "ai_unavailable", message = ex.Message });
            }
            catch (OperationCanceledException)
            {
                await SavePartialAsync(); // the user pressed stop or left the page
            }
        }, "application/x-ndjson");
    }

    private static ChatAnswerDto ToDto(ChatMessage m) =>
        new(m.Id, m.Question, m.Answer, m.Grounded,
            JsonSerializer.Deserialize<List<ChatSourceDto>>(m.SourcesJson, Json) ?? [],
            m.CreatedAt, m.Interrupted, m.Rating, m.FeedbackComment, m.Support, m.Broad);
}
