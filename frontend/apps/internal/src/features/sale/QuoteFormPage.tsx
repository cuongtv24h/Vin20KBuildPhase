import { ArrowLeft, CheckCircle2, FileEdit, Loader2, MinusCircle, Sparkles } from 'lucide-react'
import { useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { CustomerSegment, OptimizationObjective, PolicyRule, Quote, QuoteCreateRequest } from '@pricepolicy/api-client/contracts'
import { OPTIMIZATION_OBJECTIVES } from '@pricepolicy/api-client/contracts'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useActivePolicy, useConvertLead, useCreateQuote, useLead, useNewQuoteVersion, usePolicies, usePolicy, useQuote, useUnits } from '@pricepolicy/api-client/hooks'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { ErrorState, LoadingState, PageHeader } from '@pricepolicy/ui/components/common/PageStates'
import { Alert, AlertDescription, AlertTitle } from '@pricepolicy/ui/components/ui/alert'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Checkbox } from '@pricepolicy/ui/components/ui/checkbox'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@pricepolicy/ui/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { formatDate, formatPercent, formatVnd, todayIso } from '@pricepolicy/ui/lib/format'
import { OBJECTIVE_LABEL, SEGMENT_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'
import { toast } from '@pricepolicy/ui/state/toastStore'

const AUTO = '__auto__'

const EMPTY: QuoteCreateRequest = {
  unit_code: '',
  transaction_date: todayIso(),
  customer_segment: 'NEW_CUSTOMER',
  units_quantity: 1,
  selected_rule_codes: [],
  objective: 'MIN_NET_PRICE',
  customer_name: '',
  customer_phone: '',
  requested_policy_id: null,
}

/**
 * /sale/quotes/new                 — khách vãng lai
 * /sale/quotes/new?dossier=LD-…    — từ hồ sơ Pre-Sales (convert-to-quote, tính lại từ đầu)
 * /sale/quotes/:quoteId/revise     — phiên bản mới của hồ sơ
 */
export function QuoteFormPage() {
  const { quoteId } = useParams()
  const [params] = useSearchParams()
  const dossierId = params.get('dossier')
  const source = useQuote(quoteId)
  const lead = useLead(dossierId)

  if (source.isLoading || (dossierId && lead.isLoading)) return <LoadingState />
  if (source.error) return <ErrorState error={source.error} onRetry={() => source.refetch()} />
  if (lead.error) return <ErrorState error={lead.error} onRetry={() => lead.refetch()} />
  if (dossierId && !lead.data) return <ErrorState error={new Error('Không tìm thấy hồ sơ khách.')} />

  let initial = EMPTY
  if (source.data) initial = { ...source.data.transaction_context }
  else if (lead.data) {
    const c = lead.data.constraints
    initial = {
      ...EMPTY,
      unit_code: lead.data.reference_plan?.scenarios[0]?.unit_code ?? c.preferred_unit_code ?? '',
      customer_segment: c.customer_segment ?? 'NEW_CUSTOMER',
      objective: c.objective ?? 'MIN_NET_PRICE',
      customer_name: lead.data.customer.full_name,
      customer_phone: lead.data.customer.phone,
    }
  }
  return <QuoteForm key={quoteId ?? dossierId ?? 'new'} initial={initial} revise={source.data} dossierId={lead.data?.dossier_id ?? null} />
}

function QuoteForm({ initial, revise, dossierId }: { initial: QuoteCreateRequest; revise?: Quote; dossierId: string | null }) {
  const navigate = useNavigate()
  const [form, setForm] = useState<QuoteCreateRequest>(initial)
  const set = <K extends keyof QuoteCreateRequest>(k: K, v: QuoteCreateRequest[K]) => setForm((f) => ({ ...f, [k]: v }))

  const units = useUnits()
  const unit = units.data?.find((u) => u.unit_code === form.unit_code)
  const policies = usePolicies({ project_id: unit?.project_id, status: 'PUBLISHED' }, Boolean(unit))
  const active = useActivePolicy(form.requested_policy_id ? undefined : unit?.project_id, form.transaction_date)
  const pinned = usePolicy(form.requested_policy_id)
  const policy = form.requested_policy_id ? pinned.data : active.data
  const policyLoading = form.requested_policy_id ? pinned.isLoading : active.isLoading

  const create = useCreateQuote()
  const convert = useConvertLead()
  const version = useNewQuoteVersion()
  const pending = create.isPending || convert.isPending || version.isPending

  const selectable = useMemo(() => (units.data ?? []).filter((u) => u.status !== 'SOLD' || u.unit_code === initial.unit_code), [units.data, initial.unit_code])
  const ruleCodes = new Set(policy?.rules.map((r) => r.rule_code) ?? [])
  const selected = form.selected_rule_codes.filter((c) => ruleCodes.has(c))
  const valid = form.customer_name.trim() && /^[0-9 +]{9,15}$/.test(form.customer_phone.trim()) && unit && form.units_quantity >= 1

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const body: QuoteCreateRequest = { ...form, transaction_date: form.transaction_date || null, selected_rule_codes: policy ? selected : form.selected_rule_codes }
    try {
      const accepted = revise
        ? await version.mutateAsync({ quote: revise, body })
        : dossierId
          ? await convert.mutateAsync({ dossierId, body })
          : await create.mutateAsync(body)
      navigate(`/sale/quotes/${accepted.quote_id}`, { state: { streamUrl: accepted.stream_url } })
    } catch (err) {
      toast.error('Không thể tạo báo giá', errorMessage(err))
    }
  }

  const note = revise?.status === 'NEEDS_REVISION' ? revise.approval?.reason : revise?.abstention?.message

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <PageHeader
        eyebrow={
          <Link to={revise ? `/sale/quotes/${revise.quote_id}` : dossierId ? `/sale/leads?id=${dossierId}` : '/sale/quotes'} className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3.5 w-3.5" /> {revise ? revise.quote_id : dossierId ?? 'Báo giá'}
          </Link>
        }
        title={revise ? `Phiên bản ${revise.quote_version + 1}` : 'Báo giá chính thức'}
      />

      {note && (
        <Alert variant="warning">
          <FileEdit />
          <AlertTitle>{revise?.status === 'NEEDS_REVISION' ? `Yêu cầu từ ${revise.approval?.decided_by.full_name}` : 'Lý do dừng ở phiên bản trước'}</AlertTitle>
          <AlertDescription className="text-foreground">{note}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr,360px]">
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Khách hàng & căn hộ</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field id="customer_name" label="Họ tên khách hàng">
                  <Input id="customer_name" value={form.customer_name} onChange={(e) => set('customer_name', e.target.value)} required />
                </Field>
                <Field id="customer_phone" label="Số điện thoại">
                  <Input id="customer_phone" inputMode="tel" value={form.customer_phone} onChange={(e) => set('customer_phone', e.target.value)} required />
                </Field>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field id="segment" label="Hồ sơ khách">
                  <Select value={form.customer_segment} onValueChange={(v) => set('customer_segment', v as CustomerSegment)}>
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
                </Field>
                <Field id="qty" label="Số căn mua trong đợt">
                  <Input id="qty" type="number" min={1} value={form.units_quantity} onChange={(e) => set('units_quantity', Math.max(1, Math.floor(Number(e.target.value) || 1)))} />
                </Field>
              </div>
              <Field id="unit" label="Mã căn">
                <Select value={form.unit_code} onValueChange={(v) => setForm((f) => ({ ...f, unit_code: v, requested_policy_id: null }))}>
                  <SelectTrigger id="unit">
                    <SelectValue placeholder={units.isLoading ? 'Đang tải bảng hàng…' : units.error ? 'Không tải được bảng hàng' : 'Chọn căn hộ'} />
                  </SelectTrigger>
                  <SelectContent>
                    {selectable.map((u) => (
                      <SelectItem key={u.unit_code} value={u.unit_code}>
                        {u.unit_code} · {u.project_name} · {u.bedrooms}PN · {formatVnd(u.listed_price_before_tax_vnd)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Chính sách & ưu đãi</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field id="tx_date" label="Ngày giao dịch">
                  <Input id="tx_date" type="date" value={form.transaction_date ?? ''} onChange={(e) => set('transaction_date', e.target.value || null)} />
                </Field>
                <Field id="policy" label="Văn bản chính sách">
                  <Select value={form.requested_policy_id ?? AUTO} onValueChange={(v) => set('requested_policy_id', v === AUTO ? null : v)} disabled={!unit}>
                    <SelectTrigger id="policy">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={AUTO}>Theo ngày giao dịch</SelectItem>
                      {(policies.data ?? []).map((p) => (
                        <SelectItem key={p.policy_id} value={p.policy_id}>
                          {p.policy_version} · {formatDate(p.effective_from)} – {formatDate(p.effective_to)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
              {!unit ? null : policyLoading ? (
                <LoadingState label="Đang tra cứu chính sách…" className="py-6" />
              ) : !policy ? (
                <p className="rounded-md border border-dashed border-border px-3 py-4 text-center text-sm text-muted-foreground">
                  {form.transaction_date ? `Không có chính sách hiệu lực ngày ${formatDate(form.transaction_date)}` : 'Chưa có ngày giao dịch'}
                </p>
              ) : (
                <div className="space-y-2" data-testid="rule-options">
                  <p className="text-xs text-muted-foreground">
                    {policy.title} · {policy.policy_version} · {formatDate(policy.effective_from)} – {formatDate(policy.effective_to)}
                  </p>
                  {policy.rules.map((rule) => (
                    <RuleOption
                      key={rule.rule_code}
                      rule={rule}
                      segment={form.customer_segment}
                      checked={selected.includes(rule.rule_code)}
                      onToggle={(on) => set('selected_rule_codes', on ? [...selected, rule.rule_code] : selected.filter((c) => c !== rule.rule_code))}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          {unit && (
            <Card>
              <CardContent className="space-y-1 p-4 text-sm">
                <p className="font-semibold">{unit.unit_code}</p>
                <p className="text-muted-foreground">
                  {unit.project_name} · {unit.block}, tầng {unit.floor} · {unit.area_m2} m² · {unit.view}
                </p>
                <MoneyText amount={unit.listed_price_before_tax_vnd} size="lg" className="block pt-1" />
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Tiêu chí tối ưu</CardTitle>
            </CardHeader>
            <CardContent>
              <RadioGroup value={form.objective} onValueChange={(v) => set('objective', v as OptimizationObjective)} className="gap-2">
                {OPTIMIZATION_OBJECTIVES.map((o) => (
                  <label key={o} className={cn('flex cursor-pointer items-center gap-2.5 rounded-md border p-2.5 text-sm', form.objective === o ? 'border-primary bg-primary/[0.04]' : 'border-border hover:bg-muted/50')}>
                    <RadioGroupItem value={o} /> {OBJECTIVE_LABEL[o]}
                  </label>
                ))}
              </RadioGroup>
            </CardContent>
          </Card>
          <Button type="submit" className="w-full" size="lg" disabled={!valid || pending} data-testid="analyze">
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Phân tích & tính giá
          </Button>
        </div>
      </div>
    </form>
  )
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

function valueLabel(rule: PolicyRule): string {
  if (rule.kind === 'PERCENT_DISCOUNT') return `Giảm ${formatPercent(rule.discount_rate ?? 0)}`
  if (rule.kind === 'GIFT') return formatVnd(rule.cash_equivalent_vnd ?? 0)
  if (rule.kind === 'BANK_SUPPORT') return `0% · ${rule.interest_support_months} tháng`
  return 'Theo quyết định riêng'
}

function RuleOption({ rule, segment, checked, onToggle }: { rule: PolicyRule; segment: CustomerSegment; checked: boolean; onToggle: (on: boolean) => void }) {
  if (!rule.is_selectable) {
    const applies = !rule.required_segments || rule.required_segments.includes(segment)
    return (
      <div className="flex items-center gap-2.5 rounded-md border border-dashed border-border bg-muted/30 p-2.5" data-rule={rule.rule_code}>
        {applies ? <CheckCircle2 className="h-4 w-4 shrink-0 text-success" /> : <MinusCircle className="h-4 w-4 shrink-0 text-muted-foreground" />}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-tight">{rule.title}</p>
          <p className="text-xs text-muted-foreground">
            {applies ? 'Tự động theo hồ sơ khách' : 'Không áp dụng cho hồ sơ này'} · {rule.source.section}
          </p>
        </div>
        <span className="shrink-0 text-xs font-medium text-muted-foreground">{valueLabel(rule)}</span>
      </div>
    )
  }
  return (
    <label className={cn('flex cursor-pointer items-center gap-2.5 rounded-md border p-2.5', checked ? 'border-primary/40 bg-primary/[0.03]' : 'border-border hover:bg-muted/50')} data-rule={rule.rule_code}>
      <Checkbox checked={checked} onCheckedChange={(c) => onToggle(c === true)} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-tight">{rule.title}</p>
        <p className="text-xs text-muted-foreground">
          {rule.source.section}
          {rule.applicable_scenarios.length === 1 && ` · chỉ phương án ${rule.applicable_scenarios[0]}`}
          {rule.min_units_purchased && ` · từ ${rule.min_units_purchased} căn`}
        </p>
      </div>
      <span className={cn('shrink-0 text-xs font-medium', rule.is_ambiguous && 'text-warning')}>{valueLabel(rule)}</span>
    </label>
  )
}
