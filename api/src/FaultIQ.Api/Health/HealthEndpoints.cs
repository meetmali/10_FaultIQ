using System.Reflection;
using FaultIQ.Api.Hosting;
using Microsoft.Extensions.Options;

namespace FaultIQ.Api.Health;

public sealed record HealthResponse(
    string Status,
    string Service,
    string ApiVersion,
    string Environment,
    bool DemoMode,
    DateTimeOffset Timestamp);

public sealed record ReadinessResponse(
    string Status,
    IReadOnlyDictionary<string, string> Checks,
    DateTimeOffset Timestamp);

public static class HealthEndpoints
{
    public static readonly string ApiVersion = ResolveVersion();

    public static RouteGroupBuilder MapHealthEndpoints(this RouteGroupBuilder group)
    {
        // Liveness: is the process up? Never touches dependencies.
        group.MapGet("/health", (IHostEnvironment env, IOptions<DemoOptions> demo, TimeProvider clock) =>
                TypedResults.Ok(new HealthResponse(
                    "ok", "api", ApiVersion, env.EnvironmentName.ToLowerInvariant(),
                    demo.Value.Enabled, clock.GetUtcNow())))
            .WithName("GetHealth")
            .WithTags("health");

        // Readiness: are dependencies (PostgreSQL) reachable?
        group.MapGet("/health/ready", async (IDatabaseProbe probe, TimeProvider clock, CancellationToken ct) =>
            {
                var dbOk = await probe.IsReachableAsync(ct);
                var body = new ReadinessResponse(
                    dbOk ? "ready" : "not_ready",
                    new Dictionary<string, string> { ["database"] = dbOk ? "ok" : "unavailable" },
                    clock.GetUtcNow());
                return TypedResults.Json(body, statusCode: dbOk ? StatusCodes.Status200OK : StatusCodes.Status503ServiceUnavailable);
            })
            .WithName("GetReadiness")
            .WithTags("health")
            .Produces<ReadinessResponse>(StatusCodes.Status200OK)
            .Produces<ReadinessResponse>(StatusCodes.Status503ServiceUnavailable);

        return group;
    }

    private static string ResolveVersion()
    {
        var info = typeof(HealthEndpoints).Assembly
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion ?? "0.0.0";
        // Drop the "+<commit sha>" suffix added by SourceLink.
        var plus = info.IndexOf('+', StringComparison.Ordinal);
        return plus >= 0 ? info[..plus] : info;
    }
}
