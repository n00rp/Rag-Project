using System.Collections.Concurrent;
using System.Runtime.CompilerServices;
using DocAssistant.Api.Services;

namespace DocAssistant.Api.Tests.TestSupport;

public sealed class FakeAiServiceClient : IAiServiceClient
{
    public ConcurrentBag<Guid> Deleted { get; } = [];
    public ConcurrentBag<Guid> Ingested { get; } = [];

    /// <summary>When set, ingest/query/delete throw this instead of succeeding.</summary>
    public Exception? Failure { get; set; }

    /// <summary>Source documents the next query should cite.</summary>
    public Func<string, IReadOnlyList<Guid>?, QueryResult>? OnQuery { get; set; }

    /// <summary>The events of the next streamed query; defaults to a short grounded answer.</summary>
    public Func<string, IReadOnlyList<Guid>?, CancellationToken, IAsyncEnumerable<AiStreamEvent>>? OnStream { get; set; }

    public async IAsyncEnumerable<AiStreamEvent> QueryStreamAsync(
        string ownerId, string question, IReadOnlyList<Guid>? documentIds, [EnumeratorCancellation] CancellationToken ct)
    {
        if (Failure is not null) throw Failure;
        var events = OnStream?.Invoke(question, documentIds, ct) ?? Default();
        await foreach (var e in events.WithCancellation(ct)) yield return e;

        static async IAsyncEnumerable<AiStreamEvent> Default()
        {
            yield return new AiDoneEvent("Inget stöd.", Grounded: false);
            await Task.CompletedTask;
        }
    }

    public Task<IngestResult> IngestAsync(string ownerId, Guid documentId, Stream file, string fileName, CancellationToken ct)
    {
        if (Failure is not null) throw Failure;
        Ingested.Add(documentId);
        return Task.FromResult(new IngestResult(documentId, Pages: 3, Chunks: 7));
    }

    public Task<QueryResult> QueryAsync(string ownerId, string question, IReadOnlyList<Guid>? documentIds, CancellationToken ct)
    {
        if (Failure is not null) throw Failure;
        var result = OnQuery?.Invoke(question, documentIds)
                     ?? new QueryResult("Inget stöd.", Grounded: false, Sources: []);
        return Task.FromResult(result);
    }

    public Task DeleteAsync(string ownerId, Guid documentId, CancellationToken ct)
    {
        if (Failure is not null) throw Failure;
        Deleted.Add(documentId);
        return Task.CompletedTask;
    }

    public Task<bool> IsHealthyAsync(CancellationToken ct) => Task.FromResult(Failure is null);
}
