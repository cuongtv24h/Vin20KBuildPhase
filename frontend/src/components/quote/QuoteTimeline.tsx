import { CheckCircle2, Eye, FilePlus2, FileEdit, MessageSquare, RefreshCw, Send, Share2, ShieldAlert, XCircle } from 'lucide-react'
import type { ComponentType } from 'react'
import { formatDateTime } from '@/lib/format'
import { QUOTE_EVENT_LABEL, ROLE_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { QuoteEvent, QuoteEventType } from '@/types/domain'

const EVENT_META: Record<QuoteEventType, { icon: ComponentType<{ className?: string }>; tone: string }> = {
  CREATED: { icon: FilePlus2, tone: 'bg-muted text-muted-foreground' },
  REVISED: { icon: RefreshCw, tone: 'bg-muted text-muted-foreground' },
  SUBMITTED: { icon: Send, tone: 'bg-primary/10 text-primary' },
  ESCALATED: { icon: ShieldAlert, tone: 'bg-destructive/10 text-destructive' },
  APPROVED: { icon: CheckCircle2, tone: 'bg-success/15 text-success' },
  REJECTED: { icon: XCircle, tone: 'bg-destructive/10 text-destructive' },
  REVISION_REQUESTED: { icon: FileEdit, tone: 'bg-warning/15 text-warning' },
  SHARED: { icon: Share2, tone: 'bg-gold/15 text-gold' },
  CUSTOMER_VIEWED: { icon: Eye, tone: 'bg-primary/10 text-primary' },
  CUSTOMER_RESPONDED: { icon: MessageSquare, tone: 'bg-success/15 text-success' },
}

function actorLabel(e: QuoteEvent): string {
  if (e.actorRole === 'CUSTOMER') return `${e.actorName} · Khách hàng`
  if (e.actorRole === 'SYSTEM') return e.actorName
  return `${e.actorName} · ${ROLE_LABEL[e.actorRole]}`
}

export function QuoteTimeline({ events }: { events: QuoteEvent[] }) {
  const ordered = [...events].reverse()
  return (
    <ol className="space-y-4">
      {ordered.map((e, idx) => {
        const meta = EVENT_META[e.type]
        return (
          <li key={e.eventId} className="relative flex gap-3" data-event={e.type}>
            {idx < ordered.length - 1 && <span className="absolute left-[13px] top-7 h-[calc(100%-4px)] w-px bg-border" aria-hidden />}
            <span className={cn('relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full', meta.tone)}>
              <meta.icon className="h-3.5 w-3.5" />
            </span>
            <div className="min-w-0 pb-1">
              <p className="text-sm font-medium leading-tight">
                {QUOTE_EVENT_LABEL[e.type]}
                <span className="ml-1.5 text-xs font-normal text-muted-foreground">v{e.version}</span>
              </p>
              <p className="text-xs text-muted-foreground">
                {actorLabel(e)} · {formatDateTime(e.at)}
              </p>
              {e.note && <p className="mt-1 rounded-md bg-muted/60 px-2.5 py-1.5 text-sm leading-relaxed">{e.note}</p>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
