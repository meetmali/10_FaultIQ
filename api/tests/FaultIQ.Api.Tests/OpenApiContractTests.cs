namespace FaultIQ.Api.Tests;

/// <summary>
/// The OpenAPI document is committed at docs/contracts/openapi.json, and the frontend's TypeScript
/// types are generated from it (ADR 0008). This test fails when the API's contract changes without
/// that file being regenerated. To regenerate: set UPDATE_CONTRACTS=1 and run the tests.
/// </summary>
public sealed class OpenApiContractTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    private static string ContractPath()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "FaultIQ_README.md")))
        {
            dir = dir.Parent;
        }

        return Path.Combine(dir?.FullName ?? throw new InvalidOperationException("Repository root not found"),
            "docs", "contracts", "openapi.json");
    }

    [Fact]
    public async Task CommittedOpenApiDocument_MatchesTheApi()
    {
        var live = await factory.CreateClient().GetStringAsync(new Uri("/api/v1/openapi.json", UriKind.Relative));
        live = live.ReplaceLineEndings("\n").TrimEnd() + "\n";
        var path = ContractPath();
        if (Environment.GetEnvironmentVariable("UPDATE_CONTRACTS") == "1")
        {
            await File.WriteAllTextAsync(path, live);
        }

        Assert.True(File.Exists(path), "docs/contracts/openapi.json is missing. Run the tests with UPDATE_CONTRACTS=1.");
        Assert.True(live == await File.ReadAllTextAsync(path),
            "The API contract changed. Run the tests with UPDATE_CONTRACTS=1 and regenerate the frontend types.");
    }
}
