namespace FaultIQ.Api.Hosting;

/// <summary>Public demo settings (ADR 0017). Bound from the "Demo" configuration section.</summary>
public sealed class DemoOptions
{
    public const string Section = "Demo";

    /// <summary>When true, the API is read-only: every non-GET request under /api is rejected.</summary>
    public bool Enabled { get; set; }
}

/// <summary>Per-client request limits. Bound from the "RateLimiting" section.</summary>
public sealed class RateLimitingOptions
{
    public const string Section = "RateLimiting";

    /// <summary>Requests allowed per client IP per minute. 0 disables rate limiting.</summary>
    public int PermitPerMinute { get; set; } = 300;
}

/// <summary>Reverse-proxy settings. Bound from the "ReverseProxy" section.</summary>
public sealed class ReverseProxyOptions
{
    public const string Section = "ReverseProxy";

    /// <summary>
    /// Trust X-Forwarded-For and X-Forwarded-Proto headers. Enable only when the API is reachable
    /// through the proxy alone (as in compose.prod.yml), never when it's exposed directly.
    /// </summary>
    public bool Enabled { get; set; }
}
