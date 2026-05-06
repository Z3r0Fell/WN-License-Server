import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { Skeleton } from '../components/ui/skeleton';
import { EmptyState } from '../components/EmptyState';
import { FileBarChart2 } from 'lucide-react';

export default function AdminAudit() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    adminApi.get('/admin/audit').then((r) => setItems(r.data)).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
      <p className="text-sm text-muted-foreground mt-1">Every meaningful change, with actor and timestamp.</p>
      <div className="mt-6 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? <div className="p-4 space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}</div>
          : items.length === 0 ? (
            <EmptyState icon={FileBarChart2} title="No audit events yet" description="Actions performed by admins, customers, and integrators will appear here." testid="audit-empty-state" />
          ) : (
            <table className="w-full text-sm" data-testid="audit-table">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-4 py-3">When</th>
                  <th className="text-left font-medium px-4 py-3">Actor</th>
                  <th className="text-left font-medium px-4 py-3">Action</th>
                  <th className="text-left font-medium px-4 py-3">Target</th>
                  <th className="text-left font-medium px-4 py-3">Severity</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id} className="border-b border-border/60" data-testid={`audit-row-${a.id}`}>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{a.ts?.replace('T', ' ').slice(0, 19)}</td>
                    <td className="px-4 py-3 text-xs"><span className="font-mono">{a.actor_type}</span> {a.actor_email && <span className="text-muted-foreground">· {a.actor_email}</span>}</td>
                    <td className="px-4 py-3 font-mono text-xs">{a.action}</td>
                    <td className="px-4 py-3 font-mono text-[11px] text-muted-foreground">{a.target_type ? `${a.target_type}:${(a.target_id || '').slice(0, 8)}` : '—'}</td>
                    <td className="px-4 py-3 text-xs capitalize">{a.severity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  );
}
