using DocAssistant.Api.Domain;

namespace DocAssistant.Api.Contracts;

public record DocumentDto(
    Guid Id,
    string FileName,
    long SizeBytes,
    DocumentStatus Status,
    string? Error,
    int? PageCount,
    int? ChunkCount,
    DateTimeOffset CreatedAt)
{
    public static DocumentDto From(Document d) =>
        new(d.Id, d.FileName, d.SizeBytes, d.Status, d.Error, d.PageCount, d.ChunkCount, d.CreatedAt);
}

public record ChatRequest(string? Question, List<Guid>? DocumentIds);

public record ChatSourceDto(Guid DocumentId, string FileName, int Page, string Snippet, double Score);

public record ChatAnswerDto(
    Guid Id,
    string Question,
    string Answer,
    bool Grounded,
    IReadOnlyList<ChatSourceDto> Sources,
    DateTimeOffset CreatedAt,
    bool Interrupted = false,
    string? Rating = null,
    string? FeedbackComment = null);

public record FeedbackRequest(string? Rating, string? Comment);
