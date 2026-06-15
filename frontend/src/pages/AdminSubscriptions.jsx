import { useEffect, useMemo, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerFooter } from '../components/ui/drawer';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Skeleton } from '../components/ui/skeleton';
import { StatusPill } from '../components/StatusPill';
import { EmptyState } from '../components/EmptyState';
import { Badge } from '../components/ui/badge';
import { RefreshCw, Search, Ban, RotateCcw, ArrowRight, Plus, X, CreditCard } from 'lucide-react';
import { toast } from 'sonner';

const PERIOD_LABELS = { monthly: 'Monthly', yearly: 'Yearly', quarterly: 'Quarterly' };

export default function AdminSubscriptions() {
  const [items, setItems] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [detail, setDetail] = useState(null);
  const [canceling, setCanceling] = useState(false);
  const [cancelAtPeriodEnd, setCancelAtPeriodEnd] = useState(true);
  const [cancelReason, setCancelReason] = useState('');
  const [changingPlan, setChangingPlan] = useState(false);
  const [changePlanId, setChangePlanId] = useState('');
  const [changePeriod, setChangePeriod] = useState('monthly');
  const [addingLicense, setAddingLicense] = useState(false);
  const [addLicenseSeats, setAddLicenseSeats] = useState(1);

  const load = async () => {
    setLoading(true);
    try {
      const [a, p] = await Promise.all([
        adminApi.get('/admin/subscriptions'),
        adminApi.get('/admin/subscription-plans'),
      ]);
      setItems(a.data);
      setPlans(p.data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    let out = items;
    if (q) out = out.filter((s) =>
      (s.customer_email || '').toLowerCase().includes(q.toLowerCase()) ||
      (s.plan_slug || '').toLowerCase().includes(q.toLowerCase()));
    if (statusFilter !== 'all') out = out.filter((s) => s.status === statusFilter);
    return out;
  }, [items, q, statusFilter]);

  const openDetail = async (id) => {
    try {
      const r = await adminApi.get(`/admin/subscriptions/${id}`);
      setDetail(r.data);
    } catch (e) { toast.error('Could not load'); }
  };

  const doCancel = async () => {
    if (!detail) return;
    try {
      const r = await adminApi.post(`/admin/subscriptions/${detail.subscription.id}/cancel`, {
        at_period_end: cancelAtPeriodEnd,
        reason: cancelReason || null,
      });
      setDetail((d) => ({ ...d, subscription: r.data }));
      setCanceling(false);
      toast.success(cancelAtPeriodEnd ? 'Will cancel at period end' : 'Canceled immediately');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Cancel failed'); }
  };

  const doReactivate = async () => {
    if (!detail) return;
    try {
      const r = await adminApi.post(`/admin/subscriptions/${detail.subscription.id}/reactivate`);
      setDetail((d) => ({ ...d, subscription: r.data }));
      toast.success('Subscription reactivated');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Reactivate failed'); }
  };

  const doChangePlan = async () => {
    if (!detail || !changePlanId) return;
    try {
      const r = await adminApi.post(`/admin/subscriptions/${detail.subscription.id}/change-plan`, {
        plan_id: changePlanId,
        billing_period: changePeriod,
      });
      setDetail((d) => ({ ...d, subscription: r.data }));
      setChangingPlan(false);
      toast.success('Plan changed');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Plan change failed'); }
  };

  const doAddLicense = async () => {
    if (!detail) return;
    try {
      const r = await adminApi.post(`/admin/subscriptions/${detail.subscription.id}/add-license`, {
        seats: addLicenseSeats,
      });
      setDetail((d) => ({ ...d, licenses: [...(d.licenses || []), r.data] }));
      setAddingLicense(false);
      toast.success('License added');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
  };

  const statusColor = (status) => {
    const map = { active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
      past_due: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
      canceled: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
      expired: 'bg-red-500/10 text-red-400 border-red-500/30',
      paused: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
    };
    return map[status] || 'bg-muted/30 text-muted-foreground border-border';
  };

  const selectedPlan = plans.find((p) => p.id === changePlanId);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Subscriptions</h1>
          <p className="text-sm text-muted-foreground mt-1">Recurring billing subscriptions alongside perpetual licenses.</p>
        </div>
        <Button variant="secondary" onClick={load} data-testid="subscriptions-refresh">
          <RefreshCw className="h-4 w-4 mr-1.5" /> Refresh
        </Button>
      </div>

      <div className="mt-6 flex items-center gap-2 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search email, plan" className="pl-8 w-64" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="past_due">Past due</SelectItem>
            <SelectItem value="canceled">Canceled</SelectItem>
            <SelectItem value="expired">Expired</SelectItem>
            <SelectItem value="paused">Paused</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="mt-4 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? (
          <div className="p-4 space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14 rounded-lg" />)}</div>
        ) : filtered.length === 0 ? (
          <EmptyState icon={CreditCard} title="No subscriptions yet"
            description="Subscriptions are created via webhook payments or you can create plans and issue them manually."
            testid="subscriptions-empty-state" />
        ) : (
          <table className="w-full text-sm" data-testid="subscriptions-table">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="text-left font-medium px-4 py-3">Customer</th>
                <th className="text-left font-medium px-4 py-3">Plan</th>
                <th className="text-left font-medium px-4 py-3">Billing</th>
                <th className="text-left font-medium px-4 py-3">Period</th>
                <th className="text-left font-medium px-4 py-3">Licenses</th>
                <th className="text-left font-medium px-4 py-3">Status</th>
                <th className="text-left font-medium px-4 py-3">Source</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id} className="border-b border-border/60 hover:bg-muted/30 cursor-pointer"
                    onClick={() => openDetail(s.id)} data-testid={`subscription-row-${s.id}`}>
                  <td className="px-4 py-3 text-xs">{s.customer_email || '—'}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-xs">{s.plan_slug}</div>
                    <div className="text-[11px] text-muted-foreground">${s.price?.toFixed(2)} / {s.billing_period}</div>
                  </td>
                  <td className="px-4 py-3 text-xs">{s.currency}</td>
                  <td className="px-4 py-3 text-xs">
                    <div>{s.current_period_start?.slice(0, 10)}</div>
                    <div className="text-muted-foreground">→ {s.current_period_end?.slice(0, 10)}</div>
                  </td>
                  <td className="px-4 py-3 text-xs">{s.licenses_count ?? '-'}</td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className={`text-[10px] ${statusColor(s.status)}`}>
                      {s.status.replace('_', ' ')}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-[11px] font-mono">{s.source || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Drawer open={!!detail} onOpenChange={(v) => !v && setDetail(null)} direction="right">
        <DrawerContent className="max-w-[600px] ml-auto h-screen flex flex-col" data-testid="subscription-detail-drawer">
          {detail && (
            <>
              <DrawerHeader className="border-b border-border">
                <DrawerTitle className="flex items-center justify-between">
                  <span>Subscription detail</span>
                  <Button variant="ghost" size="icon" onClick={() => setDetail(null)}><X className="h-4 w-4" /></Button>
                </DrawerTitle>
                <div className="mt-3 flex items-center justify-between gap-2 flex-wrap">
                  <div className="text-sm font-medium">{detail.subscription.customer_email || 'No customer'}</div>
                  <Badge variant="outline" className={`text-xs ${statusColor(detail.subscription.status)}`}>
                    {detail.subscription.status.replace('_', ' ')}
                  </Badge>
                </div>
                <div className="mt-2 grid grid-cols-4 gap-2 text-xs">
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Plan</div>
                    <div className="font-medium">{detail.subscription.plan_slug}</div>
                  </div>
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Price</div>
                    <div className="font-medium">${detail.subscription.price?.toFixed(2)}</div>
                  </div>
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Billing</div>
                    <div className="font-medium capitalize">{detail.subscription.billing_period}</div>
                  </div>
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Auto-renew</div>
                    <div className="font-medium">{detail.subscription.auto_renew ? 'Yes' : 'No'}</div>
                  </div>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Period start</div>
                    <div className="font-medium">{detail.subscription.current_period_start?.slice(0, 10) || '—'}</div>
                  </div>
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Period end</div>
                    <div className="font-medium">{detail.subscription.current_period_end?.slice(0, 10) || '—'}</div>
                  </div>
                </div>
                {detail.subscription.canceled_at && (
                  <div className="mt-2 flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-2 text-xs text-amber-200">
                    <Ban className="h-3.5 w-3.5 shrink-0" />
                    <span>
                      Canceled {detail.subscription.canceled_at?.slice(0, 10)}
                      {detail.subscription.canceled_at_period_end ? ' (at period end)' : ' (immediate)'}
                      {detail.subscription.cancellation_reason && ` — ${detail.subscription.cancellation_reason}`}
                    </span>
                  </div>
                )}
              </DrawerHeader>

              <div className="flex-1 overflow-y-auto px-5 py-4">
                <Tabs defaultValue="licenses">
                  <TabsList className="w-full">
                    <TabsTrigger value="licenses" className="flex-1">Licenses</TabsTrigger>
                    <TabsTrigger value="audit" className="flex-1">Audit</TabsTrigger>
                  </TabsList>
                  <TabsContent value="licenses" className="mt-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">{detail.licenses?.length || 0} license(s)</span>
                      <Button size="sm" variant="secondary" onClick={() => setAddingLicense(true)}>
                        <Plus className="h-3 w-3 mr-1" /> Add license
                      </Button>
                    </div>
                    {(!detail.licenses || detail.licenses.length === 0) ? (
                      <p className="text-sm text-muted-foreground">No licenses linked.</p>
                    ) : detail.licenses.map((l) => (
                      <div key={l.id} className="flex items-center justify-between rounded-lg border border-border bg-muted/10 p-3">
                        <div className="min-w-0">
                          <div className="text-xs font-mono truncate">{l.key?.slice(0, 40)}…</div>
                          <div className="text-[11px] text-muted-foreground">
                            {l.plan} · {l.activations_count ?? 0}/{l.seats} seats
                          </div>
                        </div>
                        <StatusPill status={l.status} />
                      </div>
                    ))}
                    {addingLicense && (
                      <div className="flex items-center gap-2 rounded-lg border border-border p-3">
                        <div className="flex-1">
                          <Label className="text-xs">Seats</Label>
                          <Input type="number" min="1" value={addLicenseSeats} onChange={(e) => setAddLicenseSeats(Number(e.target.value) || 1)} />
                        </div>
                        <Button size="sm" className="mt-5" onClick={doAddLicense}>Add</Button>
                        <Button size="sm" variant="secondary" className="mt-5" onClick={() => setAddingLicense(false)}>Cancel</Button>
                      </div>
                    )}
                  </TabsContent>
                  <TabsContent value="audit" className="mt-3 space-y-2">
                    {(!detail.audit || detail.audit.length === 0) ? (
                      <p className="text-sm text-muted-foreground">No audit entries.</p>
                    ) : detail.audit.map((a) => (
                      <div key={a.id} className="text-xs rounded-md bg-muted/20 p-2">
                        <div className="font-mono">{a.action}</div>
                        <div className="text-muted-foreground">{a.actor_email || a.actor_type} · {a.ts}</div>
                      </div>
                    ))}
                  </TabsContent>
                </Tabs>
              </div>

              <DrawerFooter className="border-t border-border flex-col gap-2">
                {canceling ? (
                  <div className="space-y-2 w-full">
                    <div className="flex items-center gap-2">
                      <input type="checkbox" id="cancel-at-end" checked={cancelAtPeriodEnd}
                        onChange={(e) => setCancelAtPeriodEnd(e.target.checked)}
                        className="rounded border-border" />
                      <label htmlFor="cancel-at-end" className="text-xs">Cancel at period end (leave active until then)</label>
                    </div>
                    <Input value={cancelReason} onChange={(e) => setCancelReason(e.target.value)}
                      placeholder="Cancellation reason (optional)" className="text-xs" />
                    <div className="flex gap-2">
                      <Button size="sm" onClick={doCancel} variant="destructive">Confirm cancel</Button>
                      <Button size="sm" variant="secondary" onClick={() => setCanceling(false)}>Back</Button>
                    </div>
                  </div>
                ) : changingPlan ? (
                  <div className="space-y-2 w-full">
                    <div>
                      <Label className="text-xs">New plan</Label>
                      <Select value={changePlanId} onValueChange={setChangePlanId}>
                        <SelectTrigger><SelectValue placeholder="Select plan" /></SelectTrigger>
                        <SelectContent>
                          {plans.filter((p) => p.status === 'active').map((p) => (
                            <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    {selectedPlan && (
                      <div>
                        <Label className="text-xs">Billing period</Label>
                        <Select value={changePeriod} onValueChange={setChangePeriod}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {(selectedPlan.billing_options || []).map((bo) => (
                              <SelectItem key={bo.period} value={bo.period}>
                                {PERIOD_LABELS[bo.period] || bo.period} (${bo.price?.toFixed(2)})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    <div className="flex gap-2">
                      <Button size="sm" onClick={doChangePlan} disabled={!changePlanId}>Change plan</Button>
                      <Button size="sm" variant="secondary" onClick={() => setChangingPlan(false)}>Cancel</Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-2 flex-wrap w-full">
                    {detail.subscription.status === 'active' && (
                      <Button size="sm" variant="destructive" onClick={() => setCanceling(true)}>
                        <Ban className="h-3.5 w-3.5 mr-1" /> Cancel
                      </Button>
                    )}
                    {detail.subscription.status === 'canceled' && detail.subscription.canceled_at_period_end && (
                      <Button size="sm" variant="secondary" onClick={doReactivate}>
                        <RotateCcw className="h-3.5 w-3.5 mr-1" /> Reactivate
                      </Button>
                    )}
                    {detail.subscription.status === 'active' && (
                      <Button size="sm" variant="secondary" onClick={() => setChangingPlan(true)}>
                        <ArrowRight className="h-3.5 w-3.5 mr-1" /> Change plan
                      </Button>
                    )}
                  </div>
                )}
              </DrawerFooter>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </div>
  );
}