import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { Skeleton } from '../components/ui/skeleton';
import { EmptyState } from '../components/EmptyState';
import { Users } from 'lucide-react';

export default function AdminCustomers() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    adminApi.get('/admin/customers').then((r) => setItems(r.data)).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Customers</h1>
      <p className="text-sm text-muted-foreground mt-1">People who registered in the customer portal.</p>
      <div className="mt-6 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? <div className="p-4 space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}</div>
          : items.length === 0 ? (
            <EmptyState icon={Users} title="No customers yet" description="Customers register from the public portal at /portal/register." testid="customers-empty-state" />
          ) : (
            <table className="w-full text-sm" data-testid="customers-table">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-4 py-3">Email</th>
                  <th className="text-left font-medium px-4 py-3">Name</th>
                  <th className="text-left font-medium px-4 py-3">Licenses</th>
                  <th className="text-left font-medium px-4 py-3">Joined</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.id} className="border-b border-border/60" data-testid={`customer-row-${c.id}`}>
                    <td className="px-4 py-3 font-medium">{c.email}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.name}</td>
                    <td className="px-4 py-3">{c.licenses_count}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{c.created_at?.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  );
}
