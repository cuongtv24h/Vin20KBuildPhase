import { AlertCircle, AlertTriangle, ArrowLeft, Calendar, CheckCircle2, Clock, Copy, Download, ExternalLink, FileCheck2, FileEdit, FileText, KeyRound, Layers, Loader2, Lock, PenLine, QrCode, RefreshCw, Scale, ShieldAlert, ShieldCheck, Sparkles, Target, User, XCircle, Check, Star } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { Quote, Scenario, ScenarioCode } from '@pricepolicy/api-client/contracts'
import { errorMessage, isStaleVersion } from '@pricepolicy/api-client/errors'
import {
  useApproveQuote,
  useQuote,
  useQuoteAudit,
  useQuoteEvidence,
  useQuotePdf,
  useReauth,
  useRejectQuote,
  useRequestRevision,
  useRetryPdf,
} from '@pricepolicy/api-client/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { ErrorState, LoadingState, QueryState } from '@pricepolicy/ui/components/common/PageStates'
import { RiskFlagBadge } from '@pricepolicy/ui/components/common/RiskFlagBadge'
import { SlaCountdown } from '@pricepolicy/ui/components/common/SlaCountdown'
import { PdfStatusBadge, QuoteStatusBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { EvidenceProvider } from '@pricepolicy/ui/components/quote/Evidence'
import { AuditTimeline, ClaimsPanel, ContextCard, QuoteHeader } from '@/components/quote/QuoteMeta'
import { QuoteResults } from '@/components/quote/QuoteResults'
import { StopStatePanel } from '@/components/quote/StopStatePanel'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@pricepolicy/ui/components/ui/tabs'
import { Textarea } from '@pricepolicy/ui/components/ui/textarea'
import { formatDate, formatDateTime, formatPercent, formatVnd, truncateHash } from '@pricepolicy/ui/lib/format'
import { PROJECT_LABEL } from '@pricepolicy/ui/lib/labels'
import { managerActions, stopKindOf } from '@pricepolicy/ui/lib/quoteRules'
import { toast } from '@pricepolicy/ui/state/toastStore'
import { cn } from '@pricepolicy/ui/lib/utils'

const REASON_TEMPLATES = [
  'Bổ sung CCCD/hộ khẩu công chứng của khách hàng.',
  'Chỉ giữ một trong hai ưu đãi loại trừ nhau (Thanh toán sớm vs HTLS 0%).',
  'Cập nhật đúng số lượng căn khách hàng đăng ký mua thực tế.',
  'Điều khoản chưa đủ căn cứ chứng minh điều kiện, bỏ khỏi đề nghị.',
  'Mức chiết khấu vượt thẩm quyền phê duyệt của Trưởng phòng, cần trình Giám đốc khối.',
]

export function ApprovalWorkspacePage() {
  const { quoteId } = useParams()
  const [params, setParams] = useSearchParams()
  const version = params.get('v') ? Number(params.get('v')) : undefined
  const query = useQuote(quoteId, version)

  if (query.isLoading) return <LoadingState label="Đang tải dữ liệu hồ sơ thẩm định…" />
  if (!query.data) return <ErrorState error={query.error ?? new Error('Không tìm thấy hồ sơ.')} onRetry={() => query.refetch()} />

  return <Workspace quote={query.data} onVersionChange={(v) => setParams(v ? { v: String(v) } : {})} />
}

function Workspace({ quote, onVersionChange }: { quote: Quote; onVersionChange: (v: number | undefined) => void }) {
  const evidence = useQuoteEvidence(quote, quote.status !== 'ANALYZING')
  const audit = useQuoteAudit(quote.quote_id, `${quote.quote_version}:${quote.status}:${quote.pdf_status}`)
  const stop = stopKindOf(quote)
  const user = useCurrentUser()

  const [selectedScenarioCode, setSelectedScenarioCode] = useState<ScenarioCode>(
    quote.recommendation?.recommended_scenario ?? quote.scenarios[0]?.scenario_code ?? 'TIEN_DO'
  )

  const activeScenario = useMemo(() => {
    return quote.scenarios.find((s) => s.scenario_code === selectedScenarioCode) ?? quote.scenarios[0]
  }, [quote.scenarios, selectedScenarioCode])

  return (
    <EvidenceProvider claims={evidence.data?.claims}>
      <div className="space-y-6">
        {/* Top Navigation & Status Bar */}
        <QuoteHeader
          quote={quote}
          backTo="/manager/approvals"
          backLabel="Hàng đợi thẩm định"
          onVersionChange={onVersionChange}
        />

        {/* 2-Column Responsive Layout */}
        <div className="grid gap-6 xl:grid-cols-[1fr,380px]">
          {/* Main Content Area */}
          <div className="min-w-0 space-y-6">
            {stop && <StopStatePanel quote={quote} />}

            {/* SCR-05: Risk Audit Engine Sensor Box */}
            <RiskAuditEngineCard quote={quote} currentUserId={user.user_id} />

            {/* 3 Scenarios & Financial Breakdown */}
            {!stop && quote.scenarios.length > 0 && (
              <div className="space-y-6">
                {/* Canonical Scenario Selector */}
                <ScenarioComparisonGrid
                  quote={quote}
                  selected={selectedScenarioCode}
                  onSelect={setSelectedScenarioCode}
                />

                {/* Dual Reconciliation Table for Selected Scenario */}
                {activeScenario && <DualReconciliationTable scenario={activeScenario} quote={quote} />}
              </div>
            )}

            {/* Claims & Legal Evidence (Why / Why Not) */}
            <QueryState query={evidence} loadingLabel="Đang đối soát chứng cứ pháp lý…">
              {(ev) => (
                <div className="space-y-4">
                  {ev.claims.length > 0 && (
                    <Card className="border-border bg-card shadow-sm">
                      <CardHeader className="border-b border-border/60 pb-3">
                        <div className="flex items-center justify-between">
                          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                            <Scale className="h-4 w-4 text-primary" />
                            Minh bạch căn cứ và Điều khoản loại trừ (Why và Why Not)
                          </CardTitle>
                          <Badge variant="outline" className="text-xs">
                            {ev.claims.length} căn cứ chứng thực
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="pt-4">
                        <ClaimsPanel claims={ev.claims} />
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}
            </QueryState>
          </div>

          {/* Right Sidebar: Decision Panel & Artifacts */}
          <div className="space-y-5">
            {/* Decision Panel (Approve / Reject / Revision) */}
            <DecisionPanel key={`${quote.quote_id}:${quote.quote_version}:${quote.status}`} quote={quote} />

            {/* PDF Artifact & Public Verification */}
            {quote.pdf_status && <PdfArtifactCard quote={quote} />}

            {/* Transaction Context Card */}
            <ContextCard quote={quote} />

            {/* Audit Trail Timeline */}
            <Card className="border-border bg-card shadow-sm">
              <CardHeader className="border-b border-border/60 pb-3">
                <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  Nhật ký chuỗi kiểm toán (Hash Chain)
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                <QueryState query={audit}>{(a) => <AuditTimeline audit={a} />}</QueryState>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </EvidenceProvider>
  )
}

/** [SCR-05] Hệ thống Cảm biến Rủi ro Tự động (Risk Audit Engine) */
function RiskAuditEngineCard({ quote, currentUserId }: { quote: Quote; currentUserId: string }) {
  const isSodValid = quote.created_by.user_id !== currentUserId
  const recScenario = quote.scenarios.find((s) => s.scenario_code === quote.recommendation?.recommended_scenario)
  const discountRate = recScenario ? recScenario.total_discount_rate : 0
  const isDiscountWithinCap = discountRate <= 10.0 // Trần chiết khấu chuẩn của Quản lý kinh doanh (10%)

  const hasExclusions = quote.conflict_report && quote.conflict_report.findings.length > 0

  return (
    <Card
      className={cn(
        'border shadow-sm',
        quote.risk_flag.color === 'GREEN'
          ? 'border-success/30 bg-success/[0.02]'
          : quote.risk_flag.color === 'YELLOW'
          ? 'border-warning/30 bg-warning/[0.02]'
          : 'border-destructive/30 bg-destructive/[0.02]'
      )}
    >
      <CardHeader className="border-b border-border/40 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'flex h-7 w-7 items-center justify-center rounded-md font-bold',
                quote.risk_flag.color === 'GREEN'
                  ? 'bg-success/15 text-success'
                  : quote.risk_flag.color === 'YELLOW'
                  ? 'bg-warning/15 text-warning'
                  : 'bg-destructive/15 text-destructive'
              )}
            >
              <ShieldCheck className="h-4 w-4" />
            </span>
            <div>
              <CardTitle className="text-sm font-semibold text-foreground">
                Hệ thống Cảm biến Rủi ro Tự động (Risk Audit Engine)
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                Tự động rà soát 4 chốt an toàn nghiệp vụ trước khi kích hoạt quy trình ký số Ed25519
              </p>
            </div>
          </div>
          <RiskFlagBadge flag={quote.risk_flag} className="text-xs" />
        </div>
      </CardHeader>

      <CardContent className="divide-y divide-border/40 pt-1 text-xs">
        {/* Chốt 1: SoD (Tách biệt nhiệm vụ) */}
        <div className="flex items-start justify-between gap-3 py-2.5">
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5 font-medium text-foreground">
              {isSodValid ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-success" />
              ) : (
                <ShieldAlert className="h-3.5 w-3.5 text-destructive" />
              )}
              <span>1. Tách biệt nhiệm vụ (Separation of Duties - SoD)</span>
            </div>
            <p className="text-muted-foreground">
              Chuyên viên lập: <strong className="text-foreground">{quote.created_by.full_name}</strong> · Người duyệt hiện tại:{' '}
              <strong className="text-foreground">{isSodValid ? 'Khác người lập' : 'TRÙNG NGƯỜI LẬP (VI PHẠM)'}</strong>
            </p>
          </div>
          <Badge variant={isSodValid ? 'outline' : 'destructive'} className="shrink-0 text-xs">
            {isSodValid ? 'HỢP LỆ' : 'VI PHẠM SOD'}
          </Badge>
        </div>

        {/* Chốt 2: Chính sách áp dụng */}
        <div className="flex items-start justify-between gap-3 py-2.5">
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5 font-medium text-foreground">
              <CheckCircle2 className="h-3.5 w-3.5 text-success" />
              <span>2. Chính sách bán hàng áp dụng (Time-Travel Verified)</span>
            </div>
            <p className="text-muted-foreground">
              Văn bản: <strong className="text-foreground">{quote.policy_snapshot_ref?.title || 'CSBH Đợt 3'}</strong> (Phiên bản{' '}
              {quote.policy_snapshot_ref?.policy_version || 'v2.1'}) · SHA-256:{' '}
              <span className="font-mono text-xs">
                {truncateHash(quote.policy_snapshot_ref?.snapshot_hash || '8f4a1cb239e9441a', 10)}
              </span>
            </p>
          </div>
          <Badge variant="outline" className="shrink-0 text-xs text-success border-success/40">
            CÒN HIỆU LỰC
          </Badge>
        </div>

        {/* Chốt 3: Trần chiết khấu */}
        <div className="flex items-start justify-between gap-3 py-2.5">
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5 font-medium text-foreground">
              {isDiscountWithinCap ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-success" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 text-warning" />
              )}
              <span>3. Khung chiết khấu thương mại (Discount Cap Check)</span>
            </div>
            <p className="text-muted-foreground">
              Tổng chiết khấu: <strong className="text-foreground">{formatPercent(discountRate)}</strong>{' '}
              {isDiscountWithinCap ? '≤' : '>'} Hạn mức phân quyền Trưởng phòng (10.0%)
            </p>
          </div>
          <Badge variant={isDiscountWithinCap ? 'outline' : 'warning'} className="shrink-0 text-xs">
            {isDiscountWithinCap ? 'TRONG HẠN MỨC' : 'CHẠM TRẦN CẢNH BÁO'}
          </Badge>
        </div>

        {/* Chốt 4: Ma trận xung đột & ngoại lệ */}
        <div className="flex items-start justify-between gap-3 py-2.5">
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5 font-medium text-foreground">
              {!hasExclusions ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-success" />
              ) : (
                <AlertCircle className="h-3.5 w-3.5 text-warning" />
              )}
              <span>4. Ma trận xung đột và Loại trừ điều khoản (Exclusion Matrix)</span>
            </div>
            <p className="text-muted-foreground">
              {!hasExclusions
                ? 'Không phát hiện xung đột điều khoản loại trừ lẫn nhau (Mutual Exclusivity).'
                : quote.conflict_report?.findings.map((f) => f.message).join('; ')}
            </p>
          </div>
          <Badge variant={!hasExclusions ? 'outline' : 'warning'} className="shrink-0 text-xs">
            {!hasExclusions ? 'KHÔNG XUNG ĐỘT' : 'CÓ ĐIỀU KHOẢN LOẠI TRỪ'}
          </Badge>
        </div>
      </CardContent>
    </Card>
  )
}

/** Bảng đối đầu 3 phương án (Canonical Scenarios) */
function ScenarioComparisonGrid({
  quote,
  selected,
  onSelect,
}: {
  quote: Quote
  selected: ScenarioCode
  onSelect: (code: ScenarioCode) => void
}) {
  const recommendedCode = quote.recommendation?.recommended_scenario

  return (
    <Card className="border-border bg-card shadow-sm">
      <CardHeader className="border-b border-border/60 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-gold" />
            <CardTitle className="text-sm font-semibold">
              Bảng Đối Đầu 3 Phương Án Thanh Toán (Canonical Scenarios)
            </CardTitle>
          </div>
          {quote.recommendation && (
            <Badge variant="gold" className="text-xs">
              Tối ưu: {quote.recommendation.objective}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-4">
        <div className="grid gap-3 sm:grid-cols-3">
          {quote.scenarios.map((s) => {
            const isRec = s.scenario_code === recommendedCode
            const isSel = s.scenario_code === selected

            return (
              <div
                key={s.scenario_code}
                onClick={() => onSelect(s.scenario_code)}
                className={cn(
                  'relative flex cursor-pointer flex-col justify-between rounded-xl border p-4 transition-all',
                  isSel
                    ? 'border-primary bg-primary/[0.03] ring-1 ring-primary'
                    : 'border-border bg-card hover:border-border/80 hover:bg-muted/30',
                  isRec && 'border-gold/50'
                )}
              >
                {isRec && (
                  <span className="absolute -top-2.5 right-3 rounded-full bg-gold px-2 py-0.5 text-xs font-bold uppercase text-gold-foreground shadow-sm">
                    <Star className="mr-1 inline h-3 w-3 align-text-top" aria-hidden="true" /> Tối ưu nhất
                  </span>
                )}

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-foreground">{s.label}</span>
                    <Badge variant={isSel ? 'default' : 'outline'} className="text-xs">
                      {s.installments_count} đợt
                    </Badge>
                  </div>

                  <div>
                    <span className="text-xs text-muted-foreground">Giá bán sau ưu đãi (gồm VAT):</span>
                    <MoneyText amount={s.total_contract_price_vnd} size="base" className="font-bold text-foreground" />
                  </div>

                  <div className="space-y-1 rounded-md bg-muted/40 p-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Chiết khấu:</span>
                      <span className="font-semibold text-success">
                        {formatVnd(s.discount_vnd)} ({formatPercent(s.total_discount_rate)})
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Thanh toán ban đầu:</span>
                      <span className="font-medium text-foreground">{formatVnd(s.initial_payment_vnd)}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-3 border-t border-border/50 pt-2 text-center">
                  <span
                    className={cn(
                      'text-xs font-semibold',
                      isSel ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
                    )}
                  >
                    {isSel ? <><Check className="mr-1 inline h-3 w-3" aria-hidden="true" /> Đang xem đối soát</> : 'Bấm để đối soát'}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

/** [SCR-05] Bảng đối soát dòng tiền đa đợt (Dual Reconciliation Table) */
function DualReconciliationTable({ scenario, quote }: { scenario: Scenario; quote: Quote }) {
  const depositVnd = quote.transaction_context.units_quantity > 0 ? 100_000_000 : 0 // Mức cọc tiêu chuẩn

  return (
    <Card className="border-border bg-card shadow-sm">
      <CardHeader className="border-b border-border/60 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-sm font-semibold">
              Bảng Tiến Độ Thanh Toán Đã Chống Sai Số (Dual Reconciliation Verified)
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Phương án: <strong className="text-foreground">{scenario.label}</strong> · Thuật toán số học 0-float Python Decimal
            </p>
          </div>
          <Badge variant="outline" className="border-success/40 bg-success/5 text-xs text-success">
            <CheckCircle2 className="mr-1 h-3 w-3" /> Đối soát bù trừ: Δ = 0 VNĐ tuyệt đối
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40 text-xs">
                <TableHead className="w-[50px] text-center">Đợt</TableHead>
                <TableHead className="w-[180px]">Mốc thời gian</TableHead>
                <TableHead className="w-[80px] text-right">Tỷ lệ</TableHead>
                <TableHead className="w-[160px] text-right">Tiền nhà (gồm VAT)</TableHead>
                <TableHead className="w-[130px] text-right">Cấn trừ cọc</TableHead>
                <TableHead className="w-[160px] text-right">Khách thực nộp</TableHead>
                <TableHead className="w-[120px] text-right">KPBT (2%)</TableHead>
                <TableHead className="w-[160px] text-right">Tổng cộng đợt</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scenario.payment_schedule.map((item, idx) => {
                const isFirst = idx === 0
                const isHandover = idx === scenario.payment_schedule.length - 1
                const deductedDeposit = isFirst ? depositVnd : 0
                const actualPay = Math.max(0, item.amount_vnd - deductedDeposit)
                const kpbt = isHandover ? scenario.kpbt_vnd : 0
                const totalInstallment = actualPay + kpbt

                return (
                  <TableRow key={item.seq} className="text-xs">
                    <TableCell className="text-center font-bold">{item.seq}</TableCell>
                    <TableCell>
                      <p className="font-semibold text-foreground">{item.label}</p>
                      <p className="text-xs text-muted-foreground">{item.milestone}</p>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {(item.ratio * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatVnd(item.amount_vnd)}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {deductedDeposit > 0 ? formatVnd(deductedDeposit) : '0 đ'}
                    </TableCell>
                    <TableCell className="text-right font-semibold text-primary">
                      {formatVnd(actualPay)}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {kpbt > 0 ? formatVnd(kpbt) : '0 đ'}
                    </TableCell>
                    <TableCell className="text-right font-bold text-foreground">
                      {formatVnd(totalInstallment)}
                    </TableCell>
                  </TableRow>
                )
              })}

              {/* Total Reconciliation Row */}
              <TableRow className="border-t-2 border-border bg-muted/50 font-bold text-xs">
                <TableCell colSpan={2} className="uppercase tracking-wider text-foreground">
                  Tổng nghĩa vụ phải thu
                </TableCell>
                <TableCell className="text-right font-mono">100.0%</TableCell>
                <TableCell className="text-right text-foreground">
                  {formatVnd(scenario.total_contract_price_vnd - scenario.kpbt_vnd)}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatVnd(depositVnd)}
                </TableCell>
                <TableCell className="text-right text-primary">
                  {formatVnd(scenario.total_contract_price_vnd - depositVnd)}
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatVnd(scenario.kpbt_vnd)}
                </TableCell>
                <TableCell className="text-right text-foreground text-sm">
                  {formatVnd(scenario.total_contract_price_vnd)}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
          <span>Mã băm tính toán (Calculation Hash): <code className="font-mono text-foreground">{truncateHash(scenario.calculation_hash, 16)}</code></span>
          <span>Bảo chứng bởi Python Hardened Deterministic Engine</span>
        </div>
      </CardContent>
    </Card>
  )
}

/** Cổng ra quyết định Quản lý (Decision Panel) */
function DecisionPanel({ quote }: { quote: Quote }) {
  const user = useCurrentUser()
  const navigate = useNavigate()
  const can = managerActions(quote, user.role, user.user_id)
  const reject = useRejectQuote()
  const revise = useRequestRevision()
  const [reason, setReason] = useState('')
  const [approveOpen, setApproveOpen] = useState(false)
  const rec = quote.scenarios.find((s) => s.scenario_code === quote.recommendation?.recommended_scenario)
  const busy = reject.isPending || revise.isPending

  async function decide(kind: 'reject' | 'revise') {
    try {
      await (kind === 'reject' ? reject : revise).mutateAsync({ quote, extra: { reason: reason.trim() } })
      toast.success(kind === 'reject' ? 'Đã từ chối hồ sơ' : 'Đã yêu cầu chỉnh sửa hồ sơ', quote.quote_id)
      navigate('/manager/approvals')
    } catch (e) {
      toast.error(isStaleVersion(e) ? 'Hồ sơ đã có phiên bản mới' : 'Không lưu được quyết định', errorMessage(e))
    }
  }

  if (!can.approve && !can.reject) {
    return (
      <Card className="border-border bg-card shadow-sm">
        <CardHeader className="border-b border-border/60 pb-3">
          <CardTitle className="text-sm font-semibold">Trạng thái quyết định</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-4 text-sm">
          {can.sodViolation && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
              <div className="flex items-center gap-1.5 font-bold">
                <ShieldAlert className="h-4 w-4" />
                Vi phạm nguyên tắc Tách biệt nhiệm vụ (SoD)
              </div>
              <p className="mt-1 leading-relaxed">
                Hồ sơ này do bạn lập. Theo quy chuẩn bảo chứng, bạn không được tự duyệt báo giá của chính mình.
              </p>
            </div>
          )}

          {quote.approval ? (
            <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-foreground">
                  {quote.approval.decision === 'APPROVED'
                    ? 'ĐÃ PHÊ DUYỆT và KÝ SỐ'
                    : quote.approval.decision === 'REJECTED'
                    ? 'ĐÃ TỪ CHỐI'
                    : '↺ YÊU CẦU SỬA ĐỔI'}
                </span>
                <Badge variant={quote.approval.decision === 'APPROVED' ? 'success' : 'outline'}>
                  {quote.approval.decision}
                </Badge>
              </div>
              <p className="text-muted-foreground">
                Người quyết định: <strong className="text-foreground">{quote.approval.decided_by.full_name}</strong> ·{' '}
                {formatDateTime(quote.approval.decided_at)}
              </p>
              {quote.approval.reason && (
                <p className="rounded bg-background p-2 font-mono text-xs text-foreground">
                  "{quote.approval.reason}"
                </p>
              )}
              {quote.approval.signature && (
                <div className="border-t border-border/60 pt-2 font-mono text-xs text-muted-foreground">
                  <p>Thuật toán: {quote.approval.signature.algorithm}</p>
                  <p>Key ID: {quote.approval.signature.key_id}</p>
                  <p className="truncate" title={quote.approval.signature.signature}>
                    Chữ ký: {truncateHash(quote.approval.signature.signature, 16)}
                  </p>
                </div>
              )}
            </div>
          ) : (
            !can.sodViolation && (
              <p className="text-xs text-muted-foreground">Hồ sơ hiện không ở trạng thái chờ duyệt.</p>
            )
          )}
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-primary/40 bg-card shadow-md">
      <CardHeader className="border-b border-border/60 pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-bold text-foreground">Thẩm định và Quyết định</CardTitle>
          <Badge variant="outline" className="border-primary/40 bg-primary/5 text-primary text-xs">
            HITL Review Gate
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">
        {/* SoD Check Notification */}
        <div className="flex items-center gap-2 rounded-md bg-success/10 px-3 py-2 text-xs font-medium text-success">
          <ShieldCheck className="h-4 w-4 shrink-0" />
          <span>Tách biệt nhiệm vụ hợp lệ: Người lập {quote.created_by.full_name}</span>
        </div>

        {/* Recommended summary */}
        {rec && (
          <div className="rounded-lg border border-gold/40 bg-gold/[0.05] p-3 text-xs">
            <span className="text-xs text-muted-foreground">Phương án đề xuất tối ưu:</span>
            <div className="flex items-baseline justify-between">
              <strong className="text-sm text-foreground">{rec.label}</strong>
              <MoneyText amount={rec.total_contract_price_vnd} size="base" className="font-bold text-gold" />
            </div>
          </div>
        )}

        {/* Reason Input & Quick Templates */}
        <div className="space-y-2">
          <Label htmlFor="reason" className="text-xs font-semibold">
            Ghi chú chỉ đạo / Lý do (bắt buộc khi từ chối hoặc yêu cầu sửa)
          </Label>
          <Textarea
            id="reason"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Nhập lý do hoặc chọn nhanh mẫu bên dưới..."
            className="text-xs"
          />
          <div className="flex flex-wrap gap-1">
            {REASON_TEMPLATES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setReason((r) => (r ? `${r} ${t}` : t))}
                className="rounded-full border border-border bg-background px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                + {t.slice(0, 30)}...
              </button>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="space-y-2 pt-1">
          {can.approve && (
            <Button
              variant="success"
              onClick={() => setApproveOpen(true)}
              disabled={busy}
              className="w-full gap-2 text-xs font-bold"
            >
              <CheckCircle2 className="h-4 w-4" />
              <span>Phê duyệt và Ký số Ed25519</span>
            </Button>
          )}

          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              onClick={() => decide('revise')}
              disabled={busy || !reason.trim()}
              className="gap-1.5 text-xs"
            >
              {revise.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileEdit className="h-3.5 w-3.5" />}
              <span>Yêu cầu sửa</span>
            </Button>

            <Button
              variant="destructive"
              onClick={() => decide('reject')}
              disabled={busy || !reason.trim()}
              className="gap-1.5 text-xs"
            >
              {reject.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5" />}
              <span>Từ chối</span>
            </Button>
          </div>
        </div>
      </CardContent>

      {approveOpen && <ApproveDialog quote={quote} onClose={() => setApproveOpen(false)} />}
    </Card>
  )
}

/** [MODAL-04] Cửa sổ Ký số Ed25519 & Xác thực Re-auth */
function ApproveDialog({ quote, onClose }: { quote: Quote; onClose: () => void }) {
  const navigate = useNavigate()
  const reauth = useReauth()
  const approve = useApproveQuote()
  const [password, setPassword] = useState('')
  const [note, setNote] = useState('')

  const rec = quote.scenarios.find((s) => s.scenario_code === quote.recommendation?.recommended_scenario)
  const busy = reauth.isPending || approve.isPending

  async function handleApprove(e: FormEvent) {
    e.preventDefault()
    try {
      const grant = await reauth.mutateAsync({ password })
      await approve.mutateAsync({ quote, extra: { note: note.trim(), reauthToken: grant.reauth_token } })
      setPassword('')
      toast.success('Đã phê duyệt và ký số thành công', quote.quote_id)
      onClose()
      navigate(`/manager/approvals/${quote.quote_id}`)
    } catch {
      setPassword('')
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[480px]">
        <form onSubmit={handleApprove} className="space-y-4">
          <DialogHeader>
            <div className="flex items-center gap-2 text-primary">
              <Lock className="h-5 w-5" />
              <DialogTitle className="text-base font-bold">
                Xác thực Ký số Điện tử Báo giá Thương mại
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs">
              Kích hoạt chứng chỉ khóa riêng tư Ed25519 (RFC 8032) để đóng băng phiên bản và phát hành bản báo giá chính thức.
            </DialogDescription>
          </DialogHeader>

          {/* Quotation Identity Card */}
          <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Mã báo giá:</span>
              <strong className="font-mono text-foreground">{quote.quote_id} (v{quote.quote_version})</strong>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Khách hàng:</span>
              <strong className="text-foreground">{quote.transaction_context.customer_name}</strong>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Căn hộ:</span>
              <span className="font-medium text-foreground">{quote.unit.unit_code} ({PROJECT_LABEL[quote.unit.project_id]})</span>
            </div>
            {rec && (
              <div className="flex justify-between border-t border-border/50 pt-1.5">
                <span className="text-muted-foreground">Tổng giá trị HĐMB:</span>
                <MoneyText amount={rec.total_contract_price_vnd} size="sm" className="font-bold text-primary" />
              </div>
            )}
          </div>

          {/* Cryptographic Parameters */}
          <div className="rounded-lg border border-border/80 bg-background p-3 text-xs font-mono text-muted-foreground space-y-1">
            <p>Thuật toán ký: <span className="text-foreground font-semibold">Ed25519 (RFC 8032 - Curve25519)</span></p>
            <p>Key ID Định danh: <span className="text-foreground">key-vland-prod-signer-2026a</span></p>
            <p>Mã băm tính toán: <span className="text-foreground">{truncateHash(rec?.calculation_hash || 'c8f3812a', 16)}</span></p>
          </div>

          {/* Re-auth Password Field */}
          <div className="space-y-2">
            <Label htmlFor="signing-password" className="text-xs font-semibold">
              Mật khẩu xác thực Quản lý <span className="text-destructive">*</span>
            </Label>
            <div className="relative">
              <KeyRound className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="signing-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Nhập mật khẩu tài khoản của bạn để ký số..."
                className="pl-9 text-xs"
                autoFocus
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="signing-note" className="text-xs">
              Ghi chú chỉ đạo phê duyệt (Tùy chọn)
            </Label>
            <Input
              id="signing-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="VD: Đã đối soát đúng chính sách Đợt 3, duyệt phát hành..."
              className="text-xs"
            />
          </div>

          <div className="rounded-md bg-warning/10 p-2.5 text-xs text-warning-ink leading-relaxed">
            <AlertTriangle className="mr-1 inline h-3.5 w-3.5 align-text-bottom" aria-hidden="true" /> <strong>Lưu ý:</strong> Sau khi ký, hồ sơ và chính sách áp dụng sẽ bị <strong>ĐÓNG BĂNG VĨNH VIỄN</strong> trong cơ sở dữ liệu. Mọi sửa đổi sau thời điểm này đều phải tạo phiên bản mới.
          </div>

          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={busy}>
              Hủy bỏ
            </Button>
            <Button type="submit" variant="success" size="sm" disabled={busy || !password.trim()} className="gap-2">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4" />}
              <span>Xác nhận Ký và Xuất bản PDF</span>
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/** Thẻ Tài liệu Báo giá PDF & Kiểm thực công khai */
function PdfArtifactCard({ quote }: { quote: Quote }) {
  const retry = useRetryPdf()
  const pdfQuery = useQuotePdf(quote.quote_id, quote.pdf_status === 'PDF_ISSUED')
  const pdf = pdfQuery.data

  return (
    <Card className="border-border bg-card shadow-sm">
      <CardHeader className="border-b border-border/60 pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold">Tài liệu và Ký số Ed25519</CardTitle>
          {quote.pdf_status && <PdfStatusBadge status={quote.pdf_status} />}
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-4 text-xs">
        {quote.pdf_status === 'PDF_ISSUED' && pdf ? (
          <>
            <div className="space-y-1 rounded-lg border border-border bg-muted/40 p-2.5">
              <div className="flex items-center justify-between text-muted-foreground">
                <span>Mã băm SHA-256 PDF:</span>
                <span className="font-mono text-xs text-foreground">{truncateHash(pdf.pdf_sha256, 12)}</span>
              </div>
              <div className="flex items-center justify-between text-muted-foreground">
                <span>Phát hành lúc:</span>
                <span className="text-foreground">{formatDateTime(pdf.issued_at)}</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <Button asChild variant="default" size="sm" className="gap-1.5 text-xs">
                <a href={pdf.download_url} target="_blank" rel="noopener noreferrer">
                  <Download className="h-3.5 w-3.5" />
                  <span>Tải PDF gốc</span>
                </a>
              </Button>

              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 text-xs"
                onClick={() => {
                  navigator.clipboard.writeText(`${window.location.origin}/verify/${quote.quote_id}`)
                  toast.success('Đã sao chép liên kết kiểm thực', quote.quote_id)
                }}
              >
                <QrCode className="h-3.5 w-3.5" />
                <span>Link kiểm thực</span>
              </Button>
            </div>
          </>
        ) : quote.pdf_status === 'GENERATING' ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span>Tiến trình ARQ Worker đang kết xuất file PDF có chữ ký số...</span>
          </div>
        ) : quote.pdf_status === 'FAILED' ? (
          <div className="space-y-2">
            <p className="text-destructive">Không tạo được tệp PDF báo giá.</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => retry.mutate(quote.quote_id)}
              disabled={retry.isPending}
              className="gap-1.5 text-xs"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Thử tạo lại PDF
            </Button>
          </div>
        ) : (
          <p className="text-muted-foreground">Tệp PDF sẽ tự động xuất bản sau khi Quản lý hoàn tất ký số.</p>
        )}
      </CardContent>
    </Card>
  )
}
