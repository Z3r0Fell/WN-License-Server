// Minimal example - drop into a `dotnet new console` project alongside
// WatchNexusClient.cs.
using WatchNexus;

var client = new WatchNexusClient(
    baseUrl:    "https://licenses.example.com",
    apiKey:     "wnk_REPLACE_ME",
    licenseKey: "WNX-REPLACE_ME");

var token = await client.ActivateAsync(new ActivateRequest
{
    HardwareId = "01:23:45:67:89:AB",
    Domain     = "customer.example.com",
    DeviceName = "Marie\u2019s Surface",
});
Console.WriteLine($"activated: {token.ActivationId}");

var state = await client.ValidateAsync(token,
    hardwareId: "01:23:45:67:89:AB",
    domain:     "customer.example.com");
Console.WriteLine($"valid={state.Valid} mode={state.Mode}");

await client.DeactivateAsync(token);
Console.WriteLine("deactivated");
