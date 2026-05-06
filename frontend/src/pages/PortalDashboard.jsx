import { useEffect, useState } from 'react';
import { customerApi } from '../lib/api';
import { CopyChip } from '../components/CopyChip';
import { StatusPill } from '../components/StatusPill';
import { EmptyState } from '../components/EmptyState';
import { Skeleton } from '../components/ui/skeleton';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { KeyRound, Ban, Cpu, Globe2 } from 'lucide-react';
import { toast } from 'sonner';

export default function PortalDashboard() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState(null);

  const load = async () => {
    setLoading(true);
    try { setItems((await customerApi.get('/customer/licenses')).data); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const openLic = async (id) => {
    try { setActive((await customerApi.get(`/customer/licenses/${id}`)).data); }
    catch (e) { toast.error('Could not load'); }
  };

  const deactivate = async (lid, aid) => {
    if (!window.confirm('Deactivate this device? You can reactivate it later by running the app there again.')) return;
    try {
      await customerApi.post(`/customer/licenses/${lid}/activations/${aid}/deactivate`);
      toast.success('Device deactivated');
      await openLic(lid);
      load();
    } catch (e) { toast.error('Failed'); }
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Your licenses</h1>
      <p className="text-sm text-muted-foreground mt-1">Click a license to manage devices.</p>
      {loading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
        </div>
      ) : items.length === 0 ? (
        <div className="mt-6">
          <EmptyState icon={KeyRound} title="No licenses on this account" description="Buy WatchNexus, or contact support if you used a different email at checkout." testid="portal-licenses-empty-state" />
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-6" data-testid="portal-licenses-grid">
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
    </div>
  );
}
