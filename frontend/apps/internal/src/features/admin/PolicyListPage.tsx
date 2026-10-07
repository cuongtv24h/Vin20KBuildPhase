import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  Eye,
  FileCheck,
  FilePlus2,
  FileText,
  FileUp,
  Filter,
  Layers,
  Loader2,
  Plus,
  Scale,
  ScrollText,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  X,
} from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ExtractRulesFields, PolicyDocument, PolicyStatus } from '@pricepolicy/api-client/contracts'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useExtractRules, usePolicies, useProjectOverviews } from '@pricepolicy/api-client/hooks'
import { EmptyState, LoadingState, PageHeader } from '@pricepolicy/ui/components/common/PageStates'
import { PolicyStatusBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { formatDate, formatDateTime, todayIso, truncateHash } from '@pricepolicy/ui/lib/format'
import { PROJECT_LABEL } from '@pricepolicy/ui/lib/labels'
import { toast } from '@pricepolicy/ui/state/toastStore'
import { cn } from '@pricepolicy/ui/lib/utils'

export function PolicyListPage() {
  const policiesQuery = usePolicies()
  const projectsQuery = useProjectOverviews()
  const navigate = useNavigate()

  const [uploadOpen, setUploadOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [projectFilter, setProjectFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'DRAFT' | 'EXPIRED' | 'ARCHIVED'>('ALL')

  const today = todayIso()
  const allPolicies = policiesQuery.data ?? []

  // Metrics summary
  const metrics = useMemo(() => {
    const total = allPolicies.length
    const published = allPolicies.filter((p) => p.status === 'PUBLISHED')
    const active = published.filter((p) => p.effective_to >= today)
    const expired = published.filter((p) => p.effective_to < today)
    const drafts = allPolicies.filter((p) => p.status === 'DRAFT')
    const totalRules = allPolicies.reduce((acc, p) => acc + p.rules.length, 0)

    return {
      total,
      active: active.length,
      drafts: drafts.length,
      expired: expired.length,
      totalRules,
    }
  }, [allPolicies, today])

  // Filtered policies
  const filteredPolicies = useMemo(() => {
    return allPolicies.filter((p) => {
      if (projectFilter !== 'ALL' && p.project_id !== projectFilter) return false

      const isExpired = p.effective_to < today
      if (statusFilter === 'ACTIVE' && (p.status !== 'PUBLISHED' || isExpired)) return false
      if (statusFilter === 'DRAFT' && p.status !== 'DRAFT') return false
      if (statusFilter === 'EXPIRED' && (!isExpired || p.status !== 'PUBLISHED')) return false
      if (statusFilter === 'ARCHIVED' && p.status !== 'ARCHIVED') return false

      if (searchTerm.trim()) {
        const s = searchTerm.toLowerCase().trim()
        const matchTitle = p.title.toLowerCase().includes(s)
        const matchId = p.policy_id.toLowerCase().includes(s)
        const matchVersion = p.policy_version.toLowerCase().includes(s)
        const matchDoc = p.source_document.toLowerCase().includes(s)
        if (!matchTitle && !matchId && !matchVersion && !matchDoc) return false
      }

      return true
    })
  }, [allPolicies, projectFilter, statusFilter, searchTerm, today])

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ScrollText className="h-5 w-5" />
            </span>
            <div>
              <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
                Quản trị Chính sách Bán hàng và RAG Rules
              </h1>
              <p className="text-xs text-muted-foreground">
                Nguồn chân lý duy nhất (Single Source of Truth) · Số hóa văn bản PDF, ma trận xung đột và Time-Travel Versioning
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button onClick={() => setUploadOpen(true)} className="gap-2 text-xs font-semibold" data-testid="upload-policy">
            <FileUp className="h-4 w-4" />
            <span>Tải lên văn bản chính sách mới</span>
          </Button>
        </div>
      </div>

      {/* Metrics Dashboard */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Card className="border-primary/20 bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Tổng văn bản</span>
              <ScrollText className="h-4 w-4 text-primary" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-display text-2xl font-bold tabular-nums text-foreground">{metrics.total}</span>
              <span className="text-xs text-muted-foreground">chính sách trong hệ thống</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-success/20 bg-success/[0.02] shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-success">Đang hiệu lực</span>
              <CheckCircle2 className="h-4 w-4 text-success" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-display text-2xl font-bold tabular-nums text-success">{metrics.active}</span>
              <span className="text-xs text-muted-foreground">đang áp dụng tính giá</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-warning/20 bg-warning/[0.02] shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-warning">Bản thảo (DRAFT)</span>
              <Clock className="h-4 w-4 text-warning" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-display text-2xl font-bold tabular-nums text-warning">{metrics.drafts}</span>
              <span className="text-xs text-muted-foreground">chờ kiểm thử và ban hành</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Đã hết hạn</span>
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-display text-2xl font-bold tabular-nums text-foreground">{metrics.expired}</span>
              <span className="text-xs text-muted-foreground">lưu trữ đối soát Time-Travel</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Điều khoản số hóa</span>
              <Layers className="h-4 w-4 text-primary" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-display text-2xl font-bold tabular-nums text-foreground">{metrics.totalRules}</span>
              <span className="text-xs text-muted-foreground">atoms / rules trích xuất</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Table Container */}
      <Card className="border-border bg-card shadow-sm">
        <div className="border-b border-border/80 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {/* Search */}
            <div className="relative min-w-[240px] flex-1 sm:max-w-xs">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Tìm tiêu đề, mã chính sách, file PDF..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="h-8 pl-8 text-xs"
              />
            </div>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2">
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

              {/* Status Filter */}
              <Select
                value={statusFilter}
                onValueChange={(v) => setStatusFilter(v as 'ALL' | 'ACTIVE' | 'DRAFT' | 'EXPIRED' | 'ARCHIVED')}
              >
                <SelectTrigger className="h-8 w-[150px] text-xs">
                  <SelectValue placeholder="Trạng thái" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">Tất cả trạng thái</SelectItem>
                  <SelectItem value="ACTIVE"><span className="inline-flex items-center"><span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-full bg-success" />Đang có hiệu lực</span></SelectItem>
                  <SelectItem value="DRAFT"><span className="inline-flex items-center"><span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-full bg-warning" />Bản thảo DRAFT</span></SelectItem>
                  <SelectItem value="EXPIRED"><span className="inline-flex items-center"><span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-full bg-muted-foreground" />Đã hết hạn</span></SelectItem>
                  <SelectItem value="ARCHIVED">Lưu trữ ARCHIVED</SelectItem>
                </SelectContent>
              </Select>

              {(searchTerm || projectFilter !== 'ALL' || statusFilter !== 'ALL') && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSearchTerm('')
                    setProjectFilter('ALL')
                    setStatusFilter('ALL')
                  }}
                  className="h-8 px-2 text-xs text-muted-foreground"
                >
                  Xóa lọc
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Table Content */}
        <CardContent className="p-0">
          {policiesQuery.isLoading ? (
            <div className="py-16">
              <LoadingState label="Đang tải danh mục chính sách bán hàng…" />
            </div>
          ) : filteredPolicies.length === 0 ? (
            <div className="py-16">
              <EmptyState
                icon={ScrollText}
                title="Không tìm thấy văn bản chính sách nào"
                description={
                  searchTerm || projectFilter !== 'ALL' || statusFilter !== 'ALL'
                    ? 'Không có kết quả phù hợp với điều kiện tìm kiếm hiện tại.'
                    : 'Hệ thống chưa có văn bản chính sách nào. Hãy tải lên văn bản PDF đầu tiên.'
                }
                action={
                  <Button onClick={() => setUploadOpen(true)} size="sm" className="gap-1.5 text-xs">
                    <FileUp className="h-3.5 w-3.5" /> Tải lên văn bản
                  </Button>
                }
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30 text-xs">
                    <TableHead className="w-[300px]">Văn bản và Phiên bản</TableHead>
                    <TableHead className="w-[180px]">Dự án áp dụng</TableHead>
                    <TableHead className="w-[220px]">Thời hạn hiệu lực</TableHead>
                    <TableHead className="w-[130px] text-right">Điều khoản (Rules)</TableHead>
                    <TableHead className="w-[150px]">Trạng thái</TableHead>
                    <TableHead className="w-[120px] text-center">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPolicies.map((p) => {
                    const isExpired = p.effective_to < today
                    const isDraft = p.status === 'DRAFT'

                    return (
                      <TableRow
                        key={p.policy_id}
                        className="cursor-pointer transition-colors hover:bg-muted/40"
                        onClick={() => navigate(`/admin/policies/${encodeURIComponent(p.policy_id)}`)}
                      >
                        {/* Title & Document Info */}
                        <TableCell>
                          <div className="space-y-0.5">
                            <p className="font-semibold text-foreground text-xs hover:text-primary transition-colors">
                              {p.title}
                            </p>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span className="font-mono text-primary">{p.policy_id}</span>
                              <span>·</span>
                              <Badge variant="outline" className="px-1 py-0 text-xs">
                                {p.policy_version}
                              </Badge>
                            </div>
                            <p className="font-mono text-xs text-muted-foreground" title={p.document_hash}>
                              {p.source_document} (SHA-256: {truncateHash(p.document_hash, 8)})
                            </p>
                          </div>
                        </TableCell>

                        {/* Project */}
                        <TableCell>
                          <Badge variant="outline" className="text-xs font-medium">
                            {PROJECT_LABEL[p.project_id] ?? p.project_id}
                          </Badge>
                        </TableCell>

                        {/* Validity Range */}
                        <TableCell>
                          <div className="space-y-1 text-xs">
                            <div className="flex items-center gap-1.5 font-medium text-foreground">
                              <Calendar className="h-3 w-3 text-muted-foreground" />
                              <span>{formatDate(p.effective_from)} – {formatDate(p.effective_to)}</span>
                            </div>
                            {isDraft ? (
                              <span className="text-xs text-warning font-medium">Chưa ban hành</span>
                            ) : isExpired ? (
                              <span className="text-xs text-muted-foreground">Đã hết hiệu lực</span>
                            ) : (
                              <span className="text-xs text-success font-medium">Đang áp dụng</span>
                            )}
                          </div>
                        </TableCell>

                        {/* Rules count */}
                        <TableCell className="text-right">
                          <div className="space-y-0.5">
                            <span className="font-mono font-bold text-sm tabular-nums text-foreground">
                              {p.rules.length}
                            </span>
                            <p className="text-xs text-muted-foreground">quy tắc số hóa</p>
                          </div>
                        </TableCell>

                        {/* Status */}
                        <TableCell>
                          <PolicyStatusBadge status={p.status} expired={isExpired} />
                        </TableCell>

                        {/* Actions */}
                        <TableCell className="text-center" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant={isDraft ? 'default' : 'outline'}
                            size="sm"
                            className="h-8 gap-1 px-2.5 text-xs"
                            onClick={() => navigate(`/admin/policies/${encodeURIComponent(p.policy_id)}`)}
                          >
                            <Eye className="h-3.5 w-3.5" />
                            <span>{isDraft ? 'Thẩm định' : 'Chi tiết'}</span>
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

      {/* Upload Dialog */}
      {uploadOpen && <UploadPolicyDialog onClose={() => setUploadOpen(false)} />}
    </div>
  )
}

/** Hộp thoại tải lên văn bản chính sách & Tự động trích xuất quy tắc */
function UploadPolicyDialog({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const extract = useExtractRules()
  const projects = useProjectOverviews()

  const [file, setFile] = useState<File | null>(null)
  const [fields, setFields] = useState<ExtractRulesFields>({
    project_id: 'THE_ZEN_PARK',
    title: '',
    policy_version: 'v1.0',
    effective_from: todayIso(),
    effective_to: '2026-12-31',
  })

  const setField = (k: keyof ExtractRulesFields, v: string) => setFields((f) => ({ ...f, [k]: v }))
  const isValid = file && fields.title.trim() && fields.policy_version.trim() && fields.effective_from && fields.effective_to

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    try {
      const draft = await extract.mutateAsync({ fields, file })
      toast.success('Đã trích xuất điều khoản thành công', `${draft.rules.length} quy tắc số hóa chờ thẩm định`)
      onClose()
      navigate(`/admin/policies/${encodeURIComponent(draft.policy_id)}`)
    } catch (err) {
      toast.error('Không thể trích xuất văn bản', errorMessage(err))
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[540px]">
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <div className="flex items-center gap-2 text-primary">
              <UploadCloud className="h-5 w-5" />
              <DialogTitle className="text-base font-bold">
                Tải lên và Số hóa Văn bản Chính sách Bán hàng
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs">
              AI Agent sẽ tự động phân tích cấu trúc văn bản PDF/DOCX, trích xuất bảng chiết khấu, quà tặng và ma trận điều khoản loại trừ.
            </DialogDescription>
          </DialogHeader>

          {/* File Dropzone */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">Tệp tin chính sách (PDF hoặc Word)</Label>
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-border p-5 text-center transition-colors hover:border-primary/50 hover:bg-muted/20">
              <input
                type="file"
                id="policy-file"
                accept=".pdf,.docx,.doc"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) {
                    setFile(f)
                    if (!fields.title) {
                      setField('title', f.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' '))
                    }
                  }
                }}
              />
              <label htmlFor="policy-file" className="cursor-pointer space-y-1">
                <FileUp className="mx-auto h-8 w-8 text-muted-foreground" />
                <p className="text-xs font-medium text-foreground">
                  {file ? file.name : 'Kéo thả hoặc bấm để chọn tệp tin'}
                </p>
                <p className="text-xs text-muted-foreground">
                  {file ? `${(file.size / 1024).toFixed(1)} KB` : 'Định dạng hỗ trợ: PDF, DOCX (Tối đa 25MB)'}
                </p>
              </label>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="project" className="text-xs font-semibold">Dự án áp dụng</Label>
              <Select value={fields.project_id} onValueChange={(v) => setField('project_id', v)}>
                <SelectTrigger id="project" className="text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {projects.data?.map((p) => (
                    <SelectItem key={p.project.project_id} value={p.project.project_id}>
                      {PROJECT_LABEL[p.project.project_id] ?? p.project.name}
                    </SelectItem>
                  )) ?? (
                    <>
                      <SelectItem value="THE_ZEN_PARK">The Zen Park</SelectItem>
                      <SelectItem value="THE_BEVERLY">The Beverly</SelectItem>
                      <SelectItem value="THE_EMERALD_PALACE">The Emerald Palace</SelectItem>
                    </>
                  )}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="version" className="text-xs font-semibold">Mã phiên bản ban hành</Label>
              <Input
                id="version"
                value={fields.policy_version}
                onChange={(e) => setField('policy_version', e.target.value)}
                placeholder="VD: v2.1 hoặc CSBH-03"
                className="text-xs"
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="title" className="text-xs font-semibold">Tiêu đề chính thức của chính sách</Label>
            <Input
              id="title"
              value={fields.title}
              onChange={(e) => setField('title', e.target.value)}
              placeholder="VD: Chính sách bán hàng Đợt 3 - Tòa Park 1..."
              className="text-xs"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="from" className="text-xs font-semibold">Có hiệu lực từ ngày</Label>
              <Input
                id="from"
                type="date"
                value={fields.effective_from}
                onChange={(e) => setField('effective_from', e.target.value)}
                className="text-xs"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="to" className="text-xs font-semibold">Hết hiệu lực vào ngày</Label>
              <Input
                id="to"
                type="date"
                value={fields.effective_to}
                onChange={(e) => setField('effective_to', e.target.value)}
                className="text-xs"
                required
              />
            </div>
          </div>

          <DialogFooter className="gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={extract.isPending}>
              Hủy
            </Button>
            <Button type="submit" variant="default" size="sm" disabled={!isValid || extract.isPending} className="gap-2">
              {extract.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              <span>{extract.isPending ? 'Đang trích xuất điều khoản…' : 'Số hóa và Trích xuất điều khoản'}</span>
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
