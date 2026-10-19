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

    /// <summary>The reader's verdict on the answer: "up", "down" or null (none). Feeds the eval set.</summary>
    public string? Rating { get; set; }

    /// <summary>How well the documents support the answer: "fullt" or "delvis" ("inget" is a refusal: Grounded is false).</summary>
    public string Support { get; set; } = "fullt";

    /// <summary>An overview question (summary, count, list): the answer is built from the best excerpts and may be incomplete.</summary>
    public bool Broad { get; set; }

    /// <summary>Optional note that goes with a "down".</summary>
    public string? FeedbackComment { get; set; }

    /// <summary>Serialized list of <see cref="Contracts.ChatSourceDto"/>, stored as jsonb.</summary>
    public string SourcesJson { get; set; } = "[]";

    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}
