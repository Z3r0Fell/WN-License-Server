import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck, KeyRound, Activity, FileBarChart2, Webhook, Lock, ArrowRight,
  Github, Cpu, Globe2, ListChecks,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { CodeBlock } from '../components/CodeBlock';
import { publicApi } from '../lib/api';

const ACTIVATE_CURL = `curl -X POST $WATCHNEXUS_URL/api/integrate/activate \\
  -H "X-API-Key: $WATCHNEXUS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "license_key": "WNX-...",
    "hardware_id": "01:23:45:67:89:AB",
    "domain":      "customer.com",
    "device_name": "Marie\u2019s MacBook Pro"
  }'`;

const FEATURES = [
  { icon: KeyRound, title: 'Sign', desc: 'License keys signed with HMAC or RSA. Forgery is not on the menu.' },
  { icon: ShieldCheck, title: 'Activate', desc: 'Hardware + domain fingerprinting, configurable per product.' },
  { icon: Activity, title: 'Validate', desc: 'Online + offline grace tokens so flaky networks don’t lock paying customers out.' },
  { icon: FileBarChart2, title: 'Audit', desc: 'Every issue, revoke, and activation is recorded with actor & severity.' },
  { icon: Webhook, title: 'Webhooks', desc: 'Lemon Squeezy, Paddle, Gumroad signatures verified, idempotent issuance.' },
  { icon: Lock, title: 'Operate', desc: 'API key auth, rate limiting, daily DB backups baked in.' },
];

export default function Landing() {
  const [health, setHealth] = useState(null);
  useEffect(() => {
    publicApi.get('/health').then((r) => setHealth(r.data)).catch(() => setHealth({ status: 'down' }));
  }, []);

  return (
    <div className="dark min-h-screen bg-background text-foreground">
      {/* nav */}
      <header className="border-b border-border/60 bg-background/60 backdrop-blur sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="landing-brand">
            <div className="h-7 w-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <ListChecks className="h-3.5 w-3.5 text-emerald-400" />
            </div>
            <span className="text-sm font-semibold tracking-tight">WatchNexus</span>
            <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground hidden sm:inline">Licensing</span>
          </Link>
          <nav className="flex items-center gap-1">
            <Link to="/docs" className="text-sm text-muted-foreground hover:text-foreground px-3 py-1.5 rounded-lg hover:bg-muted/40 transition-colors" data-testid="landing-docs-link">Docs</Link>
            <Link to="/portal/login" className="text-sm text-muted-foreground hover:text-foreground px-3 py-1.5 rounded-lg hover:bg-muted/40 transition-colors" data-testid="landing-portal-link">Customer portal</Link>
            <Link to="/admin/login">
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="landing-admin-login-cta">
                Admin sign in <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </Link>
          </nav>
        </div>
      </header>

      {/* hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-emerald-wash animate-drift pointer-events-none" />
        <div className="absolute inset-0 bg-grain pointer-events-none" />
        <div className="relative max-w-6xl mx-auto px-6 pt-20 pb-16 grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-emerald-300 mb-5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {health?.status === 'ok' ? 'Server online' : 'Loading…'}
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight">
              Licensing infrastructure that <span className="text-emerald-400">just works</span>.
            </h1>
            <p className="mt-5 text-base md:text-lg text-muted-foreground max-w-xl">
              Self-hosted license server for WatchNexus. Signed keys, fingerprinted activations,
              offline grace, audited admin, and webhooks for every payment processor you actually use.
            </p>
            <div className="mt-8 flex items-center gap-3">
              <Link to="/admin/login">
                <Button size="lg" className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="landing-hero-primary-cta">
                  Open admin panel <ArrowRight className="h-4 w-4 ml-1.5" />
                </Button>
              </Link>
              <Link to="/docs">
                <Button size="lg" variant="secondary" data-testid="landing-hero-secondary-cta">
                  Integration docs
                </Button>
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5"><Cpu className="h-3.5 w-3.5" /> HMAC + RSA signing</span>
              <span className="inline-flex items-center gap-1.5"><Globe2 className="h-3.5 w-3.5" /> Domain + hardware fingerprint</span>
              <span className="inline-flex items-center gap-1.5"><Github className="h-3.5 w-3.5" /> Self-hosted on your VPS</span>
            </div>
          </div>
          <div className="relative">
            <div className="absolute -inset-4 rounded-2xl bg-emerald-500/10 blur-2xl" />
            <CodeBlock
              filename="activate.sh"
              code={ACTIVATE_CURL}
              testid="landing-hero-codeblock"
              className="relative shadow-2xl shadow-black/40"
            />
          </div>
        </div>
      </section>

      {/* features */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="max-w-2xl">
          <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight">Everything you need to ship licensing</h2>
          <p className="mt-2 text-muted-foreground">
            One server. Six things, done well, so you stop reinventing license keys for every product launch.
          </p>
        </div>
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="rounded-xl border border-border bg-card/40 p-5 hover:border-emerald-500/30 hover:bg-card/60 transition-colors"
                data-testid={`landing-feature-${f.title.toLowerCase()}`}
              >
                <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-3">
                  <Icon className="h-4 w-4" />
                </div>
                <h3 className="text-base font-semibold">{f.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* CTA band */}
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <div className="rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent p-10 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <h3 className="text-2xl font-semibold tracking-tight">Ready when your customers buy.</h3>
            <p className="mt-1 text-muted-foreground">Wire your store webhooks, hand your app an API key, and ship.</p>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/docs"><Button variant="secondary" size="lg" data-testid="landing-cta-docs">View docs</Button></Link>
            <Link to="/admin/login">
              <Button size="lg" className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="landing-cta-admin">
                Open admin <ArrowRight className="h-4 w-4 ml-1.5" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between text-xs text-muted-foreground">
          <span>WatchNexus Licensing • v1.0.0</span>
          <span className="font-mono">build.{health?.status === 'ok' ? 'ok' : 'init'}</span>
        </div>
      </footer>
    </div>
  );
}
