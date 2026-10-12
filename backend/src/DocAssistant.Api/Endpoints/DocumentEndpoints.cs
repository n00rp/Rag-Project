using DocAssistant.Api.Contracts;
using DocAssistant.Api.Data;
using DocAssistant.Api.Domain;
using DocAssistant.Api.Services;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

namespace DocAssistant.Api.Endpoints;

public class UploadOptions
{
    public long MaxBytes { get; set; } = 25 * 1024 * 1024;
}

public static class DocumentEndpoints
{
    private static readonly byte[] PdfMagic = "%PDF-"u8.ToArray();

    public static void MapDocumentEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/documents").WithTags("Documents");

        group.MapGet("/", async (AppDbContext db, ICurrentUser user, CancellationToken ct) =>
        {
            var docs = await db.Documents
                .Where(d => d.OwnerId == user.OwnerId)
                .OrderByDescending(d => d.CreatedAt)
                .ToListAsync(ct);
            return docs.Select(DocumentDto.From);
        });

        group.MapGet("/{id:guid}", async Task<Results<Ok<DocumentDto>, NotFound>> (
            Guid id, AppDbContext db, ICurrentUser user, CancellationToken ct) =>
        {
            var doc = await FindOwned(db, user, id, ct);
            return doc is null ? TypedResults.NotFound() : TypedResults.Ok(DocumentDto.From(doc));
        });

        group.MapPost("/", Upload).DisableAntiforgery();

        group.MapPost("/{id:guid}/retry", async Task<Results<Accepted<DocumentDto>, NotFound, ProblemHttpResult>> (
            Guid id, AppDbContext db, ICurrentUser user, IDocumentQueue queue, CancellationToken ct) =>
        {
            var doc = await FindOwned(db, user, id, ct);
            if (doc is null) return TypedResults.NotFound();
            if (doc.Status != DocumentStatus.Failed)
                return TypedResults.Problem("Bara misslyckade dokument kan köras om.", statusCode: StatusCodes.Status409Conflict);

            doc.Status = DocumentStatus.Queued;
            doc.Error = null;
            await db.SaveChangesAsync(ct);
            queue.Enqueue(doc.Id);
            return TypedResults.Accepted($"/api/documents/{doc.Id}", DocumentDto.From(doc));
        });

        group.MapGet("/{id:guid}/file", async Task<Results<FileStreamHttpResult, NotFound>> (
            Guid id, AppDbContext db, ICurrentUser user, IFileStorage storage, CancellationToken ct) =>
        {
            var doc = await FindOwned(db, user, id, ct);
            if (doc is null) return TypedResults.NotFound();
            // No download name => served inline, so the frontend can show it in an embedded viewer.
            return TypedResults.File(storage.OpenRead(doc.Id), "application/pdf", enableRangeProcessing: true);
        });

        group.MapDelete("/{id:guid}", async Task<Results<NoContent, NotFound>> (
            Guid id, AppDbContext db, ICurrentUser user, IAiServiceClient ai, IFileStorage storage, CancellationToken ct) =>
        {
            var doc = await FindOwned(db, user, id, ct);
            if (doc is null) return TypedResults.NotFound();

            // Remove the vectors first: if the AI service is down we keep the document so nothing is orphaned.
            await ai.DeleteAsync(doc.OwnerId, doc.Id, ct);
            db.Documents.Remove(doc);
            await db.SaveChangesAsync(ct);
            storage.Delete(doc.Id);
            return TypedResults.NoContent();
        });
    }

    private static async Task<Results<Accepted<DocumentDto>, ProblemHttpResult>> Upload(
        IFormFile file,
        AppDbContext db,
        ICurrentUser user,
        IFileStorage storage,
        IDocumentQueue queue,
        IOptions<UploadOptions> options,
        CancellationToken ct)
    {
        if (file.Length == 0)
            return TypedResults.Problem("Filen är tom.", statusCode: StatusCodes.Status400BadRequest);
        if (file.Length > options.Value.MaxBytes)
            return TypedResults.Problem(
                $"Filen är för stor (max {options.Value.MaxBytes / (1024 * 1024)} MB).",
                statusCode: StatusCodes.Status413PayloadTooLarge);

        // Trust the content, not the file name or the client-supplied content type.
        var header = new byte[PdfMagic.Length];
        await using (var peek = file.OpenReadStream())
        {
            var read = await peek.ReadAtLeastAsync(header, header.Length, throwOnEndOfStream: false, ct);
            if (read < header.Length || !header.AsSpan().SequenceEqual(PdfMagic))
                return TypedResults.Problem("Bara PDF-filer stöds.", statusCode: StatusCodes.Status400BadRequest);
        }

        var name = Path.GetFileName(file.FileName);
        var doc = new Document
        {
            Id = Guid.NewGuid(),
            OwnerId = user.OwnerId,
            FileName = name.Length > 255 ? name[..255] : name,
            SizeBytes = file.Length,
        };

        await using (var stream = file.OpenReadStream())
            await storage.SaveAsync(doc.Id, stream, ct);

        db.Documents.Add(doc);
        await db.SaveChangesAsync(ct);
        queue.Enqueue(doc.Id);

        return TypedResults.Accepted($"/api/documents/{doc.Id}", DocumentDto.From(doc));
    }

    private static Task<Document?> FindOwned(AppDbContext db, ICurrentUser user, Guid id, CancellationToken ct) =>
        db.Documents.FirstOrDefaultAsync(d => d.Id == id && d.OwnerId == user.OwnerId, ct);
}
