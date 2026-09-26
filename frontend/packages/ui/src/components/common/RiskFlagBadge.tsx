import { cn } from '@pricepolicy/ui/lib/utils'
import type { RiskFlag } from '@pricepolicy/api-client/contracts'

const DOT_CLASS: Record<RiskFlag['color'], string> = {
  RED: 'bg-destructive',
  YELLOW: 'bg-warning',
  GREEN: 'bg-success',
}

const TEXT_CLASS: Record<RiskFlag['color'], string> = {
  RED: 'text-destructive',
  YELLOW: 'text-warning',
  GREEN: 'text-success',
}

export function RiskFlagBadge({ flag, className }: { flag: RiskFlag; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-sm font-medium', TEXT_CLASS[flag.color], className)}>
      <span className={cn('h-2.5 w-2.5 shrink-0 rounded-full', DOT_CLASS[flag.color])} />
      {flag.label}
    </span>
  )
}
