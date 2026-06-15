import { useEffect, useState } from 'react';
import { customerApi } from '../lib/api';
import { CopyChip } from '../components/CopyChip';
import { StatusPill } from '../components/StatusPill';
import { EmptyState } from '../components/EmptyState';
import { Skeleton } from '../components/ui/skeleton';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle } from '../components/ui/drawer';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { KeyRound, Ban, Cpu, Globe2, CreditCard, X } from 'lucide-react';
import { toast } from 'sonner';

const SUB_STATUS_COLORS = {
  active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  past_due: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  canceled: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
  expired: 'bg-red-500/10 text-red-400 border-red-500/30',
};

export default function PortalDashboard() {
  const [items, setItems] = useState([]);
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState(null);
  const [activeSub, setActiveSub] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [lic, sub] = await Promise.all([
        customerApi.get('/customer/licenses'),
        customerApi.get('/customer/subscriptions'),
      ]);
      setItems(lic.data);
      setSubs(sub.data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const openLic = async (id) => {
    try { setActive((await customerApi.get(`/customer/licenses/${id}`)).data); }
    catch (e) { toast.error('Could not load'); }
  };

  const openSub = async (id) => {
    try { setActiveSub((await customerApi.get(`/customer/subscriptions/${id}`)).data); }
    catch (e) { toast.error('Could not load'); }
  };

  const deactivate = async (lid, aid) => {
    if (!window.confirm('Deactivate this device?')) return;
    try {
      await customerApi.post(`/customer/licenses/${lid}/activations/${aid}/deactivate`);
      toast.success('Device deactivated');
      await openLic(lid);
      load();
    } catch (e) { toast.error('Failed'); }
  };

  const cancelSub = async (sid) => {
    if (!window.confirm('Cancel this subscription at the end of the billing period?')) return;
    try {
      const r = await customerApi.post(`/customer/subscriptions/${sid}/cancel`, { at_period_end: true });
      setActiveSub((d) => ({ ...d, subscription: r.data }));
      toast.success('Subscription will cancel at period end');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Cancel failed'); }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Your licenses</h1>
      <p className="text-sm text-muted-foreground mt-1">Click a license to manage devices.</p>
      {loading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
        </div>
      ) : items.length === 0 && subs.length === 0 ? (
        <div className="mt-6">
          <EmptyState icon={KeyRound} title="No licenses on this account" description="Buy WatchNexus, or contact support if you used a different email at checkout." testid="portal-licenses-empty-state" />
        </div>
      ) : (
        <>
          {subs.length > 0 && (
            <div className="mt-6">
              <h2 className="text-sm font-semibold text-muted-foreground mb-3 flex items-center gap-1.5">
                <CreditCard className="h-4 w-4" /> Subscriptions
              </h2>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6" data-testid="portal-subscriptions-grid">
                {subs.map((s) => (
                  <button key={s.id} onClick={() => openSub(s.id)}
                    className="text-left rounded-xl border border-border bg-card p-5 hover:border-emerald-500/30 hover:bg-card/80 transition-colors"
                    data-testid={`portal-sub-card-${s.id}`}>
                    <div className="flex items-center justify-between">
                      <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{s.plan_slug}</div>
                      <Badge variant="outline" className={`text-[10px] ${SUB_STATUS_COLORS[s.status] || ''}`}>
                        {s.status.replace('_', ' ')}
                      </Badge>
                    </div>
                    <div className="mt-3 text-sm">
                      <span className="font-semibold">${s.price?.toFixed(2)}</span>
                      <span className="text-muted-foreground"> / {s.billing_period}</span>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                      <div className="bg-muted/30 rounded-md p-2">
                        <div className="text-muted-foreground">Expires</div>
                        <div className="font-medium">{s.current_period_end?.slice(0, 10) || '—'}</div>
                      </div>
                      <div className="bg-muted/30 rounded-md p-2">
                        <div className="text-muted-foreground">Licenses</div>
                        <div className="font-medium">{s.licenses_count ?? 0}</div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          <h2 className="text-sm font-semibold text-muted-foreground mb-3 flex items-center gap-1.5">
            <KeyRound className="h-4 w-4" /> License keys
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="portal-licenses-grid">
            {items.map((l) => (
              <button key={l.id} onClick={() => openLic(l.id)} className="text-left rounded-xl border border-border bg-card p-5 hover:border-emerald-500/30 hover:bg-card/80 transition-colors" data-testid={`portal-license-card-${l.id}`}>
                <div className="flex items-center justify-between">
                  <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{l.product_slug}</div>
                  <StatusPill status={l.status} />
                </div>
                <div className="mt-3"><CopyChip value={l.key} label="License key" masked testid={`portal-license-key-${l.id}`} /></div>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-muted/30 rounded-md p-2"><div className="text-muted-foreground">Plan</div><div className="font-medium">{l.plan}</div></div>
                  <div className="bg-muted/30 rounded-md p-2"><div className="text-muted-foreground">Devices</div><div className="font-medium">{l.activations_count}/{l.seats}</div></div>
                </div>
              </button>
            ))}
          </div>
        </>
      )}

      <Dialog open={!!active} onOpenChange={(v) => !v && setActive(null)}>
        <DialogContent className="max-w-xl" data-testid="portal-license-dialog">
          <DialogHeader><DialogTitle>License detail</DialogTitle></DialogHeader>
          {active && (
            <div>
              <div className="flex items-center justify-between gap-2 mb-3">
                <CopyChip value={active.license.key} label="License key" testid="portal-license-detail-key" />
                <StatusPill status={active.license.status} />
              </div>
              <div className="text-xs text-muted-foreground mb-2">Devices ({active.activations.filter((a) => a.status === 'active').length} active / {active.license.seats})</div>
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {active.activations.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No devices yet.</p>
                ) : active.activations.map((a) => (
                  <div key={a.id} className="flex items-center justify-between rounded-lg border border-border bg-muted/10 p-3" data-testid={`portal-activation-row-${a.id}`}>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">{a.device_name}</div>
                      <div className="text-[11px] text-muted-foreground flex items-center gap-2">
                        {a.hardware_id && <span className="inline-flex items-center gap-1"><Cpu className="h-3 w-3" /> {a.hardware_id.slice(0, 18)}</span>}
                        {a.domain && <span className="inline-flex items-center gap-1"><Globe2 className="h-3 w-3" /> {a.domain}</span>}
                      </div>
                      <div className="text-[11px] text-muted-foreground">last seen {a.last_seen_at?.slice(0, 19).replace('T', ' ')}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusPill status={a.status} />
                      {a.status === 'active' && (
                        <Button size="sm" variant="destructive" onClick={() => deactivate(active.license.id, a.id)} data-testid={`portal-deactivate-${a.id}`}>
                          <Ban className="h-3.5 w-3.5 mr-1" /> Deactivate
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Drawer open={!!activeSub} onOpenChange={(v) => !v && setActiveSub(null)} direction="right">
        <DrawerContent className="max-w-[560px] ml-auto h-screen flex flex-col" data-testid="portal-sub-drawer">
          {activeSub && (
            <>
              <DrawerHeader className="border-b border-border">
                <DrawerTitle className="flex items-center justify-between">
                  <span>Subscription detail</span>
                  <Button variant="ghost" size="icon" onClick={() => setActiveSub(null)}><X className="h-4 w-4" /></Button>
                </DrawerTitle>
                <div className="mt-3 flex items-center justify-between">
                  <div className="text-sm font-medium">{activeSub.plan?.name || activeSub.subscription.plan_slug}</div>
                  <Badge variant="outline" className={`text-xs ${SUB_STATUS_COLORS[activeSub.subscription.status] || ''}`}>
                    {activeSub.subscription.status.replace('_', ' ')}
                  </Badge>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                  <div className="bg-muted/30 rounded-md p-2"><div className="text-muted-foreground">Price</div><div className="font-medium">${activeSub.subscription.price?.toFixed(2)} / {activeSub.subscription.billing_period}</div></div>
                  <div className="bg-muted/30 rounded-md p-2"><div className="text-muted-foreground">Period end</div><div className="font-medium">{activeSub.subscription.current_period_end?.slice(0, 10) || '—'}</div></div>
                  <div className="bg-muted/30 rounded-md p-2"><div className="text-muted-foreground">Auto-renew</div><div className="font-medium">{activeSub.subscription.auto_renew ? 'Yes' : 'No'}</div></div>
                </div>
              </DrawerHeader>
              <div className="flex-1 overflow-y-auto px-5 py-4">
                <h4 className="text-xs text-muted-foreground mb-2">Licenses ({activeSub.licenses?.length || 0})</h4>
                {(!activeSub.licenses || activeSub.licenses.length === 0) ? (
                  <p className="text-sm text-muted-foreground">No licenses yet.</p>
                ) : activeSub.licenses.map((l) => (
                  <div key={l.id} className="flex items-center justify-between rounded-lg border border-border bg-muted/10 p-3 mb-2">
                    <div className="min-w-0">
                      <div className="text-xs font-mono truncate">{l.key?.slice(0, 40)}…</div>
                      <div className="text-[11px] text-muted-foreground">{l.plan} · {l.activations_count ?? 0}/{l.seats} seats</div>
                    </div>
                    <StatusPill status={l.status} />
                  </div>
                ))}
                {activeSub.subscription.status === 'active' && (
                  <div className="mt-4">
                    <Button size="sm" variant="destructive" onClick={() => cancelSub(activeSub.subscription.id)}>
                      <Ban className="h-3.5 w-3.5 mr-1" /> Cancel at period end
                    </Button>
                  </div>
                )}
              </div>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </div>
  );
}
