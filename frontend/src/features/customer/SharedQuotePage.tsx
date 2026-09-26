import { QRCodeSVG } from 'qrcode.react'
import {
  BadgeCheck,
  CalendarCheck,
  CheckCircle2,
  FileWarning,
  Loader2,
  Mail,
  MessageCircleQuestion,
  Phone,
  Printer,
  ShieldCheck,
  ShieldX,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { CustomerQuoteView, CustomerScenario } from '@/api/contracts'
import { ApiError, errorMessage } from '@/api/errors'
import { useRespondToQuote, useSharedQuote, useVerifySharedQuote } from '@/api/hooks'
import { MoneyText } from '@/components/common/MoneyText'
import { LoadingState } from '@/components/common/PageStates'
import { RuleStatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { formatDate, formatDateTime, formatPercent, truncateHash } from '@/lib/format'
import { OBJECTIVE_SHORT_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { CustomerDecision } from '@/types/domain'

export function SharedQuotePage() {
  const { shareToken = '' } = useParams()
  const query = useSharedQuote(shareToken)

  if (query.isLoading) return <LoadingState className="py-32" label="Đang mở báo giá…" />
  if (query.error || !query.data) {
    const expired = query.error instanceof ApiError && query.error.status === 410
    return (
      <div className="container max-w-lg py-20 text-center">
        <FileWarning className="mx-auto h-10 w-10 text-muted-foreground" />
        <h1 className="mt-3 font-display text-2xl font-semibold">{expired ? 'Báo giá đã hết hạn' : 'Không tìm thấy báo giá'}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{errorMessage(query.error)}</p>
        <Button asChild className="mt-6">
          <Link to="/">Về trang dự án</Link>
        </Button>
      </div>
    )
  }
  return <QuoteDocument view={query.data} shareToken={shareToken} />
}

function QuoteDocument({ view, shareToken }: { view: CustomerQuoteView; shareToken: string }) {
  const [selectedPlan, setSelectedPlan] = useState(view.recommendedPlan ?? view.scenarios[0]?.plan)
  const selected = view.scenarios.find((s) => s.plan === selectedPlan) ?? view.scenarios[0]
  const pageUrl = typeof window !== 'undefined' ? window.location.href : ''

  return (
    <div className="container max-w-5xl space-y-6 py-8">
      <section className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 bg-primary px-6 py-5 text-primary-foreground">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-primary-foreground/60">Báo giá chính thức</p>
            <h1 className="font-display text-2xl font-semibold">
              Căn hộ {view.unit.unitCode} · {view.projectName}
            </h1>
          </div>
          <div className="text-right text-sm">
            <p className="font-semibold">{view.quoteId}</p>
            <p className="text-primary-foreground/70">
              Phát hành {formatDate(view.issuedAt)} · hiệu lực đến {formatDate(view.validUntil)}
            </p>
          </div>
        </div>
        <div className="grid gap-4 p-6 text-sm sm:grid-cols-4">
          <div>
            <p className="text-xs text-muted-foreground">Kính gửi</p>
            <p className="font-medium">{view.customerName}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Căn hộ</p>
            <p className="font-medium">
              {view.unit.block}, tầng {view.unit.floor} · {view.unit.bedrooms}PN · {view.unit.areaM2}m²
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Giá niêm yết</p>
            <MoneyText amount={view.unit.listedPrice} className="font-medium" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Chính sách áp dụng</p>
            <p className="font-medium">{view.policy ? `${view.policy.policyId} (${view.policy.version})` : '—'}</p>
          </div>
        </div>
      </section>

      {view.rationale && (
        <section className="rounded-2xl border border-gold/40 bg-gold/[0.06] p-5">
          <p className="text-xs font-semibold text-gold">Phương án phù hợp với ưu tiên "{OBJECTIVE_SHORT_LABEL[view.objective]}" của anh/chị</p>
          <p className="mt-1 text-sm leading-relaxed">{view.rationale}</p>
        </section>
      )}

      <section className="grid gap-3 md:grid-cols-3" role="tablist">
        {view.scenarios.map((s) => (
          <button
            key={s.plan}
            type="button"
            role="tab"
            aria-selected={selected?.plan === s.plan}
            onClick={() => setSelectedPlan(s.plan)}
            className={cn(
              'rounded-2xl border bg-white p-4 text-left shadow-sm transition-all',
              selected?.plan === s.plan ? 'border-primary ring-2 ring-primary/20' : 'border-border hover:border-primary/40',
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="font-medium">{s.planLabel}</p>
              {view.recommendedPlan === s.plan && <span className="rounded-full bg-gold/15 px-2 py-0.5 text-[10px] font-semibold text-gold">Đề xuất</span>}
            </div>
            <MoneyText amount={s.netPrice} size="lg" className="mt-2 block" />
            <p className="text-xs text-muted-foreground">
              Đợt đầu <MoneyText amount={s.initialPaymentVnd} size="sm" tone="muted" /> · {s.installmentsCount} đợt
            </p>
          </button>
        ))}
      </section>

      {selected && <ScenarioDetail scenario={selected} />}

      <div className="grid gap-6 lg:grid-cols-[1fr,320px]">
        <ResponsePanel view={view} shareToken={shareToken} />
        <div className="space-y-4">
          <section className="rounded-2xl border border-border bg-white p-5 shadow-sm">
            <p className="text-sm font-semibold">Chuyên viên tư vấn</p>
            <p className="mt-1 font-medium">{view.salesRep.fullName}</p>
            <a href={`tel:${view.salesRep.phone.replace(/\s/g, '')}`} className="mt-1 flex items-center gap-1.5 text-sm text-primary">
              <Phone className="h-3.5 w-3.5" /> {view.salesRep.phone}
            </a>
            <a href={`mailto:${view.salesRep.email}`} className="flex items-center gap-1.5 text-sm text-primary">
              <Mail className="h-3.5 w-3.5" /> {view.salesRep.email}
            </a>
          </section>
          <VerificationPanel view={view} shareToken={shareToken} pageUrl={pageUrl} />
          <Button variant="outline" className="w-full" onClick={() => window.print()}>
            <Printer className="h-4 w-4" /> In / Lưu PDF
          </Button>
        </div>
      </div>
    </div>
  )
}

function ScenarioDetail({ scenario }: { scenario: CustomerScenario }) {
  const priceRows = [
    { label: 'Giá niêm yết', amount: scenario.basePrice },
    { label: `Chiết khấu (${formatPercent(scenario.totalDiscountRate)})`, amount: -scenario.discountAmount },
    { label: 'Giá bán trước thuế', amount: scenario.priceBeforeVAT },
    { label: 'Thuế GTGT (10%)', amount: scenario.vatAmount },
    { label: 'Kinh phí bảo trì (2%)', amount: scenario.kpbtAmount },
  ]
  return (
    <section className="grid gap-6 rounded-2xl border border-border bg-white p-6 shadow-sm lg:grid-cols-2">
      <div className="space-y-4">
        <h2 className="font-display text-lg font-semibold">Chi tiết giá — {scenario.planLabel}</h2>
        <div className="divide-y divide-border text-sm">
          {priceRows.map((r) => (
            <div key={r.label} className="flex justify-between py-2">
              <span className="text-muted-foreground">{r.label}</span>
              <MoneyText amount={r.amount} size="sm" tone={r.amount < 0 ? 'success' : 'default'} />
            </div>
          ))}
          <div className="flex justify-between py-3">
            <span className="font-semibold">Tổng giá trị căn hộ</span>
            <MoneyText amount={scenario.netPrice} size="lg" />
          </div>
        </div>
        <div className="space-y-2">
          <p className="text-sm font-semibold">Ưu đãi & căn cứ</p>
          {scenario.ruleBreakdown.length === 0 && <p className="text-sm text-muted-foreground">Không có ưu đãi áp dụng.</p>}
          {scenario.ruleBreakdown.map((r) => (
            <div key={r.ruleCode} className="rounded-lg border border-border/70 p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium">{r.title}</p>
                <RuleStatusBadge status={r.status} className="shrink-0" />
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {r.reasonText}
              </p>
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-3">
        <h2 className="font-display text-lg font-semibold">Lịch thanh toán</h2>
        <div className="overflow-x-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Đợt</TableHead>
                <TableHead>Thời điểm</TableHead>
                <TableHead className="text-right">Tỷ lệ</TableHead>
                <TableHead className="text-right">Số tiền</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scenario.schedule.map((row) => (
                <TableRow key={row.label}>
                  <TableCell className="whitespace-nowrap font-medium">{row.label}</TableCell>
                  <TableCell className="text-sm">
                    {row.milestone}
                    {row.payer === 'BANK' && <span className="ml-1 text-xs text-primary">(ngân hàng giải ngân)</span>}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatPercent(row.ratio)}</TableCell>
                  <TableCell className="whitespace-nowrap text-right tabular-nums">
                    <MoneyText amount={row.amountVnd} size="sm" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {scenario.benefitValueVnd > 0 && (
          <p className="rounded-lg bg-success/10 p-3 text-sm text-success">
            Quà tặng kèm trị giá quy đổi <MoneyText amount={scenario.benefitValueVnd} size="sm" tone="success" className="font-semibold" />, không trừ
            vào giá bán.
          </p>
        )}
      </div>
    </section>
  )
}

function ResponsePanel({ view, shareToken }: { view: CustomerQuoteView; shareToken: string }) {
  const respond = useRespondToQuote(shareToken)
  const [dialog, setDialog] = useState<CustomerDecision | null>(null)
  const [note, setNote] = useState('')
  const [appointment, setAppointment] = useState('')

  if (view.customerResponse) {
    const accepted = view.customerResponse.decision === 'ACCEPTED'
    return (
      <section className="h-fit rounded-2xl border border-success/40 bg-white p-6 shadow-sm" data-testid="customer-response">
        <p className="inline-flex items-center gap-2 font-semibold text-success">
          <CheckCircle2 className="h-5 w-5" /> {accepted ? 'Anh/chị đã đồng ý báo giá' : 'Đã gửi yêu cầu tư vấn thêm'}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">Ghi nhận lúc {formatDateTime(view.customerResponse.at)}.</p>
        {view.customerResponse.preferredAppointment && (
          <p className="mt-2 text-sm">Lịch hẹn mong muốn: {formatDateTime(view.customerResponse.preferredAppointment)}</p>
        )}
        {view.customerResponse.note && <p className="mt-2 rounded-md bg-muted/60 p-2.5 text-sm">{view.customerResponse.note}</p>}
        <p className="mt-3 text-sm text-muted-foreground">Chuyên viên {view.salesRep.fullName} sẽ liên hệ lại với anh/chị.</p>
      </section>
    )
  }

  async function handleConfirm() {
    if (!dialog) return
    const ok = await respond
      .mutateAsync({
        decision: dialog,
        note,
        preferredAppointment: dialog === 'ACCEPTED' && appointment ? new Date(appointment).toISOString() : null,
      })
      .catch(() => null)
    if (ok) setDialog(null)
  }

  return (
    <section className="h-fit space-y-4 rounded-2xl border border-border bg-white p-6 shadow-sm">
      <div>
        <h2 className="font-display text-lg font-semibold">Phản hồi báo giá</h2>
        <p className="text-sm text-muted-foreground">Báo giá có hiệu lực đến {formatDate(view.validUntil)}.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => setDialog('ACCEPTED')}>
          <CalendarCheck className="h-4 w-4" /> Đồng ý & đặt lịch ký cọc
        </Button>
        <Button variant="outline" onClick={() => setDialog('NEED_CONSULTATION')}>
          <MessageCircleQuestion className="h-4 w-4" /> Cần tư vấn thêm
        </Button>
      </div>

      <Dialog open={dialog !== null} onOpenChange={(open) => !open && setDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{dialog === 'ACCEPTED' ? 'Đặt lịch ký cọc' : 'Yêu cầu tư vấn thêm'}</DialogTitle>
            <DialogDescription>
              {dialog === 'ACCEPTED'
                ? 'Chọn thời gian thuận tiện, chuyên viên sẽ xác nhận lịch hẹn với anh/chị.'
                : 'Cho chúng tôi biết anh/chị cần làm rõ thêm điều gì.'}
            </DialogDescription>
          </DialogHeader>
          {dialog === 'ACCEPTED' && (
            <div className="space-y-1.5">
              <Label htmlFor="appointment">Thời gian mong muốn</Label>
              <Input id="appointment" type="datetime-local" value={appointment} onChange={(e) => setAppointment(e.target.value)} />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="response-note">Lời nhắn</Label>
            <Textarea id="response-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          {respond.isError && <p className="text-sm text-destructive">{errorMessage(respond.error)}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)}>
              Huỷ
            </Button>
            <Button onClick={handleConfirm} disabled={respond.isPending || (dialog === 'NEED_CONSULTATION' && !note.trim())}>
              {respond.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Gửi phản hồi
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}

function VerificationPanel({ view, shareToken, pageUrl }: { view: CustomerQuoteView; shareToken: string; pageUrl: string }) {
  const verify = useVerifySharedQuote(shareToken)
  return (
    <section className="space-y-3 rounded-2xl border border-border bg-white p-5 shadow-sm">
      <p className="inline-flex items-center gap-1.5 text-sm font-semibold">
        <BadgeCheck className="h-4 w-4 text-primary" /> Xác thực báo giá
      </p>
      <div className="flex items-start gap-3">
        <QRCodeSVG value={pageUrl} size={96} className="shrink-0 rounded border border-border p-1" />
        <div className="min-w-0 text-xs text-muted-foreground">
          <p>Ký duyệt bởi {view.approvedBy}</p>
          <p className="mt-1 font-mono text-foreground">{truncateHash(view.snapshotHash, 8)}</p>
        </div>
      </div>
      <Button variant="outline" size="sm" className="w-full" onClick={() => verify.mutate()} disabled={verify.isPending}>
        {verify.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />} Kiểm tra tính toàn vẹn
      </Button>
      {verify.data && (
        <p className={cn('inline-flex items-center gap-1.5 text-xs font-medium', verify.data.valid ? 'text-success' : 'text-destructive')}>
          {verify.data.valid ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldX className="h-3.5 w-3.5" />}
          {verify.data.valid ? 'Nội dung khớp bản đã ký duyệt' : 'Nội dung không khớp bản đã ký duyệt'}
        </p>
      )}
      {verify.isError && <p className="text-xs text-destructive">{errorMessage(verify.error)}</p>}
    </section>
  )
}
