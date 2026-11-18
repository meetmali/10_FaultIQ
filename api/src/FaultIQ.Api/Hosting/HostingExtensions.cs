using System.Threading.RateLimiting;
using Microsoft.AspNetCore.HttpOverrides;
using Microsoft.Extensions.Options;

namespace FaultIQ.Api.Hosting;

public static class HostingExtensions
{
    private static readonly HashSet<string> ReadOnlyMethods =
        new(StringComparer.OrdinalIgnoreCase) { "GET", "HEAD", "OPTIONS" };

    public static IServiceCollection AddFaultIqHosting(this IServiceCollection services, IConfiguration config)
    {
        services.Configure<DemoOptions>(config.GetSection(DemoOptions.Section));
        services.Configure<RateLimitingOptions>(config.GetSection(RateLimitingOptions.Section));

        // Options are read per request, so configuration overrides (tests, environment variables) always apply.
        services.AddRateLimiter(o =>
        {
            o.GlobalLimiter = PartitionedRateLimiter.Create<HttpContext, string>(ctx =>
            {
                var permits = ctx.RequestServices.GetRequiredService<IOptions<RateLimitingOptions>>()
                    .Value.PermitPerMinute;
                if (permits <= 0)
                {
                    return RateLimitPartition.GetNoLimiter("unlimited");
                }

                var client = ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown";
                return RateLimitPartition.GetFixedWindowLimiter(client, _ => new FixedWindowRateLimiterOptions
                {
                    PermitLimit = permits,
                    Window = TimeSpan.FromMinutes(1),
                    QueueLimit = 0,
                });
            });
            o.OnRejected = (ctx, _) => WriteProblemAsync(
                ctx.HttpContext, StatusCodes.Status429TooManyRequests, "rate_limited",
                "Too many requests. Please slow down and try again shortly.");
        });

        services.Configure<ForwardedHeadersOptions>(o =>
        {
            o.ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto;
            // The proxy's container address isn't fixed, so trust the immediate proxy.
            // This is safe only because ReverseProxy:Enabled is set when the API is not publicly reachable.
            o.KnownIPNetworks.Clear();
            o.KnownProxies.Clear();
        });

        return services;
    }

    public static WebApplication UseFaultIqHosting(this WebApplication app)
    {
        if (app.Configuration.GetValue<bool>($"{ReverseProxyOptions.Section}:Enabled"))
        {
            app.UseForwardedHeaders();
        }

        app.UseRateLimiter();

        // Demo mode: the public demo never accepts writes (uploads, jobs, edits).
        app.Use(async (ctx, next) =>
        {
            var demo = ctx.RequestServices.GetRequiredService<IOptions<DemoOptions>>().Value;
            if (demo.Enabled
                && ctx.Request.Path.StartsWithSegments("/api", StringComparison.OrdinalIgnoreCase)
                && !ReadOnlyMethods.Contains(ctx.Request.Method))
            {
                await WriteProblemAsync(ctx, StatusCodes.Status403Forbidden, "demo_read_only",
                    "This is a read-only public demo. Self-host FaultIQ to analyse your own data.");
                return;
            }

            await next(ctx);
        });

        return app;
    }

    private static async ValueTask WriteProblemAsync(HttpContext ctx, int status, string code, string detail)
    {
        ctx.Response.StatusCode = status;
        var problems = ctx.RequestServices.GetRequiredService<IProblemDetailsService>();
        await problems.WriteAsync(new ProblemDetailsContext
        {
            HttpContext = ctx,
            ProblemDetails =
            {
                Status = status,
                Detail = detail,
                Extensions = { ["code"] = code },
            },
        });
    }
}
