using Npgsql;

namespace FaultIQ.Api.Health;

/// <summary>Checks whether PostgreSQL is reachable. Abstracted so tests can substitute it.</summary>
public interface IDatabaseProbe
{
    Task<bool> IsReachableAsync(CancellationToken cancellationToken);
}

public sealed class NpgsqlDatabaseProbe(IConfiguration configuration, ILogger<NpgsqlDatabaseProbe> logger)
    : IDatabaseProbe
{
    private readonly string? _connectionString = BuildConnectionString(configuration.GetConnectionString("FaultIQ"));

    public async Task<bool> IsReachableAsync(CancellationToken cancellationToken)
    {
        if (_connectionString is null)
        {
            return false;
        }

        try
        {
            await using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync(cancellationToken);
            await using var command = new NpgsqlCommand("SELECT 1", connection);
            await command.ExecuteScalarAsync(cancellationToken);
            return true;
        }
        catch (Exception ex) when (ex is NpgsqlException or TimeoutException or System.Net.Sockets.SocketException)
        {
            // Log the type only: connection errors can echo host or user details.
            logger.LogWarning("Database probe failed: {ErrorType}", ex.GetType().Name);
            return false;
        }
    }

    private static string? BuildConnectionString(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw))
        {
            return null;
        }

        return new NpgsqlConnectionStringBuilder(raw) { Timeout = 3, CommandTimeout = 3 }.ConnectionString;
    }
}
