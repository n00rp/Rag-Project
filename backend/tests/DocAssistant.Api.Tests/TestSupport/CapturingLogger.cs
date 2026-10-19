using System.Collections.Concurrent;
using Microsoft.Extensions.Logging;

namespace DocAssistant.Api.Tests.TestSupport;

/// <summary>Collects every log message so tests can check what the app writes (and what it must not).</summary>
public sealed class CapturingLoggerProvider : ILoggerProvider
{
    public ConcurrentQueue<string> Messages { get; } = new();

    public ILogger CreateLogger(string categoryName) => new Capture(Messages);

    public void Dispose()
    {
    }

    private sealed class Capture(ConcurrentQueue<string> sink) : ILogger
    {
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter) =>
            sink.Enqueue(formatter(state, exception));
    }
}
