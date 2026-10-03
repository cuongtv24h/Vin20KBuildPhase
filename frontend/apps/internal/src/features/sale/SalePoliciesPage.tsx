import {
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  Eye,
  FileCheck,
  FileStack,
  FileText,
  Filter,
  HelpCircle,
  Layers,
  Percent,
  Plus,
  RefreshCw,
  Scale,
  ScrollText,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { PolicyDocument, PolicyStatus } from '@pricepolicy/api-client/contracts'
import { usePolicies, useProjectOverviews } from '@pricepolicy/api-client/hooks'
import { EmptyState, LoadingState, PageHeader } from '@pricepolicy/ui/components/common/PageStates'
import { PolicyStatusBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { formatDate, todayIso } from '@pricepolicy/ui/lib/format'
import { PROJECT_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'

export function SalePoliciesPage() {
  const policiesQuery = usePolicies()
  const projectsQuery = useProjectOverviews()
  const navigate = useNavigate()

  const [searchTerm, setSearchTerm] = useState('')
  const [projectFilter, setProjectFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'PUBLISHED' | 'DRAFT' | 'ARCHIVED'>('ALL')
  const [selectedPolicy, setSelectedPolicy] = useState<PolicyDocument | null>(null)

  const today = todayIso()
  const allPolicies = useMemo(() => policiesQuery.data ?? [], [policiesQuery.data])

  // Filtered policies
  const filteredPolicies = useMemo(() => {
    return allPolicies.filter((p) => {
      const matchSearch =
        searchTerm.trim() === '' ||
        p.policy_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.project_id.toLowerCase().includes(searchTerm.toLowerCase())

      const matchProject = projectFilter === 'ALL' || p.project_id === projectFilter

      const matchStatus =
        statusFilter === 'ALL' ||
        (statusFilter === 'PUBLISHED' && p.status === 'PUBLISHED') ||
        (statusFilter === 'DRAFT' && p.status === 'DRAFT') ||
        (statusFilter === 'ARCHIVED' && p.status === 'ARCHIVED')

      return matchSearch && matchProject && matchStatus
    })
  }, [allPolicies, searchTerm, projectFilter, statusFilter])

  // Summary Metrics
  const metrics = useMemo(() => {
    const total = allPolicies.length
    const active = allPolicies.filter((p) => p.status === 'PUBLISHED').length
    const projects = new Set(allPolicies.map((p) => p.project_id)).size
    return { total, active, projects }
  }, [allPolicies])

  function handleAskCopilot(policy: PolicyDocument) {
    const promptText = `Em hãy tóm tắt các điểm nổi bật và chính sách chiết khấu của văn bản ${policy.policy_id} (${policy.title}) giúp anh nhé.`
    navigate(`/sale/workspace?prompt=${encodeURIComponent(promptText)}`)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Chính sách bán hàng hiện hành"
        description="Tra cứu danh mục chính sách bán hàng, bảng điều kiện áp dụng, chiết khấu thanh toán sớm và gói hỗ trợ lãi suất ngân hàng theo chuẩn FCS v2.6."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to="/sale/workspace">
                <Sparkles className="mr-1.5 h-3.5 w-3.5 text-primary" /> Hỏi Trợ lý Copilot
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/sale/messages">
                <FileCheck className="mr-1.5 h-3.5 w-3.5" /> Soạn tin & Tuân thủ F8
              </Link>
            </Button>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="border-border shadow-xs">
          <CardHeader className="py-3 px-4 flex flex-row items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground">Tổng số chính sách</span>
            <ScrollText className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0">
            <div className="text-2xl font-bold font-display">{metrics.total}</div>
            <p className="text-[11px] text-muted-foreground mt-0.5">Trên {metrics.projects} dự án đang mở bán</p>
          </CardContent>
        </Card>

        <Card className="border-border shadow-xs">
          <CardHeader className="py-3 px-4 flex flex-row items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground">Đang áp dụng (Active)</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0">
            <div className="text-2xl font-bold font-display text-emerald-600">{metrics.active}</div>
            <p className="text-[11px] text-muted-foreground mt-0.5">Sẵn sàng để lên báo giá và chốt căn</p>
          </CardContent>
        </Card>

        <Card className="border-border shadow-xs">
          <CardHeader className="py-3 px-4 flex flex-row items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground">Chiết khấu tối đa hiện hành</span>
            <Percent className="h-4 w-4 text-amber-600" />
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0">
            <div className="text-2xl font-bold font-display text-amber-600">8.0% - 9.5%</div>
            <p className="text-[11px] text-muted-foreground mt-0.5">Áp dụng cho thanh toán sớm 95%</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters Card */}
      <Card className="border-border shadow-xs">
        <CardContent className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Tìm theo mã chính sách, tên văn bản, từ khóa..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 text-xs"
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <Select value={projectFilter} onValueChange={setProjectFilter}>
                <SelectTrigger className="w-[180px] text-xs">
                  <SelectValue placeholder="Dự án" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">Tất cả dự án</SelectItem>
                  {projectsQuery.data?.map((prj) => (
                    <SelectItem key={prj.project.project_id} value={prj.project.project_id}>
                      {PROJECT_LABEL[prj.project.project_id] || prj.project.name || prj.project.project_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={statusFilter}
                onValueChange={(val) => setStatusFilter(val as typeof statusFilter)}
              >
                <SelectTrigger className="w-[160px] text-xs">
                  <SelectValue placeholder="Trạng thái" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">Tất cả trạng thái</SelectItem>
                  <SelectItem value="PUBLISHED">Đang áp dụng</SelectItem>
                  <SelectItem value="DRAFT">Dự thảo</SelectItem>
                  <SelectItem value="ARCHIVED">Lưu trữ</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Policies List Table */}
      <Card className="border-border shadow-xs">
        <CardHeader className="py-3 px-4 border-b border-border bg-muted/20">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold">
              Danh sách văn bản chính sách ({filteredPolicies.length})
            </CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => policiesQuery.refetch()}
              disabled={policiesQuery.isFetching}
              className="h-7 text-xs gap-1"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', policiesQuery.isFetching && 'animate-spin')} />
              Làm mới
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {policiesQuery.isLoading ? (
            <LoadingState className="py-16" />
          ) : filteredPolicies.length === 0 ? (
            <EmptyState
              icon={ScrollText}
              title="Không tìm thấy chính sách nào"
              description="Thử thay đổi bộ lọc tìm kiếm hoặc từ khóa tra cứu."
            />
          ) : (
            <div className="overflow-x-auto">
              <Table className="min-w-[900px]">
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-[140px] text-xs">Mã văn bản</TableHead>
                    <TableHead className="text-xs">Tên chính sách & Dự án</TableHead>
                    <TableHead className="w-[120px] text-xs">Trạng thái</TableHead>
                    <TableHead className="w-[180px] text-xs">Thời hạn áp dụng</TableHead>
                    <TableHead className="w-[90px] text-xs">Phiên bản</TableHead>
                    <TableHead className="w-[220px] min-w-[220px] text-right text-xs">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPolicies.map((p) => {
                    const isEffective =
                      p.effective_from <= today && (!p.effective_to || p.effective_to >= today)

                    return (
                      <TableRow key={p.policy_id} className="hover:bg-muted/40">
                        <TableCell className="font-mono text-xs font-semibold text-primary">
                          {p.policy_id}
                        </TableCell>
                        <TableCell>
                          <div className="space-y-0.5">
                            <span className="font-medium text-xs text-foreground block">
                              {p.title}
                            </span>
                            <span className="text-[11px] text-muted-foreground">
                              {PROJECT_LABEL[p.project_id] || p.project_id}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <PolicyStatusBadge status={p.status} />
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          <div className="flex flex-col text-[11px]">
                            <span>Từ: {formatDate(p.effective_from)}</span>
                            <span>Đến: {p.effective_to ? formatDate(p.effective_to) : 'Không thời hạn'}</span>
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {p.policy_version}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1.5 whitespace-nowrap">
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 text-xs gap-1 text-primary hover:bg-primary hover:text-primary-foreground"
                              onClick={() => handleAskCopilot(p)}
                            >
                              <Sparkles className="h-3 w-3" />
                              Hỏi Copilot
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs gap-1"
                              onClick={() => setSelectedPolicy(p)}
                            >
                              <Eye className="h-3 w-3" />
                              Chi tiết
                            </Button>
                          </div>
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

      {/* Policy Detail Dialog */}
      <Dialog open={selectedPolicy !== null} onOpenChange={(open) => !open && setSelectedPolicy(null)}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle className="text-sm font-semibold flex items-center gap-2">
              <ScrollText className="h-4 w-4 text-primary" />
              Chi tiết chính sách {selectedPolicy?.policy_id}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {selectedPolicy?.title} · Dự án {PROJECT_LABEL[selectedPolicy?.project_id || ''] || selectedPolicy?.project_id}
            </DialogDescription>
          </DialogHeader>

          {selectedPolicy && (
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3 rounded-lg bg-muted/30 p-3 border border-border">
                <div>
                  <span className="text-muted-foreground block text-[11px]">Trạng thái:</span>
                  <div className="mt-1">
                    <PolicyStatusBadge status={selectedPolicy.status} />
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px]">Phiên bản:</span>
                  <span className="font-mono font-semibold text-foreground mt-1 block">
                    {selectedPolicy.policy_version}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px]">Ngày bắt đầu:</span>
                  <span className="font-medium text-foreground">
                    {formatDate(selectedPolicy.effective_from)}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px]">Ngày kết thúc:</span>
                  <span className="font-medium text-foreground">
                    {selectedPolicy.effective_to ? formatDate(selectedPolicy.effective_to) : 'Vô thời hạn'}
                  </span>
                </div>
              </div>

              {(selectedPolicy.source_document || selectedPolicy.document_id) && (
                <div className="flex items-center justify-between rounded-lg border border-border p-2.5">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-primary" />
                    <span className="font-mono text-[11px] text-foreground">
                      {selectedPolicy.source_document || selectedPolicy.document_id}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-[10px]">
                    Văn bản gốc
                  </Badge>
                </div>
              )}

              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 space-y-1">
                <div className="font-semibold text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4" />
                  Được xác thực bởi Deterministic Math Engine (FCS v2.6)
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Tất cả các công thức chiết khấu thanh toán sớm, ân hạn nợ gốc và lãi suất 0% đều được đối soát tự động khi lập báo giá.
                </p>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={() => setSelectedPolicy(null)}>
              Đóng
            </Button>
            {selectedPolicy && (
              <Button
                size="sm"
                onClick={() => {
                  const p = selectedPolicy
                  setSelectedPolicy(null)
                  handleAskCopilot(p)
                }}
              >
                <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                Hỏi Copilot về chính sách này
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
export default SalePoliciesPage
