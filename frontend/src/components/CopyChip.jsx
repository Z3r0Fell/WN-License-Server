import { useState } from 'react';
import { Copy, Check, Eye, EyeOff } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

export const CopyChip = ({ value, label, masked = false, testid, className }) => {
  const [revealed, setRevealed] = useState(!masked);
  const [copied, setCopied] = useState(false);

  const display = () => {
    if (!value) return '—';
    if (revealed) return value;
    if (value.length < 14) return '•'.repeat(value.length);
    return value.slice(0, 6) + '••••••••' + value.slice(-4);
  };

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      toast.success(`${label || 'Value'} copied`);
      setTimeout(() => setCopied(false), 1400);
    } catch (e) {
      toast.error('Copy failed');
    }
  };

  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-1.5',
        'font-mono text-xs tracking-[0.08em]',
        className,
      )}
      data-testid={testid}
    >
      <span className="truncate max-w-[280px]">{display()}</span>
      {masked && (
        <button
          type="button"
          aria-label={revealed ? 'Hide' : 'Reveal'}
          onClick={() => setRevealed((r) => !r)}
          className="text-muted-foreground hover:text-foreground transition-colors"
          data-testid={testid ? `${testid}-reveal` : undefined}
        >
          {revealed ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
      )}
      <button
        type="button"
        aria-label="Copy"
        onClick={onCopy}
        className="text-muted-foreground hover:text-emerald-500 transition-colors"
        data-testid={testid ? `${testid}-copy` : undefined}
      >
        {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
};

export default CopyChip;
