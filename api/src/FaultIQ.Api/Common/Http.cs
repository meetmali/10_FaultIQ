using Microsoft.AspNetCore.Http.HttpResults;

namespace FaultIQ.Api.Common;

/// <summary>A page of results with the total count, so clients can render pagination.</summary>
public sealed record PagedResult<T>(IReadOnlyList<T> Items, int Page, int PageSize, int Total);

public sealed record PageQuery(int? Page, int? PageSize)
{
    public const int MaxPageSize = 100;
    public int Number => Math.Max(1, Page ?? 1);
    public int Size => Math.Clamp(PageSize ?? 20, 1, MaxPageSize);
    public int Skip => (Number - 1) * Size;
}

/// <summary>RFC 9457 problem responses with a stable `code` clients can branch on (ADR 0007).</summary>
public static class Problems
{
    public static ProblemHttpResult Of(int status, string code, string detail) =>
        TypedResults.Problem(detail: detail, statusCode: status,
            extensions: new Dictionary<string, object?> { ["code"] = code });

    public static ProblemHttpResult NotFound(string what) =>
        Of(StatusCodes.Status404NotFound, "not_found", $"{what} was not found.");

    public static ProblemHttpResult Invalid(string field, string message) =>
        TypedResults.Problem(
            detail: "The request is not valid.",
            statusCode: StatusCodes.Status400BadRequest,
            extensions: new Dictionary<string, object?>
            {
                ["code"] = "validation_error",
                ["errors"] = new Dictionary<string, string[]> { [field] = [message] },
            });
}
