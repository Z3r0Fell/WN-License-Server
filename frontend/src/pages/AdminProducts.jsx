import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { EmptyState } from '../components/EmptyState';
import { Package, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { Skeleton } from '../components/ui/skeleton';

export default function AdminProducts() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: '', slug: '', signing_method: 'hmac', fingerprint_mode: 'both',
    max_seats_default: 1, description: '',
  });

  const load = async () => {
    setLoading(true);
    try {
      const r = await adminApi.get('/admin/products');
      setItems(r.data);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e?.preventDefault?.();
    try {
      await adminApi.post('/admin/products', { ...form, max_seats_default: Number(form.max_seats_default) || 1 });
      toast.success('Product created');
      setOpen(false);
      setForm({ name: '', slug: '', signing_method: 'hmac', fingerprint_mode: 'both', max_seats_default: 1, description: '' });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Products</h1>
          <p className="text-sm text-muted-foreground mt-1">Define signing method and fingerprinting per product.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="products-create-button">
              <Plus className="h-4 w-4 mr-1.5" /> New product
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle>Create product</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-3 mt-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Name</Label>
                  <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="product-create-name-input" />
                </div>
                <div>
                  <Label>Slug</Label>
                  <Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') })} required data-testid="product-create-slug-input" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Signing method</Label>
                  <Select value={form.signing_method} onValueChange={(v) => setForm({ ...form, signing_method: v })}>
                    <SelectTrigger data-testid="product-signing-method-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="hmac">HMAC-SHA256 (symmetric)</SelectItem>
                      <SelectItem value="rsa">RSA-PSS-SHA256 (offline verifiable)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Fingerprint mode</Label>
                  <Select value={form.fingerprint_mode} onValueChange={(v) => setForm({ ...form, fingerprint_mode: v })}>
                    <SelectTrigger data-testid="product-fingerprint-mode-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      <SelectItem value="hw">Hardware ID</SelectItem>
                      <SelectItem value="domain">Domain</SelectItem>
                      <SelectItem value="both">Both</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>Default seats</Label>
                <Input type="number" min="1" value={form.max_seats_default} onChange={(e) => setForm({ ...form, max_seats_default: e.target.value })} data-testid="product-create-seats-input" />
              </div>
              <div>
                <Label>Description</Label>
                <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} data-testid="product-create-desc-input" />
              </div>
              <DialogFooter>
                <Button variant="secondary" type="button" onClick={() => setOpen(false)}>Cancel</Button>
                <Button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="product-create-submit-button">Create</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="mt-6 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? (
          <div className="p-4 space-y-2">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={Package}
            title="No products yet"
            description="Create your first product to start issuing licenses."
            primaryLabel="New product"
            onPrimary={() => setOpen(true)}
            testid="products-empty-state"
          />
        ) : (
          <table className="w-full text-sm" data-testid="products-table">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="text-left font-medium px-4 py-3">Name</th>
                <th className="text-left font-medium px-4 py-3">Slug</th>
                <th className="text-left font-medium px-4 py-3">Signing</th>
                <th className="text-left font-medium px-4 py-3">Fingerprint</th>
                <th className="text-left font-medium px-4 py-3">Seats</th>
                <th className="text-left font-medium px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} className="border-b border-border/60 hover:bg-muted/30" data-testid={`product-row-${p.slug}`}>
                  <td className="px-4 py-3 font-medium">{p.name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{p.slug}</td>
                  <td className="px-4 py-3 uppercase text-xs">{p.signing_method}</td>
                  <td className="px-4 py-3 capitalize text-xs">{p.fingerprint_mode}</td>
                  <td className="px-4 py-3">{p.max_seats_default}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{p.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
