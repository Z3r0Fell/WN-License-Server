import { Link } from 'react-router-dom';
import { ListChecks, ArrowLeft } from 'lucide-react';
import { Button } from '../components/ui/button';
import { CodeBlock } from '../components/CodeBlock';

const ACTIVATE = `POST  /api/integrate/activate
Header  X-API-Key: <your-key>
Body:
{
  "license_key":  "WNX-...",
  "hardware_id":  "01:23:45:67:89:AB",   // optional, depends on product
  "domain":       "customer.com",         // optional, depends on product
  "device_name":  "Marie’s MacBook Pro"   // optional, friendly label
}`;

const ACTIVATE_RES = `200 OK
{
  "activation_id":    "e96ac3c5-...-...",
  "activation_token": "eyJhbGciOiJI...",
  "expires_at":       1778190484,   // unix seconds, valid online window
  "grace_until":      1778795284,   // unix seconds, additional offline grace
  "license":          {"id": "...", "plan": "pro", "product": "watchnexus-pro"},
  "reused":           false         // true = same fingerprint already activated
}`;

const VALIDATE = `POST  /api/integrate/validate
Header  X-API-Key: <your-key>
Body:
{
  "activation_token": "eyJhbGciOi...",
  "hardware_id":      "01:23:45:67:89:AB",  // optional re-bind check
  "domain":           "customer.com"
}`;

const VALIDATE_RES = `200 OK
{
  "valid": true,
  "mode":  "online" | "grace" | "expired" | "fingerprint_mismatch" | ...
  "license":     {"id":"...","plan":"pro","product":"watchnexus-pro","expires_at":null,"seats":2},
  "activation":  {"id":"...","device_name":"laptop1"},
  "expires_at":  1778190484,
  "grace_until": 1778795284
}`;

const DEACTIVATE = `POST  /api/integrate/deactivate
Header  X-API-Key: <your-key>
Body:
{ "activation_token": "eyJhbGciOi..." }
// or, equivalently:
{ "license_key": "WNX-...", "hardware_id": "01:23:45:67:89:AB", "domain": "customer.com" }`;

const CURL_ACTIVATE = `curl -X POST "$WATCHNEXUS_URL/api/integrate/activate" \\
  -H "X-API-Key: $WATCHNEXUS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"license_key":"WNX-...","hardware_id":"01:23","domain":"customer.com","device_name":"laptop"}'`;

const CURL_VALIDATE = `curl -X POST "$WATCHNEXUS_URL/api/integrate/validate" \\
  -H "X-API-Key: $WATCHNEXUS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"activation_token":"eyJhbGciOi...","hardware_id":"01:23","domain":"customer.com"}'`;

const CURL_DEACT = `curl -X POST "$WATCHNEXUS_URL/api/integrate/deactivate" \\
  -H "X-API-Key: $WATCHNEXUS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"activation_token":"eyJhbGciOi..."}'`;

const CURL_MINT = `curl -X POST "$WATCHNEXUS_URL/api/integrate/mint" \\
  -H "X-API-Key: $WATCHNEXUS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"customer_email":"buyer@example.com","product_slug":"watchnexus-pro","plan":"standard","seats":1}'`;

const MINT_RES = `200 OK
{
  "id":            "f7d5...-...",
  "key":           "WNX-...",
  "product_id":    "...",
  "product_slug":  "watchnexus-pro",
  "plan":          "standard",
  "seats":         1,
  "expires_at":    null,
  "status":        "active",
  "source":        "website"
}
// The serial is also emailed to customer_email automatically.`;

const PSEUDO = `// Your client app (pseudo-code)
const t = localStorage.get("wnx_token");
let ok = false;
try {
  const r = await fetch(API + "/integrate/validate", {
    method: "POST", headers: {"X-API-Key": KEY, "Content-Type":"application/json"},
    body: JSON.stringify({ activation_token: t, hardware_id, domain }),
  });
  ok = (await r.json()).valid;
} catch (e) {
  // Network blip: trust local token if not past grace_until
  ok = isWithinGrace(t);
}`;

const SECTIONS = [
  { id: 'auth', label: 'Authentication' },
  { id: 'mint', label: 'POST /mint' },
  { id: 'activate', label: 'POST /activate' },
  { id: 'validate', label: 'POST /validate' },
  { id: 'deactivate', label: 'POST /deactivate' },
  { id: 'grace', label: 'Offline grace period' },
  { id: 'fingerprint', label: 'Fingerprinting' },
  { id: 'webhooks', label: 'Webhooks' },
  { id: 'rsa', label: 'RSA public key' },
  { id: 'rate', label: 'Rate limits' },
];

export default function Docs() {
  return (
    <div className="dark min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-background/60 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="docs-brand">
            <ListChecks className="h-4 w-4 text-emerald-400" />
            <span className="text-sm font-semibold">WatchNexus Docs</span>
          </Link>
          <Link to="/"><Button size="sm" variant="ghost" data-testid="docs-back"><ArrowLeft className="h-3.5 w-3.5 mr-1" /> Home</Button></Link>
        </div>
      </header>
      <div className="max-w-7xl mx-auto px-6 py-10 grid grid-cols-12 gap-8">
        <aside className="hidden lg:block col-span-3" data-testid="docs-left-nav">
          <div className="sticky top-20">
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground mb-2">On this page</div>
            <nav className="space-y-0.5">
              {SECTIONS.map((s) => (
                <a key={s.id} href={`#${s.id}`} className="block text-sm text-muted-foreground hover:text-foreground py-1">{s.label}</a>
              ))}
            </nav>
          </div>
        </aside>
        <article className="col-span-12 lg:col-span-9 max-w-3xl space-y-12">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Integration guide</h1>
            <p className="mt-2 text-muted-foreground">
              Three endpoints, one header, and you’re live. Every example below assumes
              <code className="font-mono mx-1">$WATCHNEXUS_URL</code> is your server’s base URL
              and <code className="font-mono mx-1">$WATCHNEXUS_API_KEY</code> is an API key issued in admin → API keys.
            </p>
          </div>

          <section id="auth">
            <h2 className="text-xl font-semibold mb-3">Authentication</h2>
            <p className="text-sm text-muted-foreground">
              Send your API key on every request as <code className="font-mono">X-API-Key</code>.
              Keys are revealed once at creation time and stored hashed-feeling on the server.
              Revoke any leaked key from the API Keys admin page.
            </p>
          </section>

          <section id="mint">
            <h2 className="text-xl font-semibold mb-3">POST /api/integrate/mint</h2>
            <p className="text-sm text-muted-foreground mb-3">
              Call this from your website’s backend after a successful purchase (payment handled on your side, e.g. Stripe).
              The server generates a signed serial, stores it, and emails it to the buyer. Pick a product by
              <code className="font-mono mx-1">product_id</code> or <code className="font-mono mx-1">product_slug</code>.
            </p>
            <CodeBlock testid="docs-mint-curl" filename="curl" code={CURL_MINT} />
            <CodeBlock testid="docs-mint-response" filename="response" className="mt-3" code={MINT_RES} />
          </section>

          <section id="activate">
            <h2 className="text-xl font-semibold mb-3">POST /api/integrate/activate</h2>
            <p className="text-sm text-muted-foreground mb-3">
              First-run binding. Verify the license key, optionally bind to fingerprint, and receive a JWT-style token.
            </p>
            <CodeBlock testid="docs-activate-spec" filename="request" code={ACTIVATE} />
            <CodeBlock testid="docs-activate-response" filename="response" className="mt-3" code={ACTIVATE_RES} />
            <CodeBlock testid="docs-activate-curl" filename="curl" className="mt-3" code={CURL_ACTIVATE} />
          </section>

          <section id="validate">
            <h2 className="text-xl font-semibold mb-3">POST /api/integrate/validate</h2>
            <p className="text-sm text-muted-foreground mb-3">
              Heartbeat. Validates a token, re-checks fingerprint if you send hardware_id/domain, and updates last_seen on the server.
            </p>
            <CodeBlock testid="docs-validate-spec" filename="request" code={VALIDATE} />
            <CodeBlock testid="docs-validate-response" filename="response" className="mt-3" code={VALIDATE_RES} />
            <CodeBlock testid="docs-validate-curl" filename="curl" className="mt-3" code={CURL_VALIDATE} />
          </section>

          <section id="deactivate">
            <h2 className="text-xl font-semibold mb-3">POST /api/integrate/deactivate</h2>
            <p className="text-sm text-muted-foreground mb-3">
              Free a seat. Pass the activation token (preferred) or original license key + fingerprint inputs.
            </p>
            <CodeBlock testid="docs-deactivate-spec" filename="request" code={DEACTIVATE} />
            <CodeBlock testid="docs-deactivate-curl" filename="curl" className="mt-3" code={CURL_DEACT} />
          </section>

          <section id="grace">
            <h2 className="text-xl font-semibold mb-3">Offline grace period</h2>
            <p className="text-sm text-muted-foreground mb-3">
              Activation tokens carry both <code className="font-mono">exp</code> (24h online) and
              <code className="font-mono mx-1">grace_until</code> (+7d offline). If <code className="font-mono">/validate</code>
              fails because the network is down, your client should accept the token as long as
              <code className="font-mono mx-1">now ≤ grace_until</code> and the JWT signature is locally valid.
            </p>
            <CodeBlock testid="docs-grace-pseudo" filename="client.js (pseudo)" code={PSEUDO} />
          </section>

          <section id="fingerprint">
            <h2 className="text-xl font-semibold mb-3">Fingerprinting</h2>
            <p className="text-sm text-muted-foreground">
              Each product chooses a mode in admin: <strong>none</strong>, <strong>hw</strong>, <strong>domain</strong>, or <strong>both</strong>.
              The server hashes <code className="font-mono">hardware_id</code> and/or <code className="font-mono">domain</code>
              into a stable fingerprint and binds it to the activation token. Sending a different fingerprint to <code className="font-mono">/validate</code>
              returns <code className="font-mono">fingerprint_mismatch</code>.
            </p>
          </section>

          <section id="webhooks">
            <h2 className="text-xl font-semibold mb-3">Webhooks</h2>
            <p className="text-sm text-muted-foreground">
              Point your Stripe account at this endpoint. Requests are signature-verified; duplicates are ignored.
            </p>
            <ul className="mt-3 space-y-1 text-sm font-mono">
              <li>POST <span className="text-emerald-400">/api/webhooks/stripe</span> &nbsp; (header <code>Stripe-Signature: t=...,v1=...</code>)</li>
            </ul>
          </section>

          <section id="rsa">
            <h2 className="text-xl font-semibold mb-3">RSA public key (offline verification)</h2>
            <p className="text-sm text-muted-foreground">
              For RSA-signed products, fetch the server’s public key once from <code className="font-mono">GET /api/public-key</code>
              and bake it into your client to verify license keys offline without ever calling the server.
            </p>
          </section>

          <section id="rate">
            <h2 className="text-xl font-semibold mb-3">Rate limits</h2>
            <p className="text-sm text-muted-foreground">Per-IP, sliding window:</p>
            <ul className="mt-2 space-y-1 text-sm font-mono">
              <li><span className="text-emerald-400">/admin/login</span> &nbsp; 10/min</li>
              <li><span className="text-emerald-400">/customer/login</span> &nbsp; 15/min</li>
              <li><span className="text-emerald-400">/customer/register</span> &nbsp; 5/min</li>
              <li><span className="text-emerald-400">/integrate/activate</span> &nbsp; 60/min</li>
              <li><span className="text-emerald-400">/integrate/validate</span> &nbsp; 600/min (heartbeats)</li>
              <li><span className="text-emerald-400">/integrate/deactivate</span> &nbsp; 30/min</li>
              <li><span className="text-emerald-400">/webhooks/*</span> &nbsp; 300/min</li>
            </ul>
            <p className="text-sm text-muted-foreground mt-2">
              On <code className="font-mono">429</code>, back off and retry; tokens within grace stay valid in the meantime. Use the <code className="font-mono">Retry-After</code> header.
            </p>
          </section>
        </article>
      </div>
    </div>
  );
}
