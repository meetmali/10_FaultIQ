using System.Text.Json;
using FaultIQ.Api.Health;
using FaultIQ.Api.Hosting;

var builder = WebApplication.CreateBuilder(args);

// Structured JSON logs. Never log secrets or raw sensor data (project plan, section 13).
builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole(o =>
{
    o.UseUtcTimestamp = true;
    o.TimestampFormat = "yyyy-MM-ddTHH:mm:ss.fffZ";
});

// snake_case JSON so the API matches the Python pipeline and the frontend (ADR 0007).
builder.Services.ConfigureHttpJsonOptions(o =>
    o.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower);

// RFC 9457 Problem Details for every error, with a stable "code" field. No stack traces.
builder.Services.AddProblemDetails(o => o.CustomizeProblemDetails = ctx =>
{
    var status = ctx.ProblemDetails.Status ?? StatusCodes.Status500InternalServerError;
    ctx.ProblemDetails.Extensions.TryAdd(
        "code", status >= 500 ? "internal_error" : $"http_{status}");
    ctx.ProblemDetails.Detail = status >= 500 ? "An unexpected error occurred." : ctx.ProblemDetails.Detail;
});

var corsOrigins = (builder.Configuration["Cors:Origins"] ?? string.Empty)
    .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
builder.Services.AddCors(o => o.AddDefaultPolicy(p => p
    .WithOrigins(corsOrigins)
    .WithMethods("GET", "POST", "PATCH", "DELETE")
    .AllowAnyHeader()));

builder.Services.AddFaultIqHosting(builder.Configuration);
builder.Services.AddOpenApi("v1");
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton<IDatabaseProbe, NpgsqlDatabaseProbe>();

var app = builder.Build();

app.UseExceptionHandler();
app.UseStatusCodePages();
app.UseFaultIqHosting();
app.UseCors();

app.MapOpenApi("/api/{documentName}/openapi.json");

var v1 = app.MapGroup("/api/v1");
v1.MapHealthEndpoints();

app.Run();

// Exposed for WebApplicationFactory in integration tests.
public partial class Program;
