import { Timer } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

function useNow(intervalMs: number) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(t)
  }, [intervalMs])
  return now
}

const span = (ms: number) => {
  const minutes = Math.floor(Math.abs(ms) / 60_000)
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h > 0 ? `${h} giờ ${String(m).padStart(2, '0')} phút` : `${m} phút`
}

/** Đếm ngược SLA liên hệ khách (C-10). Dưới 30 phút chuyển vàng, quá hạn chuyển đỏ. */
export function SlaCountdown({ dueAt, className }: { dueAt: string; className?: string }) {
  const now = useNow(30_000)
  const left = Date.parse(dueAt) - now
  const tone = left < 0 ? 'text-destructive' : left < 30 * 60_000 ? 'text-warning' : 'text-muted-foreground'
  return (
    <span className={cn('inline-flex items-center gap-1 text-xs font-medium tabular-nums', tone, className)} data-sla={left < 0 ? 'overdue' : 'ok'}>
      <Timer className="h-3.5 w-3.5" />
      {left < 0 ? `Quá hạn ${span(left)}` : `Còn ${span(left)}`}
    </span>
  )
}
