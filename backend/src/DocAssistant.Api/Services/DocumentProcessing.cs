using System.Threading.Channels;
using DocAssistant.Api.Data;
using DocAssistant.Api.Domain;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

namespace DocAssistant.Api.Services;

public class ProcessingOptions
{
    public int MaxAttempts { get; set; } = 3;
    public int RetryDelayMs { get; set; } = 5000;
}

public interface IDocumentQueue
{
    void Enqueue(Guid documentId);
}

public sealed class DocumentQueue : IDocumentQueue
{
    private readonly Channel<Guid> _channel = Channel.CreateUnbounded<Guid>(new UnboundedChannelOptions { SingleReader = true });

    public ChannelReader<Guid> Reader => _channel.Reader;

    public void Enqueue(Guid documentId) => _channel.Writer.TryWrite(documentId);
}

/// <summary>
/// Processes one document at a time so heavy embedding work can't starve the machine.
/// Documents left Queued/Processing by a restart are picked up again on startup.
/// </summary>
public sealed class DocumentProcessingWorker(
    DocumentQueue queue,
    IServiceScopeFactory scopes,
    IOptions<ProcessingOptions> options,
    ILogger<DocumentProcessingWorker> log) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await RequeueUnfinishedAsync(stoppingToken);

        await foreach (var id in queue.Reader.ReadAllAsync(stoppingToken))
        {
            try
            {
                await ProcessAsync(id, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                return;
            }
            catch (Exception ex)
            {
                log.LogError(ex, "Unexpected failure processing document {DocumentId}", id);
            }
        }
    }

    private async Task RequeueUnfinishedAsync(CancellationToken ct)
    {
        using var scope = scopes.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var ids = await db.Documents
            .Where(d => d.Status == DocumentStatus.Queued || d.Status == DocumentStatus.Processing)
            .OrderBy(d => d.CreatedAt)
            .Select(d => d.Id)
            .ToListAsync(ct);
        foreach (var id in ids) queue.Enqueue(id);
    }

    private async Task ProcessAsync(Guid id, CancellationToken ct)
    {
        using var scope = scopes.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var ai = scope.ServiceProvider.GetRequiredService<IAiServiceClient>();
        var storage = scope.ServiceProvider.GetRequiredService<IFileStorage>();

        var doc = await db.Documents.FindAsync([id], ct);
        if (doc is null || doc.Status == DocumentStatus.Ready) return;

        doc.Status = DocumentStatus.Processing;
        doc.Error = null;
        await db.SaveChangesAsync(ct);

        var opts = options.Value;
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                await using var file = storage.OpenRead(doc.Id);
                var result = await ai.IngestAsync(doc.OwnerId, doc.Id, file, doc.FileName, ct);
                doc.Status = DocumentStatus.Ready;
                doc.PageCount = result.Pages;
                doc.ChunkCount = result.Chunks;
                doc.ProcessedAt = DateTimeOffset.UtcNow;
                break;
            }
            catch (AiServiceRejectedException ex)
            {
                Fail(doc, ex.Message);
                break;
            }
            catch (AiServiceUnavailableException ex)
            {
                log.LogWarning(ex, "AI service unavailable for {DocumentId} (attempt {Attempt})", id, attempt);
                if (attempt >= opts.MaxAttempts)
                {
                    Fail(doc, "AI-tjänsten är inte tillgänglig just nu. Försök igen senare.");
                    break;
                }
                await Task.Delay(opts.RetryDelayMs * attempt, ct);
            }
        }

        await db.SaveChangesAsync(ct);
    }

    private static void Fail(Document doc, string message)
    {
        doc.Status = DocumentStatus.Failed;
        doc.Error = message.Length > 1000 ? message[..1000] : message;
        doc.ProcessedAt = DateTimeOffset.UtcNow;
    }
}
