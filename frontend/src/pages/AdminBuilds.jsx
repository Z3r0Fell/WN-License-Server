import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { EmptyState } from '../components/EmptyState';
import { Skeleton } from '../components/ui/skeleton';
import { Download, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminBuilds() {
  const [items, setItems] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ product_id: '', version: '', download_url: '', notes: '' });

  const load = async () => {
    setLoading(true);
    try {
      const [b, p] = await Promise.all([
        adminApi.get('/admin/builds'),
        adminApi.get('/admin/products'),
      ]);
      setItems(b.data);
      setProducts(p.data);
      if (p.data[0] && !form.product_id) setForm((f) => ({ ...f, product_id: p.data[0].id }));
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await adminApi.post('/admin/builds', form);
      toast.success('Build added');
      setOpen(false);
      setForm({ product_id: products[0]?.id || '', version: '', download_url: '', notes: '' });
      load();
    } catch (e) { toast.error('Failed'); }
  };
  const del = async (id) => {
    if (!window.confirm('Delete this build?')) return;
    await adminApi.delete(`/admin/builds/${id}`);
    toast.success('Deleted');
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Builds</h1>
          <p className="text-sm text-muted-foreground mt-1">Versioned download URLs for each product. Customers see only their products’ builds.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="builds-create-button"><Plus className="h-4 w-4 mr-1.5" /> New build</Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle>New build</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-3">
              <div>
                <Label>Product</Label>
                <Select value={form.product_id} onValueChange={(v) => setForm({ ...form, product_id: v })}>
                  <SelectTrigger data-testid="build-create-product-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label>Version</Label><Input value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} required placeholder="1.4.2" data-testid="build-create-version-input" /></div>
              <div><Label>Download URL</Label><Input value={form.download_url} onChange={(e) => setForm({ ...form, download_url: e.target.value })} required placeholder="https://..." data-testid="build-create-url-input" /></div>
              <div><Label>Notes</Label><Textarea value={form.notes} rows={2} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="build-create-notes-input" /></div>
              <DialogFooter>
                <Button variant="secondary" type="button" onClick={() => setOpen(false)}>Cancel</Button>
                <Button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="build-create-submit-button">Create</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="mt-6 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? <div className="p-4 space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
          : items.length === 0 ? (
            <EmptyState icon={Download} title="No builds yet" description="Add a build URL so customers can download your software."
              primaryLabel="New build" onPrimary={() => setOpen(true)} testid="builds-empty-state" />
          ) : (
            <table className="w-full text-sm" data-testid="builds-table">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-4 py-3">Product</th>
                  <th className="text-left font-medium px-4 py-3">Version</th>
                  <th className="text-left font-medium px-4 py-3">URL</th>
                  <th className="text-left font-medium px-4 py-3">Created</th>
                  <th className="text-right font-medium px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((b) => (
                  <tr key={b.id} className="border-b border-border/60" data-testid={`build-row-${b.id}`}>
                    <td className="px-4 py-3 font-mono text-xs">{b.product_slug}</td>
                    <td className="px-4 py-3 font-medium">{b.version}</td>
                    <td className="px-4 py-3 truncate max-w-md">
                      <a href={b.download_url} target="_blank" rel="noreferrer" className="text-emerald-400 hover:underline text-xs font-mono break-all">{b.download_url}</a>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{b.created_at?.slice(0, 10)}</td>
                    <td className="px-4 py-3 text-right">
                      <Button size="sm" variant="ghost" onClick={() => del(b.id)} data-testid={`build-delete-${b.id}`}><Trash2 className="h-3.5 w-3.5" /></Button>
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
