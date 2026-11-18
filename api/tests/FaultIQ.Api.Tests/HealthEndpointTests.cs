using System.Net;
using System.Text.Json;
using FaultIQ.Api.Health;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;

namespace FaultIQ.Api.Tests;

public sealed class HealthEndpointTests(WebApplicationFactory<Program> factory)
    : IClassFixture<WebApplicationFactory<Program>>
{
    private sealed class FakeProbe(Func<bool> result) : IDatabaseProbe
    {
        public Task<bool> IsReachableAsync(CancellationToken cancellationToken) => Task.FromResult(result());
    }

    private HttpClient ClientWithProbe(Func<bool> probe) =>
        factory.WithWebHostBuilder(b => b.ConfigureTestServices(s =>
            s.AddSingleton<IDatabaseProbe>(new FakeProbe(probe)))).CreateClient();

    private static async Task<JsonElement> ReadJson(HttpResponseMessage resp) =>
        JsonDocument.Parse(await resp.Content.ReadAsStringAsync()).RootElement;

    [Fact]
    public async Task Health_ReportsStatusAndVersionInSnakeCase()
    {
        var resp = await factory.CreateClient().GetAsync(new Uri("/api/v1/health", UriKind.Relative));

        Assert.Equal(HttpStatusCode.OK, resp.StatusCode);
        var body = await ReadJson(resp);
        Assert.Equal("ok", body.GetProperty("status").GetString());
        Assert.Equal("api", body.GetProperty("service").GetString());
        Assert.False(string.IsNullOrEmpty(body.GetProperty("api_version").GetString()));
        Assert.True(body.TryGetProperty("timestamp", out _));
    }

    [Fact]
    public async Task Readiness_Returns200_WhenDatabaseReachable()
    {
        var resp = await ClientWithProbe(() => true).GetAsync(new Uri("/api/v1/health/ready", UriKind.Relative));

        Assert.Equal(HttpStatusCode.OK, resp.StatusCode);
        var body = await ReadJson(resp);
        Assert.Equal("ok", body.GetProperty("checks").GetProperty("database").GetString());
    }

    [Fact]
    public async Task Readiness_Returns503_WhenDatabaseUnreachable()
    {
        var resp = await ClientWithProbe(() => false).GetAsync(new Uri("/api/v1/health/ready", UriKind.Relative));

        Assert.Equal(HttpStatusCode.ServiceUnavailable, resp.StatusCode);
        Assert.Equal("not_ready", (await ReadJson(resp)).GetProperty("status").GetString());
    }

    [Fact]
    public async Task UnknownRoute_ReturnsProblemDetailsWithCode()
    {
        var resp = await factory.CreateClient().GetAsync(new Uri("/api/v1/does-not-exist", UriKind.Relative));

        Assert.Equal(HttpStatusCode.NotFound, resp.StatusCode);
        Assert.Equal("application/problem+json", resp.Content.Headers.ContentType?.MediaType);
        Assert.Equal("http_404", (await ReadJson(resp)).GetProperty("code").GetString());
    }

    [Fact]
    public async Task UnhandledException_ReturnsSafeProblemDetails()
    {
        var client = ClientWithProbe(() => throw new InvalidOperationException("secret connection detail"));

        var resp = await client.GetAsync(new Uri("/api/v1/health/ready", UriKind.Relative));
        var text = await resp.Content.ReadAsStringAsync();

        Assert.Equal(HttpStatusCode.InternalServerError, resp.StatusCode);
        Assert.Contains("\"internal_error\"", text, StringComparison.Ordinal);
        Assert.DoesNotContain("secret connection detail", text, StringComparison.Ordinal);
        Assert.DoesNotContain("InvalidOperationException", text, StringComparison.Ordinal);
    }

    [Fact]
    public async Task OpenApi_IsServedUnderVersionedPrefix()
    {
        var resp = await factory.CreateClient().GetAsync(new Uri("/api/v1/openapi.json", UriKind.Relative));
        Assert.Equal(HttpStatusCode.OK, resp.StatusCode);
    }

    [Fact]
    public async Task Cors_AllowsConfiguredFrontendOrigin()
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, new Uri("/api/v1/health", UriKind.Relative));
        request.Headers.Add("Origin", "http://localhost:5173");

        var resp = await factory.CreateClient().SendAsync(request);

        Assert.Equal("http://localhost:5173", resp.Headers.GetValues("Access-Control-Allow-Origin").Single());
    }
}
