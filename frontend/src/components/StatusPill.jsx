import { cn } from '../lib/utils';

const MAP = {
  active: { label: 'Active', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' },
  revoked: { label: 'Revoked', cls: 'bg-red-500/15 text-red-400 border-red-500/20' },
  expired: { label: 'Expired', cls: 'bg-slate-500/20 text-slate-300 border-slate-500/20' },
  grace: { label: 'Grace', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/20' },
  pending: { label: 'Pending', cls: 'bg-sky-500/15 text-sky-300 border-sky-500/20' },
  deactivated: { label: 'Deactivated', cls: 'bg-slate-500/15 text-slate-300 border-slate-500/20' },
  processed: { label: 'Processed', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' },
  signature_invalid: { label: 'Signature Invalid', cls: 'bg-red-500/15 text-red-400 border-red-500/20' },
  parse_error: { label: 'Parse Error', cls: 'bg-red-500/15 text-red-400 border-red-500/20' },
  duplicate: { label: 'Duplicate', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/20' },
  online: { label: 'Online', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' },
};

export const StatusPill = ({ status, className, testid }) => {
  const m = MAP[status] || { label: status, cls: 'bg-muted text-muted-foreground border-border' };
  return (
    <span
      data-testid={testid || 'status-pill'}
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider',
        m.cls,
        className,
      )}
    >
      {m.label}
    </span>
  );
};

export default StatusPill;
