import { useState, useRef } from 'react';
import { UploadCloud } from 'lucide-react';
import { Button } from './ui/button';
import { cn } from '../lib/utils';

export const CsvUpload = ({ onFile, accept = '.csv', testid, hint }) => {
  const ref = useRef(null);
  const [drag, setDrag] = useState(false);
  const [file, setFile] = useState(null);

  const handle = (f) => {
    if (!f) return;
    setFile(f);
    onFile?.(f);
  };
  return (
    <div
      className={cn(
        'rounded-xl border-2 border-dashed transition-colors p-8 text-center',
        drag ? 'border-emerald-500 bg-emerald-500/5' : 'border-border bg-muted/10',
      )}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        handle(e.dataTransfer.files?.[0]);
      }}
      data-testid={testid || 'csv-upload-zone'}
    >
      <div className="mx-auto h-10 w-10 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-3">
        <UploadCloud className="h-5 w-5" />
      </div>
      <div className="text-sm font-medium">
        {file ? file.name : 'Drop a CSV file here'}
      </div>
      <div className="text-xs text-muted-foreground mt-1">
        {hint || 'Columns: product_slug, customer_email, plan, seats, expires_at, notes'}
      </div>
      <div className="mt-4">
        <input
          ref={ref}
          type="file"
          accept={accept}
          className="hidden"
          data-testid={testid ? `${testid}-input` : 'csv-upload-input'}
          onChange={(e) => handle(e.target.files?.[0])}
        />
        <Button
          type="button"
          variant="secondary"
          onClick={() => ref.current?.click()}
          data-testid={testid ? `${testid}-pick` : 'csv-upload-pick'}
        >
          Choose file
        </Button>
      </div>
    </div>
  );
};

export default CsvUpload;
