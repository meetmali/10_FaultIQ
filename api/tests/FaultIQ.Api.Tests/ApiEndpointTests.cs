using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using FaultIQ.Api.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace FaultIQ.Api.Tests;

/// <summary>Upload checks that reject a request before the database is ever asked.</summary>
public sealed class UploadValidationTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    internal static MultipartFormDataContent Form(byte[] content, string fileName, string format, Guid equipmentId)
    {
        var file = new ByteArrayContent(content);
        file.Headers.ContentType = new MediaTypeHeaderValue("text/csv");
        return new MultipartFormDataContent
        {
            { file, "file", fileName },
            { new StringContent(format), "format" },
            { new StringContent(equipmentId.ToString()), "equipment_id" },
        };
    }

    private static async Task<string?> Code(HttpResponseMessage resp) =>
        JsonDocument.Parse(await resp.Content.ReadAsStringAsync()).RootElement.GetProperty("code").GetString();

    [Fact]
    public async Task RejectsUnknownFormat()
    {
        var resp = await factory.CreateClient().PostAsync(new Uri("/api/v1/uploads", UriKind.Relative),
            Form("a,b\n1,2\n"u8.ToArray(), "x.csv", "excel", Guid.NewGuid()));
        Assert.Equal(HttpStatusCode.BadRequest, resp.StatusCode);
        Assert.Equal("validation_error", await Code(resp));
    }

    [Fact]
    public async Task RejectsFilesThatAreNotCsv()
    {
        var resp = await factory.CreateClient().PostAsync(new Uri("/api/v1/uploads", UriKind.Relative),
            Form("a,b\n1,2\n"u8.ToArray(), "data.xlsx", "lbnl_simulated", Guid.NewGuid()));
        Assert.Equal(HttpStatusCode.UnsupportedMediaType, resp.StatusCode);
        Assert.Equal("unsupported_file_type", await Code(resp));
    }

    [Fact]
    public async Task RejectsBinaryContentRenamedToCsv()
    {
        var resp = await factory.CreateClient().PostAsync(new Uri("/api/v1/uploads", UriKind.Relative),
            Form([0x50, 0x4B, 0x03, 0x04, 0x00, 0x00], "data.csv", "lbnl_simulated", Guid.NewGuid()));
        Assert.Equal(HttpStatusCode.UnsupportedMediaType, resp.StatusCode);
        Assert.Equal("not_text", await Code(resp));
    }

    [Fact]
    public void Model_HasNoChangesMissingFromMigrations()
    {
        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<FaultIqDbContext>();
        Assert.False(db.Database.HasPendingModelChanges(),
            "The EF model changed without a migration. Run `dotnet ef migrations add <Name>`.");
    }
}

/// <summary>The API against a real, freshly migrated PostgreSQL database.</summary>
public sealed class DatabaseEndpointTests(DatabaseFactory factory) : IClassFixture<DatabaseFactory>
{
    private static readonly JsonSerializerOptions Snake = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };
    private static Uri Url(string path) => new(path, UriKind.Relative);

    private async Task<Guid> CreateEquipmentAsync(HttpClient client, string name = "RTU-1")
    {
        var resp = await client.PostAsJsonAsync(Url("/api/v1/equipment"), new { name, site = "Test site" });
        Assert.Equal(HttpStatusCode.Created, resp.StatusCode);
        return (await resp.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
    }

    private async Task<JsonElement> UploadAsync(HttpClient client, Guid equipmentId, byte[] content)
    {
        var resp = await client.PostAsync(Url("/api/v1/uploads"),
            UploadValidationTests.Form(content, "my export.csv", "lbnl_simulated", equipmentId));
        Assert.Equal(HttpStatusCode.Created, resp.StatusCode);
        return await resp.Content.ReadFromJsonAsync<JsonElement>();
    }

    [DatabaseFact]
    public async Task Equipment_ValidatesAndPaginates()
    {
        var client = factory.CreateClient();
        var bad = await client.PostAsJsonAsync(Url("/api/v1/equipment"), new { name = "  " });
        Assert.Equal(HttpStatusCode.BadRequest, bad.StatusCode);

        await CreateEquipmentAsync(client, "RTU-A");
        await CreateEquipmentAsync(client, "RTU-B");
        var page = await client.GetFromJsonAsync<JsonElement>(Url("/api/v1/equipment?page=1&page_size=1"));
        Assert.Single(page.GetProperty("items").EnumerateArray());
        Assert.True(page.GetProperty("total").GetInt32() >= 2);
        Assert.Equal(1, page.GetProperty("page_size").GetInt32());
    }

    [DatabaseFact]
    public async Task Upload_StoresUnderServerName_WithHash()
    {
        var client = factory.CreateClient();
        var content = Encoding.UTF8.GetBytes("Timestamp,SAT\n2018-07-20 00:00:00,12.0\n");
        var upload = await UploadAsync(client, await CreateEquipmentAsync(client), content);

        Assert.Equal(Convert.ToHexStringLower(SHA256.HashData(content)), upload.GetProperty("sha256").GetString());
        Assert.Equal("my export.csv", upload.GetProperty("original_name").GetString());
        var stored = Directory.GetFiles(factory.UploadDirectory).Select(Path.GetFileName).ToList();
        Assert.Contains($"{upload.GetProperty("id").GetGuid():N}.csv", stored);
        Assert.DoesNotContain("my export.csv", stored);
    }

    [DatabaseFact]
    public async Task Upload_ToUnknownEquipment_IsNotFound()
    {
        var resp = await factory.CreateClient().PostAsync(Url("/api/v1/uploads"),
            UploadValidationTests.Form("a\n1\n"u8.ToArray(), "x.csv", "lbnl_simulated", Guid.NewGuid()));
        Assert.Equal(HttpStatusCode.NotFound, resp.StatusCode);
    }

    [DatabaseFact]
    public async Task Analysis_QueuesAJob_AndServesTheStoredResultWhenDone()
    {
        var client = factory.CreateClient();
        var equipmentId = await CreateEquipmentAsync(client);
        var upload = await UploadAsync(client, equipmentId, "a\n1\n"u8.ToArray());

        var created = await client.PostAsJsonAsync(Url("/api/v1/analyses"),
            new { upload_id = upload.GetProperty("id").GetGuid() }, Snake);
        Assert.Equal(HttpStatusCode.Accepted, created.StatusCode);
        var analysis = await created.Content.ReadFromJsonAsync<JsonElement>();
        var id = analysis.GetProperty("id").GetGuid();
        Assert.Equal("queued", analysis.GetProperty("status").GetString());
        Assert.Equal($"/api/v1/analyses/{id}", created.Headers.Location?.OriginalString);

        var early = await client.GetAsync(Url($"/api/v1/analyses/{id}/result"));
        Assert.Equal(HttpStatusCode.Conflict, early.StatusCode);

        // Play the worker's part: store a result and an event summary, as worker/db.py does.
        const string result = """{"schema_version": "1.0.0", "events": [{"id": "event-1"}]}""";
        await using (var scope = factory.Services.CreateAsyncScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<FaultIqDbContext>();
            var row = await db.Analyses.SingleAsync(a => a.Id == id);
            Assert.NotNull(row.Traceparent); // the worker continues this request's trace
            row.Status = AnalysisStatus.Succeeded;
            row.Result = result;
            row.EventCount = 1;
            db.FaultEvents.Add(new FaultEvent
            {
                Id = Guid.NewGuid(),
                AnalysisId = id,
                EquipmentId = equipmentId,
                EventKey = "event-1",
                Kind = "fault",
                Fault = "condenser_fouling",
                StartsAt = DateTimeOffset.UtcNow.AddHours(-3),
                EndsAt = DateTimeOffset.UtcNow,
                Hours = 3,
                Confidence = 0.97,
                DetectorScore = 9.1,
            });
            await db.SaveChangesAsync();
        }

        var stored = await client.GetFromJsonAsync<JsonElement>(Url($"/api/v1/analyses/{id}/result"));
        Assert.Equal("1.0.0", stored.GetProperty("schema_version").GetString());
        var events = await client.GetFromJsonAsync<JsonElement>(
            Url($"/api/v1/fault-events?analysis_id={id}&fault=condenser_fouling"));
        Assert.Equal(1, events.GetProperty("total").GetInt32());
    }

    [DatabaseFact]
    public async Task Analysis_RejectsUnknownPointSet_AndUnknownUpload()
    {
        var client = factory.CreateClient();
        var bad = await client.PostAsJsonAsync(Url("/api/v1/analyses"),
            new { upload_id = Guid.NewGuid(), point_set = "everything" }, Snake);
        Assert.Equal(HttpStatusCode.BadRequest, bad.StatusCode);
        var missing = await client.PostAsJsonAsync(Url("/api/v1/analyses"), new { upload_id = Guid.NewGuid() }, Snake);
        Assert.Equal(HttpStatusCode.NotFound, missing.StatusCode);
    }
}
