import { useEffect, useMemo, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerFooter } from '../components/ui/drawer';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Skeleton } from '../components/ui/skeleton';
import { CopyChip } from '../components/CopyChip';
import { StatusPill } from '../components/StatusPill';
import { EmptyState } from '../components/EmptyState';
import { CsvUpload } from '../components/CsvUpload';
import { KeyRound, Plus, Search, FileUp, Ban, CalendarRange, X } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminLicenses() {
  const [items, setItems] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [productFilter, setProductFilter] = useState('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [detail, setDetail] = useState(null);
  const [extending, setExtending] = useState(false);
  const [extendValue, setExtendValue] = useState('');

  const [form, setForm] = useState({ product_id: '', customer_email: '', plan: 'standard', seats: 1, expires_at: '', notes: '' });

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (q) params.q = q;
      if (statusFilter !== 'all') params.status = statusFilter;
      if (productFilter !== 'all') params.product_id = productFilter;
      const r = await adminApi.get('/admin/licenses', { params });
      setItems(r.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    adminApi.get('/admin/products').then((r) => {
      setProducts(r.data);
      if (r.data[0]) setForm((f) => ({ ...f, product_id: f.product_id || r.data[0].id }));
    });
  }, []);
  useEffect(() => { load(); }, [q, statusFilter, productFilter]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await adminApi.post('/admin/licenses', { ...form, seats: Number(form.seats) || 1, expires_at: form.expires_at || null });
      toast.success('License created');
      setCreateOpen(false);
      setForm({ product_id: products[0]?.id || '', customer_email: '', plan: 'standard', seats: 1, expires_at: '', notes: '' });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed');
    }
  };

  const openDetail = async (id) => {
    try {
      const r = await adminApi.get(`/admin/licenses/${id}`);
      setDetail(r.data);
    } catch (e) {
      toast.error('Could not load detail');
    }
  };

  const revoke = async () => {
    if (!detail) return;
    if (!window.confirm('Revoke this license? All active installs will be deactivated.')) return;
    try {
      await adminApi.post(`/admin/licenses/${detail.license.id}/revoke`);
      toast.success('License revoked');
      await openDetail(detail.license.id);
      load();
    } catch (e) { toast.error('Revoke failed'); }
  };

  const extend = async () => {
    if (!detail || !extendValue) return;
    try {
      const iso = new Date(extendValue).toISOString();
      await adminApi.post(`/admin/licenses/${detail.license.id}/extend`, { expires_at: iso });
      toast.success('License extended');
      setExtending(false);
      setExtendValue('');
      await openDetail(detail.license.id);
      load();
    } catch (e) { toast.error('Extend failed'); }
  };

  const deactivate = async (aid) => {
    if (!detail) return;
    if (!window.confirm('Deactivate this install?')) return;
    try {
      await adminApi.post(`/admin/licenses/${detail.license.id}/activations/${aid}/deactivate`);
      toast.success('Install deactivated');
      await openDetail(detail.license.id);
      load();
    } catch (e) { toast.error('Deactivate failed'); }
  };

  const doImport = async () => {
    if (!importFile) return;
    try {
      const fd = new FormData();
      fd.append('file', importFile);
      const r = await adminApi.post('/admin/licenses/bulk-import', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setImportResult(r.data);
      toast.success(`Imported ${r.data.created} (failed ${r.data.failed})`);
      load();
    } catch (e) {
      toast.error('Import failed');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Licenses</h1>
          <p className="text-sm text-muted-foreground mt-1">Issue, revoke, extend, and inspect installs.</p>
        </div>
        <div className="flex items-center gap-2">
          <Dialog open={importOpen} onOpenChange={(v) => { setImportOpen(v); if (!v) { setImportFile(null); setImportResult(null); } }}>
            <DialogTrigger asChild>
              <Button variant="secondary" data-testid="licenses-bulk-import-button"><FileUp className="h-4 w-4 mr-1.5" /> Bulk import</Button>
            </DialogTrigger>
            <DialogContent className="max-w-xl">
              <DialogHeader><DialogTitle>Bulk import licenses (CSV)</DialogTitle></DialogHeader>
              <p className="text-sm text-muted-foreground">
                CSV header: <code className="font-mono">product_slug,customer_email,plan,seats,expires_at,notes</code>
              </p>
              <CsvUpload onFile={setImportFile} testid="licenses-csv-upload" />
              {importResult && (
                <div className="mt-3 max-h-64 overflow-auto rounded-lg border border-border bg-muted/20 p-3 text-xs font-mono">
                  <div>created: {importResult.created} · failed: {importResult.failed}</div>
                  {importResult.results.slice(0, 100).map((r, i) => (
                    <div key={i} className={r.ok ? 'text-emerald-400' : 'text-red-400'}>
                      row {r.row}: {r.ok ? r.key : r.error}
                    </div>
                  ))}
                </div>
              )}
              <DialogFooter>
                <Button variant="secondary" onClick={() => setImportOpen(false)}>Close</Button>
                <Button onClick={doImport} disabled={!importFile} className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="licenses-csv-import-confirm">
                  Import
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="licenses-create-button">
                <Plus className="h-4 w-4 mr-1.5" /> New license
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader><DialogTitle>Create license</DialogTitle></DialogHeader>
              <form onSubmit={submit} className="space-y-3 mt-2">
                <div>
                  <Label>Product</Label>
                  <Select value={form.product_id} onValueChange={(v) => setForm({ ...form, product_id: v })}>
                    <SelectTrigger data-testid="license-create-product-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Customer email</Label>
                    <Input type="email" value={form.customer_email} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} placeholder="buyer@example.com" data-testid="license-create-email-input" />
                  </div>
                  <div>
                    <Label>Plan</Label>
                    <Input value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value })} data-testid="license-create-plan-input" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Seats</Label>
                    <Input type="number" min="1" value={form.seats} onChange={(e) => setForm({ ...form, seats: e.target.value })} data-testid="license-create-seats-input" />
                  </div>
                  <div>
                    <Label>Expires at (ISO)</Label>
                    <Input type="datetime-local" value={form.expires_at} onChange={(e) => setForm({ ...form, expires_at: e.target.value })} data-testid="license-create-expires-input" />
                  </div>
                </div>
                <div>
                  <Label>Notes</Label>
                  <Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="license-create-notes-input" />
                </div>
                <DialogFooter>
                  <Button variant="secondary" type="button" onClick={() => setCreateOpen(false)}>Cancel</Button>
                  <Button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="license-create-submit-button">Create</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* filters */}
      <div className="mt-6 flex items-center gap-2 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search key, email, plan" className="pl-8 w-64" data-testid="licenses-filter-search-input" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40" data-testid="licenses-filter-status-select"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="revoked">Revoked</SelectItem>
            <SelectItem value="expired">Expired</SelectItem>
          </SelectContent>
        </Select>
        <Select value={productFilter} onValueChange={setProductFilter}>
          <SelectTrigger className="w-48" data-testid="licenses-filter-product-select"><SelectValue placeholder="Product" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All products</SelectItem>
            {products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="mt-4 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? (
          <div className="p-4 space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={KeyRound}
            title="No licenses yet"
            description="Create your first license or import a reseller batch."
            primaryLabel="New license"
            onPrimary={() => setCreateOpen(true)}
            secondaryLabel="Bulk import"
            onSecondary={() => setImportOpen(true)}
            testid="licenses-empty-state"
          />
        ) : (
          <table className="w-full text-sm" data-testid="licenses-table">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="text-left font-medium px-4 py-3">Key</th>
                <th className="text-left font-medium px-4 py-3">Customer</th>
                <th className="text-left font-medium px-4 py-3">Product</th>
                <th className="text-left font-medium px-4 py-3">Status</th>
                <th className="text-left font-medium px-4 py-3">Installs</th>
                <th className="text-left font-medium px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {items.map((l) => (
                <tr key={l.id}
                    className="border-b border-border/60 hover:bg-muted/30 cursor-pointer"
                    onClick={() => openDetail(l.id)}
                    data-testid={`license-row-${l.id}`}>
                  <td className="px-4 py-3">
                    <div onClick={(e) => e.stopPropagation()} className="inline-block">
                      <CopyChip value={l.key} label="License key" masked testid={`license-key-copy-chip-${l.id}`} />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs">{l.customer_email || '—'}</td>
                  <td className="px-4 py-3 text-xs font-mono">{l.product_slug}</td>
                  <td className="px-4 py-3"><StatusPill status={l.status} /></td>
                  <td className="px-4 py-3 text-xs">{l.activations_count}/{l.seats}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{l.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail drawer */}
      <Drawer open={!!detail} onOpenChange={(v) => !v && setDetail(null)} direction="right">
        <DrawerContent className="max-w-[560px] ml-auto h-screen flex flex-col" data-testid="license-detail-drawer">
          {detail && (
            <>
              <DrawerHeader className="border-b border-border">
                <DrawerTitle className="flex items-center justify-between">
                  <span>License detail</span>
                  <Button variant="ghost" size="icon" onClick={() => setDetail(null)} data-testid="license-detail-close"><X className="h-4 w-4" /></Button>
                </DrawerTitle>
                <div className="mt-3 flex items-center justify-between gap-2 flex-wrap">
                  <CopyChip value={detail.license.key} label="License key" testid="license-detail-key-chip" />
                  <StatusPill status={detail.license.status} testid="license-detail-status-pill" />
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                  <div className="bg-muted/30 rounded-md p-2"><div className="text-muted-foreground">Plan</div><div className="font-medium">{detail.license.plan}</div></div>
                  <div className="bg-muted/30 rounded-md p-2"><div className="text-muted-foreground">Seats</div><div className="font-medium">{detail.license.seats}</div></div>
                  <div className="bg-muted/30 rounded-md p-2"><div className="text-muted-foreground">Active</div><div className="font-medium">{detail.activations.filter((a) => a.status === 'active').length}</div></div>
                </div>
              </DrawerHeader>
              <div className="flex-1 overflow-y-auto px-5 py-4">
                <Tabs defaultValue="activations">
                  <TabsList className="w-full">
                    <TabsTrigger value="activations" className="flex-1" data-testid="license-detail-tab-activations">Activations</TabsTrigger>
                    <TabsTrigger value="audit" className="flex-1" data-testid="license-detail-tab-audit">Audit</TabsTrigger>
                  </TabsList>
                  <TabsContent value="activations" className="mt-3 space-y-2">
                    {detail.activations.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No activations yet.</p>
                    ) : detail.activations.map((a) => (
                      <div key={a.id} className="flex items-center justify-between rounded-lg border border-border bg-muted/10 p-3" data-testid={`activation-row-${a.id}`}>
                        <div className="min-w-0">
                          <div className="text-sm font-medium truncate">{a.device_name}</div>
                          <div className="text-[11px] text-muted-foreground font-mono truncate">fp:{a.fingerprint?.slice(0, 16)}…</div>
                          <div className="text-[11px] text-muted-foreground">last seen {a.last_seen_at?.slice(0, 19).replace('T', ' ')}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <StatusPill status={a.status} />
                          {a.status === 'active' && (
                            <Button size="sm" variant="destructive" onClick={() => deactivate(a.id)} data-testid={`activation-deactivate-${a.id}`}>
                              <Ban className="h-3.5 w-3.5 mr-1" /> Deactivate
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </TabsContent>
                  <TabsContent value="audit" className="mt-3 space-y-2">
                    {detail.audit.length === 0 ? (
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
              <DrawerFooter className="border-t border-border flex-row gap-2 justify-end">
                {extending ? (
                  <div className="flex items-center gap-2 w-full">
                    <Input type="datetime-local" value={extendValue} onChange={(e) => setExtendValue(e.target.value)} data-testid="license-extend-date-input" />
                    <Button onClick={extend} className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="license-extend-confirm-button">Save</Button>
                    <Button variant="secondary" onClick={() => setExtending(false)}>Cancel</Button>
                  </div>
                ) : (
                  <>
                    <Button variant="secondary" onClick={() => setExtending(true)} data-testid="license-detail-extend-button"><CalendarRange className="h-3.5 w-3.5 mr-1" /> Extend</Button>
                    <Button variant="destructive" onClick={revoke} disabled={detail.license.status === 'revoked'} data-testid="license-detail-revoke-button"><Ban className="h-3.5 w-3.5 mr-1" /> Revoke</Button>
                  </>
                )}
              </DrawerFooter>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </div>
  );
}
