import { Button } from './ui/button';
import { cn } from '../lib/utils';

export const EmptyState = ({
  icon: Icon,
  title,
  description,
  primaryLabel,
  onPrimary,
  secondaryLabel,
  onSecondary,
  testid,
  className,
}) => {
  return (
    <div
      data-testid={testid || 'empty-state'}
      className={cn(
        'flex flex-col items-center justify-center text-center',
        'rounded-xl border border-dashed border-border bg-muted/10',
        'px-6 py-16 gap-3',
        className,
      )}
    >
      {Icon ? (
        <div className="rounded-full bg-emerald-500/10 p-3 text-emerald-500">
          <Icon className="h-5 w-5" />
        </div>
      ) : null}
      <h3 className="text-base font-semibold tracking-tight">{title}</h3>
      {description ? (
        <p className="text-sm text-muted-foreground max-w-md">{description}</p>
      ) : null}
      {(primaryLabel || secondaryLabel) && (
        <div className="flex items-center gap-2 mt-2">
          {primaryLabel && (
            <Button
              size="sm"
              onClick={onPrimary}
              data-testid={testid ? `${testid}-primary` : undefined}
              className="bg-emerald-600 hover:bg-emerald-500 text-white"
            >
              {primaryLabel}
            </Button>
          )}
          {secondaryLabel && (
            <Button
              size="sm"
              variant="secondary"
              onClick={onSecondary}
              data-testid={testid ? `${testid}-secondary` : undefined}
            >
              {secondaryLabel}
            </Button>
          )}
        </div>
      )}
    </div>
  );
};

export default EmptyState;
