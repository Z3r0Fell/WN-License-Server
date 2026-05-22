// WatchNexus Licensing Server - drop-in .NET / C# client.
//
// Target: .NET 6.0+ (uses System.Net.Http.Json + System.Text.Json).
// Works in: console apps, WinForms/WPF/MAUI, ASP.NET, Unity (with HttpClient),
//           and any other .NET host with networking.
//
// Usage:
//
//     using WatchNexus;
//
//     var client = new WatchNexusClient(
//         baseUrl: "https://licenses.example.com",
//         apiKey:  "wnk_...",
//         licenseKey: "WNX-...");
//
//     var token = await client.ActivateAsync(new ActivateRequest {
//         HardwareId = "01:23:45:67:89:AB",
//         Domain     = "customer.example.com",
//         DeviceName = "Marie\u2019s Surface",
//     });
//
//     var state = await client.ValidateAsync(token);
//     // state.Valid + state.Mode ("online" | "grace" | "grace_offline" | ...)
//
//     await client.DeactivateAsync(token);
//
// Includes automatic offline-grace fallback in ValidateAsync (returns
// mode="grace_offline" when the server is unreachable BUT the locally
// decoded token is still within its grace_until window).
//
// MIT-licensed. Copy this single file into your project. No NuGet packages
// beyond what ships with .NET 6+.

using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace WatchNexus;

public sealed class WatchNexusException : Exception
{
    public int? StatusCode { get; init; }
    public string? RawBody { get; init; }

    public WatchNexusException(string message, int? statusCode = null,
                               string? rawBody = null, Exception? inner = null)
        : base(message, inner)
    {
        StatusCode = statusCode;
        RawBody = rawBody;
    }
}

public record ActivateRequest
{
    [JsonPropertyName("license_key")]   public string? LicenseKey { get; init; }
    [JsonPropertyName("hardware_id")]   public string? HardwareId { get; init; }
    [JsonPropertyName("domain")]        public string? Domain     { get; init; }
    [JsonPropertyName("device_name")]   public string? DeviceName { get; init; }
}

public record ActivateResponse
{
    [JsonPropertyName("activation_id")]    public string ActivationId    { get; init; } = "";
    [JsonPropertyName("activation_token")] public string ActivationToken { get; init; } = "";
    [JsonPropertyName("expires_at")]       public long ExpiresAt         { get; init; }
    [JsonPropertyName("grace_until")]      public long GraceUntil        { get; init; }
    [JsonPropertyName("reused")]           public bool Reused            { get; init; }
}

public record ValidateResponse
{
    [JsonPropertyName("valid")]       public bool Valid { get; init; }
    [JsonPropertyName("mode")]        public string? Mode { get; init; }
    [JsonPropertyName("expires_at")]  public long? ExpiresAt  { get; init; }
    [JsonPropertyName("grace_until")] public long? GraceUntil { get; init; }
}

public sealed class WatchNexusClient : IDisposable
{
    private readonly HttpClient _http;
    private readonly bool _ownsClient;
    private readonly string _baseUrl;
    private readonly string _apiKey;
    private readonly string? _licenseKey;
    private readonly JsonSerializerOptions _json = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        PropertyNameCaseInsensitive = true,
    };

    public WatchNexusClient(string baseUrl, string apiKey, string? licenseKey = null,
                            HttpClient? httpClient = null,
                            TimeSpan? timeout = null)
    {
        if (string.IsNullOrWhiteSpace(baseUrl)) throw new ArgumentException("baseUrl is required");
        if (string.IsNullOrWhiteSpace(apiKey))  throw new ArgumentException("apiKey is required");
        _baseUrl = baseUrl.TrimEnd('/');
        _apiKey = apiKey;
        _licenseKey = licenseKey;
        if (httpClient is null)
        {
            _http = new HttpClient();
            _ownsClient = true;
        }
        else
        {
            _http = httpClient;
            _ownsClient = false;
        }
        _http.Timeout = timeout ?? TimeSpan.FromSeconds(10);
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("watchnexus-dotnet/1.0");
        _http.DefaultRequestHeaders.Remove("X-API-Key");
        _http.DefaultRequestHeaders.Add("X-API-Key", _apiKey);
    }

    public async Task<ActivateResponse> ActivateAsync(ActivateRequest req,
                                                       CancellationToken ct = default)
    {
        var body = req with { LicenseKey = req.LicenseKey ?? _licenseKey };
        if (string.IsNullOrEmpty(body.LicenseKey))
            throw new ArgumentException("LicenseKey required (pass it or set licenseKey ctor arg)");
        return await PostAsync<ActivateResponse>("/api/integrate/activate", body, ct);
    }

    /// <summary>
    /// Validate the activation token against the server. If the call fails
    /// AND <paramref name="allowOfflineGrace"/> is true AND the local JWT is
    /// still within its grace_until, returns a synthetic
    /// <see cref="ValidateResponse"/> with <c>Mode = "grace_offline"</c>.
    /// </summary>
    public async Task<ValidateResponse> ValidateAsync(string activationToken,
        string? hardwareId = null, string? domain = null,
        bool allowOfflineGrace = true, CancellationToken ct = default)
    {
        var body = new { activation_token = activationToken, hardware_id = hardwareId, domain };
        try
        {
            return await PostAsync<ValidateResponse>("/api/integrate/validate", body, ct);
        }
        catch (WatchNexusException) when (allowOfflineGrace) { return OfflineFallback(activationToken); }
        catch (HttpRequestException) when (allowOfflineGrace) { return OfflineFallback(activationToken); }
        catch (TaskCanceledException) when (allowOfflineGrace) { return OfflineFallback(activationToken); }
    }

    public Task<ValidateResponse> ValidateAsync(ActivateResponse token,
        string? hardwareId = null, string? domain = null,
        bool allowOfflineGrace = true, CancellationToken ct = default)
        => ValidateAsync(token.ActivationToken, hardwareId, domain, allowOfflineGrace, ct);

    public async Task<bool> DeactivateAsync(string activationToken,
        CancellationToken ct = default)
    {
        var body = new { activation_token = activationToken, license_key = _licenseKey };
        var resp = await PostAsync<JsonElement>("/api/integrate/deactivate", body, ct);
        return resp.TryGetProperty("ok", out var ok) && ok.GetBoolean();
    }

    public Task<bool> DeactivateAsync(ActivateResponse token,
                                       CancellationToken ct = default)
        => DeactivateAsync(token.ActivationToken, ct);

    public async Task<string> GetPublicKeyPemAsync(CancellationToken ct = default)
    {
        var r = await _http.GetAsync($"{_baseUrl}/api/public-key", ct);
        r.EnsureSuccessStatusCode();
        var doc = await r.Content.ReadFromJsonAsync<JsonElement>(_json, ct);
        return doc.GetProperty("pem").GetString() ?? "";
    }

    // -------------------- helpers --------------------
    private async Task<T> PostAsync<T>(string path, object body, CancellationToken ct)
    {
        using var req = new HttpRequestMessage(HttpMethod.Post, $"{_baseUrl}{path}")
        {
            Content = JsonContent.Create(body, options: _json),
        };
        using var r = await _http.SendAsync(req, ct);
        var raw = await r.Content.ReadAsStringAsync(ct);
        if (!r.IsSuccessStatusCode)
        {
            throw new WatchNexusException(
                $"{path} failed: {(int)r.StatusCode}",
                statusCode: (int)r.StatusCode, rawBody: raw);
        }
        return JsonSerializer.Deserialize<T>(raw, _json)
               ?? throw new WatchNexusException($"{path}: empty body");
    }

    private static ValidateResponse OfflineFallback(string token)
    {
        var claims = DecodeJwtPayload(token);
        var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        if (claims is not null && claims.Value.TryGetProperty("grace_until", out var g)
            && g.GetInt64() >= now)
        {
            return new ValidateResponse
            {
                Valid = true,
                Mode = "grace_offline",
                ExpiresAt = claims.Value.TryGetProperty("exp", out var e) ? e.GetInt64() : null,
                GraceUntil = g.GetInt64(),
            };
        }
        return new ValidateResponse { Valid = false, Mode = "unreachable" };
    }

    /// <summary>Decode (without verifying) the JWT payload of an activation token.</summary>
    public static JsonElement? DecodeJwtPayload(string token)
    {
        try
        {
            var parts = token.Split('.');
            if (parts.Length != 3) return null;
            var payload = Base64UrlDecode(parts[1]);
            using var doc = JsonDocument.Parse(payload);
            return doc.RootElement.Clone();
        }
        catch { return null; }
    }

    private static byte[] Base64UrlDecode(string s)
    {
        s = s.Replace('-', '+').Replace('_', '/');
        switch (s.Length % 4) { case 2: s += "=="; break; case 3: s += "="; break; }
        return Convert.FromBase64String(s);
    }

    public void Dispose()
    {
        if (_ownsClient) _http.Dispose();
    }
}
