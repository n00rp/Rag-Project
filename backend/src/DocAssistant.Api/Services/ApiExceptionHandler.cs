using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;

namespace DocAssistant.Api.Services;

/// <summary>
/// Turns known failure modes into proper RFC 7807 problem responses instead of a generic 500:
/// the AI service being unreachable (503) and malformed client requests (400).
/// </summary>
public sealed class ApiExceptionHandler(IProblemDetailsService problems) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(HttpContext http, Exception exception, CancellationToken ct)
    {
        var problem = exception switch
        {
            AiServiceUnavailableException => new ProblemDetails
            {
                Status = StatusCodes.Status503ServiceUnavailable,
                Title = "AI-tjänsten är inte tillgänglig just nu.",
                Extensions = { ["code"] = "ai_unavailable" },
            },
            BadHttpRequestException bad => new ProblemDetails
            {
                Status = bad.StatusCode,
                Title = "Ogiltig begäran.",
            },
            _ => null,
        };
        if (problem is null) return false;

        http.Response.StatusCode = problem.Status!.Value;
        return await problems.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = http,
            Exception = exception,
            ProblemDetails = problem,
        });
    }
}
