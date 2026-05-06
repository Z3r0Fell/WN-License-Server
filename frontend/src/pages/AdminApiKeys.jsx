import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { CopyChip } from '../components/CopyChip';
import { StatusPill } from '../components/StatusPill';
import { EmptyState } from '../components/EmptyState';
import { Skeleton } from '../components/ui/skeleton';
import { ShieldCheck, Plus, Ban, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminApiKeys() {
  const [items, setItems] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [productId, setProductId] = useState('any');
  const [revealed, setRevealed] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [a, p] = await Promise.all([
        adminApi.get('/admin/api-keys'),
        adminApi.get('/admin/products'),
      ]);
      setItems(a.data);
      setProducts(p.data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      const r = await adminApi.post('/admin/api-keys', {
        name,
        product_id: productId === 'any' ? null : productId,
      });
      setRevealed(r.data);
      setName('');
      setProductId('any');
      toast.success('API key created');
      load();
    } catch (e) { toast.error('Failed to create'); }
  };

  const revoke = async (id) => {
    if (!window.confirm('Revoke this API key? Clients using it will fail immediately.')) return;
    try {
      await adminApi.post(`/admin/api-keys/${id}/revoke`);
      toast.success('Revoked');
      load();
    } catch (e) { toast.error('Revoke failed'); }
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">API Keys</h1>
          <p className="text-sm text-muted-foreground mt-1">Server-to-server auth between your product and this license server.</p>
        </div>
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) setRevealed(null); }}>
          <DialogTrigger asChild>
            <Button className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="api-keys-create-button"><Plus className="h-4 w-4 mr-1.5" /> New API key</Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle>{revealed ? 'API key created' : 'New API key'}</DialogTitle></DialogHeader>
            {revealed ? (
              <div className="space-y-3">
                <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>Copy this key now. It will not be shown again.</span>
                </div>
                <CopyChip value={revealed.key} label="API key" testid="api-key-revealed-chip" className="w-full" />
                <DialogFooter>
                  <Button onClick={() => { setOpen(false); setRevealed(null); }} className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="api-key-revealed-done">Done</Button>
                </DialogFooter>
              </div>
            ) : (
              <form onSubmit={create} className="space-y-3">
                <div>
                  <Label>Name</Label>
                  <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="e.g. WatchNexus desktop client" data-testid="api-key-name-input" />
                </div>
                <div>
                  <Label>Scope (product)</Label>
                  <Select value={productId} onValueChange={setProductId}>
                    <SelectTrigger data-testid="api-key-product-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any product</SelectItem>
                      {products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <DialogFooter>
                  <Button variant="secondary" type="button" onClick={() => setOpen(false)}>Cancel</Button>
                  <Button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="api-key-create-submit-button">Create</Button>
                </DialogFooter>
              </form>
            )}
          </DialogContent>
        </Dialog>
      </div>

      <div className="mt-6 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? <div className="p-4 space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
          : items.length === 0 ? (
            <EmptyState icon={ShieldCheck} title="No API keys yet" description="Create one and configure your client to send X-API-Key on every /integrate call."
              primaryLabel="New API key" onPrimary={() => setOpen(true)} testid="api-keys-empty-state" />
          ) : (
            <table className="w-full text-sm" data-testid="api-keys-table">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-4 py-3">Name</th>
                  <th className="text-left font-medium px-4 py-3">Key</th>
                  <th className="text-left font-medium px-4 py-3">Scope</th>
                  <th className="text-left font-medium px-4 py-3">Last used</th>
                  <th className="text-left font-medium px-4 py-3">Status</th>
                  <th className="text-right font-medium px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((k) => (
                  <tr key={k.id} className="border-b border-border/60" data-testid={`api-key-row-${k.id}`}>
                    <td className="px-4 py-3 font-medium">{k.name}</td>
                    <td className="px-4 py-3 font-mono text-xs">{k.key_masked}</td>
                    <td className="px-4 py-3 text-xs">{k.product_id ? products.find((p) => p.id === k.product_id)?.name || k.product_id : 'Any product'}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{k.last_used_at ? k.last_used_at.replace('T', ' ').slice(0, 19) : 'never'}</td>
                    <td className="px-4 py-3"><StatusPill status={k.status === 'active' ? 'active' : 'revoked'} /></td>
                    <td className="px-4 py-3 text-right">
                      {k.status === 'active' && (
                        <Button size="sm" variant="destructive" onClick={() => revoke(k.id)} data-testid={`api-key-revoke-${k.id}`}>
                          <Ban className="h-3.5 w-3.5 mr-1" /> Revoke
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  );
}
