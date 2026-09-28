import { CheckCircle2, Circle, Loader2, RotateCcw, Send, ShieldCheck, UserRoundCheck } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { CustomerConstraints, CustomerSegment, OptimizationObjective, PreSalesSession } from '@pricepolicy/api-client/contracts'
import { OPTIMIZATION_OBJECTIVES } from '@pricepolicy/api-client/contracts'
import { errorMessage, isApiError } from '@pricepolicy/api-client/errors'
import { useConfirmConstraints, useGeneratePlan, useHandoff, usePreSalesEvents, usePreSalesSession, useSendPreSalesMessage, useStartPreSales } from '@pricepolicy/api-client/hooks'
import { ErrorState, LoadingState } from '@pricepolicy/ui/components/common/PageStates'
import { MoneyInput } from '@pricepolicy/ui/components/common/MoneyInput'
import { ReferencePlanView } from '@pricepolicy/ui/components/presales/ReferencePlanView'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Checkbox } from '@pricepolicy/ui/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { CONSTRAINT_LABEL, OBJECTIVE_LABEL, PROJECT_LABEL, SEGMENT_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'

const SESSION_KEY = 'pricepolicy.presales-session'
const CONSENT_VERSION = 'consent-v1'

const readStored = () => {
  try {
    return localStorage.getItem(SESSION_KEY)
  } catch {
    return null
  }
}
const writeStored = (id: string | null) => {
  try {
    if (id) localStorage.setItem(SESSION_KEY, id)
    else localStorage.removeItem(SESSION_KEY)
  } catch {
    // storage bị chặn — phiên chỉ sống tới khi đóng tab
  }
}

export function AdvisorPage() {
  const [params] = useSearchParams()
  const unitFromLink = params.get('can')
  const [sessionId, setSessionId] = useState<string | null>(() => (unitFromLink ? null : readStored()))
  const session = usePreSalesSession(sessionId)
  const start = useStartPreSales()
  const started = useRef(false)

  const begin = (unit: string | null) =>
    start.mutateAsync(unit).then((s) => {
      writeStored(s.session_id)
      setSessionId(s.session_id)
    })

  useEffect(() => {
    if (sessionId || started.current) return
    started.current = true
    void begin(unitFromLink).catch(() => undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  // Phiên hết hạn / không còn trên server → mở phiên mới thay vì kẹt ở màn lỗi.
  useEffect(() => {
    if (isApiError(session.error) && [404, 410].includes(session.error.status)) {
      writeStored(null)
      started.current = false
      setSessionId(null)
    }
  }, [session.error])

  const restart = () => {
    writeStored(null)
    started.current = true
    setSessionId(null)
    void begin(null).catch(() => undefined)
  }

  return (
    <div className="container max-w-6xl space-y-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gold">Tư vấn tài chính</p>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-primary">Lập phương án thanh toán tham khảo</h1>
        </div>
        {session.data && (
          <Button variant="ghost" size="sm" onClick={restart}>
            <RotateCcw className="h-4 w-4" /> Bắt đầu lại
          </Button>
        )}
      </div>
      {start.isError && !session.data ? (
        <ErrorState error={start.error} onRetry={() => void begin(unitFromLink).catch(() => undefined)} />
      ) : session.error && !session.data ? (
        <ErrorState error={session.error} onRetry={() => session.refetch()} />
      ) : !session.data ? (
        <LoadingState label="Đang mở phiên tư vấn…" />
      ) : (
        <Advisor session={session.data} />
      )}
    </div>
  )
}

function Advisor({ session }: { session: PreSalesSession }) {
  // Giữ kết nối SSE sống khi đang lập phương án — sự kiện PRE_SALES_PLAN_READY tự làm mới session
  // (qua invalidateQueries), nhờ đó nhánh render dưới đây tự chuyển từ "đang lập" sang phương án
  // thật mà không cần đọc trực tiếp giá trị trả về ở đây.
  usePreSalesEvents(session)
  const closed = session.status === 'HANDED_OFF' || session.status === 'EXPIRED'
  const generating = Boolean(session.stream_url) && !session.plan
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr,420px]">
      <Chat session={session} disabled={closed} />
      <div className="space-y-4">
        {session.status === 'HANDED_OFF' ? (
          <HandedOff session={session} />
        ) : session.plan ? (
          <>
            <ReferencePlanView plan={session.plan} compact />
            <HandoffCard session={session} />
          </>
        ) : generating ? (
          <Card>
            <CardContent className="p-5">
              <PlanSteps />
            </CardContent>
          </Card>
        ) : (
          <ConstraintsCard key={`${session.messages.length}`} session={session} />
        )}
      </div>
      {session.plan && session.status === 'HANDED_OFF' && (
        <div className="lg:col-span-2">
          <ReferencePlanView plan={session.plan} />
        </div>
      )}
    </div>
  )
}

function Chat({ session, disabled }: { session: PreSalesSession; disabled: boolean }) {
  const send = useSendPreSalesMessage()
  const [text, setText] = useState('')
  const bottom = useRef<HTMLDivElement>(null)
  const last = session.messages[session.messages.length - 1]

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' })
  }, [session.messages.length, send.isPending])

  const submit = async (value: string) => {
    if (!value.trim()) return
    setText('')
    await send.mutateAsync({ sessionId: session.session_id, text: value }).catch(() => setText(value))
  }

  return (
    <Card className="flex h-[620px] flex-col">
      <CardContent className="flex-1 space-y-3 overflow-y-auto p-4" data-testid="chat">
        {session.messages.map((m) => (
          <div key={m.message_id} className={cn('flex', m.role === 'CUSTOMER' ? 'justify-end' : 'justify-start')}>
            <p
              className={cn(
                'max-w-[85%] whitespace-pre-line rounded-2xl px-3.5 py-2 text-sm leading-relaxed',
                m.role === 'CUSTOMER' ? 'rounded-br-sm bg-primary text-primary-foreground' : 'rounded-bl-sm bg-muted',
              )}
            >
              {m.text}
            </p>
          </div>
        ))}
        {send.isPending && (
          <div className="flex justify-start">
            <span className="inline-flex items-center gap-1.5 rounded-2xl bg-muted px-3.5 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Đang ghi nhận
            </span>
          </div>
        )}
        {send.isError && <p className="text-center text-xs text-destructive">{errorMessage(send.error)}</p>}
        <div ref={bottom} />
      </CardContent>
      {!disabled && last?.role === 'ASSISTANT' && last.suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t border-border px-4 pt-3">
          {last.suggestions.map((s) => (
            <button
              key={s}
              type="button"
              disabled={send.isPending}
              onClick={() => void submit(s)}
              className="rounded-full border border-primary/30 bg-primary/[0.04] px-3 py-1 text-sm text-primary hover:bg-primary/10 disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      <form
        className="flex gap-2 p-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault()
          void submit(text)
        }}
      >
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={disabled ? 'Phiên tư vấn đã kết thúc' : 'Nhập câu trả lời'} disabled={disabled} aria-label="Tin nhắn" />
        <Button type="submit" size="icon" disabled={disabled || send.isPending || !text.trim()} aria-label="Gửi">
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </Card>
  )
}

const PLAN_STEPS = ['Đã hiểu nhu cầu', 'Đang kiểm tra chính sách', 'Đang tính phương án', 'Đã kiểm tra điều kiện']

function PlanSteps() {
  const [step, setStep] = useState(1)
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, PLAN_STEPS.length - 1)), 700)
    return () => clearInterval(t)
  }, [])
  return (
    <ol className="space-y-2" data-testid="plan-steps">
      {PLAN_STEPS.map((label, i) => (
        <li key={label} className="flex items-center gap-2 text-sm">
          {i < step ? <CheckCircle2 className="h-4 w-4 text-success" /> : i === step ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : <Circle className="h-4 w-4 text-muted-foreground/40" />}
          <span className={i <= step ? 'font-medium' : 'text-muted-foreground'}>{label}</span>
        </li>
      ))}
    </ol>
  )
}

/** F2 — khách thấy và sửa được giả định trước khi lập phương án. */
function ConstraintsCard({ session }: { session: PreSalesSession }) {
  const [c, setC] = useState<CustomerConstraints>(session.constraints)
  const confirm = useConfirmConstraints()
  const plan = useGeneratePlan()
  const set = <K extends keyof CustomerConstraints>(k: K, v: CustomerConstraints[K]) => setC((x) => ({ ...x, [k]: v }))
  const ready = c.project_id && c.own_funds_vnd && c.monthly_capacity_vnd && c.customer_segment && c.objective
  const busy = confirm.isPending || plan.isPending

  async function handleConfirm() {
    await confirm.mutateAsync({ sessionId: session.session_id, constraints: c })
    await plan.mutateAsync(session.session_id)
  }

  return (
    <Card className={cn(session.status === 'AWAITING_CONFIRMATION' && 'border-primary/40 shadow-md')} data-testid="constraints">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Thông tin của anh/chị</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="project">{CONSTRAINT_LABEL.project_id}</Label>
          <Select value={c.project_id ?? ''} onValueChange={(v) => set('project_id', v)}>
            <SelectTrigger id="project">
              <SelectValue placeholder="Chọn dự án" />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(PROJECT_LABEL).map(([id, name]) => (
                <SelectItem key={id} value={id}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {c.preferred_unit_code && <p className="text-sm text-muted-foreground">Căn quan tâm: {c.preferred_unit_code}</p>}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="own">{CONSTRAINT_LABEL.own_funds_vnd}</Label>
            <MoneyInput id="own" value={c.own_funds_vnd} onChange={(v) => set('own_funds_vnd', v)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="monthly">{CONSTRAINT_LABEL.monthly_capacity_vnd}</Label>
            <MoneyInput id="monthly" value={c.monthly_capacity_vnd} onChange={(v) => set('monthly_capacity_vnd', v)} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="bedrooms">{CONSTRAINT_LABEL.bedrooms}</Label>
            <Select value={c.bedrooms ? String(c.bedrooms) : ''} onValueChange={(v) => set('bedrooms', Number(v))}>
              <SelectTrigger id="bedrooms">
                <SelectValue placeholder="Bất kỳ" />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} phòng ngủ
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="segment">{CONSTRAINT_LABEL.customer_segment}</Label>
            <Select value={c.customer_segment ?? ''} onValueChange={(v) => set('customer_segment', v as CustomerSegment)}>
              <SelectTrigger id="segment">
                <SelectValue placeholder="Chọn" />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(SEGMENT_LABEL) as CustomerSegment[]).map((s) => (
                  <SelectItem key={s} value={s}>
                    {SEGMENT_LABEL[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="objective">{CONSTRAINT_LABEL.objective}</Label>
          <Select value={c.objective ?? ''} onValueChange={(v) => set('objective', v as OptimizationObjective)}>
            <SelectTrigger id="objective">
              <SelectValue placeholder="Chọn ưu tiên" />
            </SelectTrigger>
            <SelectContent>
              {OPTIMIZATION_OBJECTIVES.map((o) => (
                <SelectItem key={o} value={o}>
                  {OBJECTIVE_LABEL[o]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {(confirm.isError || plan.isError) && <p className="text-sm text-destructive">{errorMessage(confirm.error ?? plan.error)}</p>}
        <Button className="w-full" onClick={() => void handleConfirm().catch(() => undefined)} disabled={!ready || busy} data-testid="confirm-constraints">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} Xác nhận & lập phương án
        </Button>
      </CardContent>
    </Card>
  )
}

function HandoffCard({ session }: { session: PreSalesSession }) {
  const [open, setOpen] = useState(false)
  return (
    <Card className="border-gold/40">
      <CardContent className="space-y-3 p-4">
        <p className="text-sm">Chuyên viên kiểm tra lại với chính sách hiện hành và gửi báo giá chính thức đã được phê duyệt.</p>
        <Button className="w-full" onClick={() => setOpen(true)} data-testid="open-handoff">
          <UserRoundCheck className="h-4 w-4" /> Nhận báo giá chính thức
        </Button>
      </CardContent>
      {open && <HandoffDialog session={session} onClose={() => setOpen(false)} />}
    </Card>
  )
}

function HandoffDialog({ session, onClose }: { session: PreSalesSession; onClose: () => void }) {
  const handoff = useHandoff()
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [consent, setConsent] = useState(false)
  const valid = name.trim() && /^[0-9 +]{9,15}$/.test(phone.trim()) && consent

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      await handoff.mutateAsync({ sessionId: session.session_id, body: { full_name: name, phone, consent: true, consent_text_version: CONSENT_VERSION } })
      onClose()
    } catch {
      // lỗi hiển thị trong dialog
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Kết nối chuyên viên</DialogTitle>
            <DialogDescription>Chuyên viên sẽ gọi lại theo số điện thoại bên dưới.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="name">Họ tên</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="phone">Số điện thoại</Label>
            <Input id="phone" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required />
          </div>
          <label className="flex items-start gap-2.5 rounded-md border border-border p-3 text-sm">
            <Checkbox checked={consent} onCheckedChange={(c) => setConsent(c === true)} className="mt-0.5" data-testid="consent" />
            <span>Tôi đồng ý chia sẻ nhu cầu, thông tin tài chính và phương án tham khảo trong phiên này cho chuyên viên VLandFuture để được tư vấn và lập báo giá.</span>
          </label>
          {handoff.isError && <p className="text-sm text-destructive">{errorMessage(handoff.error)}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Huỷ
            </Button>
            <Button type="submit" disabled={!valid || handoff.isPending} data-testid="submit-handoff">
              {handoff.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />} Gửi cho chuyên viên
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function HandedOff({ session }: { session: PreSalesSession }) {
  return (
    <Card className="border-success/40 bg-success/5" data-testid="handed-off">
      <CardContent className="space-y-2 p-5">
        <p className="inline-flex items-center gap-2 font-semibold text-success">
          <CheckCircle2 className="h-5 w-5" /> Đã gửi cho chuyên viên
        </p>
        <p className="text-sm">{session.messages[session.messages.length - 1]?.text}</p>
        <p className="text-xs text-muted-foreground">Mã hồ sơ {session.dossier_id}</p>
      </CardContent>
    </Card>
  )
}
