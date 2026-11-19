using System.Security.Cryptography;
using Microsoft.Extensions.Options;

namespace FaultIQ.Api.Storage;

public sealed class UploadOptions
{
    public const string Section = "Uploads";
    public string Directory { get; set; } = "./data/uploads";
    public int MaxSizeMb { get; set; } = 100;
    public long MaxBytes => MaxSizeMb * 1024L * 1024L;
}

public sealed record StoredFile(string StoredName, long SizeBytes, string Sha256);

/// <summary>Where uploaded files live (ADR 0015): local disk by default, S3-compatible later.</summary>
public interface IFileStore
{
    /// <summary>Stores the stream under a server-generated name and returns its size and SHA-256.</summary>
    Task<StoredFile> SaveAsync(Guid id, string extension, Stream content, CancellationToken ct);

    Task DeleteAsync(string storedName, CancellationToken ct);
}

public sealed class LocalFileStore(IOptions<UploadOptions> options) : IFileStore
{
    private string Root => Path.GetFullPath(options.Value.Directory);

    public async Task<StoredFile> SaveAsync(Guid id, string extension, Stream content, CancellationToken ct)
    {
        System.IO.Directory.CreateDirectory(Root);
        // The name comes from a server-generated ID only, never from user input.
        var storedName = $"{id:N}{extension}";
        var final = Path.Combine(Root, storedName);
        var temp = final + ".part";
        using var sha = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        long size = 0;
        try
        {
            await using (var file = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None,
                             bufferSize: 81920, useAsync: true))
            {
                var buffer = new byte[81920];
                int read;
                while ((read = await content.ReadAsync(buffer, ct)) > 0)
                {
                    sha.AppendData(buffer, 0, read);
                    await file.WriteAsync(buffer.AsMemory(0, read), ct);
                    size += read;
                }
            }

            File.Move(temp, final);
        }
        catch
        {
            File.Delete(temp);
            throw;
        }

        return new StoredFile(storedName, size, Convert.ToHexStringLower(sha.GetHashAndReset()));
    }

    public Task DeleteAsync(string storedName, CancellationToken ct)
    {
        File.Delete(Path.Combine(Root, Path.GetFileName(storedName)));
        return Task.CompletedTask;
    }
}
