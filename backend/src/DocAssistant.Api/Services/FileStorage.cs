using Microsoft.Extensions.Options;

namespace DocAssistant.Api.Services;

public class StorageOptions
{
    public string Path { get; set; } = "data/uploads";
}

public interface IFileStorage
{
    Task SaveAsync(Guid documentId, Stream content, CancellationToken ct);
    Stream OpenRead(Guid documentId);
    void Delete(Guid documentId);
}

/// <summary>Stores uploads on local disk named by document id, never by user-supplied file name.</summary>
public sealed class LocalFileStorage : IFileStorage
{
    private readonly string _root;

    public LocalFileStorage(IOptions<StorageOptions> options)
    {
        _root = System.IO.Path.GetFullPath(options.Value.Path);
        Directory.CreateDirectory(_root);
    }

    private string PathFor(Guid id) => System.IO.Path.Combine(_root, $"{id:N}.pdf");

    public async Task SaveAsync(Guid documentId, Stream content, CancellationToken ct)
    {
        await using var target = File.Create(PathFor(documentId));
        await content.CopyToAsync(target, ct);
    }

    public Stream OpenRead(Guid documentId) => File.OpenRead(PathFor(documentId));

    public void Delete(Guid documentId)
    {
        var path = PathFor(documentId);
        if (File.Exists(path)) File.Delete(path);
    }
}
