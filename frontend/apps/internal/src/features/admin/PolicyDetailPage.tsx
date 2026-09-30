import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileCheck2,
  FileText,
  Filter,
  HelpCircle,
  Layers,
  Loader2,
  Lock,
  Play,
  RotateCcw,
  Scale,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Stamp,
  XCircle,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { PolicyDocument, PolicyRule, RulesTestReport } from '@pricepolicy/api-client/contracts'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { usePolicy, usePublishPolicy, useTestRules } from '@pricepolicy/api-client/hooks'
import { ErrorState, LoadingState } from '@pricepolicy/ui/components/common/PageStates'
import { PolicyStatusBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { CitationButton, EvidenceProvider } from '@pricepolicy/ui/components/quote/Evidence'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@pricepolicy/ui/components/ui/tabs'
import { formatDate, formatDateTime, formatPercent, formatVnd, truncateHash } from '@pricepolicy/ui/lib/format'
import { PROJECT_LABEL } from '@pricepolicy/ui/lib/labels'
import { toast } from '@pricepolicy/ui/state/toastStore'
import { cn } from '@pricepolicy/ui/lib/utils'

export function PolicyDetailPage() {
  const { policyId } = useParams()
  const policy = usePolicy(policyId)

  if (policy.isLoading) return <LoadingState label="Đang tải dữ liệu chính sách bán hàng…" />
  if (!policy.data) return <ErrorState error={policy.error ?? new Error('Không tìm thấy văn bản chính sách.')} onRetry={() => policy.refetch()} />

  return <PolicyDetail policy={policy.data} />
}

function formatRuleValue(rule: PolicyRule) {
  if (rule.kind === 'PERCENT_DISCOUNT') return formatPercent(rule.discount_rate ?? 0)
  if (rule.kind === 'GIFT') return `${formatVnd(rule.cash_equivalent_vnd ?? 0)} (Hiện vật)`
  if (rule.kind === 'BANK_SUPPORT') return `Hỗ trợ 0% · ${rule.interest_support_months ?? 0} tháng`
  return 'Theo quyết định riêng của CĐT'
}

function PolicyDetail({ policy }: { policy: PolicyDocument }) {
  const test = useTestRules()
  const publish = usePublishPolicy()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [kindFilter, setKindFilter] = useState<string>('ALL')

  const report = test.data?.policy_id === policy.policy_id ? test.data : null

  async function handlePublish() {
    try {
      await publish.mutateAsync(policy.policy_id)
      toast.success('Đã ban hành chính sách thành công', `${policy.title} · ${policy.policy_version}`)
      setConfirmOpen(false)
    } catch (e) {
      toast.error('Không thể ban hành chính sách', errorMessage(e))
    }
  }

  // Filter rules
  const filteredRules = useMemo(() => {
    return policy.rules.filter((r) => {
      if (kindFilter !== 'ALL' && r.kind !== kindFilter) return false
      if (searchTerm.trim()) {
        const s = searchTerm.toLowerCase().trim()
        const matchTitle = r.title.toLowerCase().includes(s)
        const matchCode = r.rule_code.toLowerCase().includes(s)
        if (!matchTitle && !matchCode) return false
      }
      return true
    })
  }, [policy.rules, kindFilter, searchTerm])

  const ruleStats = useMemo(() => {
    const discounts = policy.rules.filter((r) => r.kind === 'PERCENT_DISCOUNT').length
    const gifts = policy.rules.filter((r) => r.kind === 'GIFT').length
    const bankSupport = policy.rules.filter((r) => r.kind === 'BANK_SUPPORT').length
    const exclusiveRelations = policy.rules.reduce(
      (acc, r) => acc + r.relations.filter((rel) => rel.type === 'MUTUALLY_EXCLUSIVE').length,
      0
    )
    return { discounts, gifts, bankSupport, exclusiveRelations }
  }, [policy.rules])

  return (
    <EvidenceProvider>
      <div className="space-y-6">
        {/* Navigation & Header */}
        <div className="space-y-3">
          <Link
            to="/admin/policies"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Quay lại Danh mục chính sách
          </Link>

          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/60 pb-5">
            <div className="space-y-1.5 max-w-3xl">
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
                  {policy.title}
                </h1>
                <PolicyStatusBadge status={policy.status} />
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span className="font-mono font-semibold text-primary">{policy.policy_id}</span>
                <span>·</span>
                <Badge variant="outline" className="px-1.5 py-0 text-[11px]">
                  Phiên bản {policy.policy_version}
                </Badge>
                <span>·</span>
                <span className="font-medium text-foreground">{PROJECT_LABEL[policy.project_id] ?? policy.project_id}</span>
                <span>·</span>
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  Hiệu lực: {formatDate(policy.effective_from)} – {formatDate(policy.effective_to)}
                </span>
              </div>

              <p className="font-mono text-[11px] text-muted-foreground" title={policy.document_hash}>
                Tệp nguồn: <span className="text-foreground">{policy.source_document}</span> · SHA-256:{' '}
                <span className="text-foreground">{truncateHash(policy.document_hash, 16)}</span>
              </p>
            </div>

            {/* Actions for DRAFT policies */}
            {policy.status === 'DRAFT' && (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  onClick={() =>
                    test.mutateAsync(policy.policy_id).catch((e) =>
                      toast.error('Không chạy được kiểm tra tiền kiểm', errorMessage(e))
                    )
                  }
                  disabled={test.isPending}
                  className="gap-2 text-xs"
                  data-testid="run-rules-test"
                >
                  {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4 text-primary" />}
                  <span>{test.isPending ? 'Đang phân tích xung đột…' : 'Kiểm tra trước ban hành (Pre-flight)'}</span>
                </Button>

                <Button
                  variant="default"
                  onClick={() => setConfirmOpen(true)}
                  disabled={!report?.can_publish}
                  className="gap-2 text-xs font-semibold"
                  data-testid="publish"
                >
                  <Stamp className="h-4 w-4" />
                  <span>Ban hành chính thức</span>
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Card className="border-border bg-card p-3 shadow-sm">
            <span className="text-[11px] text-muted-foreground">Tổng điều khoản số hóa</span>
            <p className="mt-1 font-display text-xl font-bold text-foreground">{policy.rules.length}</p>
          </Card>
          <Card className="border-border bg-card p-3 shadow-sm">
            <span className="text-[11px] text-muted-foreground">Chiết khấu thương mại (%)</span>
            <p className="mt-1 font-display text-xl font-bold text-primary">{ruleStats.discounts} điều khoản</p>
          </Card>
          <Card className="border-border bg-card p-3 shadow-sm">
            <span className="text-[11px] text-muted-foreground">Quà tặng & Gói HTLS 0%</span>
            <p className="mt-1 font-display text-xl font-bold text-foreground">
              {ruleStats.gifts + ruleStats.bankSupport} gói ưu đãi
            </p>
          </Card>
          <Card className="border-border bg-card p-3 shadow-sm">
            <span className="text-[11px] text-muted-foreground">Cặp quan hệ loại trừ (Exclusivity)</span>
            <p className="mt-1 font-display text-xl font-bold text-destructive">{ruleStats.exclusiveRelations} ràng buộc</p>
          </Card>
        </div>

        {/* Pre-flight Audit Report Banner */}
        {report && <PrePublishAuditReport report={report} />}

        {/* Rules Matrix Card */}
        <Card className="border-border bg-card shadow-sm">
          <CardHeader className="border-b border-border/80 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                  <Layers className="h-4 w-4 text-primary" />
                  Ma trận Điều khoản Chính sách ({policy.rules.length} quy tắc)
                </CardTitle>
                <p className="text-[11px] text-muted-foreground">
                  Mỗi quy tắc được gắn tọa độ dẫn chứng (Source Coordinates) đến từng trang và điều khoản trong văn bản gốc
                </p>
              </div>

              {/* Rule Filters */}
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative min-w-[200px] flex-1 sm:w-56 sm:flex-initial">
                  <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Tìm tên hoặc mã điều khoản..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="h-8 pl-8 text-xs"
                  />
                </div>

                <Select value={kindFilter} onValueChange={setKindFilter}>
                  <SelectTrigger className="h-8 w-[160px] text-xs">
                    <SelectValue placeholder="Phân loại" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ALL">Tất cả phân loại</SelectItem>
                    <SelectItem value="PERCENT_DISCOUNT">Chiết khấu tỷ lệ (%)</SelectItem>
                    <SelectItem value="GIFT">Quà tặng hiện vật</SelectItem>
                    <SelectItem value="BANK_SUPPORT">Hỗ trợ lãi suất (HTLS)</SelectItem>
                    <SelectItem value="DISCRETIONARY">Quyết định riêng</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>

          <CardContent className="p-0">
            {filteredRules.length === 0 ? (
              <div className="p-12 text-center text-xs text-muted-foreground">
                Không tìm thấy điều khoản nào phù hợp với bộ lọc.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/30 hover:bg-muted/30 text-[11px]">
                      <TableHead className="w-[300px]">Tên điều khoản & Dẫn chứng</TableHead>
                      <TableHead className="w-[140px]">Phân loại</TableHead>
                      <TableHead className="w-[160px]">Giá trị ưu đãi</TableHead>
                      <TableHead className="w-[180px]">Phương án áp dụng</TableHead>
                      <TableHead className="w-[200px]">Quan hệ ràng buộc & Loại trừ</TableHead>
                      <TableHead className="w-[130px]">Trạng thái</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredRules.map((r) => (
                      <TableRow key={r.rule_code} className="hover:bg-muted/30 transition-colors">
                        {/* Title & Citation */}
                        <TableCell>
                          <div className="space-y-1">
                            <p className="font-semibold text-foreground text-xs">{r.title}</p>
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="font-mono text-[11px] text-muted-foreground">{r.rule_code}</span>
                              <CitationButton title={r.title} source={r.source} ruleCode={r.rule_code} />
                            </div>
                          </div>
                        </TableCell>

                        {/* Kind */}
                        <TableCell>
                          <Badge variant="outline" className="text-[10px]">
                            {r.kind === 'PERCENT_DISCOUNT'
                              ? 'Chiết khấu %'
                              : r.kind === 'GIFT'
                              ? 'Quà tặng'
                              : r.kind === 'BANK_SUPPORT'
                              ? 'HTLS Ngân hàng'
                              : 'Quyết định riêng'}
                          </Badge>
                        </TableCell>

                        {/* Value */}
                        <TableCell>
                          <span
                            className={cn(
                              'text-xs font-semibold tabular-nums',
                              r.is_ambiguous ? 'text-warning' : 'text-foreground'
                            )}
                          >
                            {formatRuleValue(r)}
                          </span>
                          {r.is_ambiguous && (
                            <p className="text-[10px] text-warning flex items-center gap-1 mt-0.5">
                              <AlertTriangle className="h-3 w-3" /> Điều khoản cần làm rõ
                            </p>
                          )}
                        </TableCell>

                        {/* Applicable Scenarios */}
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {r.applicable_scenarios.map((sc) => (
                              <Badge key={sc} variant="outline" className="text-[10px] bg-background">
                                {sc === 'PA-CHUDONG' ? 'Tiến độ' : sc === 'PA-NHANH' ? 'Trả nhanh' : 'Vay HTLS'}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>

                        {/* Exclusivity / Relations */}
                        <TableCell>
                          <div className="space-y-1 text-[11px]">
                            {r.relations.length > 0 ? (
                              r.relations.map((rel) => (
                                <div key={rel.rule_code} className="flex items-center gap-1">
                                  <Badge
                                    variant={rel.type === 'MUTUALLY_EXCLUSIVE' ? 'destructive' : 'warning'}
                                    className="px-1 py-0 text-[9px]"
                                  >
                                    {rel.type === 'MUTUALLY_EXCLUSIVE' ? 'Loại trừ' : 'Ràng buộc'}
                                  </Badge>
                                  <span className="font-mono text-muted-foreground">{rel.rule_code}</span>
                                </div>
                              ))
                            ) : (
                              <span className="text-muted-foreground text-[11px]">Độc lập, không loại trừ</span>
                            )}
                          </div>
                        </TableCell>

                        {/* Validation Status */}
                        <TableCell>
                          <Badge
                            variant={r.validation_status === 'APPROVED_FOR_USE' ? 'success' : 'outline'}
                            className="text-[10px]"
                          >
                            {r.validation_status === 'APPROVED_FOR_USE' ? 'Đã duyệt dùng' : 'Chờ xác thực'}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Publish Confirmation Dialog */}
        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogContent className="sm:max-w-[480px]">
            <DialogHeader>
              <div className="flex items-center gap-2 text-primary">
                <Stamp className="h-5 w-5" />
                <DialogTitle className="text-base font-bold">
                  Ban hành Chính thức Chính sách Bán hàng
                </DialogTitle>
              </div>
              <DialogDescription className="text-xs">
                Kích hoạt chính sách thành nguồn sự thật duy nhất (Single Source of Truth) trong hệ thống tính giá và AI RAG.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Văn bản:</span>
                <strong className="text-foreground">{policy.title}</strong>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Phiên bản:</span>
                <span className="font-mono text-foreground">{policy.policy_version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Dự án:</span>
                <span className="text-foreground">{PROJECT_LABEL[policy.project_id] ?? policy.project_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Thời hạn hiệu lực:</span>
                <span className="text-foreground">{formatDate(policy.effective_from)} – {formatDate(policy.effective_to)}</span>
              </div>
              <div className="flex justify-between border-t border-border/50 pt-1.5">
                <span className="text-muted-foreground">Tổng điều khoản kích hoạt:</span>
                <strong className="text-primary">{policy.rules.length} quy tắc số hóa</strong>
              </div>
            </div>

            <div className="rounded-md bg-warning/10 p-2.5 text-[11px] text-warning-foreground leading-relaxed">
              ⚠ <strong>Lưu ý:</strong> Sau khi ban hành, chính sách sẽ được đóng băng snapshot băm SHA-256 để đảm bảo kiểm toán Time-Travel. Mọi báo giá lập trong thời hạn này sẽ tự động liên kết với phiên bản này.
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" size="sm" onClick={() => setConfirmOpen(false)} disabled={publish.isPending}>
                Hủy bỏ
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handlePublish}
                disabled={publish.isPending}
                className="gap-2"
              >
                {publish.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Stamp className="h-4 w-4" />}
                <span>Xác nhận Ban hành</span>
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </EvidenceProvider>
  )
}

const CHECK_STATUS_ICON = {
  PASS: <CheckCircle2 className="h-4 w-4 text-success shrink-0" />,
  WARN: <AlertTriangle className="h-4 w-4 text-warning shrink-0" />,
  FAIL: <XCircle className="h-4 w-4 text-destructive shrink-0" />,
}

/** Báo cáo kiểm tra trước ban hành & Quét xung đột ma trận (Semantic Conflict Detection) */
function PrePublishAuditReport({ report }: { report: RulesTestReport }) {
  const passCount = report.checks.filter((c) => c.status === 'PASS').length
  const warnCount = report.checks.filter((c) => c.status === 'WARN').length
  const failCount = report.checks.filter((c) => c.status === 'FAIL').length

  return (
    <div className="space-y-4" data-testid="rules-report">
      <Card
        className={cn(
          'border shadow-sm',
          report.can_publish ? 'border-success/40 bg-success/[0.02]' : 'border-destructive/40 bg-destructive/[0.02]'
        )}
      >
        <CardHeader className="border-b border-border/40 pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'flex h-7 w-7 items-center justify-center rounded-md font-bold',
                  report.can_publish ? 'bg-success/15 text-success' : 'bg-destructive/15 text-destructive'
                )}
              >
                {report.can_publish ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
              </span>
              <div>
                <CardTitle className="text-sm font-semibold">
                  Kết Quả Kiểm Tra Trước Ban Hành (Pre-Flight Audit & Conflict Detection)
                </CardTitle>
                <p className="text-[11px] text-muted-foreground">
                  Thực hiện lúc {formatDateTime(report.checked_at)} · Kiểm thử hồi quy: {report.regression.passed}/{report.regression.total} ca đạt
                </p>
              </div>
            </div>

            <Badge variant={report.can_publish ? 'success' : 'destructive'} className="text-xs">
              {report.can_publish ? '✓ ĐỦ ĐIỀU KIỆN BAN HÀNH' : '✕ CẦN XỬ LÝ LỖI'}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="grid gap-4 p-4 lg:grid-cols-2">
          {/* Checks List */}
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-semibold">
              <span>Các tiêu chí kiểm soát quy tắc:</span>
              <div className="flex gap-2 text-[10px]">
                <span className="text-success font-bold">{passCount} Đạt</span>
                <span className="text-warning font-bold">{warnCount} Lưu ý</span>
                <span className="text-destructive font-bold">{failCount} Lỗi</span>
              </div>
            </div>

            <div className="space-y-2">
              {report.checks.map((c) => (
                <div
                  key={c.code}
                  className="flex items-start gap-2.5 rounded-lg border border-border/70 bg-background/80 p-2.5 text-xs"
                >
                  <span className="mt-0.5">{CHECK_STATUS_ICON[c.status]}</span>
                  <div className="min-w-0 space-y-0.5">
                    <p className="font-semibold text-foreground">{c.label}</p>
                    <p className="text-muted-foreground leading-relaxed">{c.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Conflict Findings (L1 / L2 / L3) */}
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-semibold">
              <span>Phát hiện xung đột ma trận ({report.conflict_findings.length}):</span>
              <span className="text-[11px] text-muted-foreground">3 Cấp độ Semantic Matrix</span>
            </div>

            {report.conflict_findings.length === 0 ? (
              <div className="flex h-32 flex-col items-center justify-center rounded-lg border border-dashed border-success/30 bg-success/[0.03] text-center p-4">
                <CheckCircle2 className="h-6 w-6 text-success" />
                <p className="mt-1 text-xs font-semibold text-success">Không có xung đột điều khoản</p>
                <p className="text-[11px] text-muted-foreground">Các điều khoản trong chính sách nhất quán 100%.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {report.conflict_findings.map((f, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-border/80 bg-background/80 p-2.5 text-xs space-y-1"
                  >
                    <div className="flex items-center gap-1.5">
                      <Badge variant={f.tier === 1 ? 'destructive' : f.tier === 2 ? 'warning' : 'outline'} className="text-[10px]">
                        {f.tier === 1 ? 'Cấp 1: Triệt tiêu' : f.tier === 2 ? 'Cấp 2: Chồng chéo' : 'Cấp 3: Mơ hồ'}
                      </Badge>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {f.rule_codes.join(' ↔ ')}
                      </span>
                    </div>
                    <p className="text-foreground leading-relaxed">{f.message}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
