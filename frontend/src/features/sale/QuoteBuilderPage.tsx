import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Circle,
  FileEdit,
  Loader2,
  MinusCircle,
  Send,
  ShieldAlert,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { AnalysisProgressEvent, AnalysisStage, CreateQuoteRequest } from '@/api/contracts'
import { errorMessage } from '@/api/errors'
import { useActivePolicy, useAnalyzeQuote, useLead, usePreflight, useQuote, useSubmitQuote, useUnits } from '@/api/hooks'
import { MoneyText } from '@/components/common/MoneyText'
import { ErrorState, LoadingState, PageHeader } from '@/components/common/PageStates'
import { ActivePolicyBanner, FindingItem } from '@/components/quote/PreflightFindings'
import { QuoteAnalysisView } from '@/components/quote/QuoteAnalysisView'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { formatPercent, formatVnd, todayIso } from '@/lib/format'
import { ANALYSIS_STAGE_LABEL, OBJECTIVE_OPTIONS, SEGMENT_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { toast } from '@/state/toastStore'
import type { CustomerSegment, OptimizationObjective, PaymentPlanType, PolicyRule, Quote } from '@/types/domain'

type FormState = Omit<CreateQuoteRequest, 'leadId'>

const EMPTY_FORM: FormState = {
  unitCode: '',
  transactionDate: todayIso(),
  customerSegment: 'NEW_CUSTOMER',
  unitsQuantity: 1,
  selectedRuleCodes: [],
  objective: 'MIN_NET_PRICE',
  customerName: '',
  customerPhone: '',
}

const PLAN_SHORT: Record<PaymentPlanType, string> = {
  STANDARD_PROGRESS: 'Tiến độ chuẩn',
  EARLY_PAYMENT_95: 'Thanh toán sớm 95%',
  BANK_LOAN_SUPPORT: 'Vay ngân hàng',
}

const STAGES: AnalysisStage[] = ['POLICY_LOOKUP', 'PREFLIGHT', 'PRICING', 'RANKING']

/**
 * Routes:
 *  /sale/quotes/new?leadId=…        — lập mới từ yêu cầu khách
 *  /sale/quotes/new?fromQuote=…     — lập hồ sơ mới dựa trên hồ sơ cũ (sau khi bị từ chối)
 *  /sale/quotes/:quoteId/revise     — phân tích lại phiên bản mới của hồ sơ
 */
export function QuoteBuilderPage() {
  const { quoteId } = useParams()
  const [params] = useSearchParams()
  const leadId = params.get('leadId')
  const fromQuoteId = params.get('fromQuote')
  const source = useQuote(quoteId ?? fromQuoteId ?? undefined)
  const lead = useLead(leadId)

  if (source.isLoading || lead.isLoading) return <LoadingState />
  if (source.error) return <ErrorState error={source.error} />
  if (lead.error) return <ErrorState error={lead.error} />

  let initial: FormState = EMPTY_FORM
  if (source.data) {
    initial = { ...source.data.context, transactionDate: quoteId ? source.data.context.transactionDate : todayIso() }
  } else if (lead.data) {
    initial = {
      ...EMPTY_FORM,
      unitCode: lead.data.unitCode,
      customerSegment: lead.data.customerSegment,
      objective: lead.data.objective,
      customerName: lead.data.fullName,
      customerPhone: lead.data.phone,
    }
  }

  return (
    <QuoteBuilder
      key={quoteId ?? fromQuoteId ?? leadId ?? 'new'}
      initial={initial}
      leadId={source.data?.leadId ?? leadId}
      reviseQuote={quoteId ? source.data : undefined}
      leadNote={lead.data?.note}
    />
  )
}

function QuoteBuilder({
  initial,
  leadId,
  reviseQuote,
  leadNote,
}: {
  initial: FormState
  leadId: string | null
  reviseQuote?: Quote
  leadNote?: string
}) {
  const navigate = useNavigate()
  const [step, setStep] = useState<1 | 2 | 3>(reviseQuote ? 2 : 1)
  const [form, setForm] = useState<FormState>(initial)
  const [quoteId, setQuoteId] = useState<string | undefined>(reviseQuote?.quoteId)
  const [progress, setProgress] = useState<Partial<Record<AnalysisStage, AnalysisProgressEvent>>>({})
  const [result, setResult] = useState<Quote | null>(null)
  const analyze = useAnalyzeQuote()
  const submit = useSubmitQuote()

  const units = useUnits()
  const selectableUnits = useMemo(
    () => (units.data ?? []).filter((u) => u.status === 'AVAILABLE' || u.unitCode === initial.unitCode),
    [units.data, initial.unitCode],
  )
  const unit = units.data?.find((u) => u.unitCode === form.unitCode)
  const policy = useActivePolicy(unit?.projectId, form.transactionDate)
  const preflight = usePreflight(
    step === 2 && unit
      ? {
          unitCode: form.unitCode,
          transactionDate: form.transactionDate,
          customerSegment: form.customerSegment,
          unitsQuantity: form.unitsQuantity,
          selectedRuleCodes: form.selectedRuleCodes,
        }
      : null,
  )

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }))
  const availableRuleCodes = new Set(policy.data?.rules.map((r) => r.ruleCode) ?? [])
  const effectiveSelected = form.selectedRuleCodes.filter((c) => availableRuleCodes.has(c))

  const step1Valid =
    form.customerName.trim().length > 0 &&
    /^[0-9 +]{9,15}$/.test(form.customerPhone.trim()) &&
    Boolean(unit) &&
    form.unitsQuantity >= 1 &&
    Boolean(form.transactionDate)

  async function runAnalysis() {
    setStep(3)
    setResult(null)
    setProgress({})
    try {
      const quote = await analyze.mutateAsync({
        input: { ...form, selectedRuleCodes: effectiveSelected, leadId },
        quoteId,
        onProgress: (e) => setProgress((p) => ({ ...p, [e.stage]: e })),
      })
      setQuoteId(quote.quoteId)
      setResult(quote)
    } catch (e) {
      toast.error('Không thể phân tích báo giá', errorMessage(e))
      setStep(2)
    }
  }

  async function handleSubmit() {
    if (!result) return
    try {
      await submit.mutateAsync(result.quoteId)
      toast.success('Đã gửi Quản lý duyệt', `${result.quoteId} · ${result.context.customerName}`)
      navigate(`/sale/quotes/${result.quoteId}`)
    } catch (e) {
      toast.error('Không thể gửi duyệt', errorMessage(e))
    }
  }

  const revisionNote = reviseQuote?.status === 'NEEDS_REVISION' ? reviseQuote.approval?.notes : undefined

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={
          <Link to={reviseQuote ? `/sale/quotes/${reviseQuote.quoteId}` : '/sale/quotes'} className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3.5 w-3.5" /> {reviseQuote ? reviseQuote.quoteId : 'Hồ sơ báo giá'}
          </Link>
        }
        title={reviseQuote ? `Chỉnh sửa hồ sơ — phiên bản ${reviseQuote.version + 1}` : 'Lập báo giá'}
      />

      <Stepper step={step} />

      {revisionNote && (
        <Alert variant="warning">
          <FileEdit />
          <AlertTitle>Yêu cầu chỉnh sửa từ {reviseQuote?.approval?.approverName}</AlertTitle>
          <AlertDescription className="text-foreground">{revisionNote}</AlertDescription>
        </Alert>
      )}

      {step === 1 && (
        <div className="grid gap-6 lg:grid-cols-[1fr,340px]">
          <Card>
            <CardHeader>
              <CardTitle>Khách hàng & căn hộ</CardTitle>
              {leadId && <CardDescription>Từ yêu cầu {leadId}</CardDescription>}
            </CardHeader>
            <CardContent className="space-y-4">
              {leadNote && <p className="rounded-md bg-muted/60 px-3 py-2 text-sm">Ghi chú của khách: {leadNote}</p>}
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="customerName">Họ tên khách hàng</Label>
                  <Input id="customerName" value={form.customerName} onChange={(e) => set('customerName', e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="customerPhone">Số điện thoại</Label>
                  <Input id="customerPhone" inputMode="tel" value={form.customerPhone} onChange={(e) => set('customerPhone', e.target.value)} />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="segment">Phân khúc khách hàng</Label>
                <Select value={form.customerSegment} onValueChange={(v) => set('customerSegment', v as CustomerSegment)}>
                  <SelectTrigger id="segment">
                    <SelectValue />
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
              <div className="space-y-1.5">
                <Label htmlFor="unit">Căn hộ</Label>
                <Select value={form.unitCode} onValueChange={(v) => set('unitCode', v)}>
                  <SelectTrigger id="unit">
                    <SelectValue placeholder={units.isLoading ? 'Đang tải bảng hàng…' : 'Chọn căn hộ đang mở bán'} />
                  </SelectTrigger>
                  <SelectContent>
                    {selectableUnits.map((u) => (
                      <SelectItem key={u.unitCode} value={u.unitCode}>
                        {u.unitCode} — {u.projectName} · {u.bedrooms}PN · {formatVnd(u.listedPrice)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="txDate">Ngày giao dịch</Label>
                  <Input id="txDate" type="date" value={form.transactionDate} onChange={(e) => set('transactionDate', e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="qty">Số căn khách mua trong đợt</Label>
                  <Input
                    id="qty"
                    type="number"
                    min={1}
                    value={form.unitsQuantity}
                    onChange={(e) => set('unitsQuantity', Math.max(1, Math.floor(Number(e.target.value) || 1)))}
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <Button onClick={() => setStep(2)} disabled={!step1Valid}>
                  Tiếp tục <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
          {unit && (
            <Card className="h-fit">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{unit.unitCode}</CardTitle>
                <CardDescription>{unit.projectName}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>
                  {unit.block}, tầng {unit.floor} · {unit.bedrooms} phòng ngủ · {unit.areaM2} m²
                </p>
                <p className="text-muted-foreground">{unit.view}</p>
                <p className="pt-2 text-xs text-muted-foreground">Giá niêm yết</p>
                <MoneyText amount={unit.listedPrice} size="lg" />
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="grid gap-6 lg:grid-cols-[1fr,360px]">
          <div className="space-y-4">
            {policy.isLoading && <LoadingState label="Đang tra cứu chính sách…" className="py-8" />}
            {policy.data && (
              <ActivePolicyBanner
                policy={{
                  policyId: policy.data.policyId,
                  version: policy.data.version,
                  title: policy.data.title,
                  effectiveFrom: policy.data.effectiveFrom,
                  effectiveTo: policy.data.effectiveTo,
                  sourceFileHash: policy.data.sourceFileHash,
                }}
              />
            )}
            {!policy.isLoading && !policy.data && (
              <Alert variant="destructive">
                <ShieldAlert />
                <AlertTitle>Không có chính sách hiệu lực tại ngày {form.transactionDate}</AlertTitle>
                <AlertDescription className="text-foreground/80">
                  Hồ sơ sẽ được chuyển Quản lý thẩm định ngoại lệ. Kiểm tra lại ngày giao dịch nếu nhập nhầm.
                </AlertDescription>
              </Alert>
            )}

            {policy.data && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle>Ưu đãi</CardTitle>
                  <CardDescription>Chọn các ưu đãi khách đề nghị xét. Ưu đãi theo hồ sơ được áp dụng tự động.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {policy.data.rules.map((rule) => (
                    <RuleOption
                      key={rule.ruleCode}
                      rule={rule}
                      segment={form.customerSegment}
                      unitsQuantity={form.unitsQuantity}
                      checked={effectiveSelected.includes(rule.ruleCode)}
                      conflicted={Boolean(preflight.data?.findings.some((f) => f.ruleCodes.includes(rule.ruleCode)))}
                      onToggle={(checked) =>
                        set(
                          'selectedRuleCodes',
                          checked ? [...effectiveSelected, rule.ruleCode] : effectiveSelected.filter((c) => c !== rule.ruleCode),
                        )
                      }
                    />
                  ))}
                  {preflight.data && preflight.data.findings.length > 0 && (
                    <div className="space-y-2 pt-2" data-testid="live-preflight">
                      {preflight.data.findings.map((f, i) => (
                        <FindingItem key={i} finding={f} />
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          <div className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Mục tiêu của khách</CardTitle>
              </CardHeader>
              <CardContent>
                <RadioGroup value={form.objective} onValueChange={(v) => set('objective', v as OptimizationObjective)} className="gap-2">
                  {OBJECTIVE_OPTIONS.map((opt) => (
                    <label
                      key={opt.value}
                      className={cn(
                        'flex cursor-pointer items-start gap-2.5 rounded-md border p-2.5',
                        form.objective === opt.value ? 'border-primary bg-primary/[0.04]' : 'border-border hover:bg-muted/50',
                      )}
                    >
                      <RadioGroupItem value={opt.value} className="mt-0.5" />
                      <span>
                        <span className="block text-sm font-medium leading-tight">{opt.label}</span>
                        <span className="block text-xs text-muted-foreground">{opt.hint}</span>
                      </span>
                    </label>
                  ))}
                </RadioGroup>
              </CardContent>
            </Card>
            <div className="flex justify-between gap-2">
              <Button variant="outline" onClick={() => setStep(1)}>
                <ArrowLeft className="h-4 w-4" /> Quay lại
              </Button>
              <Button onClick={runAnalysis} disabled={policy.isLoading}>
                <Sparkles className="h-4 w-4" /> Phân tích & tính giá
              </Button>
            </div>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-6">
          <AnalysisProgress progress={progress} />
          {result && (
            <>
              <QuoteAnalysisView quote={result} />
              <ResultActions
                quote={result}
                submitting={submit.isPending}
                onSubmit={handleSubmit}
                onAdjust={() => setStep(2)}
                onOpen={() => navigate(`/sale/quotes/${result.quoteId}`)}
              />
            </>
          )}
        </div>
      )}
    </div>
  )
}

function Stepper({ step }: { step: 1 | 2 | 3 }) {
  const steps = ['Khách hàng & căn hộ', 'Ưu đãi & mục tiêu', 'Kết quả phân tích']
  return (
    <ol className="flex flex-wrap items-center gap-2 text-sm">
      {steps.map((label, idx) => {
        const n = (idx + 1) as 1 | 2 | 3
        const done = n < step
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={cn(
                'flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold',
                n === step ? 'bg-primary text-primary-foreground' : done ? 'bg-success text-success-foreground' : 'bg-muted text-muted-foreground',
              )}
            >
              {done ? <Check className="h-3.5 w-3.5" /> : n}
            </span>
            <span className={cn(n === step ? 'font-medium' : 'text-muted-foreground')}>{label}</span>
            {idx < steps.length - 1 && <span className="mx-1 h-px w-8 bg-border" />}
          </li>
        )
      })}
    </ol>
  )
}

function ruleValueLabel(rule: PolicyRule): string {
  if (rule.kind === 'PERCENT_DISCOUNT') return `Giảm ${formatPercent(rule.discountRate ?? 0)}`
  if (rule.kind === 'GIFT') return `Quà tặng ${formatVnd(rule.cashEquivalentVnd ?? 0)}`
  if (rule.kind === 'BANK_SUPPORT') return `HTLS 0% ${rule.interestSupportMonths} tháng`
  return 'Cần Quản lý thẩm định'
}

function RuleOption({
  rule,
  segment,
  unitsQuantity,
  checked,
  conflicted,
  onToggle,
}: {
  rule: PolicyRule
  segment: CustomerSegment
  unitsQuantity: number
  checked: boolean
  conflicted: boolean
  onToggle: (checked: boolean) => void
}) {
  const planScope = rule.applicablePlans.length < 3 ? `Chỉ phương án ${rule.applicablePlans.map((p) => PLAN_SHORT[p]).join(', ')}` : null
  const conditions = [
    planScope,
    rule.minUnitsPurchased ? `Từ ${rule.minUnitsPurchased} căn${unitsQuantity < rule.minUnitsPurchased ? ' — khách đang mua ' + unitsQuantity : ''}` : null,
  ].filter(Boolean)

  if (!rule.isSelectable) {
    const applies = !rule.requiredSegments || rule.requiredSegments.includes(segment)
    return (
      <div className="flex items-start gap-2.5 rounded-md border border-dashed border-border bg-muted/30 p-2.5" data-rule={rule.ruleCode}>
        {applies ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" /> : <MinusCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-tight">{rule.title}</p>
          <p className="text-xs text-muted-foreground">
            {applies ? 'Tự động áp dụng theo hồ sơ khách' : `Chỉ dành cho ${rule.requiredSegments?.map((s) => SEGMENT_LABEL[s]).join(', ')}`} ·{' '}
            {rule.source.clauseTitle}
          </p>
        </div>
        <span className="shrink-0 text-xs font-medium text-muted-foreground">{ruleValueLabel(rule)}</span>
      </div>
    )
  }

  return (
    <label
      data-rule={rule.ruleCode}
      className={cn(
        'flex cursor-pointer items-start gap-2.5 rounded-md border p-2.5 transition-colors',
        conflicted ? 'border-destructive/50 bg-destructive/[0.04]' : checked ? 'border-primary/40 bg-primary/[0.03]' : 'border-border hover:bg-muted/50',
      )}
    >
      <Checkbox checked={checked} onCheckedChange={(c) => onToggle(c === true)} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-tight">{rule.title}</p>
        <p className="text-xs text-muted-foreground">{[rule.source.clauseTitle, ...conditions].join(' · ')}</p>
      </div>
      <span className={cn('shrink-0 text-xs font-medium', rule.isAmbiguous ? 'text-warning' : 'text-foreground')}>{ruleValueLabel(rule)}</span>
    </label>
  )
}

function AnalysisProgress({ progress }: { progress: Partial<Record<AnalysisStage, AnalysisProgressEvent>> }) {
  return (
    <Card>
      <CardContent className="grid gap-3 p-4 sm:grid-cols-4">
        {STAGES.map((stage) => {
          const e = progress[stage]
          const state = e?.state ?? 'PENDING'
          return (
            <div key={stage} className="flex items-start gap-2" data-stage={stage} data-state={state}>
              {state === 'RUNNING' && <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />}
              {state === 'DONE' && <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />}
              {state === 'BLOCKED' && <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />}
              {(state === 'SKIPPED' || state === 'PENDING') && <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/50" />}
              <div className="min-w-0">
                <p className={cn('text-sm leading-tight', state === 'SKIPPED' || state === 'PENDING' ? 'text-muted-foreground' : 'font-medium')}>
                  {ANALYSIS_STAGE_LABEL[stage]}
                </p>
                {e?.message && <p className="truncate text-xs text-muted-foreground">{e.message}</p>}
                {state === 'SKIPPED' && <p className="text-xs text-muted-foreground">Bỏ qua</p>}
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

function ResultActions({
  quote,
  submitting,
  onSubmit,
  onAdjust,
  onOpen,
}: {
  quote: Quote
  submitting: boolean
  onSubmit: () => void
  onAdjust: () => void
  onOpen: () => void
}) {
  return (
    <Card className="sticky bottom-4 z-10 border-primary/20 shadow-lg">
      <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm">
          <span className="font-semibold">{quote.quoteId}</span>
          <span className="text-muted-foreground">
            {quote.status === 'DRAFT' && ' đã lưu nháp. Gửi Quản lý duyệt để phát hành báo giá cho khách.'}
            {quote.status === 'ABSTAINED' && ' đã được chuyển Quản lý thẩm định ngoại lệ. Bạn có thể điều chỉnh ưu đãi để phân tích lại.'}
            {quote.status === 'CALCULATION_FAILED' && ' không thể phát hành. Điều chỉnh dữ liệu và phân tích lại.'}
          </span>
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={onAdjust}>
            <FileEdit className="h-4 w-4" /> Điều chỉnh
          </Button>
          {quote.status === 'DRAFT' ? (
            <Button onClick={onSubmit} disabled={submitting}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Gửi Quản lý duyệt
            </Button>
          ) : (
            <Button variant="secondary" onClick={onOpen}>
              Xem hồ sơ <ArrowRight className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
