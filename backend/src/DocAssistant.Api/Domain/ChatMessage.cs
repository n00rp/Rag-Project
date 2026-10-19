namespace DocAssistant.Api.Domain;

public class ChatMessage
{
    public Guid Id { get; set; }
    public required string OwnerId { get; set; }
    public required string Question { get; set; }
    public required string Answer { get; set; }
    public bool Grounded { get; set; }

    /// <summary>The answer was cut off (the user pressed stop, or the AI service failed while it was being written).</summary>
    public bool Interrupted { get; set; }

    /// <summary>Serialized list of <see cref="Contracts.ChatSourceDto"/>, stored as jsonb.</summary>
    public string SourcesJson { get; set; } = "[]";

    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}
