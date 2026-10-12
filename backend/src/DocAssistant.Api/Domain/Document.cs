namespace DocAssistant.Api.Domain;

public enum DocumentStatus
{
    Queued,
    Processing,
    Ready,
    Failed,
}

public class Document
{
    public Guid Id { get; set; }
    public required string OwnerId { get; set; }
    public required string FileName { get; set; }
    public long SizeBytes { get; set; }
    public DocumentStatus Status { get; set; } = DocumentStatus.Queued;
    public string? Error { get; set; }
    public int? PageCount { get; set; }
    public int? ChunkCount { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? ProcessedAt { get; set; }
}
