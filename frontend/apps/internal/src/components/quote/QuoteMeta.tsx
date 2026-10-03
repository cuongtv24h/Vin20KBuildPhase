import { ArrowLeft, Building2, CalendarDays, CheckCircle2, Link2, Lock, ShieldX, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { EvidenceBackedClaim, Quote, QuoteAudit } from '@pricepolicy/api-client/contracts'
import { useActivePolicy, usePolicy } from '@pricepolicy/api-client/hooks'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { RiskFlagBadge } from '@pricepolicy/ui/components/common/RiskFlagBadge'
import { PdfStatusBadge, QuoteStatusBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { Alert, AlertDescription, AlertTitle } from '@pricepolicy/ui/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { formatDate, formatDateTime, maskPhone, truncateHash } from '@pricepolicy/ui/lib/format'
import { AUDIT_EVENT_LABEL, OBJECTIVE_LABEL, QUOTE_STATUS_LABEL, ROLE_LABEL, SEGMENT_LABEL } from '@pricepolicy/ui/lib/labels'
import { isLatest } from '@pricepolicy/ui/lib/quoteRules'
import { ClaimRow } from '@pricepolicy/ui/components/quote/Evidence'
import { useOpenEvidence } from '@pricepolicy/ui/components/quote/evidenceContext'

const hasText = (v: unknown): v is string => typeof v === 'string' && v.trim() !== '' && v.trim() !== '—'

function NotUpdated() {
  return <span className="font-normal text-muted-foreground/70">Chưa cập nhật</span>
}

/** "ZEN-A-1205 · Dự án" — chỉ hiện một lần nếu tên dự án trống hoặc trùng mã căn. */
function unitLabel(unit: Quote['unit']): string {
  const project = hasText(unit.project_name) && unit.project_name.trim() !== unit.unit_code ? unit.project_name.trim() : ''
  return project ? `${unit.unit_code} · ${project}` : unit.unit_code
}

/** "2PN · 68 m²" — bỏ phần thiếu dữ liệu (0/null/rỗng). */
function unitSpecs(unit: Quote['unit']): string {
  const parts: string[] = []
  if (Number(unit.bedrooms) > 0) parts.push(`${unit.bedrooms}PN`)
  if (Number(unit.area_m2) > 0) parts.push(`${unit.area_m2} m²`)
  return parts.join(' · ')
}

export function QuoteHeader({
  quote,
  backTo,
  backLabel,
  actions,
  onVersionChange,
}: {
  quote: Quote
  backTo: string
  backLabel: string
  actions?: ReactNode
  onVersionChange?: (version: number | undefined) => void
}) {
  const latest = isLatest(quote)
  return (
    <div className="space-y-3">
      <Link to={backTo} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> {backLabel}
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-2xl font-semibold tracking-tight">{quote.quote_id}</h1>
            {onVersionChange && quote.versions.length > 1 ? (
              <Select value={String(quote.quote_version)} onValueChange={(v) => onVersionChange(Number(v) === Math.max(...quote.versions.map((x) => x.quote_version)) ? undefined : Number(v))}>
                <SelectTrigger className="h-7 w-auto gap-1 px-2 text-xs" aria-label="Phiên bản">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {quote.versions.map((v) => (
                    <SelectItem key={v.quote_version} value={String(v.quote_version)}>
                      v{v.quote_version} · {QUOTE_STATUS_LABEL[v.status]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <span className="text-sm text-muted-foreground">v{quote.quote_version}</span>
            )}
            <QuoteStatusBadge status={quote.status} />
            {quote.pdf_status && <PdfStatusBadge status={quote.pdf_status} />}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <UserRound className="h-3.5 w-3.5" />{' '}
              {hasText(quote.transaction_context.customer_name) ? quote.transaction_context.customer_name : <NotUpdated />}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5" /> {unitLabel(quote.unit)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="h-3.5 w-3.5" /> {formatDateTime(quote.updated_at)}
            </span>
          </div>
        </div>
        {latest && actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {!latest && (
        <Alert>
          <Lock />
          <AlertTitle>Phiên bản {quote.quote_version} — chỉ đọc</AlertTitle>
          <AlertDescription>
            <button type="button" className="text-primary hover:underline" onClick={() => onVersionChange?.(undefined)}>
              Mở phiên bản mới nhất
            </button>
          </AlertDescription>
        </Alert>
      )}
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

export function ContextCard({ quote }: { quote: Quote }) {
  const c = quote.transaction_context
  // Tên điều khoản lấy từ chính văn bản đã áp dụng/viện dẫn (kể cả khi đang phân tích chưa có kết quả).
  const pinnedId = quote.policy_snapshot_ref?.policy_id ?? c.requested_policy_id
  const pinned = usePolicy(pinnedId)
  const active = useActivePolicy(pinnedId ? undefined : quote.unit.project_id, c.transaction_date)
  const rules = (pinnedId ? pinned.data : active.data)?.rules ?? []
  const titleOf = (code: string) =>
    rules.find((r) => r.rule_code === code)?.title ?? quote.scenarios.flatMap((s) => s.rule_evaluations).find((r) => r.rule_code === code)?.title ?? code
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Thông tin giao dịch</CardTitle>
      </CardHeader>
      <CardContent className="divide-y divide-border">
        <Row label="Khách hàng">{hasText(c.customer_name) ? c.customer_name : <NotUpdated />}</Row>
        <Row label="Điện thoại">{hasText(c.customer_phone) ? maskPhone(c.customer_phone) : <NotUpdated />}</Row>
        <Row label="Phân khúc">{SEGMENT_LABEL[c.customer_segment]}</Row>
        <Row label="Căn hộ">
          {[quote.unit.unit_code, unitSpecs(quote.unit) || null].filter(Boolean).join(' · ')}
          {!unitSpecs(quote.unit) && <span className="ml-1 font-normal text-muted-foreground/70">(Chưa có dữ liệu)</span>}
        </Row>
        <Row label="Giá niêm yết">
          <MoneyText amount={quote.unit.listed_price_before_tax_vnd} size="sm" />
        </Row>
        <Row label="Ngày giao dịch">{c.transaction_date ? formatDate(c.transaction_date) : <NotUpdated />}</Row>
        <Row label="Số căn">{c.units_quantity}</Row>
        <Row label="Tiêu chí">{OBJECTIVE_LABEL[c.objective]}</Row>
        <Row label="Chuyên viên">{quote.created_by.full_name}</Row>
        {quote.policy_snapshot_ref && (
          <div className="py-2 text-sm">
            <p className="text-muted-foreground">Chính sách áp dụng</p>
            <p className="font-medium">
              {quote.policy_snapshot_ref.title} · {quote.policy_snapshot_ref.policy_version}
            </p>
            <p className="font-mono text-[11px] text-muted-foreground" title={quote.policy_snapshot_ref.snapshot_hash}>
              {truncateHash(quote.policy_snapshot_ref.snapshot_hash, 14)}
            </p>
          </div>
        )}
        <div className="py-2 text-sm">
          <p className="mb-1 text-muted-foreground">Ưu đãi đề nghị xét</p>
          {c.selected_rule_codes.length === 0 ? (
            <p>Chỉ ưu đãi tự động theo hồ sơ</p>
          ) : (
            <ul className="space-y-0.5">
              {c.selected_rule_codes.map((code) => (
                <li key={code} className="font-medium">
                  {titleOf(code)}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className={quote.status === 'ANALYZING' ? 'hidden' : 'pt-2'}>
          <RiskFlagBadge flag={quote.risk_flag} />
          {quote.risk_flag.reasons.map((r) => (
            <p key={r} className="mt-1 text-xs text-muted-foreground">
              {r}
            </p>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

/** C-07: dòng thời gian audit append-only, mỗi sự kiện nối hash với sự kiện trước. */
export function AuditTimeline({ audit }: { audit: QuoteAudit }) {
  const events = [...audit.events].reverse()
  return (
    <div className="space-y-3">
      <p className={audit.chain_valid ? 'inline-flex items-center gap-1.5 text-xs font-medium text-success' : 'inline-flex items-center gap-1.5 text-xs font-medium text-destructive'}>
        {audit.chain_valid ? <CheckCircle2 className="h-3.5 w-3.5" /> : <ShieldX className="h-3.5 w-3.5" />}
        {audit.chain_valid ? `Chuỗi hash toàn vẹn · ${audit.events.length} sự kiện` : 'Chuỗi hash không khớp'}
      </p>
      <ol className="space-y-3">
        {events.map((e) => (
          <li key={e.event_id} className="relative border-l border-border pl-4" data-event={e.event_type}>
            <span className="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-background bg-primary" />
            <p className="text-sm font-medium leading-tight">
              {AUDIT_EVENT_LABEL[e.event_type]} <span className="text-xs font-normal text-muted-foreground">v{e.quote_version}</span>
            </p>
            <p className="text-xs text-muted-foreground">
              {e.actor.full_name}
              {e.actor.role !== 'SYSTEM' && ` · ${ROLE_LABEL[e.actor.role]}`} · {formatDateTime(e.occurred_at)}
            </p>
            {e.note && <p className="mt-1 rounded-md bg-muted/60 px-2.5 py-1.5 text-sm">{e.note}</p>}
            <p className="mt-0.5 inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground/80" title={e.event_hash}>
              <Link2 className="h-2.5 w-2.5" /> {e.event_hash.slice(0, 10)}
            </p>
          </li>
        ))}
      </ol>
    </div>
  )
}

/** Toàn bộ luận điểm Why kèm trạng thái chứng cứ — cho Quản lý thẩm định. */
export function ClaimsPanel({ claims }: { claims: EvidenceBackedClaim[] }) {
  const open = useOpenEvidence()
  const why = claims.filter((c) => c.direction === 'WHY')
  const flagged = why.filter((c) => c.support_status !== 'SUPPORTED').length
  return (
    <div className="space-y-2" data-testid="claims">
      {flagged > 0 && <p className="text-xs font-medium text-warning">{flagged} luận điểm cần lưu ý</p>}
      {why.map((c) => (
        <ClaimRow key={c.claim_id} claim={c} onOpen={() => open({ title: c.text, source: c.source_coordinates[0] ?? null, ruleCode: c.rule_code })} />
      ))}
    </div>
  )
}
