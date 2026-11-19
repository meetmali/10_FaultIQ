using System.Text;
using FaultIQ.Api.Common;
using FaultIQ.Api.Data;
using FaultIQ.Api.Storage;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

namespace FaultIQ.Api.Features;

public sealed record UploadResponse(
    Guid Id, Guid EquipmentId, string OriginalName, string Format, long SizeBytes, string Sha256,
    DateTimeOffset CreatedAt)
{
    public static UploadResponse From(Upload u) =>
        new(u.Id, u.EquipmentId, u.OriginalName, u.Format, u.SizeBytes, u.Sha256, u.CreatedAt);
}

public static class UploadEndpoints
{
    private const int SniffBytes = 8192;

    public static RouteGroupBuilder MapUploadEndpoints(this RouteGroupBuilder api)
    {
        var g = api.MapGroup("/uploads").WithTags("uploads");

        g.MapPost("/", async Task<Results<Created<UploadResponse>, ProblemHttpResult>> (
                IFormFile file,
                [FromForm(Name = "equipment_id")] Guid equipmentId,
                [FromForm] string format,
                FaultIqDbContext db, IFileStore store, IOptions<UploadOptions> options, TimeProvider clock,
                CancellationToken ct) =>
            {
                if (!Formats.All.Contains(format))
                {
                    return Problems.Invalid("format", $"Format must be one of: {string.Join(", ", Formats.All)}.");
                }

                if (!string.Equals(Path.GetExtension(file.FileName), ".csv", StringComparison.OrdinalIgnoreCase))
                {
                    return Problems.Of(StatusCodes.Status415UnsupportedMediaType, "unsupported_file_type",
                        "Only .csv files are accepted.");
                }

                if (file.Length == 0)
                {
                    return Problems.Invalid("file", "The file is empty.");
                }

                if (file.Length > options.Value.MaxBytes)
                {
                    return Problems.Of(StatusCodes.Status413PayloadTooLarge, "upload_too_large",
                        $"Files may be at most {options.Value.MaxSizeMb} MB.");
                }

                if (!await LooksLikeTextAsync(file, ct))
                {
                    return Problems.Of(StatusCodes.Status415UnsupportedMediaType, "not_text",
                        "The file is not UTF-8 text, so it can't be a CSV export.");
                }

                // Cheap checks first; the database is only asked once the file itself looks acceptable.
                if (!await db.Equipment.AnyAsync(e => e.Id == equipmentId, ct))
                {
                    return Problems.NotFound("Equipment");
                }

                var id = Guid.CreateVersion7();
                await using var stream = file.OpenReadStream();
                var stored = await store.SaveAsync(id, ".csv", stream, ct);
                var upload = new Upload
                {
                    Id = id,
                    EquipmentId = equipmentId,
                    OriginalName = SafeDisplayName(file.FileName),
                    StoredName = stored.StoredName,
                    Format = format,
                    SizeBytes = stored.SizeBytes,
                    Sha256 = stored.Sha256,
                    CreatedAt = clock.GetUtcNow(),
                };
                db.Uploads.Add(upload);
                try
                {
                    await db.SaveChangesAsync(ct);
                }
                catch
                {
                    await store.DeleteAsync(stored.StoredName, CancellationToken.None);
                    throw;
                }

                return TypedResults.Created($"/api/v1/uploads/{id}", UploadResponse.From(upload));
            })
            // No cookie authentication exists yet, so there is no CSRF risk to defend against.
            // Phase 8 adds Identity and must turn antiforgery on for form posts (ADR 0024).
            .DisableAntiforgery()
            .WithName("CreateUpload");

        g.MapGet("/{id:guid}", async Task<Results<Ok<UploadResponse>, ProblemHttpResult>> (
            Guid id, FaultIqDbContext db, CancellationToken ct) =>
        {
            var u = await db.Uploads.AsNoTracking().FirstOrDefaultAsync(x => x.Id == id, ct);
            return u is null ? Problems.NotFound("Upload") : TypedResults.Ok(UploadResponse.From(u));
        }).WithName("GetUpload");

        return api;
    }

    /// <summary>Rejects binaries early: no NUL bytes and valid UTF-8 in the first few kilobytes.</summary>
    private static async Task<bool> LooksLikeTextAsync(IFormFile file, CancellationToken ct)
    {
        await using var s = file.OpenReadStream();
        var buffer = new byte[SniffBytes];
        var read = await s.ReadAtLeastAsync(buffer, SniffBytes, throwOnEndOfStream: false, ct);
        var head = buffer.AsSpan(0, read);
        if (head.Contains((byte)0))
        {
            return false;
        }

        // The sniffed block may end mid-character; trim up to 3 trailing bytes before decoding.
        var strict = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true);
        for (var trim = 0; trim <= Math.Min(3, read); trim++)
        {
            try
            {
                strict.GetCharCount(head[..(read - trim)]);
                return true;
            }
            catch (DecoderFallbackException)
            {
                if (read < SniffBytes)
                {
                    return false; // the whole file was read, so there is no cut character to excuse
                }
            }
        }

        return false;
    }

    private static string SafeDisplayName(string name)
    {
        var clean = new string(Path.GetFileName(name).Where(c => !char.IsControl(c)).ToArray()).Trim();
        return clean.Length switch
        {
            0 => "upload.csv",
            > 255 => clean[..255],
            _ => clean,
        };
    }
}
