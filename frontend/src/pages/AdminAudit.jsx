import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { EmptyState } from '../components/EmptyState';
import { FileBarChart2, Search, X, AlertOctagon, AlertTriangle, Info } from 'lucide-react';

const ACTOR_OPTIONS = [
  { value: 'all',        label: 'All actors' },
  { value: 'admin',      label: 'Admin' },
  { value: 'customer',   label: 'Customer' },
  { value: 'integrator', label: 'Integrator (API key)' },
  { value: 'webhook',    label: 'Webhook' },
  { value: 'system',     label: 'System' },
];

const ACTION_PRESETS = [
  { value: 'license',         label: 'license.*' },
  { value: 'activation',      label: 'activation.*' },
  { value: 'api_key',         label: 'api_key.*' },
  { value: 'product',         label: 'product.*' },
  { value: 'quickstart',      label: 'quickstart.*' },
  { value: 'admin.login',     label: 'admin.login' },
  { value: 'customer.login',  label: 'customer.login' },
  { value: 'email',           label: 'email.*' },
];

function SeverityIcon({ severity }) {
  if (severity === 'error')   return <AlertOctagon className="h-3.5 w-3.5 text-red-400" />;
  if (severity === 'warning') return <AlertTriangle className="h-3.5 w-3.5 text-amber-300" />;
  return <Info className="h-3.5 w-3.5 text-sky-300" />;
}

export default function AdminAudit() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actor, setActor] = useState('all');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => clearTimeout(id);
  }, [search]);

  const load = async () => {
    setLoading(true);
    try {
      const params = { limit: 300 };
      if (actor !== 'all') params.actor_type = actor;
      if (debouncedSearch) params.action = debouncedSearch;
      const r = await adminApi.get('/admin/audit', { params });
      setItems(r.data);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [actor, debouncedSearch]);

  const reset = () => { setActor('all'); setSearch(''); };

  const hasFilter = actor !== 'all' || !!debouncedSearch;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
          <p className="text-sm text-muted-foreground mt-1">Every meaningful change, with actor, target, and severity.</p>
        </div>
      </div>

      {/* Filters */}
      <div className="mt-6 flex items-center gap-2 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by action (e.g. license.revoke)"
            className="pl-8 w-72"
            data-testid="audit-search-input"
          />
        </div>
        <Select value={actor} onValueChange={setActor}>
          <SelectTrigger className="w-52" data-testid="audit-actor-select">
            <SelectValue placeholder="Actor" />
          </SelectTrigger>
          <SelectContent>
            {ACTOR_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value} data-testid={`audit-actor-option-${o.value}`}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {hasFilter && (
          <Button size="sm" variant="ghost" onClick={reset} data-testid="audit-filter-reset">
            <X className="h-3.5 w-3.5 mr-1" /> Clear
          </Button>
        )}
      </div>

      {/* Action chips */}
      <div className="mt-3 flex items-center gap-1.5 flex-wrap" data-testid="audit-action-presets">
        <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mr-1">Quick filters:</span>
        {ACTION_PRESETS.map((p) => {
          const active = debouncedSearch === p.value;
          return (
            <button
              key={p.value}
              type="button"
              onClick={() => setSearch(active ? '' : p.value)}
              className={`text-[11px] font-mono px-2 py-0.5 rounded-md border transition-colors ${
                active
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : 'border-border bg-muted/20 text-muted-foreground hover:text-foreground hover:border-emerald-500/30'
              }`}
              data-testid={`audit-preset-${p.value.replace(/[^a-z0-9]/gi, '_')}`}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      <div className="mt-4 rounded-xl border border-border bg-card overflow-hidden">
        {loading ? (
          <div className="p-4 space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}</div>
        ) : items.length === 0 ? (
          hasFilter ? (
            <EmptyState
              icon={Search}
              title="No matching events"
              description="Try a different filter or clear them."
              primaryLabel="Clear filters"
              onPrimary={reset}
              testid="audit-empty-state-filtered"
            />
          ) : (
            <EmptyState icon={FileBarChart2} title="No audit events yet" description="Actions performed by admins, customers, and integrators will appear here." testid="audit-empty-state" />
          )
        ) : (
          <table className="w-full text-sm" data-testid="audit-table">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b border-border">
                <th className="text-left font-medium px-4 py-3 w-44">When</th>
                <th className="text-left font-medium px-4 py-3">Actor</th>
                <th className="text-left font-medium px-4 py-3">Action</th>
                <th className="text-left font-medium px-4 py-3">Target</th>
                <th className="text-left font-medium px-4 py-3 w-28">Severity</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className="border-b border-border/60 hover:bg-muted/30" data-testid={`audit-row-${a.id}`}>
                  <td className="px-4 py-3 text-xs text-muted-foreground font-mono">{a.ts?.replace('T', ' ').slice(0, 19)}</td>
                  <td className="px-4 py-3 text-xs">
                    <span className="font-mono">{a.actor_type}</span>
                    {a.actor_email && <span className="text-muted-foreground"> · {a.actor_email}</span>}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{a.action}</td>
                  <td className="px-4 py-3 font-mono text-[11px] text-muted-foreground">
                    {a.target_type ? `${a.target_type}:${(a.target_id || '').slice(0, 8)}` : '—'}
                  </td>
                  <td className="px-4 py-3 text-xs capitalize flex items-center gap-1.5"><SeverityIcon severity={a.severity} /> {a.severity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="mt-3 text-[11px] text-muted-foreground">
        Showing {items.length} event{items.length === 1 ? '' : 's'}{hasFilter && ' (filtered)'}.
      </div>
    </div>
  );
}
