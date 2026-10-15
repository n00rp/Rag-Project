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
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    public static void MapChatEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/chat").WithTags("Chat");

        group.MapPost("/", Ask);

        group.MapGet("/history", async (AppDbContext db, ICurrentUser user, CancellationToken ct, int limit = 50) =>
        {
            var rows = await db.ChatMessages
                .Where(m => m.OwnerId == user.OwnerId)
                .OrderByDescending(m => m.CreatedAt)
                .Take(Math.Clamp(limit, 1, 200))
                .ToListAsync(ct);
            return rows.AsEnumerable().Reverse().Select(ToDto);
        });

        group.MapDelete("/history", async (AppDbContext db, ICurrentUser user, CancellationToken ct) =>
        {
            await db.ChatMessages.Where(m => m.OwnerId == user.OwnerId).ExecuteDeleteAsync(ct);
            return TypedResults.NoContent();
        });
    }

    private static async Task<Results<Ok<ChatAnswerDto>, ProblemHttpResult>> Ask(
        ChatRequest request,
        AppDbContext db,
        ICurrentUser user,
        IAiServiceClient ai,
        CancellationToken ct)
    {
        var question = request.Question?.Trim();
        if (string.IsNullOrEmpty(question))
            return TypedResults.Problem("Frågan får inte vara tom.", statusCode: StatusCodes.Status400BadRequest);
        if (question.Length > MaxQuestionLength)
            return TypedResults.Problem($"Frågan är för lång (max {MaxQuestionLength} tecken).", statusCode: StatusCodes.Status400BadRequest);

        var documentIds = request.DocumentIds?.Distinct().ToList();
        Dictionary<Guid, string> names;
        if (documentIds is { Count: > 0 })
        {
            names = await db.Documents
                .Where(d => d.OwnerId == user.OwnerId && documentIds.Contains(d.Id))
                .ToDictionaryAsync(d => d.Id, d => d.FileName, ct);
            if (names.Count != documentIds.Count)
                return TypedResults.Problem("Ett eller flera dokument hittades inte.", statusCode: StatusCodes.Status404NotFound);
        }
        else
        {
            documentIds = null;
            names = await db.Documents
                .Where(d => d.OwnerId == user.OwnerId && d.Status == DocumentStatus.Ready)
                .ToDictionaryAsync(d => d.Id, d => d.FileName, ct);
        }

        QueryResult result;
        try
        {
            result = await ai.QueryAsync(user.OwnerId, question, documentIds, ct);
        }
        catch (AiServiceUnavailableException)
        {
            return TypedResults.Problem(
                "AI-modellen är inte tillgänglig just nu. Försök igen om en stund.",
                statusCode: StatusCodes.Status503ServiceUnavailable,
                extensions: new Dictionary<string, object?> { ["code"] = "ai_unavailable" });
        }

        var sources = result.Sources
            .Select(s => new ChatSourceDto(s.DocumentId, names.GetValueOrDefault(s.DocumentId, "okänt dokument"), s.Page, s.Snippet, s.Score))
            .ToList();

        var message = new ChatMessage
        {
            Id = Guid.NewGuid(),
            OwnerId = user.OwnerId,
            Question = question,
            Answer = result.Answer,
            Grounded = result.Grounded,
            SourcesJson = JsonSerializer.Serialize(sources, Json),
        };
        db.ChatMessages.Add(message);
        await db.SaveChangesAsync(ct);

        return TypedResults.Ok(ToDto(message));
    }

    private static ChatAnswerDto ToDto(ChatMessage m) =>
        new(m.Id, m.Question, m.Answer, m.Grounded,
            JsonSerializer.Deserialize<List<ChatSourceDto>>(m.SourcesJson, Json) ?? [],
            m.CreatedAt);
}
