import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { StatusPill } from '../components/StatusPill';
import { EmptyState } from '../components/EmptyState';
import { Skeleton } from '../components/ui/skeleton';
import { Webhook } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { CodeBlock } from '../components/CodeBlock';

function ProviderTag({ p }) {
  const map = {
    lemonsqueezy: { color: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/20', label: 'Lemon Squeezy' },
    paddle: { color: 'bg-sky-500/15 text-sky-300 border-sky-500/20', label: 'Paddle' },
    gumroad: { color: 'bg-pink-500/15 text-pink-300 border-pink-500/20', label: 'Gumroad' },
    stripe: { color: 'bg-violet-500/15 text-violet-300 border-violet-500/20', label: 'Stripe' },
  };
  const m = map[p] || { color: 'bg-muted text-muted-foreground border-border', label: p };
  return <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium ${m.color}`}>{m.label}</span>;
}

export default function AdminWebhooks() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState(null);

  const load = async () => {
    setLoading(true);
    try { setItems((await adminApi.get('/admin/webhook-events')).data); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Webhook events</h1>
          <p className="text-sm text-muted-foreground mt-1">All deliveries from Lemon Squeezy, Paddle, Gumroad, and Stripe. Signature-verified, idempotent.</p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { p: 'lemonsqueezy', path: '/api/webhooks/lemonsqueezy', hdr: 'X-Signature' },
          { p: 'paddle', path: '/api/webhooks/paddle', hdr: 'Paddle-Signature' },
          { p: 'gumroad', path: '/api/webhooks/gumroad', hdr: 'X-Gumroad-Signature' },
          { p: 'stripe', path: '/api/webhooks/stripe', hdr: 'Stripe-Signature' },
        ].map((c) => (
          <div key={c.p} className="rounded-xl border border-border bg-card p-4" data-testid={`webhook-endpoint-card-${c.p}`}>
            <div className="flex items-center justify-between"><ProviderTag p={c.p} /><Webhook className="h-3.5 w-3.5 text-muted-foreground" /></div>
            <div className="mt-3 text-xs font-mono text-emerald-400 break-all">{c.path}</div>
            <div className="mt-1 text-[11px] text-muted-foreground">Header: <span className="font-mono">{c.hdr}</span></div>
          </div>
        ))}
      </div>

      <div className="mt-6 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? <div className="p-4 space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
          : items.length === 0 ? (
            <EmptyState icon={Webhook} title="No webhook events yet" description="Configure your store webhook to point at one of the URLs above." testid="webhooks-empty-state" />
          ) : (
            <table className="w-full text-sm" data-testid="webhook-events-table">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-4 py-3">Provider</th>
                  <th className="text-left font-medium px-4 py-3">Event</th>
                  <th className="text-left font-medium px-4 py-3">Status</th>
                  <th className="text-left font-medium px-4 py-3">Received</th>
                  <th className="text-left font-medium px-4 py-3">License</th>
                </tr>
              </thead>
              <tbody>
                {items.map((e) => (
                  <tr key={e.id} className="border-b border-border/60 hover:bg-muted/30 cursor-pointer" onClick={() => setActive(e)} data-testid={`webhook-event-row-${e.id}`}>
                    <td className="px-4 py-3"><ProviderTag p={e.provider} /></td>
                    <td className="px-4 py-3 font-mono text-xs">{e.event_type}</td>
                    <td className="px-4 py-3"><StatusPill status={e.status} testid="webhook-event-status-badge" /></td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{e.received_at?.replace('T', ' ').slice(0, 19)}</td>
                    <td className="px-4 py-3 font-mono text-[11px] text-muted-foreground">{e.license_id?.slice(0, 8) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>

      <Dialog open={!!active} onOpenChange={(v) => !v && setActive(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-auto" data-testid="webhook-payload-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2">Webhook payload {active && <ProviderTag p={active.provider} />}</DialogTitle></DialogHeader>
          {active && (
            <div className="space-y-3">
              <div className="text-xs text-muted-foreground">Event: <span className="font-mono">{active.event_type}</span> · status: <StatusPill status={active.status} /></div>
              <CodeBlock filename="raw payload" code={(() => { try { return JSON.stringify(JSON.parse(active.raw), null, 2); } catch { return active.raw; } })()} testid="webhook-payload-codeblock" />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
