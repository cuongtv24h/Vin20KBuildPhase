import { ArrowLeft, BedDouble, CheckCircle2, Compass, Gift, Loader2, Maximize2, Phone, Send } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { LeadReceipt } from '@/api/contracts'
import { errorMessage } from '@/api/errors'
import { useEstimate, useProjectOverviews, useSubmitLead, useUnit } from '@/api/hooks'
import { MoneyText } from '@/components/common/MoneyText'
import { ErrorState, LoadingState } from '@/components/common/PageStates'
import { UnitStatusBadge } from '@/components/common/StatusBadge'
import { HOTLINE } from '@/components/layout/CustomerLayout'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { formatDate, formatDateTime, formatPercent } from '@/lib/format'
import { OBJECTIVE_OPTIONS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { CustomerSegment, OptimizationObjective } from '@/types/domain'

export function UnitDetailPage() {
  const { unitCode = '' } = useParams()
  const unit = useUnit(unitCode)
  const overviews = useProjectOverviews()
  const [segment, setSegment] = useState<CustomerSegment>('NEW_CUSTOMER')
  const estimate = useEstimate(unit.data ? { unitCode, customerSegment: segment } : null)
  const [receipt, setReceipt] = useState<LeadReceipt | null>(null)

  if (unit.isLoading) return <LoadingState className="py-32" />
  if (unit.error || !unit.data) {
    return (
      <div className="container py-16">
        <ErrorState error={unit.error ?? new Error('Không tìm thấy căn hộ.')} />
      </div>
    )
  }

  const u = unit.data
  const project = overviews.data?.find((o) => o.project.projectId === u.projectId)?.project
  const bestPlan = estimate.data?.plans.reduce<(typeof estimate.data.plans)[number] | null>(
    (best, p) => (!best || p.netPrice < best.netPrice ? p : best),
    null,
  )

  return (
    <div className="container space-y-6 py-8">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Bảng hàng
      </Link>

      <div className="grid gap-6 lg:grid-cols-[1fr,380px]">
        <div className="space-y-6">
          <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm text-muted-foreground">{u.projectName}</p>
                <h1 className="font-display text-3xl font-semibold tracking-tight text-primary">Căn hộ {u.unitCode}</h1>
                <p className="text-sm text-muted-foreground">
                  {u.block}, tầng {u.floor}
                  {project ? ` · Bàn giao ${project.handoverTime}` : ''}
                </p>
              </div>
              <UnitStatusBadge status={u.status} />
            </div>
            <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                { icon: BedDouble, label: 'Phòng ngủ', value: `${u.bedrooms} PN` },
                { icon: Maximize2, label: 'Diện tích', value: `${u.areaM2} m²` },
                { icon: Compass, label: 'Hướng nhìn', value: u.view },
              ].map((item) => (
                <div key={item.label}>
                  <p className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <item.icon className="h-3.5 w-3.5" /> {item.label}
                  </p>
                  <p className="font-medium">{item.value}</p>
                </div>
              ))}
              <div>
                <p className="text-xs text-muted-foreground">Giá niêm yết</p>
                <MoneyText amount={u.listedPrice} className="font-semibold" />
              </div>
            </div>
          </section>

          <section className="space-y-4 rounded-2xl border border-border bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-display text-xl font-semibold">Giá tham khảo theo phương án thanh toán</h2>
                {estimate.data?.policy && (
                  <p className="text-sm text-muted-foreground">
                    Theo {estimate.data.policy.title}, áp dụng đến {formatDate(estimate.data.policy.effectiveTo)}
                  </p>
                )}
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <Switch
                  checked={segment === 'EXISTING_RESIDENT'}
                  onCheckedChange={(checked) => setSegment(checked ? 'EXISTING_RESIDENT' : 'NEW_CUSTOMER')}
                />
                Tôi đã sở hữu sản phẩm VLandFuture
              </label>
            </div>

            {estimate.isLoading && <LoadingState label="Đang tính giá tham khảo…" className="py-8" />}
            {estimate.error && <ErrorState error={estimate.error} />}
            {estimate.data && estimate.data.plans.length === 0 && (
              <p className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
                Dự án đang cập nhật chính sách bán hàng mới. Vui lòng để lại thông tin để được tư vấn giá.
              </p>
            )}
            {estimate.data && estimate.data.plans.length > 0 && (
              <div className={cn('grid gap-3 md:grid-cols-3', estimate.isFetching && 'opacity-60')}>
                {estimate.data.plans.map((p) => (
                  <div
                    key={p.plan}
                    className={cn(
                      'flex flex-col rounded-xl border p-4',
                      bestPlan?.plan === p.plan ? 'border-gold/60 bg-gold/[0.05]' : 'border-border',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium leading-tight">{p.planLabel}</p>
                      {bestPlan?.plan === p.plan && <span className="rounded-full bg-gold/15 px-2 py-0.5 text-[10px] font-semibold text-gold">Giá tốt nhất</span>}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{p.description}</p>
                    <div className="mt-3">
                      <p className="text-xs text-muted-foreground">Tổng giá sau ưu đãi (gồm VAT, KPBT)</p>
                      <MoneyText amount={p.netPrice} size="lg" />
                      {p.totalDiscountRate > 0 && <p className="text-xs text-success">Đã giảm {formatPercent(p.totalDiscountRate)}</p>}
                    </div>
                    <div className="mt-3 border-t border-border pt-2 text-sm">
                      <p className="text-xs text-muted-foreground">Thanh toán đợt đầu</p>
                      <MoneyText amount={p.initialPaymentVnd} size="sm" className="font-medium" />
                      <p className="text-xs text-muted-foreground">{p.installmentsCount} đợt thanh toán</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {estimate.data && estimate.data.gifts.length > 0 && (
              <div className="rounded-lg bg-muted/60 p-3 text-sm">
                <p className="mb-1 inline-flex items-center gap-1.5 font-medium">
                  <Gift className="h-4 w-4 text-gold" /> Quà tặng có thể lựa chọn khi ký HĐMB
                </p>
                <ul className="grid gap-0.5 sm:grid-cols-2">
                  {estimate.data.gifts.map((g) => (
                    <li key={g.title}>
                      · {g.title} (<MoneyText amount={g.cashEquivalentVnd} size="sm" />)
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Giá tham khảo cập nhật {estimate.data ? formatDateTime(estimate.data.estimatedAt) : '—'}. Giá trị chính thức, ưu đãi cộng dồn và
              lịch thanh toán chi tiết được thể hiện trên báo giá do chuyên viên gửi sau khi được phê duyệt.
            </p>
          </section>
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          {receipt ? (
            <LeadReceiptCard receipt={receipt} />
          ) : (
            <LeadForm unitCode={u.unitCode} segment={segment} disabled={u.status === 'SOLD'} onSubmitted={setReceipt} />
          )}
        </aside>
      </div>
    </div>
  )
}

function LeadForm({
  unitCode,
  segment,
  disabled,
  onSubmitted,
}: {
  unitCode: string
  segment: CustomerSegment
  disabled: boolean
  onSubmitted: (r: LeadReceipt) => void
}) {
  const submit = useSubmitLead()
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [objective, setObjective] = useState<OptimizationObjective>('MIN_NET_PRICE')
  const [note, setNote] = useState('')
  const [consent, setConsent] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const receipt = await submit
      .mutateAsync({ fullName, phone, email, unitCode, customerSegment: segment, objective, note })
      .catch(() => null)
    if (receipt) onSubmitted(receipt)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-2xl border border-border bg-white p-5 shadow-sm">
      <div>
        <h2 className="font-display text-lg font-semibold">Nhận báo giá chính thức</h2>
        <p className="text-sm text-muted-foreground">Chuyên viên sẽ liên hệ và gửi báo giá căn {unitCode} cho bạn.</p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="lead-name">Họ và tên</Label>
        <Input id="lead-name" value={fullName} onChange={(e) => setFullName(e.target.value)} required disabled={disabled} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="lead-phone">Số điện thoại</Label>
          <Input id="lead-phone" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required disabled={disabled} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lead-email">Email</Label>
          <Input id="lead-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={disabled} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="lead-objective">Bạn ưu tiên điều gì?</Label>
        <Select value={objective} onValueChange={(v) => setObjective(v as OptimizationObjective)} disabled={disabled}>
          <SelectTrigger id="lead-objective">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OBJECTIVE_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="lead-note">Ghi chú</Label>
        <Textarea
          id="lead-note"
          rows={3}
          placeholder="Ví dụ: muốn vay ngân hàng, mua 2 căn, thời gian thuận tiện để gọi…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={disabled}
        />
      </div>
      <label className="flex items-start gap-2 text-xs text-muted-foreground">
        <Checkbox checked={consent} onCheckedChange={(c) => setConsent(c === true)} className="mt-0.5" disabled={disabled} />
        Tôi đồng ý để VLandFuture liên hệ tư vấn và xử lý thông tin cá nhân theo chính sách bảo mật.
      </label>
      {submit.isError && <p className="text-sm text-destructive">{errorMessage(submit.error)}</p>}
      <Button type="submit" className="w-full" disabled={disabled || !consent || submit.isPending}>
        {submit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        {disabled ? 'Căn hộ đã có chủ' : 'Gửi yêu cầu'}
      </Button>
      <p className="text-center text-xs text-muted-foreground">
        Hoặc gọi{' '}
        <a href={`tel:${HOTLINE.replace(/\s/g, '')}`} className="inline-flex items-center gap-1 font-medium text-primary">
          <Phone className="h-3 w-3" /> {HOTLINE}
        </a>
      </p>
    </form>
  )
}

function LeadReceiptCard({ receipt }: { receipt: LeadReceipt }) {
  return (
    <div className="space-y-4 rounded-2xl border border-success/40 bg-white p-6 text-center shadow-sm" data-testid="lead-receipt">
      <CheckCircle2 className="mx-auto h-10 w-10 text-success" />
      <div className="space-y-1">
        <h2 className="font-display text-lg font-semibold">Đã nhận yêu cầu của bạn</h2>
        <p className="text-sm text-muted-foreground">
          Mã yêu cầu <span className="font-semibold text-foreground">{receipt.leadId}</span> · {formatDateTime(receipt.createdAt)}
        </p>
      </div>
      <ol className="space-y-2 text-left text-sm">
        <li>1. Chuyên viên kinh doanh gọi xác nhận nhu cầu trong giờ làm việc.</li>
        <li>2. Báo giá căn {receipt.unitCode} được lập và Quản lý phê duyệt.</li>
        <li>3. Bạn nhận đường dẫn báo giá chính thức qua Zalo/SMS/Email.</li>
      </ol>
      <Button asChild variant="outline" className="w-full">
        <Link to="/">Xem căn hộ khác</Link>
      </Button>
    </div>
  )
}
