namespace DocAssistant.Api.Services;

public interface ICurrentUser
{
    string OwnerId { get; }
}

/// <summary>
/// Phase 1 placeholder: everything belongs to one demo owner. Replaced by a JWT-based
/// implementation in phase 2 without touching the endpoints, which only depend on ICurrentUser.
/// </summary>
public sealed class DemoUser : ICurrentUser
{
    public string OwnerId => "demo";
}
