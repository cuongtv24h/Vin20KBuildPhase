import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  Eye,
  FileCheck2,
  FileEdit,
  Filter,
  Layers,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserCheck,
  XCircle,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Quote, QuoteWorkflowStatus, RiskFlagColor } from '@pricepolicy/api-client/contracts'
import { useProjectOverviews, useQuotes } from '@pricepolicy/api-client/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { EmptyState, LoadingState, PageHeader } from '@pricepolicy/ui/components/common/PageStates'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { RiskFlagBadge } from '@pricepolicy/ui/components/common/RiskFlagBadge'
import { SlaCountdown } from '@pricepolicy/ui/components/common/SlaCountdown'
import { QuoteStatusBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent } from '@pricepolicy/ui/components/ui/card'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@pricepolicy/ui/components/ui/tabs'
import { formatDateTime, formatRelative, formatVnd } from '@pricepolicy/ui/lib/format'
import { PROJECT_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'

const RISK_WEIGHT: Record<RiskFlagColor, number> = { RED: 0, YELLOW: 1, GREEN: 2 }

const byPriority = (a: Quote, b: Quote) =>
  RISK_WEIGHT[a.risk_flag.color] - RISK_WEIGHT[b.risk_flag.color] ||
  (a.submitted_at ?? a.updated_at).localeCompare(b.submitted_at ?? b.updated_at)

const TABS: { key: string; label: string; statuses: QuoteWorkflowStatus[]; icon: typeof ClipboardCheck }[] = [
  { key: 'review', label: 'Chờ thẩm định (HITL)', statuses: ['READY_FOR_REVIEW'], icon: ClipboardCheck },
  { key: 'exception', label: 'Ngoại lệ (Abstained)', statuses: ['ABSTAINED'], icon: AlertTriangle },
  { key: 'done', label: 'Đã xử lý', statuses: ['APPROVED', 'REJECTED', 'NEEDS_REVISION'], icon: FileCheck2 },
]

export function ApprovalQueuePage() {
  const user = useCurrentUser()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('review')
  const [searchTerm, setSearchTerm] = useState('')
  const [riskFilter, setRiskFilter] = useState<'ALL' | RiskFlagColor>('ALL')
  const [projectFilter, setProjectFilter] = useState<string>('ALL')

  const projectsQuery = useProjectOverviews()
  const quotesQuery = useQuotes({ status: TABS.flatMap((t) => t.statuses) }, { live: true })
  const allQuotes = quotesQuery.data ?? []

  // KPI Metrics Calculation
  const metrics = useMemo(() => {
    const readyForReview = allQuotes.filter((q) => q.status === 'READY_FOR_REVIEW')
    const redFlags = readyForReview.filter((q) => q.risk_flag.color === 'RED').length
    const yellowFlags = readyForReview.filter((q) => q.risk_flag.color === 'YELLOW').length
    const greenFlags = readyForReview.filter((q) => q.risk_flag.color === 'GREEN').length
    const approvedCount = allQuotes.filter((q) => q.status === 'APPROVED').length
    const rejectedOrRevisionCount = allQuotes.filter((q) => q.status === 'REJECTED' || q.status === 'NEEDS_REVISION').length
    const abstainedCount = allQuotes.filter((q) => q.status === 'ABSTAINED').length

    return {
      waiting: readyForReview.length,
      redFlags,
      yellowFlags,
      greenFlags,
      approvedCount,
      rejectedOrRevisionCount,
      abstainedCount,
    }
  }, [allQuotes])

  // Filtered rows for currently active tab
  const tabConfig = TABS.find((t) => t.key === activeTab) ?? TABS[0]

  const filteredQuotes = useMemo(() => {
    return allQuotes
      .filter((q) => tabConfig.statuses.includes(q.status))
      .filter((q) => {
        if (riskFilter !== 'ALL' && q.risk_flag.color !== riskFilter) return false
        if (projectFilter !== 'ALL' && q.unit.project_id !== projectFilter) return false
        if (searchTerm.trim()) {
          const s = searchTerm.toLowerCase().trim()
          const matchCode = q.quote_id.toLowerCase().includes(s)
          const matchCustomer = q.transaction_context.customer_name.toLowerCase().includes(s)
          const matchUnit = q.unit.unit_code.toLowerCase().includes(s)
          const matchCreator = q.created_by.full_name.toLowerCase().includes(s)
          if (!matchCode && !matchCustomer && !matchUnit && !matchCreator) return false
        }
        return true
      })
      .sort(activeTab === 'done' ? (a, b) => b.updated_at.localeCompare(a.updated_at) : byPriority)
  }, [allQuotes, tabConfig, riskFilter, projectFilter, searchTerm, activeTab])

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div>
              <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
                Cổng Thẩm định và Phê duyệt Báo giá
              </h1>
              <p className="text-xs text-muted-foreground">
                Hệ thống HITL Gate (Human-In-The-Loop) · Quản trị rủi ro và Ký số Ed25519 bảo chứng
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="border-border/80 bg-background/50 px-3 py-1 text-xs">
            <UserCheck className="mr-1.5 h-3.5 w-3.5 text-primary" />
            Quản lý duyệt: <strong className="ml-1 text-foreground">{user.full_name}</strong>
          </Badge>
        </div>
      </div>

      {/* Dải chỉ số gọn một khối (bố cục Remote/Deel): 5 chỉ số chia cột bằng đường kẻ, thay cho 5 thẻ rời */}
      <div className="grid grid-cols-2 divide-border overflow-hidden rounded-xl border border-border bg-card sm:grid-cols-3 sm:divide-x lg:grid-cols-5">
        {[
          { label: 'Chờ thẩm định', value: metrics.waiting, hint: `${metrics.redFlags} đỏ · ${metrics.yellowFlags} vàng · ${metrics.greenFlags} xanh`, icon: Clock, tone: 'text-foreground', dot: 'bg-primary' },
          { label: 'Cảnh báo Cờ Đỏ', value: metrics.redFlags, hint: 'Rà soát kỹ trước khi duyệt', icon: ShieldAlert, tone: 'text-destructive', dot: 'bg-destructive' },
          { label: 'Cảnh báo Cờ Vàng', value: metrics.yellowFlags, hint: 'Chiết khấu chạm trần hoặc dời ngày', icon: AlertTriangle, tone: 'text-warning', dot: 'bg-warning' },
          { label: 'Đã phê duyệt', value: metrics.approvedCount, hint: 'Đã ký số Ed25519', icon: CheckCircle2, tone: 'text-success', dot: 'bg-success' },
          { label: 'Từ chối / Yêu cầu sửa', value: metrics.rejectedOrRevisionCount, hint: 'Đã phản hồi Sales', icon: RotateCcw, tone: 'text-foreground', dot: 'bg-muted-foreground' },
        ].map(({ label, value, hint, icon: Icon, tone, dot }) => (
          <div key={label} className="space-y-1 border-b border-border p-4 last:border-b-0 sm:[&:nth-last-child(-n+1)]:border-b-0 lg:border-b-0">
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <span aria-hidden="true" className={cn('h-1.5 w-1.5 rounded-full', dot)} />
              {label}
              <Icon className="ml-auto h-3.5 w-3.5" aria-hidden="true" />
            </div>
            <p className={cn('font-display text-2xl font-semibold tabular-nums', tone)}>{value}</p>
            <p className="truncate text-xs text-muted-foreground">{hint}</p>
          </div>
        ))}
      </div>

      {/* Main Filter & Tabs Area */}
      <Card className="border-border bg-card shadow-sm">
        <div className="border-b border-border/80 p-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full min-w-0 xl:w-auto">
              <TabsList className="h-auto gap-1 rounded-full bg-muted/60 p-1">
                {TABS.map((t) => {
                  const count = allQuotes.filter((q) => t.statuses.includes(q.status)).length
                  const Icon = t.icon
                  return (
                    <TabsTrigger key={t.key} value={t.key} className="gap-2 rounded-full text-xs">
                      <Icon className="h-3.5 w-3.5" />
                      <span>{t.label}</span>
                      <span
                        className={cn(
                          'rounded-full px-1.5 py-0.2 text-xs font-semibold tabular-nums',
                          activeTab === t.key
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted-foreground/20 text-muted-foreground'
                        )}
                      >
                        {count}
                      </span>
                    </TabsTrigger>
                  )
                })}
              </TabsList>
            </Tabs>

            {/* Quick Filters */}
            <div className="flex flex-wrap items-center gap-2.5">
              {/* Search input */}
              <div className="relative min-w-[220px] flex-1 sm:w-64 sm:flex-initial">
                <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Tìm mã báo giá, khách hàng, căn hộ..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="h-8 pl-8 text-xs"
                />
              </div>

              {/* Risk Filter */}
              <Select value={riskFilter} onValueChange={(v) => setRiskFilter(v as 'ALL' | RiskFlagColor)}>
                <SelectTrigger className="h-8 w-[130px] text-xs">
                  <SelectValue placeholder="Cờ rủi ro" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">Tất cả cờ</SelectItem>
                  <SelectItem value="GREEN"><span className="inline-flex items-center"><span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-full bg-success" />Cờ Xanh (An toàn)</span></SelectItem>
                  <SelectItem value="YELLOW"><span className="inline-flex items-center"><span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-full bg-warning" />Cờ Vàng (Lưu ý)</span></SelectItem>
                  <SelectItem value="RED"><span className="inline-flex items-center"><span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-full bg-destructive" />Cờ Đỏ (Chặn/Cảnh báo)</span></SelectItem>
                </SelectContent>
              </Select>

              {/* Project Filter */}
              <Select value={projectFilter} onValueChange={setProjectFilter}>
                <SelectTrigger className="h-8 w-[150px] text-xs">
                  <SelectValue placeholder="Dự án" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">Tất cả dự án</SelectItem>
                  {projectsQuery.data?.map((p) => (
                    <SelectItem key={p.project.project_id} value={p.project.project_id}>
                      {PROJECT_LABEL[p.project.project_id] ?? p.project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {(searchTerm || riskFilter !== 'ALL' || projectFilter !== 'ALL') && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSearchTerm('')
                    setRiskFilter('ALL')
                    setProjectFilter('ALL')
                  }}
                  className="h-8 px-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  Xóa lọc
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Quotes Table */}
        <CardContent className="p-0">
          {quotesQuery.isLoading ? (
            <div className="py-16">
              <LoadingState label="Đang tải danh sách hồ sơ cần thẩm định…" />
            </div>
          ) : filteredQuotes.length === 0 ? (
            <div className="py-16">
              <EmptyState
                icon={ClipboardCheck}
                title="Không có hồ sơ nào trong mục này"
                description={
                  searchTerm || riskFilter !== 'ALL' || projectFilter !== 'ALL'
                    ? 'Không tìm thấy hồ sơ phù hợp với bộ lọc hiện tại.'
                    : activeTab === 'review'
                    ? 'Hiện tại không có hồ sơ nào đang chờ Quản lý thẩm định.'
                    : 'Chưa có hồ sơ được xử lý trong danh mục này.'
                }
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead className="w-[180px]">Hồ sơ và Căn hộ</TableHead>
                    <TableHead className="w-[180px]">Khách hàng</TableHead>
                    <TableHead className="w-[170px]">Chuyên viên Sales</TableHead>
                    <TableHead className="w-[130px]">Trạng thái</TableHead>
                    <TableHead className="w-[180px]">Cảm biến rủi ro</TableHead>
                    <TableHead className="w-[200px] text-right">Phương án đề xuất</TableHead>
                    <TableHead className="w-[140px] text-right">Thời gian / SLA</TableHead>
                    <TableHead className="w-[130px] text-center">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredQuotes.map((q) => {
                    const rec = q.scenarios.find((s) => s.scenario_code === q.recommendation?.recommended_scenario)
                    const isSodViolation = user.user_id === q.created_by.user_id
                    const isReview = q.status === 'READY_FOR_REVIEW'

                    return (
                      <TableRow
                        key={q.quote_id}
                        className={cn(
                          'cursor-pointer transition-colors hover:bg-muted/40',
                          isReview && q.risk_flag.color === 'RED' && 'bg-destructive/[0.02]',
                          isReview && q.risk_flag.color === 'YELLOW' && 'bg-warning/[0.02]'
                        )}
                        onClick={() => navigate(`/manager/approvals/${q.quote_id}`)}
                      >
                        {/* Quote & Unit — thanh màu bên trái theo cờ rủi ro (bố cục Deel) */}
                        <TableCell
                          className={cn(
                            'border-l-[3px] border-l-transparent',
                            isReview && q.risk_flag.color === 'RED' && 'border-l-destructive',
                            isReview && q.risk_flag.color === 'YELLOW' && 'border-l-warning',
                          )}
                        >
                          <div className="space-y-0.5">
                            <span className="font-mono text-xs font-semibold text-primary hover:underline">
                              {q.quote_id}
                            </span>
                            <div className="flex items-center gap-1.5 text-xs text-foreground font-medium">
                              <span>Căn: {q.unit.unit_code}</span>
                              <span className="text-muted-foreground">·</span>
                              <span className="text-muted-foreground">{q.unit.bedrooms}PN ({q.unit.area_m2}m²)</span>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {PROJECT_LABEL[q.unit.project_id] ?? q.unit.project_id} · v{q.quote_version}
                            </p>
                          </div>
                        </TableCell>

                        {/* Customer */}
                        <TableCell>
                          <div className="space-y-0.5">
                            <p className="text-xs font-semibold text-foreground">
                              {q.transaction_context.customer_name || 'Khách vãng lai'}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {q.transaction_context.customer_phone || 'Chưa cập nhật SĐT'}
                            </p>
                            <Badge variant="outline" className="px-1.5 py-0 text-xs text-muted-foreground">
                              Phân khúc: {q.transaction_context.customer_segment}
                            </Badge>
                          </div>
                        </TableCell>

                        {/* Sales Owner */}
                        <TableCell>
                          <div className="space-y-0.5">
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-foreground">
                              {q.created_by.full_name}
                            </span>
                            {isSodViolation ? (
                              <div
                                className="inline-flex items-center gap-1 rounded bg-destructive/10 px-1.5 py-0.5 text-xs font-semibold text-destructive"
                                title="Vi phạm nguyên tắc Tách biệt nhiệm vụ: Quản lý không được tự duyệt báo giá do chính mình tạo ra"
                              >
                                <ShieldAlert className="h-3 w-3 shrink-0" />
                                <span>Trùng người lập</span>
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground">
                                ID: {q.created_by.user_id.slice(0, 8)}
                              </p>
                            )}
                          </div>
                        </TableCell>

                        {/* Workflow Status */}
                        <TableCell>
                          <QuoteStatusBadge status={q.status} />
                        </TableCell>

                        {/* Risk Flag & Reasons */}
                        <TableCell>
                          <div className="space-y-1">
                            <RiskFlagBadge flag={q.risk_flag} className="text-xs font-semibold" />
                            {q.risk_flag.reasons.length > 0 && (
                              <p className="line-clamp-2 text-xs text-muted-foreground leading-tight">
                                {q.risk_flag.reasons.join('; ')}
                              </p>
                            )}
                          </div>
                        </TableCell>

                        {/* Recommended Scenario & Price */}
                        <TableCell className="text-right">
                          {rec ? (
                            <div className="space-y-0.5">
                              <MoneyText
                                amount={rec.total_contract_price_vnd}
                                size="sm"
                                className="font-bold text-foreground"
                              />
                              <div className="flex items-center justify-end gap-1">
                                <Badge variant="gold" className="px-1 py-0 text-xs">
                                  {rec.label}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground">
                                Chiết khấu: {formatVnd(rec.discount_vnd)} ({rec.total_discount_rate}%)
                              </p>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>

                        {/* Time & SLA */}
                        <TableCell className="text-right">
                          <div className="space-y-1">
                            <span className="text-xs text-muted-foreground">
                              {formatRelative(q.submitted_at ?? q.updated_at)}
                            </span>
                            {isReview && q.submitted_at && (
                              <div className="flex justify-end">
                                <SlaCountdown dueAt={new Date(Date.parse(q.submitted_at) + 2 * 3600 * 1000).toISOString()} />
                              </div>
                            )}
                          </div>
                        </TableCell>

                        {/* Actions */}
                        <TableCell className="text-center" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant={isReview ? (q.risk_flag.color === 'RED' ? 'destructive' : 'default') : 'outline'}
                            size="sm"
                            className="h-8 gap-1 px-2.5 text-xs shadow-none"
                            onClick={() => navigate(`/manager/approvals/${q.quote_id}`)}
                          >
                            <Eye className="h-3.5 w-3.5" />
                            <span>{isReview ? 'Thẩm định' : 'Xem hồ sơ'}</span>
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
