using System.Net;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc.Testing;

namespace FaultIQ.Api.Tests;

public sealed class HostingTests(WebApplicationFactory<Program> factory)
    : IClassFixture<WebApplicationFactory<Program>>
{
    private HttpClient ClientWith(params (string Key, string Value)[] settings) =>
        factory.WithWebHostBuilder(b =>
        {
            foreach (var (key, value) in settings)
            {
                b.UseSetting(key, value);
            }
        }).CreateClient();

    private static async Task<JsonElement> ReadJson(HttpResponseMessage resp) =>
        JsonDocument.Parse(await resp.Content.ReadAsStringAsync()).RootElement;

    private static Uri Url(string path) => new(path, UriKind.Relative);

    [Fact]
    public async Task Health_ReportsDemoModeOff_ByDefault()
    {
        var body = await ReadJson(await factory.CreateClient().GetAsync(Url("/api/v1/health")));
        Assert.False(body.GetProperty("demo_mode").GetBoolean());
    }

    [Fact]
    public async Task Health_ReportsDemoModeOn_WhenEnabled()
    {
        var client = ClientWith(("Demo:Enabled", "true"));
        var body = await ReadJson(await client.GetAsync(Url("/api/v1/health")));
        Assert.True(body.GetProperty("demo_mode").GetBoolean());
    }

    [Theory]
    [InlineData("POST")]
    [InlineData("PUT")]
    [InlineData("PATCH")]
    [InlineData("DELETE")]
    public async Task DemoMode_RejectsWrites_WithProblemDetails(string method)
    {
        var client = ClientWith(("Demo:Enabled", "true"));
        using var request = new HttpRequestMessage(new HttpMethod(method), Url("/api/v1/ingestions"));

        var resp = await client.SendAsync(request);

        Assert.Equal(HttpStatusCode.Forbidden, resp.StatusCode);
        Assert.Equal("application/problem+json", resp.Content.Headers.ContentType?.MediaType);
        Assert.Equal("demo_read_only", (await ReadJson(resp)).GetProperty("code").GetString());
    }

    [Fact]
    public async Task DemoMode_StillAllowsReads()
    {
        var client = ClientWith(("Demo:Enabled", "true"));
        var resp = await client.GetAsync(Url("/api/v1/health"));
        Assert.Equal(HttpStatusCode.OK, resp.StatusCode);
    }

    [Fact]
    public async Task WithoutDemoMode_WritesAreNotBlockedByDemoGuard()
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, Url("/api/v1/ingestions"));
        var resp = await factory.CreateClient().SendAsync(request);
        Assert.NotEqual(HttpStatusCode.Forbidden, resp.StatusCode);
    }

    [Fact]
    public async Task RateLimit_Returns429ProblemDetails_WhenExceeded()
    {
        var client = ClientWith(("RateLimiting:PermitPerMinute", "2"));

        await client.GetAsync(Url("/api/v1/health"));
        await client.GetAsync(Url("/api/v1/health"));
        var resp = await client.GetAsync(Url("/api/v1/health"));

        Assert.Equal(HttpStatusCode.TooManyRequests, resp.StatusCode);
        Assert.Equal("rate_limited", (await ReadJson(resp)).GetProperty("code").GetString());
    }
}
