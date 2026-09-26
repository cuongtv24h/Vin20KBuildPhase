import { ArrowLeft, Building2, CalendarDays, Phone, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useActivePolicy } from '@/api/hooks'
import { MoneyText } from '@/components/common/MoneyText'
import { RiskFlagBadge } from '@/components/common/RiskFlagBadge'
import { WorkflowStatusBadge } from '@/components/common/StatusBadge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatDateTime } from '@/lib/format'
import { OBJECTIVE_SHORT_LABEL, SEGMENT_LABEL } from '@/lib/labels'
import type { Quote } from '@/types/domain'

export function QuoteHeader({ quote, backTo, backLabel, actions }: { quote: Quote; backTo: string; backLabel: string; actions?: ReactNode }) {
  return (
    <div className="space-y-3">
      <Link to={backTo} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> {backLabel}
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-2xl font-semibold tracking-tight">{quote.quoteId}</h1>
            <span className="text-sm text-muted-foreground">phiên bản {quote.version}</span>
            <WorkflowStatusBadge status={quote.status} />
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <UserRound className="h-3.5 w-3.5" /> {quote.context.customerName}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5" /> {quote.unit.unitCode} · {quote.unit.projectName}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="h-3.5 w-3.5" /> Cập nhật {formatDateTime(quote.updatedAt)}
            </span>
          </div>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{children}</span>
    </div>
  )
}

/** Thông tin đầu vào của phiên bản hồ sơ — dùng ở cột bên cho Sale/Quản lý/Admin. */
export function QuoteContextCard({ quote }: { quote: Quote }) {
  const policy = useActivePolicy(quote.unit.projectId, quote.context.transactionDate)
  const titleOf = (code: string) =>
    policy.data?.rules.find((r) => r.ruleCode === code)?.title ??
    quote.scenarios.flatMap((s) => s.ruleBreakdown).find((r) => r.ruleCode === code)?.title ??
    code
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Thông tin giao dịch</CardTitle>
      </CardHeader>
      <CardContent className="divide-y divide-border">
        <Row label="Khách hàng">{quote.context.customerName}</Row>
        <Row label="Điện thoại">
          <span className="inline-flex items-center gap-1">
            <Phone className="h-3 w-3" /> {quote.context.customerPhone}
          </span>
        </Row>
        <Row label="Phân khúc">{SEGMENT_LABEL[quote.context.customerSegment]}</Row>
        <Row label="Căn hộ">
          {quote.unit.unitCode} · {quote.unit.bedrooms}PN · {quote.unit.areaM2}m²
        </Row>
        <Row label="Giá niêm yết">
          <MoneyText amount={quote.unit.listedPrice} size="sm" />
        </Row>
        <Row label="Số căn mua">{quote.context.unitsQuantity}</Row>
        <Row label="Ngày giao dịch">{formatDate(quote.context.transactionDate)}</Row>
        <Row label="Mục tiêu">{OBJECTIVE_SHORT_LABEL[quote.context.objective]}</Row>
        <Row label="Chuyên viên">{quote.ownerName}</Row>
        <div className="py-2 text-sm">
          <p className="mb-1 text-muted-foreground">Ưu đãi đề nghị xét</p>
          {quote.context.selectedRuleCodes.length === 0 ? (
            <p className="text-muted-foreground">Chỉ ưu đãi tự động theo hồ sơ</p>
          ) : (
            <ul className="space-y-0.5">
              {quote.context.selectedRuleCodes.map((code) => (
                <li key={code} className="font-medium">
                  · {titleOf(code)}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="pt-2">
          <p className="mb-1 text-sm text-muted-foreground">Mức rủi ro</p>
          <RiskFlagBadge flag={quote.riskFlag} />
          {quote.riskFlag.reasons.map((r) => (
            <p key={r} className="mt-1 text-xs text-muted-foreground">
              {r}
            </p>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
