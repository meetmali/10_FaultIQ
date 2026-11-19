using FaultIQ.Api.Common;
using FaultIQ.Api.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace FaultIQ.Api.Features;

public sealed record FaultEventResponse(
    Guid Id, Guid AnalysisId, Guid EquipmentId, string EventKey, string Kind, string? Fault,
    DateTimeOffset StartsAt, DateTimeOffset EndsAt, int Hours, double? Confidence, double DetectorScore);

public static class FaultEventEndpoints
{
    public static RouteGroupBuilder MapFaultEventEndpoints(this RouteGroupBuilder api)
    {
        // Events across analyses, newest first: the dashboard's "recent fault events" (ADR 0023).
        api.MapGet("/fault-events", async (
            FaultIqDbContext db, CancellationToken ct,
            [FromQuery(Name = "equipment_id")] Guid? equipmentId,
            [FromQuery(Name = "analysis_id")] Guid? analysisId,
            [FromQuery] string? kind, [FromQuery] string? fault,
            [FromQuery] DateTimeOffset? from, [FromQuery] DateTimeOffset? to,
            [FromQuery] int? page, [FromQuery(Name = "page_size")] int? pageSize) =>
        {
            var p = new PageQuery(page, pageSize);
            var q = db.FaultEvents.AsNoTracking();
            if (equipmentId is not null)
            {
                q = q.Where(e => e.EquipmentId == equipmentId);
            }

            if (analysisId is not null)
            {
                q = q.Where(e => e.AnalysisId == analysisId);
            }

            if (kind is not null)
            {
                q = q.Where(e => e.Kind == kind);
            }

            if (fault is not null)
            {
                q = q.Where(e => e.Fault == fault);
            }

            if (from is not null)
            {
                q = q.Where(e => e.EndsAt > from.Value.ToUniversalTime());
            }

            if (to is not null)
            {
                q = q.Where(e => e.StartsAt < to.Value.ToUniversalTime());
            }

            var total = await q.CountAsync(ct);
            var items = await q.OrderByDescending(e => e.StartsAt).ThenBy(e => e.Id)
                .Skip(p.Skip).Take(p.Size)
                .Select(e => new FaultEventResponse(e.Id, e.AnalysisId, e.EquipmentId, e.EventKey, e.Kind,
                    e.Fault, e.StartsAt, e.EndsAt, e.Hours, e.Confidence, e.DetectorScore))
                .ToListAsync(ct);
            return TypedResults.Ok(new PagedResult<FaultEventResponse>(items, p.Number, p.Size, total));
        }).WithTags("fault-events").WithName("ListFaultEvents");

        return api;
    }
}
