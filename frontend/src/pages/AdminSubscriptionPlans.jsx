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
import { Badge } from '../components/ui/badge';
import { Package, Plus, Pencil, Archive, DollarSign, ShieldCheck, Users } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminSubscriptionPlans() {
  const [items, setItems] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    name: '', slug: '', description: '', product_id: '',
    billing_options: [{ period: 'monthly', price: '', currency: 'USD' }],
    features: '', max_seats: 1, max_activations: '', grace_days: 7, trial_days: '',
  });

  const load = async () => {
    setLoading(true);
    try {
      const [a, p] = await Promise.all([
        adminApi.get('/admin/subscription-plans'),
        adminApi.get('/admin/products'),
      ]);
      setItems(a.data);
      setProducts(p.data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const resetForm = () => {
    setForm({
      name: '', slug: '', description: '', product_id: products[0]?.id || '',
      billing_options: [{ period: 'monthly', price: '', currency: 'USD' }],
      features: '', max_seats: 1, max_activations: '', grace_days: 7, trial_days: '',
    });
    setEditing(null);
  };

  const openEdit = (plan) => {
    setEditing(plan);
    setForm({
      name: plan.name,
      slug: plan.slug,
      description: plan.description || '',
      product_id: plan.product_id,
      billing_options: plan.billing_options || [{ period: 'monthly', price: '', currency: 'USD' }],
      features: (plan.features || []).join('\n'),
      max_seats: plan.max_seats,
      max_activations: plan.max_activations || '',
      grace_days: plan.grace_days,
      trial_days: plan.trial_days || '',
    });
    setOpen(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    const payload = {
      ...form,
      billing_options: form.billing_options.map((bo) => ({
        ...bo,
        price: parseFloat(bo.price) || 0,
      })),
      features: form.features.split('\n').map((s) => s.trim()).filter(Boolean),
      max_seats: Number(form.max_seats) || 1,
      max_activations: form.max_activations ? Number(form.max_activations) : null,
      grace_days: Number(form.grace_days) || 7,
      trial_days: form.trial_days ? Number(form.trial_days) : null,
    };
    try {
      if (editing) {
        await adminApi.put(`/admin/subscription-plans/${editing.id}`, payload);
        toast.success('Plan updated');
      } else {
        await adminApi.post('/admin/subscription-plans', payload);
        toast.success('Plan created');
      }
      setOpen(false);
      resetForm();
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed');
    }
  };

  const archive = async (id) => {
    if (!window.confirm('Archive this plan? Existing subscriptions continue but new ones cannot be created.')) return;
    try {
      await adminApi.delete(`/admin/subscription-plans/${id}`);
      toast.success('Plan archived');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Archive failed');
    }
  };

  const addBillingOption = () => {
    setForm((f) => ({
      ...f,
      billing_options: [...f.billing_options, { period: 'monthly', price: '', currency: 'USD' }],
    }));
  };

  const updateBillingOption = (i, field, value) => {
    const updated = [...form.billing_options];
    updated[i] = { ...updated[i], [field]: value };
    setForm({ ...form, billing_options: updated });
  };

  const removeBillingOption = (i) => {
    if (form.billing_options.length <= 1) return;
    setForm({ ...form, billing_options: form.billing_options.filter((_, idx) => idx !== i) });
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Subscription Plans</h1>
          <p className="text-sm text-muted-foreground mt-1">Define recurring billing tiers with multiple pricing options.</p>
        </div>
        <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) resetForm(); }}>
          <DialogTrigger asChild>
            <Button className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="sub-plans-create-button">
              <Plus className="h-4 w-4 mr-1.5" /> New plan
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader><DialogTitle>{editing ? 'Edit plan' : 'Create plan'}</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-4 mt-2 max-h-[70vh] overflow-y-auto pr-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Name</Label>
                  <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
                </div>
                <div>
                  <Label>Slug</Label>
                  <Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') })} required />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Product</Label>
                  <Select value={form.product_id} onValueChange={(v) => setForm({ ...form, product_id: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <Label>Max seats</Label>
                    <Input type="number" min="1" value={form.max_seats} onChange={(e) => setForm({ ...form, max_seats: e.target.value })} />
                  </div>
                  <div>
                    <Label>Max activations</Label>
                    <Input type="number" min="0" value={form.max_activations} onChange={(e) => setForm({ ...form, max_activations: e.target.value })} placeholder="Unlimited" />
                  </div>
                  <div>
                    <Label>Grace days</Label>
                    <Input type="number" min="0" value={form.grace_days} onChange={(e) => setForm({ ...form, grace_days: e.target.value })} />
                  </div>
                </div>
              </div>
              <div>
                <Label>Description</Label>
                <Textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <Label>Billing options</Label>
                  <Button type="button" variant="ghost" size="sm" onClick={addBillingOption}>
                    <Plus className="h-3 w-3 mr-1" /> Add option
                  </Button>
                </div>
                <div className="space-y-2">
                  {form.billing_options.map((bo, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <Select value={bo.period} onValueChange={(v) => updateBillingOption(i, 'period', v)}>
                        <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="monthly">Monthly</SelectItem>
                          <SelectItem value="yearly">Yearly</SelectItem>
                          <SelectItem value="quarterly">Quarterly</SelectItem>
                        </SelectContent>
                      </Select>
                      <div className="relative flex-1">
                        <DollarSign className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                        <Input type="number" step="0.01" min="0" value={bo.price} onChange={(e) => updateBillingOption(i, 'price', e.target.value)} className="pl-7" placeholder="9.99" />
                      </div>
                      <Select value={bo.currency} onValueChange={(v) => updateBillingOption(i, 'currency', v)}>
                        <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="USD">USD</SelectItem>
                          <SelectItem value="EUR">EUR</SelectItem>
                          <SelectItem value="GBP">GBP</SelectItem>
                          <SelectItem value="CAD">CAD</SelectItem>
                          <SelectItem value="AUD">AUD</SelectItem>
                        </SelectContent>
                      </Select>
                      {form.billing_options.length > 1 && (
                        <Button type="button" variant="ghost" size="icon" onClick={() => removeBillingOption(i)} className="shrink-0">
                          <span className="text-muted-foreground hover:text-destructive">&times;</span>
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <Label>Features (one per line)</Label>
                <Textarea rows={3} value={form.features} onChange={(e) => setForm({ ...form, features: e.target.value })} placeholder="unlimited_devices&#10;priority_support&#10;api_access" className="font-mono text-xs" />
              </div>
              <div>
                <Label>Trial days (optional)</Label>
                <Input type="number" min="0" value={form.trial_days} onChange={(e) => setForm({ ...form, trial_days: e.target.value })} placeholder="14" />
              </div>
              <DialogFooter>
                <Button variant="secondary" type="button" onClick={() => { setOpen(false); resetForm(); }}>Cancel</Button>
                <Button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white">
                  {editing ? 'Update' : 'Create'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="mt-6 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? (
          <div className="p-4 space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-lg" />)}</div>
        ) : items.length === 0 ? (
          <EmptyState icon={Package} title="No subscription plans yet"
            description="Create your first recurring billing plan."
            primaryLabel="New plan" onPrimary={() => setOpen(true)} testid="sub-plans-empty-state" />
        ) : (
          <table className="w-full text-sm" data-testid="sub-plans-table">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="text-left font-medium px-4 py-3">Name</th>
                <th className="text-left font-medium px-4 py-3">Pricing</th>
                <th className="text-left font-medium px-4 py-3">Product</th>
                <th className="text-left font-medium px-4 py-3">Seats</th>
                <th className="text-left font-medium px-4 py-3">Features</th>
                <th className="text-left font-medium px-4 py-3">Status</th>
                <th className="text-right font-medium px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} className="border-b border-border/60 hover:bg-muted/30" data-testid={`sub-plan-row-${p.slug}`}>
                  <td className="px-4 py-3">
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-muted-foreground font-mono">{p.slug}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="space-y-0.5">
                      {(p.billing_options || []).map((bo, i) => (
                        <div key={i} className="text-xs">
                          <span className="font-medium">${bo.price?.toFixed(2)}</span>
                          <span className="text-muted-foreground"> / {bo.period}</span>
                          <span className="text-muted-foreground ml-1">{bo.currency}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs font-mono">{p.product_slug}</td>
                  <td className="px-4 py-3 text-xs">{p.max_seats}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {(p.features || []).slice(0, 3).map((f) => (
                        <Badge key={f} variant="outline" className="text-[10px] font-mono">{f}</Badge>
                      ))}
                      {(p.features || []).length > 3 && (
                        <Badge variant="outline" className="text-[10px]">+{p.features.length - 3}</Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={p.status === 'active' ? 'default' : 'secondary'} className="text-[10px]">
                      {p.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right space-x-1">
                    <Button size="sm" variant="ghost" onClick={() => openEdit(p)} data-testid={`sub-plan-edit-${p.slug}`}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    {p.status === 'active' && (
                      <Button size="sm" variant="ghost" onClick={() => archive(p.id)} data-testid={`sub-plan-archive-${p.slug}`}>
                        <Archive className="h-3.5 w-3.5 text-muted-foreground" />
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