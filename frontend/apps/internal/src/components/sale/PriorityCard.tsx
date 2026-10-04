import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { cn } from '@pricepolicy/ui/lib/utils'

export type PriorityTone = 'danger' | 'warning' | 'info' | 'gold'

// Class đầy đủ (không ghép chuỗi) để Tailwind quét được. Tất cả đều là token màu.
const TONE: Record<PriorityTone, { card: string; icon: string }> = {
  danger: { card: 'border-destructive/30 bg-destructive/[0.06]', icon: 'bg-destructive/15 text-destructive' },
  warning: { card: 'border-warning/30 bg-warning/[0.06]', icon: 'bg-warning/15 text-warning' },
  info: { card: 'border-info/30 bg-info/[0.06]', icon: 'bg-info/15 text-info' },
  gold: { card: 'border-primary/30 bg-primary/[0.06]', icon: 'bg-primary/15 text-gold' },
}

interface PriorityCardProps {
  tone: PriorityTone
  icon: LucideIcon
  title: ReactNode
  description: ReactNode
  actionLabel: string
  onAction: () => void
  className?: string
}

/** Thẻ ưu tiên dùng chung ở màn hình chào: một mẫu duy nhất cho mọi loại việc cần làm. */
export function PriorityCard({ tone, icon: Icon, title, description, actionLabel, onAction, className }: PriorityCardProps) {
  const t = TONE[tone]
  return (
    <div className={cn('flex min-w-0 basis-full flex-col gap-3 rounded-2xl border p-4 text-left sm:basis-[calc(50%-0.375rem)]', t.card, className)}>
      <div className="flex min-w-0 items-start gap-3">
        <span className={cn('grid h-9 w-9 shrink-0 place-items-center rounded-lg', t.icon)}>
          <Icon className="h-[18px] w-[18px]" />
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="line-clamp-2 text-sm font-semibold leading-snug text-foreground">{title}</p>
          <div className="text-xs leading-relaxed text-muted-foreground">{description}</div>
        </div>
      </div>
      <Button type="button" size="sm" variant="outline" onClick={onAction} className="w-full justify-center">
        {actionLabel}
      </Button>
    </div>
  )
}
