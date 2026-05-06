import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

export const CodeBlock = ({ code, filename, language = 'bash', testid, className }) => {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      toast.success('Copied to clipboard');
      setTimeout(() => setCopied(false), 1400);
    } catch (e) {
      toast.error('Copy failed');
    }
  };
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-muted/30 overflow-hidden',
        className,
      )}
      data-testid={testid}
    >
      <div className="flex items-center justify-between px-4 py-2 bg-background/40 border-b border-border">
        <span className="font-mono text-xs text-muted-foreground">
          {filename || language}
        </span>
        <button
          type="button"
          onClick={onCopy}
          className="text-xs font-mono text-muted-foreground hover:text-emerald-500 transition-colors flex items-center gap-1.5"
          data-testid={testid ? `${testid}-copy` : undefined}
          aria-label="Copy code"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-[13px] leading-6 font-mono whitespace-pre">
{code}
      </pre>
    </div>
  );
};

export default CodeBlock;
