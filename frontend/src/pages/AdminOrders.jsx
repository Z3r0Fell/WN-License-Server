import { useEffect, useMemo, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerFooter } from '../components/ui/drawer';
import { Skeleton } from '../components/ui/skeleton';
import { EmptyState } from '../components/EmptyState';
import { Badge } from '../components/ui/badge';
import {
  RefreshCw, Search, ShoppingCart, CheckCircle2, XCircle, Send, Copy, Loader2,
} from 'lucide-react';
import { toast } from 'sonner';

const STATUS_META = {
  pending_payment: { label: 'Pending payment', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
  paid: { label: 'Paid', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  canceled: { label: 'Canceled', cls: 'bg-slate-500/10 text-slate-400 border-slate-500/30' },
};

export default function AdminOrders() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [detail, setDetail] = useState(null);
  const [actionBusy, setActionBusy] = useState('');
  const [notes, setNotes] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const r = await adminApi.get('/admin/orders');
      setItems(r.data);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Could not load orders'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    let out = items;
    if (q) out = out.filter((o) =>
      (o.reference || '').toLowerCase().includes(q.toLowerCase()) ||
      (o.email || '').toLowerCase().includes(q.toLowerCase()) ||
      (o.buyer_name || '').toLowerCase().includes(q.toLowerCase()));
    if (statusFilter !== 'all') out = out.filter((o) => o.status === statusFilter);
    return out;
  }, [items, q, statusFilter]);

  const refreshDetail = async () => {
    if (!detail) return;
    const r = await adminApi.get('/admin/orders');
    const fresh = r.data.find((o) => o.id === detail.id);
    if (fresh) setDetail(fresh);
    load();
  };

  const doMarkPaid = async () => {
    if (!detail) return;
    setActionBusy('mark-paid');
    try {
      const r = await adminApi.post(`/admin/orders/${detail.id}/mark-paid`, { notes: notes || null });
      setDetail(r.data);
      setNotes('');
      toast.success(`Serial ${r.data.license_key} issued to ${r.data.email}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Mark paid failed');
    } finally { setActionBusy(''); }
  };

  const doCancel = async () => {
    if (!detail) return;
    setActionBusy('cancel');
    try {
      await adminApi.post(`/admin/orders/${detail.id}/cancel`);
      toast.success('Order canceled');
      setDetail(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Cancel failed'); }
    finally { setActionBusy(''); }
  };

  const doResend = async () => {
    if (!detail) return;
    setActionBusy('resend');
    try {
      const r = await adminApi.post(`/admin/orders/${detail.id}/resend-email`);
      if (r.data.sent) toast.success('Serial email re-sent');
      else toast.warning('Email queued via log-only provider (no SMTP/SendGrid configured)');
    } catch (e) { toast.error(e?.response?.data?.detail || 'Resend failed'); }
    finally { setActionBusy(''); }
  };

  const copySerial = (key) => { navigator.clipboard?.writeText(key); toast.success('Serial copied'); };

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Orders</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Purchase-portal checkouts. Confirm payment to issue the serial and email it to the buyer.
          </p>
        </div>
        <Button variant="secondary" onClick={load} data-testid="orders-refresh">
          <RefreshCw className="h-4 w-4 mr-1.5" /> Refresh
        </Button>
      </div>

      <div className="mt-6 flex items-center gap-2 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search reference, email, name" className="pl-8 w-72" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending_payment">Pending payment</SelectItem>
            <SelectItem value="paid">Paid</SelectItem>
            <SelectItem value="canceled">Canceled</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="mt-4 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? (
          <div className="p-4 space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14 rounded-lg" />)}</div>
        ) : filtered.length === 0 ? (
          <EmptyState icon={ShoppingCart} title="No orders yet"
            description="Orders are created when buyers check out at /checkout. Confirm payment here to issue their serial."
            testid="orders-empty-state" />
        ) : (
          <table className="w-full text-sm" data-testid="orders-table">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="text-left font-medium px-4 py-3">Reference</th>
                <th className="text-left font-medium px-4 py-3">Buyer</th>
                <th className="text-left font-medium px-4 py-3">Plan</th>
                <th className="text-left font-medium px-4 py-3">Amount</th>
                <th className="text-left font-medium px-4 py-3">Created</th>
                <th className="text-left font-medium px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => (
                <tr key={o.id} className="border-b border-border/60 hover:bg-muted/30 cursor-pointer"
                    onClick={() => { setDetail(o); setNotes(''); }} data-testid={`order-row-${o.id}`}>
                  <td className="px-4 py-3 font-mono text-xs text-emerald-300">{o.reference}</td>
                  <td className="px-4 py-3 text-xs">
                    <div>{o.buyer_name || '—'}</div>
                    <div className="text-muted-foreground">{o.email}</div>
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <div className="font-medium">{o.plan_name}</div>
                    <div className="text-[11px] text-muted-foreground">{o.tier}</div>
                  </td>
                  <td className="px-4 py-3 text-xs">CAD ${o.price_cad?.toFixed(2)}</td>
                  <td className="px-4 py-3 text-xs">{o.created_at?.slice(0, 16).replace('T', ' ')}</td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className={`text-[10px] ${STATUS_META[o.status]?.cls || ''}`}>
                      {STATUS_META[o.status]?.label || o.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Drawer open={!!detail} onOpenChange={(v) => !v && setDetail(null)} direction="right">
        <DrawerContent className="max-w-[600px] ml-auto h-screen flex flex-col" data-testid="order-detail-drawer">
          {detail && (
            <>
              <DrawerHeader className="border-b border-border">
                <DrawerTitle className="flex items-center justify-between">
                  <span className="font-mono text-sm">{detail.reference}</span>
                  <Badge variant="outline" className={`text-xs ${STATUS_META[detail.status]?.cls || ''}`}>
                    {STATUS_META[detail.status]?.label || detail.status}
                  </Badge>
                </DrawerTitle>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Buyer</div>
                    <div className="font-medium">{detail.buyer_name || '—'}</div>
                    <div className="text-muted-foreground">{detail.email}</div>
                  </div>
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Plan / amount</div>
                    <div className="font-medium">{detail.plan_name} · CAD ${detail.price_cad?.toFixed(2)}</div>
                  </div>
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Created</div>
                    <div className="font-medium">{detail.created_at?.slice(0, 16).replace('T', ' ')}</div>
                  </div>
                  <div className="bg-muted/30 rounded-md p-2">
                    <div className="text-muted-foreground">Paid</div>
                    <div className="font-medium">{detail.paid_at ? detail.paid_at.slice(0, 16).replace('T', ' ') : '—'}</div>
                  </div>
                </div>
                {detail.status === 'paid' && (
                  <div className="mt-3 rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-3">
                    <div className="text-[11px] text-muted-foreground uppercase tracking-wider">Serial issued</div>
                    <div className="mt-1 flex items-center justify-between gap-2">
                      <code className="font-mono text-emerald-300 text-sm">{detail.license_key}</code>
                      <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => copySerial(detail.license_key)} aria-label="Copy serial">
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    {detail.fulfilled_by && (
                      <div className="mt-1 text-[11px] text-muted-foreground">Fulfilled by {detail.fulfilled_by} · {detail.fulfilled_at?.slice(0, 16).replace('T', ' ')}</div>
                    )}
                  </div>
                )}
                {detail.canceled_at && (
                  <div className="mt-3 flex items-center gap-2 rounded-lg border border-slate-500/20 bg-slate-500/5 p-2 text-xs text-slate-300">
                    <XCircle className="h-3.5 w-3.5 shrink-0" /> Canceled {detail.canceled_at?.slice(0, 16).replace('T', ' ')}
                  </div>
                )}
              </DrawerHeader>

              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                {detail.notes && (
                  <div>
                    <Label className="text-xs">Notes</Label>
                    <p className="mt-1 text-sm rounded-lg bg-muted/20 p-2">{detail.notes}</p>
                  </div>
                )}

                {detail.status === 'pending_payment' && (
                  <div>
                    <Label className="text-xs">Fulfillment notes <span className="text-muted-foreground font-normal">(optional)</span></Label>
                    <Input value={notes} onChange={(e) => setNotes(e.target.value)}
                      placeholder="e.g. paid via e-transfer reference ABC123" className="mt-1 text-xs" />
                  </div>
                )}

                {detail.status === 'paid' && (
                  <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/10 p-3 text-xs text-muted-foreground">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    Serial was emailed to {detail.email} when the order was marked paid. Buyer can also look it up at the checkout page with the reference.
                  </div>
                )}
              </div>

              <DrawerFooter className="border-t border-border flex-col gap-2">
                {detail.status === 'pending_payment' && (
                  <>
                    <Button className="w-full bg-emerald-600 hover:bg-emerald-500 text-white"
                      onClick={doMarkPaid} disabled={actionBusy === 'mark-paid'}
                      data-testid="order-mark-paid">
                      {actionBusy === 'mark-paid' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                      Confirm payment & issue serial
                    </Button>
                    <Button variant="outline" className="w-full" onClick={doCancel}
                      disabled={actionBusy === 'cancel'} data-testid="order-cancel">
                      {actionBusy === 'cancel' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                      Cancel order
                    </Button>
                  </>
                )}
                {detail.status === 'paid' && (
                  <Button variant="secondary" className="w-full" onClick={doResend}
                    disabled={actionBusy === 'resend'} data-testid="order-resend-email">
                    {actionBusy === 'resend' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    Re-send serial email
                  </Button>
                )}
                {detail.status === 'canceled' && (
                  <p className="text-center text-xs text-muted-foreground">This order was canceled. Create a new one if the buyer still wants a license.</p>
                )}
              </DrawerFooter>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </div>
  );
}
