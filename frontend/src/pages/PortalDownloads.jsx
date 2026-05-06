import { useEffect, useState } from 'react';
import { customerApi } from '../lib/api';
import { Skeleton } from '../components/ui/skeleton';
import { EmptyState } from '../components/EmptyState';
import { Button } from '../components/ui/button';
import { Download } from 'lucide-react';

export default function PortalDownloads() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    customerApi.get('/customer/builds').then((r) => setItems(r.data)).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Downloads</h1>
      <p className="text-sm text-muted-foreground mt-1">Builds available to your active licenses.</p>
      {loading ? (
        <div className="mt-6 space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      ) : items.length === 0 ? (
        <div className="mt-6"><EmptyState icon={Download} title="No downloads available" description="Once your products have published builds, they will appear here." testid="portal-downloads-empty-state" /></div>
      ) : (
        <div className="mt-6 space-y-3" data-testid="portal-downloads-list">
          {items.map((b) => (
            <div key={b.id} className="rounded-xl border border-border bg-card p-4 flex items-center justify-between gap-4" data-testid={`portal-build-row-${b.id}`}>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{b.product_slug}</span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">v{b.version}</span>
                </div>
                {b.notes && <p className="text-xs text-muted-foreground mt-1 truncate">{b.notes}</p>}
              </div>
              <a href={b.download_url} target="_blank" rel="noreferrer">
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid={`portal-build-download-${b.id}`}>
                  <Download className="h-3.5 w-3.5 mr-1" /> Download
                </Button>
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
