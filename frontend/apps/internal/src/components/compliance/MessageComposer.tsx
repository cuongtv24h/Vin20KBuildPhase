import { CheckCircle2, Loader2, Send, Sparkles, WandSparkles } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { ComplianceCheckMode, ComplianceClaim, ComplianceStatus, MessageChannel, MessageSendResult, Quote } from '@pricepolicy/api-client/contracts'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useComplianceCheck, useDraftMessage, useSendMessage } from '@pricepolicy/api-client/hooks'
import { ComplianceBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { Textarea } from '@pricepolicy/ui/components/ui/textarea'
import { formatDateTime } from '@pricepolicy/ui/lib/format'
import { CHANNEL_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'
import { toast } from '@pricepolicy/ui/state/toastStore'

const MARK: Record<ComplianceStatus, string> = {
  SUPPORTED: 'bg-success/15 decoration-success',
  CONDITIONAL: 'bg-warning/20 decoration-warning',
  UNSUPPORTED: 'bg-destructive/10 decoration-destructive',
  PROHIBITED: 'bg-destructive/20 decoration-destructive font-semibold',
}

function Highlighted({ text, claims, active, onPick }: { text: string; claims: ComplianceClaim[]; active: string | null; onPick: (id: string) => void }) {
  const parts: ReactNode[] = []
  let cursor = 0
  for (const c of claims) {
    if (c.span_start < cursor) continue
    parts.push(text.slice(cursor, c.span_start))
    parts.push(
      <mark
        key={c.claim_id}
        onClick={() => onPick(c.claim_id)}
        className={cn('cursor-pointer rounded-sm px-0.5 text-foreground underline decoration-2 underline-offset-4', MARK[c.status], active === c.claim_id && 'ring-2 ring-primary/40')}
        data-compliance={c.status}
      >
        {text.slice(c.span_start, c.span_end)}
      </mark>,
    )
    cursor = c.span_end
  }
  parts.push(text.slice(cursor))
  return <p className="whitespace-pre-wrap text-sm leading-7">{parts}</p>
}

/** Sales Message Composer (F8 / ADR-019): tin Agent soạn và tin Sale sửa đều phải qua cùng một cổng. */
export function MessageComposer({ quote }: { quote: Quote }) {
  const [text, setText] = useState('')
  const [mode, setMode] = useState<ComplianceCheckMode>('ON_DRAFT')
  const [channel, setChannel] = useState<MessageChannel>('ZALO')
  const [active, setActive] = useState<string | null>(null)
  const [sent, setSent] = useState<MessageSendResult | null>(null)
  const check = useComplianceCheck(text, quote, mode)
  const draft = useDraftMessage()
  const send = useSendMessage()

  const result = check.stale ? null : check.result
  const blocked = result?.overall_status === 'PROHIBITED'
  const canSend = Boolean(result) && !check.checking && !blocked && text.trim().length > 0 && !send.isPending

  async function generate() {
    try {
      const d = await draft.mutateAsync({ quote_id: quote.quote_id, quote_version: quote.quote_version })
      setMode('ON_DRAFT')
      setText(d.message_text)
      setSent(null)
    } catch (e) {
      toast.error('Không tạo được tin đề xuất', errorMessage(e))
    }
  }

  function applyRewrite(c: ComplianceClaim) {
    if (!c.suggested_rewrite) return
    setMode('DEBOUNCE')
    setText(text.slice(0, c.span_start) + c.suggested_rewrite + text.slice(c.span_end))
  }

  async function handleSend() {
    if (!result) return
    try {
      const r = await send.mutateAsync({ quote, text, check: result, channel })
      setSent(r)
      setText('')
      toast.success(`Đã gửi qua ${CHANNEL_LABEL[channel]}`, quote.transaction_context.customer_name)
    } catch (e) {
      toast.error('Tin nhắn không được gửi', errorMessage(e))
    }
  }

  return (
    <Card data-testid="composer">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-sm">Tin nhắn gửi khách</CardTitle>
        <Button variant="outline" size="sm" onClick={generate} disabled={draft.isPending}>
          {draft.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Tạo tin đề xuất
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {sent && (
          <p className="flex items-center gap-2 rounded-md bg-success/10 px-3 py-2 text-sm text-success" data-testid="sent-receipt">
            <CheckCircle2 className="h-4 w-4" /> Đã gửi {sent.message_id} lúc {sent.sent_at ? formatDateTime(sent.sent_at) : ''}
          </p>
        )}
        <Textarea
          rows={6}
          value={text}
          placeholder="Nội dung tin nhắn"
          onChange={(e) => {
            setMode('DEBOUNCE')
            setText(e.target.value)
            setSent(null)
          }}
          aria-label="Nội dung tin nhắn"
        />

        {text.trim() && (
          <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3">
            <div className="flex items-center justify-between gap-2">
              {check.checking || check.stale || !result ? (
                <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Đang kiểm tra
                </span>
              ) : (
                <ComplianceBadge status={result.overall_status} />
              )}
              {result && <span className="font-mono text-xs text-muted-foreground">{result.message_hash.slice(0, 19)}…</span>}
            </div>
            {result && <Highlighted text={text} claims={result.claims} active={active} onPick={setActive} />}
            {result && result.claims.some((c) => c.status !== 'SUPPORTED') && (
              <ul className="space-y-2">
                {result.claims
                  .filter((c) => c.status !== 'SUPPORTED')
                  .map((c) => (
                    <li
                      key={c.claim_id}
                      className={cn('rounded-md border bg-background p-2.5 text-sm', active === c.claim_id ? 'border-primary/50' : 'border-border')}
                      onMouseEnter={() => setActive(c.claim_id)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium">“{c.text}”</p>
                        <ComplianceBadge status={c.status} />
                      </div>
                      <p className="mt-1 text-muted-foreground">{c.reason}</p>
                      {c.suggested_rewrite && (
                        <button type="button" onClick={() => applyRewrite(c)} className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                          <WandSparkles className="h-3 w-3" /> Thay bằng: “{c.suggested_rewrite}”
                        </button>
                      )}
                    </li>
                  ))}
              </ul>
            )}
          </div>
        )}
        {check.error != null && <p className="text-sm text-destructive">{errorMessage(check.error)}</p>}

        <div className="flex flex-wrap items-center justify-end gap-2">
          <Select value={channel} onValueChange={(v) => setChannel(v as MessageChannel)}>
            <SelectTrigger className="w-28" aria-label="Kênh gửi">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(CHANNEL_LABEL) as MessageChannel[]).map((c) => (
                <SelectItem key={c} value={c}>
                  {CHANNEL_LABEL[c]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={handleSend} disabled={!canSend} data-testid="send-message">
            {send.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            {blocked ? 'Không thể gửi' : 'Gửi khách'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
