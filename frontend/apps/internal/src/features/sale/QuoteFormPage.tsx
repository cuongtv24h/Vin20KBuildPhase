import { ArrowLeft, Loader2, Sparkles } from 'lucide-react'
import { useState, type ComponentProps, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { BackendObjective, QuoteCreatePayload } from '@pricepolicy/api-client/contracts'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useCreateQuote, useLead, useQuote } from '@pricepolicy/api-client/hooks'
import { ErrorState, LoadingState, PageHeader } from '@pricepolicy/ui/components/common/PageStates'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@pricepolicy/ui/components/ui/radio-group'
import { cn } from '@pricepolicy/ui/lib/utils'
import { toast } from '@pricepolicy/ui/state/toastStore'

/** Đúng theo `OptimizationObjective` (6 giá trị) trong src/contracts/enums.py — backend thật. */
const BACKEND_OBJECTIVES: { value: BackendObjective; label: string }[] = [
  { value: 'MIN_NET_PRICE', label: 'Giá thực trả thấp nhất' },
  { value: 'MIN_INITIAL_CASH', label: 'Vốn ban đầu thấp nhất' },
  { value: 'MIN_MONTHLY_BURDEN', label: 'Gánh nặng hàng tháng thấp nhất' },
  { value: 'MIN_TOTAL_CASH_OUTFLOW', label: 'Tổng dòng tiền ra thấp nhất' },
  { value: 'MAX_BENEFIT_VALUE', label: 'Giá trị ưu đãi cao nhất' },
  { value: 'EARLY_HANDOVER', label: 'Bàn giao sớm' },
]

type FormState = {
  project_id: string
  unit_code: string
  listed_price_before_tax_vnd: number
  deposit_amount_vnd: number
  own_funds_vnd: number
  monthly_capacity_vnd: number
  objective: BackendObjective
}

const EMPTY: FormState = {
  project_id: '',
  unit_code: '',
  listed_price_before_tax_vnd: 0,
  deposit_amount_vnd: 100_000_000,
  own_funds_vnd: 1_000_000_000,
  monthly_capacity_vnd: 50_000_000,
  objective: 'MIN_INITIAL_CASH',
}

/**
 * /sale/quotes/new                 — khách vãng lai
 * /sale/quotes/new?dossier=LD-…    — từ hồ sơ Pre-Sales (chỉ dùng để gợi ý căn hộ, không có endpoint convert riêng)
 * /sale/quotes/:quoteId/revise     — backend hiện chưa có endpoint tạo phiên bản mới, tạo báo giá mới độc lập
 *
 * Ghi chú quan trọng — backend thật (src/api/endpoints/quotes.py) khác với thiết kế "đề xuất" cũ:
 *  - POST /api/v1/quotes chỉ nhận project_id + unit_code + listed_price_before_tax_vnd
 *    (+ deposit/own_funds/monthly_capacity + objective) và trả về hồ sơ đầy đủ ngay (201, đồng bộ,
 *    không phải 202 + SSE).
 *  - Không có endpoint danh mục căn hộ (GET /units 404) → không thể chọn qua danh sách, phải nhập
 *    tay project_id/unit_code.
 */
export function QuoteFormPage() {
  const { quoteId } = useParams()
  const [params] = useSearchParams()
  const dossierId = params.get('dossier')
  const source = useQuote(quoteId)
  const lead = useLead(dossierId)

  if ((quoteId && source.isLoading) || (dossierId && lead.isLoading)) return <LoadingState />
  if (quoteId && source.error) return <ErrorState error={source.error} onRetry={() => source.refetch()} />
  if (dossierId && lead.error) return <ErrorState error={lead.error} onRetry={() => lead.refetch()} />
  if (dossierId && !lead.data) return <ErrorState error={new Error('Không tìm thấy hồ sơ khách.')} />

  let initial = EMPTY
  if (source.data) {
    initial = {
      ...EMPTY,
      project_id: source.data.unit.project_id,
      unit_code: source.data.unit.unit_code,
      listed_price_before_tax_vnd: source.data.unit.listed_price_before_tax_vnd,
    }
  } else if (lead.data) {
    initial = {
      ...EMPTY,
      unit_code: lead.data.reference_plan?.scenarios[0]?.unit_code ?? lead.data.constraints.preferred_unit_code ?? '',
    }
  }
  return <QuoteForm key={quoteId ?? dossierId ?? 'new'} initial={initial} backTo={dossierId ? `/sale?id=${dossierId}` : quoteId ? `/sale/quotes/${quoteId}` : '/sale/quotes'} />
}

function QuoteForm({ initial, backTo }: { initial: FormState; backTo: string }) {
  const navigate = useNavigate()
  const [form, setForm] = useState<FormState>(initial)
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }))

  const create = useCreateQuote()

  const valid = form.project_id.trim().length > 0 && form.unit_code.trim().length > 0 && form.listed_price_before_tax_vnd > 0

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const body: QuoteCreatePayload = {
      project_id: form.project_id.trim(),
      unit_code: form.unit_code.trim(),
      listed_price_before_tax_vnd: form.listed_price_before_tax_vnd,
      deposit_amount_vnd: form.deposit_amount_vnd,
      own_funds_vnd: form.own_funds_vnd,
      monthly_capacity_vnd: form.monthly_capacity_vnd,
      objective: form.objective,
    }
    try {
      const result = await create.mutateAsync(body)
      toast.success('Đã tạo báo giá', result.quote_id)
      navigate(`/sale/quotes/${result.quote_id}`)
    } catch (err) {
      toast.error('Không thể tạo báo giá', errorMessage(err))
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <PageHeader
        eyebrow={
          <Link to={backTo} className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3.5 w-3.5" /> Báo giá
          </Link>
        }
        title="Báo giá chính thức"
      />

      <div className="grid gap-6 lg:grid-cols-[1fr,360px]">
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Dự án và căn hộ</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field id="project_id" label="Mã dự án">
                  <Input id="project_id" value={form.project_id} onChange={(e) => set('project_id', e.target.value)} required />
                </Field>
                <Field id="unit_code" label="Mã căn">
                  <Input id="unit_code" value={form.unit_code} onChange={(e) => set('unit_code', e.target.value)} required />
                </Field>
              </div>
              <Field id="price" label="Giá niêm yết trước thuế (VND)">
                <MoneyInput id="price" value={form.listed_price_before_tax_vnd} onValueChange={(v) => set('listed_price_before_tax_vnd', v)} required />
              </Field>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Dòng tiền dự kiến</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-3">
              <Field id="deposit" label="Tiền đặt cọc (VND)">
                <MoneyInput id="deposit" value={form.deposit_amount_vnd} onValueChange={(v) => set('deposit_amount_vnd', v)} />
              </Field>
              <Field id="own_funds" label="Vốn tự có (VND)">
                <MoneyInput id="own_funds" value={form.own_funds_vnd} onValueChange={(v) => set('own_funds_vnd', v)} />
              </Field>
              <Field id="monthly_capacity" label="Khả năng trả hàng tháng (VND)">
                <MoneyInput id="monthly_capacity" value={form.monthly_capacity_vnd} onValueChange={(v) => set('monthly_capacity_vnd', v)} />
              </Field>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Tiêu chí tối ưu</CardTitle>
            </CardHeader>
            <CardContent>
              <RadioGroup value={form.objective} onValueChange={(v) => set('objective', v as BackendObjective)} className="gap-2">
                {BACKEND_OBJECTIVES.map((o) => (
                  <label
                    key={o.value}
                    className={cn('flex cursor-pointer items-center gap-2.5 rounded-md border p-2.5 text-sm', form.objective === o.value ? 'border-primary bg-primary/[0.04]' : 'border-border hover:bg-muted/50')}
                  >
                    <RadioGroupItem value={o.value} /> {o.label}
                  </label>
                ))}
              </RadioGroup>
            </CardContent>
          </Card>
          <Button type="submit" className="w-full" size="lg" disabled={!valid || create.isPending} data-testid="analyze">
            {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Tạo báo giá
          </Button>
        </div>
      </div>
    </form>
  )
}

/** Ô nhập tiền VND: chỉ nhận chữ số, hiển thị dấu chấm nghìn; hiện "0" ban đầu và gõ số vào thì số 0 đó được thay đi. */
function MoneyInput({
  value,
  onValueChange,
  ...props
}: { value: number; onValueChange: (v: number) => void } & Omit<ComponentProps<typeof Input>, 'value' | 'onChange' | 'type'>) {
  return (
    <Input
      {...props}
      type="text"
      inputMode="numeric"
      autoComplete="off"
      className={cn('tabular-nums', props.className)}
      value={value.toLocaleString('vi-VN')}
      onChange={(e) => {
        const digits = e.target.value.replace(/\D/g, '').slice(0, 15)
        onValueChange(digits ? Number(digits) : 0)
      }}
    />
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
