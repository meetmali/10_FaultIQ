using FaultIQ.Api.Common;
using FaultIQ.Api.Data;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace FaultIQ.Api.Features;

public sealed record CreateEquipmentRequest(string Name, string? Site);

public sealed record EquipmentResponse(Guid Id, string Name, string? Site, DateTimeOffset CreatedAt)
{
    public static EquipmentResponse From(Equipment e) => new(e.Id, e.Name, e.Site, e.CreatedAt);
}

public static class EquipmentEndpoints
{
    public static RouteGroupBuilder MapEquipmentEndpoints(this RouteGroupBuilder api)
    {
        var g = api.MapGroup("/equipment").WithTags("equipment");

        g.MapPost("/", async Task<Results<Created<EquipmentResponse>, ProblemHttpResult>> (
            CreateEquipmentRequest body, FaultIqDbContext db, TimeProvider clock, CancellationToken ct) =>
        {
            var name = body.Name?.Trim() ?? "";
            if (name.Length is 0 or > 200)
            {
                return Problems.Invalid("name", "Name is required and must be at most 200 characters.");
            }

            var site = string.IsNullOrWhiteSpace(body.Site) ? null : body.Site.Trim();
            if (site is { Length: > 200 })
            {
                return Problems.Invalid("site", "Site must be at most 200 characters.");
            }

            var e = new Equipment { Id = Guid.CreateVersion7(), Name = name, Site = site, CreatedAt = clock.GetUtcNow() };
            db.Equipment.Add(e);
            await db.SaveChangesAsync(ct);
            return TypedResults.Created($"/api/v1/equipment/{e.Id}", EquipmentResponse.From(e));
        }).WithName("CreateEquipment");

        g.MapGet("/", async (
            FaultIqDbContext db, CancellationToken ct,
            [FromQuery] string? site, [FromQuery] int? page, [FromQuery(Name = "page_size")] int? pageSize) =>
        {
            var p = new PageQuery(page, pageSize);
            var q = db.Equipment.AsNoTracking();
            if (!string.IsNullOrWhiteSpace(site))
            {
                q = q.Where(e => e.Site == site);
            }

            var total = await q.CountAsync(ct);
            var items = await q.OrderBy(e => e.Name).ThenBy(e => e.Id).Skip(p.Skip).Take(p.Size)
                .Select(e => new EquipmentResponse(e.Id, e.Name, e.Site, e.CreatedAt)).ToListAsync(ct);
            return TypedResults.Ok(new PagedResult<EquipmentResponse>(items, p.Number, p.Size, total));
        }).WithName("ListEquipment");

        g.MapGet("/{id:guid}", async Task<Results<Ok<EquipmentResponse>, ProblemHttpResult>> (
            Guid id, FaultIqDbContext db, CancellationToken ct) =>
        {
            var e = await db.Equipment.AsNoTracking().FirstOrDefaultAsync(x => x.Id == id, ct);
            return e is null ? Problems.NotFound("Equipment") : TypedResults.Ok(EquipmentResponse.From(e));
        }).WithName("GetEquipment");

        return api;
    }
}
