import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminApi } from '../lib/api';
import { Skeleton } from '../components/ui/skeleton';
import { StatusPill } from '../components/StatusPill';
import { CopyChip } from '../components/CopyChip';
import { KeyRound, Activity, Users, Package, Webhook, FileBarChart2, Zap, ArrowRight } from 'lucide-react';

function StatCard({ icon: Icon, label, value, hint, testid }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5" data-testid={testid}>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5 text-emerald-400" /> {label}
      </div>
      <div className="mt-2 text-3xl font-semibold tracking-tight">{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  );
}

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    adminApi.get('/admin/dashboard')
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">A high-level look at your licensing health.</p>
        </div>
      </div>

      {/* Integration kit banner */}
      <Link
        to="/admin/quickstart"
        className="mt-6 group flex items-center justify-between gap-4 rounded-xl border border-emerald-500/20 bg-gradient-to-r from-emerald-500/10 via-emerald-500/5 to-transparent p-4 hover:border-emerald-500/40 transition-colors"
        data-testid="admin-dashboard-quickstart-banner"
      >
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
            <Zap className="h-5 w-5 text-emerald-400" />
          </div>
          <div>
            <div className="text-sm font-semibold">Tie WatchNexus into your app suite</div>
            <div className="text-xs text-muted-foreground">Bootstrap API key, demo license, copy-paste code, live test. Open the Quickstart.</div>
          </div>
        </div>
        <ArrowRight className="h-4 w-4 text-emerald-400 group-hover:translate-x-0.5 transition-transform" />
      </Link>

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <StatCard icon={KeyRound} label="Total licenses" value={data?.licenses_total ?? 0} testid="admin-stats-total-licenses" />
          <StatCard icon={Activity} label="Active installs" value={data?.active_installs ?? 0} testid="admin-stats-active-installs" />
          <StatCard icon={Users} label="Customers" value={data?.customers_total ?? 0} testid="admin-stats-customers" />
          <StatCard icon={Package} label="Products" value={data?.products_total ?? 0} testid="admin-stats-products" />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
        <div className="rounded-xl border border-border bg-card p-5" data-testid="admin-recent-activations-card">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Recent activations</h3>
            <Activity className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div className="mt-3 space-y-2">
            {!data || (data.recent_activations || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No activations yet.</p>
            ) : data.recent_activations.map((a) => (
              <div key={a.id} className="flex items-center justify-between text-sm">
                <div className="min-w-0">
                  <div className="truncate">{a.device_name || 'unknown'}</div>
                  <div className="text-xs text-muted-foreground font-mono truncate">{a.product_slug}</div>
                </div>
                <StatusPill status={a.status} />
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-5" data-testid="admin-recent-webhooks-card">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Recent webhook events</h3>
            <Webhook className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div className="mt-3 space-y-2">
            {!data || (data.recent_webhooks || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No webhook events received yet.</p>
            ) : data.recent_webhooks.map((w) => (
              <div key={w.id} className="flex items-center justify-between text-sm">
                <div className="min-w-0">
                  <div className="truncate font-mono text-xs">{w.provider} · {w.event_type}</div>
                  <div className="text-xs text-muted-foreground">{w.received_at}</div>
                </div>
                <StatusPill status={w.status} />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-5 mt-6" data-testid="admin-recent-audit-card">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Latest audit events</h3>
          <FileBarChart2 className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
        <div className="mt-3 divide-y divide-border">
          {!data || (data.recent_audit || []).length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">No audit events.</p>
          ) : data.recent_audit.map((a) => (
            <div key={a.id} className="flex items-center justify-between py-2 text-sm">
              <div className="min-w-0">
                <div className="font-mono text-xs">{a.action}</div>
                <div className="text-xs text-muted-foreground truncate">
                  {a.actor_email || a.actor_type} · {a.target_type || '—'}
                </div>
              </div>
              <span className="text-[11px] text-muted-foreground">{a.ts}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
