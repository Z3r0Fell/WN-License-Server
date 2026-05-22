import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Skeleton } from '../components/ui/skeleton';
import { CodeBlock } from '../components/CodeBlock';
import { CopyChip } from '../components/CopyChip';
import {
  Zap, RotateCcw, PlayCircle, CheckCircle2, AlertTriangle, Sparkles, Download,
} from 'lucide-react';
import { toast } from 'sonner';

const buildCurlActivate = (info) => `curl -X POST "${info.endpoints.activate}" \\
  -H "X-API-Key: ${info.api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "license_key": "${info.demo_license?.key || 'WNX-...'}",
    "hardware_id": "${info.fingerprint_sample.hardware_id}",
    "domain":      "${info.fingerprint_sample.domain}",
    "device_name": "${info.fingerprint_sample.device_name}"
  }'`;

const buildPython = (info) => `# pip install requests
import requests

WATCHNEXUS_URL = "${info.base_url}"
WATCHNEXUS_API_KEY = "${info.api_key}"
LICENSE_KEY = "${info.demo_license?.key || 'WNX-...'}"

def activate(hardware_id: str, domain: str, device_name: str):
    r = requests.post(f"{WATCHNEXUS_URL}/api/integrate/activate",
        headers={"X-API-Key": WATCHNEXUS_API_KEY},
        json={"license_key": LICENSE_KEY,
              "hardware_id": hardware_id,
              "domain": domain,
              "device_name": device_name})
    r.raise_for_status()
    return r.json()  # { activation_token, expires_at, grace_until, ... }

def validate(activation_token: str, hardware_id: str, domain: str):
    r = requests.post(f"{WATCHNEXUS_URL}/api/integrate/validate",
        headers={"X-API-Key": WATCHNEXUS_API_KEY},
        json={"activation_token": activation_token,
              "hardware_id": hardware_id, "domain": domain})
    return r.json()  # { valid: bool, mode: "online"|"grace"|..., license, activation }

def deactivate(activation_token: str):
    r = requests.post(f"{WATCHNEXUS_URL}/api/integrate/deactivate",
        headers={"X-API-Key": WATCHNEXUS_API_KEY},
        json={"activation_token": activation_token})
    return r.json()

if __name__ == "__main__":
    res = activate("${info.fingerprint_sample.hardware_id}",
                   "${info.fingerprint_sample.domain}",
                   "${info.fingerprint_sample.device_name}")
    print("activation_token:", res["activation_token"][:32] + "...")
    print(validate(res["activation_token"],
                   "${info.fingerprint_sample.hardware_id}",
                   "${info.fingerprint_sample.domain}"))`;

const buildJavascript = (info) => `// Node 18+ (fetch global) or any modern browser
const WATCHNEXUS_URL = "${info.base_url}";
const WATCHNEXUS_API_KEY = "${info.api_key}";
const LICENSE_KEY = "${info.demo_license?.key || 'WNX-...'}";

async function activate({ hardware_id, domain, device_name }) {
  const r = await fetch(\`\${WATCHNEXUS_URL}/api/integrate/activate\`, {
    method: "POST",
    headers: { "X-API-Key": WATCHNEXUS_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ license_key: LICENSE_KEY, hardware_id, domain, device_name }),
  });
  if (!r.ok) throw new Error(\`activate failed: \${r.status}\`);
  return r.json();
}

async function validate(activation_token, { hardware_id, domain }) {
  const r = await fetch(\`\${WATCHNEXUS_URL}/api/integrate/validate\`, {
    method: "POST",
    headers: { "X-API-Key": WATCHNEXUS_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ activation_token, hardware_id, domain }),
  });
  return r.json();
}

async function deactivate(activation_token) {
  const r = await fetch(\`\${WATCHNEXUS_URL}/api/integrate/deactivate\`, {
    method: "POST",
    headers: { "X-API-Key": WATCHNEXUS_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ activation_token }),
  });
  return r.json();
}

// Demo
const res = await activate({ hardware_id: "${info.fingerprint_sample.hardware_id}",
                             domain:      "${info.fingerprint_sample.domain}",
                             device_name: "${info.fingerprint_sample.device_name}" });
console.log(await validate(res.activation_token,
            { hardware_id: "${info.fingerprint_sample.hardware_id}",
              domain:      "${info.fingerprint_sample.domain}" }));`;

const buildDotnet = (info) => `// .NET 6+ / C#
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;

public class WatchNexusClient
{
    private const string BaseUrl = "${info.base_url}";
    private const string ApiKey  = "${info.api_key}";
    private readonly HttpClient _http = new();

    public WatchNexusClient()
    {
        _http.DefaultRequestHeaders.Add("X-API-Key", ApiKey);
    }

    public record ActivateReq(string license_key, string? hardware_id,
                              string? domain, string? device_name);
    public record ActivateRes(string activation_id, string activation_token,
                              long expires_at, long grace_until);

    public async Task<ActivateRes?> Activate(ActivateReq req)
    {
        var r = await _http.PostAsJsonAsync($"{BaseUrl}/api/integrate/activate", req);
        r.EnsureSuccessStatusCode();
        return await r.Content.ReadFromJsonAsync<ActivateRes>();
    }
}`;

const buildClientLib = (info) => `# Drop-in Python client (also at /app/clients/python/watchnexus_client.py)
from watchnexus_client import WatchNexusClient

client = WatchNexusClient(
    base_url="${info.base_url}",
    api_key="${info.api_key}",
    license_key="${info.demo_license?.key || 'WNX-...'}",
)

token = client.activate(hardware_id="${info.fingerprint_sample.hardware_id}",
                        domain="${info.fingerprint_sample.domain}",
                        device_name="${info.fingerprint_sample.device_name}")
print(client.validate(token))   # respects offline grace automatically
client.deactivate(token)`;

function StepResult({ step, idx }) {
  return (
    <div className="rounded-lg border border-border bg-muted/10 overflow-hidden" data-testid={`quickstart-test-step-${idx}`}>
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-background/40">
        <div className="flex items-center gap-2 text-xs font-mono">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
          <span className="text-emerald-300">{step.status}</span>
          <span className="text-muted-foreground">{step.label}</span>
        </div>
      </div>
      <pre className="px-4 py-3 overflow-x-auto text-[12px] leading-5 font-mono whitespace-pre">
{JSON.stringify(step.response, null, 2)}
      </pre>
    </div>
  );
}

export default function AdminQuickstart() {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rotating, setRotating] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await adminApi.get('/admin/quickstart');
      setInfo(r.data);
    } catch (e) {
      toast.error('Failed to load quickstart info');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const rotate = async () => {
    if (!window.confirm('Rotate the bootstrap API key? The current key will be revoked immediately and any client still using it will start failing.')) return;
    setRotating(true);
    try {
      await adminApi.post('/admin/quickstart/rotate-key');
      toast.success('Bootstrap key rotated');
      load();
      setTestResult(null);
    } catch (e) {
      toast.error('Rotation failed');
    } finally {
      setRotating(false);
    }
  };

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await adminApi.post('/admin/quickstart/test', {});
      setTestResult(r.data);
      toast.success('Live integration test passed');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-12 rounded-xl" />
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }
  if (!info) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-emerald-300 mb-2">
            <Sparkles className="h-3 w-3" /> Integration kit
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Tie your app suite in — in 60 seconds</h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            We auto-generated a bootstrap API key and a demo license. Drop the snippet below
            into your code, hit run, and your software is talking to this license server.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={rotate}
          disabled={rotating}
          data-testid="quickstart-rotate-key-button"
        >
          <RotateCcw className={`h-4 w-4 mr-1.5 ${rotating ? 'animate-spin' : ''}`} />
          {rotating ? 'Rotating…' : 'Rotate bootstrap key'}
        </Button>
      </div>

      {/* The kit */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-border bg-card p-5" data-testid="quickstart-api-key-card">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Your API Key</div>
            <Zap className="h-3.5 w-3.5 text-emerald-400" />
          </div>
          <CopyChip value={info.api_key} label="API key" testid="quickstart-api-key-chip" className="w-full" />
          <p className="text-[11px] text-muted-foreground mt-2">
            Send this in the <code className="font-mono">X-API-Key</code> header on every <code className="font-mono">/api/integrate/*</code> call.
            Rotate it any time with the button above.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5" data-testid="quickstart-base-url-card">
          <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-3">Base URL</div>
          <CopyChip value={info.base_url} label="Base URL" testid="quickstart-base-url-chip" className="w-full" />
          <p className="text-[11px] text-muted-foreground mt-2">Endpoints:</p>
          <ul className="mt-1 text-[11px] font-mono space-y-0.5">
            <li><span className="text-emerald-400">POST</span> /api/integrate/activate</li>
            <li><span className="text-emerald-400">POST</span> /api/integrate/validate</li>
            <li><span className="text-emerald-400">POST</span> /api/integrate/deactivate</li>
            <li><span className="text-muted-foreground">GET</span>  /api/public-key   <span className="text-muted-foreground">(offline RSA verify)</span></li>
          </ul>
        </div>
      </div>

      {info.demo_license && (
        <div className="rounded-xl border border-border bg-card p-5" data-testid="quickstart-demo-license-card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Demo license</div>
              <div className="text-sm text-muted-foreground mt-1">3 seats, no expiry. Safe to use for development.</div>
            </div>
            <span className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-emerald-300">{info.demo_license.product_slug}</span>
          </div>
          <CopyChip value={info.demo_license.key} label="License key" testid="quickstart-demo-license-chip" className="w-full" />
        </div>
      )}

      {/* Live test runner */}
      <div className="rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent p-5" data-testid="quickstart-test-card">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h3 className="text-base font-semibold flex items-center gap-2">
              <PlayCircle className="h-4 w-4 text-emerald-400" /> Test the integration right now
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Runs a real <span className="font-mono">activate → validate → deactivate</span> cycle against this
              server using your bootstrap key and demo license. The responses below are exactly what your app will see.
            </p>
          </div>
          <Button
            onClick={runTest}
            disabled={testing}
            className="bg-emerald-600 hover:bg-emerald-500 text-white"
            data-testid="quickstart-run-test-button"
          >
            {testing ? 'Running…' : <><PlayCircle className="h-4 w-4 mr-1.5" /> Run test</>}
          </Button>
        </div>
        {testResult && (
          <div className="mt-4 space-y-3" data-testid="quickstart-test-results">
            <div className="text-xs text-muted-foreground">
              fingerprint = <span className="font-mono text-emerald-300">{testResult.fingerprint.slice(0, 16)}…</span>
            </div>
            {testResult.steps.map((s, i) => <StepResult key={i} step={s} idx={i} />)}
          </div>
        )}
      </div>

      {/* Code samples */}
      <div className="rounded-xl border border-border bg-card p-5" data-testid="quickstart-snippets-card">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-base font-semibold">Drop this into your code</h3>
            <p className="text-sm text-muted-foreground mt-1">Every snippet already has your key, base URL and demo license baked in.</p>
          </div>
        </div>
        <Tabs defaultValue="curl">
          <TabsList>
            <TabsTrigger value="curl" data-testid="quickstart-tab-curl">curl</TabsTrigger>
            <TabsTrigger value="python" data-testid="quickstart-tab-python">Python</TabsTrigger>
            <TabsTrigger value="javascript" data-testid="quickstart-tab-javascript">JavaScript / Node</TabsTrigger>
            <TabsTrigger value="dotnet" data-testid="quickstart-tab-dotnet">.NET / C#</TabsTrigger>
            <TabsTrigger value="lib" data-testid="quickstart-tab-lib">Drop-in client</TabsTrigger>
          </TabsList>
          <TabsContent value="curl" className="mt-3">
            <CodeBlock filename="activate.sh" code={buildCurlActivate(info)} testid="quickstart-code-curl" />
          </TabsContent>
          <TabsContent value="python" className="mt-3">
            <CodeBlock filename="watchnexus_client.py" code={buildPython(info)} testid="quickstart-code-python" />
          </TabsContent>
          <TabsContent value="javascript" className="mt-3">
            <CodeBlock filename="watchnexus.js" code={buildJavascript(info)} testid="quickstart-code-javascript" />
          </TabsContent>
          <TabsContent value="dotnet" className="mt-3">
            <CodeBlock filename="WatchNexusClient.cs" code={buildDotnet(info)} testid="quickstart-code-dotnet" />
          </TabsContent>
          <TabsContent value="lib" className="mt-3">
            <div className="flex items-start gap-2 rounded-lg border border-sky-500/30 bg-sky-500/10 p-3 text-xs text-sky-200 mb-3">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>Ready-to-ship clients ship in this repo at <code className="font-mono">/app/clients/python/</code> and <code className="font-mono">/app/clients/javascript/</code>. Copy the file into your project — no install needed.</span>
            </div>
            <CodeBlock filename="example.py" code={buildClientLib(info)} testid="quickstart-code-lib" />
          </TabsContent>
        </Tabs>
      </div>

      {/* Heads-up */}
      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5 flex items-start gap-3" data-testid="quickstart-heads-up">
        <AlertTriangle className="h-5 w-5 text-amber-300 shrink-0 mt-0.5" />
        <div className="text-sm">
          <div className="font-semibold text-amber-100">Before you ship to customers</div>
          <ul className="mt-1 space-y-1 text-amber-100/80 text-[13px]">
            <li>• Rotate the bootstrap key once you go live, and (optionally) lock it to your VPS&apos; outbound IP under <a href="/admin/api-keys" className="text-emerald-400 underline">API Keys</a>.</li>
            <li>• Replace the demo license with real ones (issued via webhooks or the <a href="/admin/licenses" className="text-emerald-400 underline">Licenses</a> page).</li>
            <li>• Pin <code className="font-mono">grace_until</code> handling in your client so a flaky network never locks paying users out.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
