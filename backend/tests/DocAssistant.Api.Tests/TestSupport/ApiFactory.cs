using DocAssistant.Api.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Npgsql;

namespace DocAssistant.Api.Tests.TestSupport;

/// <summary>
/// Runs the real app against a real, throwaway Postgres database (created per factory, dropped on dispose).
/// Needs the compose db to be up: `docker compose up -d db`. Override with TEST_PG_ADMIN.
/// </summary>
public sealed class ApiFactory : WebApplicationFactory<Program>
{
    private static readonly string AdminConnection =
        Environment.GetEnvironmentVariable("TEST_PG_ADMIN")
        ?? "Host=localhost;Port=5432;Database=postgres;Username=app;Password=change-me-locally";

    private readonly string _dbName = $"rag_test_{Guid.NewGuid():N}";
    private readonly string _uploadDir = Path.Combine(Path.GetTempPath(), $"rag_uploads_{Guid.NewGuid():N}");

    public FakeAiServiceClient Ai { get; } = new();

    public ApiFactory()
    {
        using var conn = new NpgsqlConnection(AdminConnection);
        conn.Open();
        using var cmd = new NpgsqlCommand($"CREATE DATABASE \"{_dbName}\"", conn);
        cmd.ExecuteNonQuery();
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["ConnectionStrings:Default"] = new NpgsqlConnectionStringBuilder(AdminConnection) { Database = _dbName }.ConnectionString,
            ["Database:MigrateOnStartup"] = "true",
            ["Storage:Path"] = _uploadDir,
            ["Upload:MaxBytes"] = "2048",
            ["Processing:RetryDelayMs"] = "1",
            ["Processing:MaxAttempts"] = "2",
        }));
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IAiServiceClient>();
            services.AddSingleton<IAiServiceClient>(Ai);
        });
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (!disposing) return;

        NpgsqlConnection.ClearAllPools();
        using var conn = new NpgsqlConnection(AdminConnection);
        conn.Open();
        using var cmd = new NpgsqlCommand($"DROP DATABASE IF EXISTS \"{_dbName}\" WITH (FORCE)", conn);
        cmd.ExecuteNonQuery();
        if (Directory.Exists(_uploadDir)) Directory.Delete(_uploadDir, recursive: true);
    }
}
