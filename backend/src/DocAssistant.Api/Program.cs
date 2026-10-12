using System.Text.Json.Serialization;
using DocAssistant.Api.Data;
using DocAssistant.Api.Endpoints;
using DocAssistant.Api.Services;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.EntityFrameworkCore;
using Scalar.AspNetCore;

var builder = WebApplication.CreateBuilder(args);
var config = builder.Configuration;

builder.Services.AddDbContext<AppDbContext>(o =>
    o.UseNpgsql(config.GetConnectionString("Default")
                ?? throw new InvalidOperationException("ConnectionStrings:Default saknas")));

builder.Services.Configure<StorageOptions>(config.GetSection("Storage"));
builder.Services.Configure<UploadOptions>(config.GetSection("Upload"));
builder.Services.Configure<ProcessingOptions>(config.GetSection("Processing"));
builder.Services.Configure<FormOptions>(o =>
    o.MultipartBodyLengthLimit = (config.GetValue<long?>("Upload:MaxBytes") ?? 25 * 1024 * 1024) + 1024 * 1024);

builder.Services.AddScoped<ICurrentUser, DemoUser>();
builder.Services.AddSingleton<IFileStorage, LocalFileStorage>();
builder.Services.AddSingleton<DocumentQueue>();
builder.Services.AddSingleton<IDocumentQueue>(sp => sp.GetRequiredService<DocumentQueue>());
builder.Services.AddHostedService<DocumentProcessingWorker>();

builder.Services.AddHttpClient<IAiServiceClient, AiServiceClient>(client =>
{
    client.BaseAddress = new Uri(config["AiService:BaseUrl"] ?? "http://localhost:8000/");
    // The LLM can be slow on a local GPU; fail clearly rather than hang forever.
    client.Timeout = TimeSpan.FromSeconds(config.GetValue("AiService:TimeoutSeconds", 150));
    var key = config["AiService:InternalKey"];
    if (!string.IsNullOrEmpty(key)) client.DefaultRequestHeaders.Add("X-Internal-Key", key);
});

builder.Services.ConfigureHttpJsonOptions(o => o.SerializerOptions.Converters.Add(new JsonStringEnumConverter()));
builder.Services.AddExceptionHandler<ApiExceptionHandler>();
builder.Services.AddProblemDetails();
builder.Services.AddOpenApi();
builder.Services.AddCors(o => o.AddDefaultPolicy(p => p
    .WithOrigins(config.GetSection("Cors:Origins").Get<string[]>() ?? [])
    .AllowAnyHeader()
    .AllowAnyMethod()));

var app = builder.Build();

app.UseExceptionHandler();
app.UseStatusCodePages();
app.UseCors();

if (config.GetValue("Database:MigrateOnStartup", false))
{
    using var scope = app.Services.CreateScope();
    await scope.ServiceProvider.GetRequiredService<AppDbContext>().Database.MigrateAsync();
}

app.MapOpenApi();
app.MapScalarApiReference();

app.MapGet("/health", async (AppDbContext db, IAiServiceClient ai, CancellationToken ct) =>
{
    var dbOk = await db.Database.CanConnectAsync(ct);
    var aiOk = await ai.IsHealthyAsync(ct);
    var body = new { database = dbOk, aiService = aiOk };
    return dbOk ? Results.Ok(body) : Results.Json(body, statusCode: StatusCodes.Status503ServiceUnavailable);
}).WithTags("Health");

app.MapDocumentEndpoints();
app.MapChatEndpoints();

app.Run();

public partial class Program;
