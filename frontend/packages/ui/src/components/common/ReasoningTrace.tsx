import { useState } from 'react'
import { AlertTriangle, Brain, CheckCircle2, ChevronDown, ChevronRight, ListChecks, Link2, Loader2, ShieldAlert, Wrench } from 'lucide-react'
import type { CopilotCitation, CopilotReasoningStep } from '@pricepolicy/api-client/contracts'
import { cn } from '@pricepolicy/ui/lib/utils'

/**
 * Timeline tiến trình ReAct của Sales Copilot (Thought → Action → Observation).
 *
 * Hiển thị đúng những gì agent đã làm thay vì spinner giả:
 * - `thought`: agent đang nghĩ gì (có thể thu gọn).
 * - `action`: tool nào được gọi, tham số gì.
 * - `observation`: kết quả tool trả về + căn cứ (citation).
 *
 * A11y: `role="log"` + `aria-live="polite"` để screen-reader đọc tiến trình.
 */
export function ReasoningTrace({
  steps,
  streaming,
  degraded,
  error,
  onRetry,
  onOpenCitation,
  compact = false,
}: {
  steps: CopilotReasoningStep[]
  streaming?: boolean
  degraded?: boolean
  error?: string | null
  onRetry?: () => void
  onOpenCitation?: (citation: CopilotCitation) => void
  compact?: boolean
}) {
  const [collapsed, setCollapsed] = useState(false)
  if (!steps.length && !streaming && !error) return null

  const toolCalls = steps.filter((s) => s.type === 'action').length
  const observations = steps.filter((s) => s.type === 'observation')
  const failed = observations.some((s) => s.ok === false) || Boolean(error)

  return (
    <div
      role="log"
      aria-live="polite"
      aria-busy={streaming ? true : undefined}
      className="w-full max-w-[92%] rounded-xl border border-primary/20 bg-primary/[0.03] text-xs shadow-xs"
      data-testid="reasoning-trace"
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        aria-expanded={!collapsed}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        {streaming ? (
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" aria-hidden />
        ) : failed ? (
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warning" aria-hidden />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-success" aria-hidden />
        )}
        <span className={cn('font-semibold text-foreground', streaming && 'stream-caret')}>
          {streaming ? 'Trợ lý đang suy luận…' : failed ? 'Suy luận có bước lỗi' : 'Tiến trình suy luận'}
        </span>
        {toolCalls > 0 && (
          <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-xs font-medium text-primary">
            {toolCalls} tool
          </span>
        )}
        {degraded && (
          <span className="rounded-full bg-warning/15 px-1.5 py-0.5 text-xs font-medium text-warning-ink">
            chế độ tất định
          </span>
        )}
        <span className="ml-auto text-muted-foreground">
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </span>
      </button>

      {!collapsed && (
        <ol className="space-y-1.5 border-t border-primary/10 px-3 py-2">
          {steps
            .filter((s) => s.type === 'plan' || s.type === 'thought' || s.type === 'action' || s.type === 'observation')
            .map((step, idx) => (
              <TraceStep
                key={`${step.type}-${idx}`}
                step={step}
                isLast={idx === steps.length - 1 && Boolean(streaming)}
                onOpenCitation={onOpenCitation}
                compact={compact}
              />
            ))}
          {error && (
            <li className="flex items-start gap-2 rounded-md bg-destructive/5 px-2 py-1.5 text-destructive">
              <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="flex-1">{error}</span>
              {onRetry && (
                <button type="button" onClick={onRetry} className="font-semibold underline underline-offset-2">
                  Thử lại
                </button>
              )}
            </li>
          )}
        </ol>
      )}
    </div>
  )
}

function TraceStep({
  step,
  isLast,
  onOpenCitation,
  compact,
}: {
  step: CopilotReasoningStep
  isLast: boolean
  onOpenCitation?: (citation: CopilotCitation) => void
  compact?: boolean
}) {
  const [open, setOpen] = useState(!compact)

  if (step.type === 'plan') {
    const planSteps = step.steps ?? []
    if (!planSteps.length) return null
    return (
      <li className="flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/[0.03] px-2 py-1.5">
        <ListChecks className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <div className="font-medium text-foreground">Kế hoạch {planSteps.length} bước</div>
          <ol className="mt-0.5 space-y-0.5 text-xs text-muted-foreground">
            {planSteps.map((p, i) => (
              <li key={`${p.tool ?? p.intent}-${i}`}>
                {i + 1}. {p.reason || p.intent}
                {p.tool ? ` → ${p.tool}` : ''}
              </li>
            ))}
          </ol>
        </div>
      </li>
    )
  }

  if (step.type === 'thought') {
    return (
      <li className="flex items-start gap-2 text-muted-foreground">
        <Brain className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary/70" aria-hidden />
        <span className={isLast ? 'text-foreground' : ''}>
          {step.text}
          {isLast && <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-primary/60 align-middle" />}
        </span>
      </li>
    )
  }

  if (step.type === 'action') {
    return (
      <li className="flex items-start gap-2">
        <Wrench className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="font-medium text-foreground">Gọi công cụ</span>{' '}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs text-foreground">{step.tool}</code>
          {step.args && Object.keys(step.args).length > 0 && (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              className="ml-1 text-xs text-primary underline underline-offset-2"
            >
              {open ? 'ẩn tham số' : 'xem tham số'}
            </button>
          )}
          {open && step.args && Object.keys(step.args).length > 0 && (
            <pre className="mt-1 overflow-x-auto rounded-md bg-muted/60 p-1.5 font-mono text-xs text-muted-foreground">
              {JSON.stringify(step.args, null, 2)}
            </pre>
          )}
        </span>
      </li>
    )
  }

  return (
    <li className="flex items-start gap-2">
      {step.ok === false ? (
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" aria-hidden />
      ) : (
        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" aria-hidden />
      )}
      <span className="min-w-0 flex-1">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="text-left font-medium text-foreground hover:underline"
        >
          Kết quả <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">{step.tool}</code>
        </button>
        {open && (
          <span className="mt-0.5 block whitespace-pre-line text-muted-foreground">{step.summary || step.text}</span>
        )}
        {(step.citations?.length ?? 0) > 0 && (
          <span className="mt-1 flex flex-wrap gap-1">
            {step.citations!.slice(0, 3).map((citation, i) => (
              <button
                key={`${citation.policy_id}-${i}`}
                type="button"
                onClick={() => onOpenCitation?.(citation)}
                title={citation.quote || undefined}
                className="rounded-full border border-primary/25 bg-card px-2 py-0.5 text-xs text-primary hover:bg-primary/10"
              >
                {citation.policy_id}
                {citation.section ? ` · ${citation.section}` : ''}
              </button>
            ))}
          </span>
        )}
      </span>
    </li>
  )
}

/** Dải citation dưới câu trả lời cuối — bấm để mở hộp Căn cứ pháp lý. */
export function CitationChips({
  citations,
  onOpen,
}: {
  citations: CopilotCitation[]
  onOpen?: (citation: CopilotCitation) => void
}) {
  if (!citations.length) return null
  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-1">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Căn cứ</span>
      {citations.slice(0, 5).map((citation, i) => (
        <button
          key={`${citation.policy_id}-${i}`}
          type="button"
          onClick={() => onOpen?.(citation)}
          title={citation.quote || undefined}
          className="inline-flex max-w-[260px] items-center gap-1 truncate rounded-full border border-success/30 bg-success/5 px-2 py-0.5 text-xs font-medium text-success hover:bg-success/15"
        >
          <Link2 className="h-3 w-3 shrink-0" aria-hidden="true" /> {citation.policy_id}
          {citation.section ? ` · ${citation.section}` : ''}
        </button>
      ))}
    </div>
  )
}
