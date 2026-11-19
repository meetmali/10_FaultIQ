using FaultIQ.Api.Data;
using FaultIQ.Api.Storage;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

namespace FaultIQ.Api.Hosting;

public static class PersistenceExtensions
{
    public static IServiceCollection AddFaultIqPersistence(this IServiceCollection services, IConfiguration config)
    {
        services.Configure<UploadOptions>(config.GetSection(UploadOptions.Section));
        services.AddSingleton<IFileStore, LocalFileStore>();

        var connection = config.GetConnectionString("FaultIQ");
        services.AddDbContext<FaultIqDbContext>(o => o
            .UseNpgsql(string.IsNullOrWhiteSpace(connection) ? "Host=unconfigured" : connection)
            .UseSnakeCaseNamingConvention());
        return services;
    }

    /// <summary>
    /// OpenTelemetry tracing for HTTP and database calls (ADR 0012). Spans are exported over OTLP
    /// only when OTEL_EXPORTER_OTLP_ENDPOINT is set; otherwise they still give logs a trace ID.
    /// </summary>
    public static IServiceCollection AddFaultIqTelemetry(this IServiceCollection services, IConfiguration config)
    {
        services.AddOpenTelemetry()
            .ConfigureResource(r => r.AddService("faultiq-api"))
            .WithTracing(t =>
            {
                t.AddAspNetCoreInstrumentation(o => o.Filter = ctx => !ctx.Request.Path.StartsWithSegments("/api/v1/health"))
                    .AddNpgsql();
                if (!string.IsNullOrWhiteSpace(config["OTEL_EXPORTER_OTLP_ENDPOINT"]))
                {
                    t.AddOtlpExporter();
                }
            });
        return services;
    }

    /// <summary>Applies pending migrations at startup when configured (dev, Compose, single-node installs).</summary>
    public static async Task MigrateIfConfiguredAsync(this WebApplication app)
    {
        if (!app.Configuration.GetValue("Database:MigrateOnStartup", false)
            || string.IsNullOrWhiteSpace(app.Configuration.GetConnectionString("FaultIQ")))
        {
            return;
        }

        await using var scope = app.Services.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<FaultIqDbContext>();
        var log = scope.ServiceProvider.GetRequiredService<ILoggerFactory>().CreateLogger("FaultIQ.Migrations");
        var pending = (await db.Database.GetPendingMigrationsAsync()).ToList();
        if (pending.Count > 0)
        {
            log.LogInformation("Applying {Count} migration(s): {Migrations}", pending.Count, pending);
            await db.Database.MigrateAsync();
        }
    }
}
