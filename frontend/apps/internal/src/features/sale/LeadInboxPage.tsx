import React, { useState, useMemo, useEffect } from 'react'
import {
  ArrowRight,
  FilePlus2,
  Inbox,
  Phone,
  ShieldCheck,
  UserPlus,
  UserCheck,
  Users,
  Search,
  Sparkles,
  Edit3,
  Save,
  Trash2,
  Flame,
  CheckCircle2,
  Clock,
  Building,
  DollarSign,
  Tag,
  MessageSquare,
  X,
  ExternalLink,
  RefreshCw,
  ChevronRight,
} from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import type {
  LeadDossier,
  LeadCreatePayload,
  LeadUpdatePayload,
  CustomerSegment,
  LeadTemperature,
  LeadDossierStatus,
  OptimizationObjective,
} from '@pricepolicy/api-client/contracts'
import {
  useLeads,
  useCreateLead,
  useUpdateLead,
  useDeleteLead,
} from '@pricepolicy/api-client/hooks'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { EmptyState, PageHeader, QueryState } from '@pricepolicy/ui/components/common/PageStates'
import { SlaCountdown } from '@pricepolicy/ui/components/common/SlaCountdown'
import { TemperatureBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import { Textarea } from '@pricepolicy/ui/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@pricepolicy/ui/components/ui/select'
import { formatDateTime, formatRelative, formatVnd, formatNumber } from '@pricepolicy/ui/lib/format'
import {
  DOSSIER_STATUS_LABEL,
  OBJECTIVE_LABEL,
  PROJECT_LABEL,
  SEGMENT_LABEL,
} from '@pricepolicy/ui/lib/labels'
import { toast } from '@pricepolicy/ui/state/toastStore'
import { cn } from '@pricepolicy/ui/lib/utils'

// ============================================================================
// MAIN CRM KHÁCH HÀNG PAGE (MENU TRÁI: KHÁCH HÀNG)
// ============================================================================

export function LeadInboxPage() {
  const leadsQuery = useLeads()
  const createLeadMutation = useCreateLead()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()

  // Selection & Search State
  const selectedId = params.get('id')
  const [searchQuery, setSearchQuery] = useState('')
  const [segmentFilter, setSegmentFilter] = useState<string>('ALL')
  const [temperatureFilter, setTemperatureFilter] = useState<string>('ALL')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [isCreateOpen, setIsCreateOpen] = useState(false)

  // Quick form for manual "+ Thêm khách hàng"
  const [newForm, setNewForm] = useState<LeadCreatePayload>({
    customer_name: '',
    customer_phone: '',
    customer_segment: 'NEW_CUSTOMER',
    project_id: 'P-001',
    preferred_unit_code: 'R-02.02',
    bedrooms: 2,
    own_funds_vnd: 1500000000,
    monthly_capacity_vnd: 25000000,
    objective: 'MIN_INITIAL_OUTFLOW',
    temperature: 'WARM',
    needs_summary: '',
  })

  const leads = useMemo(() => leadsQuery.data ?? [], [leadsQuery.data])

  const selectedLead = useMemo(() => {
    if (!selectedId) return null
    return leads.find((l) => l.dossier_id === selectedId) ?? null
  }, [leads, selectedId])

  // Handle manual customer creation form
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newForm.customer_name.trim()) {
      toast.error('Vui lòng nhập họ và tên khách hàng')
      return
    }
    try {
      const created = await createLeadMutation.mutateAsync(newForm)
      toast.success('Đã thêm khách hàng mới vào CRM', created.customer?.full_name || created.customer_name)
      setIsCreateOpen(false)
      setParams({ id: created.dossier_id })
      setNewForm({
        customer_name: '',
        customer_phone: '',
        customer_segment: 'NEW_CUSTOMER',
        project_id: 'P-001',
        preferred_unit_code: 'R-02.02',
        bedrooms: 2,
        own_funds_vnd: 1500000000,
        monthly_capacity_vnd: 25000000,
        objective: 'MIN_INITIAL_OUTFLOW',
        temperature: 'WARM',
        needs_summary: '',
      })
    } catch (err: any) {
      toast.error('Không thể tạo khách hàng', err?.message || 'Lỗi kết nối')
    }
  }

  // Filter CRM leads
  const filteredLeads = useMemo(() => {
    return leads.filter((d) => {
      const name = d.customer?.full_name || d.customer_name || ''
      const phone = d.customer?.phone || d.customer_phone_masked || ''
      const unit = d.constraints?.preferred_unit_code || d.preferred_unit_code || d.unit_code || ''
      const matchSearch =
        searchQuery.trim() === '' ||
        name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        phone.includes(searchQuery.trim()) ||
        unit.toLowerCase().includes(searchQuery.toLowerCase())

      const matchTemp =
        temperatureFilter === 'ALL' ||
        d.temperature === temperatureFilter ||
        d.lead_temperature === temperatureFilter

      const segment = d.constraints?.customer_segment || d.customer_segment || d.segment || ''
      const matchSegment = segmentFilter === 'ALL' || segment === segmentFilter

      const matchStatus = statusFilter === 'ALL' || d.status === statusFilter

      return matchSearch && matchTemp && matchSegment && matchStatus
    })
  }, [leads, searchQuery, temperatureFilter, segmentFilter, statusFilter])

  // KPIs
  const kpis = useMemo(() => {
    const total = leads.length
    const hot = leads.filter((l) => l.temperature === 'HOT' || l.lead_temperature === 'HOT').length
    const inProgress = leads.filter((l) => l.status === 'NEW' || l.status === 'ASSIGNED').length
    const converted = leads.filter((l) => l.status === 'CONVERTED_TO_QUOTE').length
    return { total, hot, inProgress, converted }
  }, [leads])

  return (
    <div className="space-y-6">
      {/* 1. Header & Actions */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
              CRM Quản trị khách hàng
            </h1>
            <Badge variant="outline" className="border-primary/30 text-primary bg-primary/10 text-xs">
              VLand Future Riverside
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            Theo dõi, phân loại và cập nhật hồ sơ khách hàng tiềm năng cho chuyên viên kinh doanh
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline" size="sm" className="gap-1.5 h-8 text-xs border-amber-500/40 text-amber-700 dark:text-amber-300 hover:bg-amber-500/10">
            <Link to="/sale/workspace">
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              Mở Trợ lý Copilot
            </Link>
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => leadsQuery.refetch()}
            className="h-8 text-xs gap-1.5"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', leadsQuery.isFetching && 'animate-spin')} />
            Làm mới
          </Button>
          <Button
            size="sm"
            onClick={() => setIsCreateOpen(true)}
            className="h-8 text-xs gap-1.5 bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <UserPlus className="h-3.5 w-3.5" />
            + Thêm khách hàng
          </Button>
        </div>
      </div>

      {/* 2. Top KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="border-border bg-card shadow-xs">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Tổng khách hàng</p>
              <p className="font-display text-2xl font-bold text-foreground mt-0.5">{kpis.total}</p>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Users className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-red-500/20 bg-red-500/[0.02] shadow-xs">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-red-700 dark:text-red-400 uppercase tracking-wider">Khách HOT 🔥</p>
              <p className="font-display text-2xl font-bold text-red-600 dark:text-red-400 mt-0.5">{kpis.hot}</p>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-500/10 text-red-600">
              <Flame className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-blue-500/20 bg-blue-500/[0.02] shadow-xs">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-blue-700 dark:text-blue-400 uppercase tracking-wider">Đang tư vấn</p>
              <p className="font-display text-2xl font-bold text-blue-600 dark:text-blue-400 mt-0.5">{kpis.inProgress}</p>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/10 text-blue-600">
              <Clock className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-emerald-500/20 bg-emerald-500/[0.02] shadow-xs">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400 uppercase tracking-wider">Đã lên báo giá</p>
              <p className="font-display text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">{kpis.converted}</p>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3. Search & Multi-criteria Filters */}
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-3 shadow-xs lg:flex-row lg:items-center lg:justify-between">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Tìm kiếm theo họ tên, số điện thoại hoặc mã căn hộ..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-8 text-xs"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Temperature Filter Chips */}
          <div className="flex items-center rounded-lg border border-border bg-background p-0.5 text-xs">
            {(['ALL', 'HOT', 'WARM', 'COLD'] as const).map((temp) => (
              <button
                key={temp}
                type="button"
                onClick={() => setTemperatureFilter(temp)}
                className={cn(
                  'rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors',
                  temperatureFilter === temp
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {temp === 'ALL' ? 'Tất cả' : temp === 'HOT' ? '🔥 HOT' : temp === 'WARM' ? '⛅ WARM' : '❄️ COLD'}
              </button>
            ))}
          </div>

          {/* Segment Dropdown */}
          <Select value={segmentFilter} onValueChange={setSegmentFilter}>
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <SelectValue placeholder="Phân khúc" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Mọi phân khúc</SelectItem>
              <SelectItem value="NEW_CUSTOMER">Khách mới</SelectItem>
              <SelectItem value="INVESTOR">Nhà đầu tư</SelectItem>
              <SelectItem value="END_USER">Mua ở thực</SelectItem>
              <SelectItem value="VIP">VIP</SelectItem>
            </SelectContent>
          </Select>

          {/* Status Dropdown */}
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <SelectValue placeholder="Trạng thái" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Mọi trạng thái</SelectItem>
              <SelectItem value="NEW">Chờ tiếp nhận</SelectItem>
              <SelectItem value="ASSIGNED">Đang tư vấn</SelectItem>
              <SelectItem value="CONVERTED_TO_QUOTE">Đã lên báo giá</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* 4. CRM Two-Column Main Area */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Left: Customer Cards List */}
        <div className="lg:col-span-5 space-y-2.5 max-h-[720px] overflow-y-auto pr-1">
          {filteredLeads.length === 0 ? (
            <Card className="border-dashed p-8 text-center text-muted-foreground">
              <p className="text-xs">Không tìm thấy khách hàng nào khớp với bộ lọc.</p>
            </Card>
          ) : (
            filteredLeads.map((d) => {
              const isSelected = d.dossier_id === selectedId
              const custName = d.customer?.full_name || d.customer_name || 'Khách hàng'
              const phone = d.customer?.phone || d.customer_phone_masked || '090***'
              const temp = d.temperature || d.lead_temperature || 'WARM'
              const unit = d.constraints?.preferred_unit_code || d.preferred_unit_code || d.unit_code || 'R-02.02'
              const funds = d.constraints?.own_funds_vnd || 0
              const segment = d.constraints?.customer_segment || d.customer_segment || d.segment || 'NEW_CUSTOMER'

              return (
                <Card
                  key={d.dossier_id}
                  onClick={() => setParams({ id: d.dossier_id })}
                  className={cn(
                    'cursor-pointer border transition-all hover:border-primary/50 hover:shadow-sm text-xs',
                    isSelected ? 'border-primary ring-1 ring-primary/30 bg-primary/[0.02]' : 'border-border bg-card'
                  )}
                >
                  <CardContent className="p-3.5 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-bold text-sm text-foreground truncate">{custName}</span>
                          <TemperatureBadge temperature={temp} />
                          {d.status === 'CONVERTED_TO_QUOTE' && (
                            <Badge variant="outline" className="border-emerald-500/30 text-emerald-700 bg-emerald-500/10 text-[9px] px-1 py-0">
                              Đã chốt báo giá
                            </Badge>
                          )}
                        </div>
                        <div className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-2">
                          <span>📞 {phone}</span>
                          <span>·</span>
                          <span>{SEGMENT_LABEL[segment as CustomerSegment] || segment}</span>
                        </div>
                      </div>
                      <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                        {formatRelative(d.created_at)}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 rounded-lg bg-muted/40 p-2 text-[11px]">
                      <div>
                        <span className="text-muted-foreground">Căn quan tâm: </span>
                        <span className="font-semibold text-foreground">{unit}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-muted-foreground">Vốn tự có: </span>
                        <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                          {funds > 0 ? formatVnd(funds) : 'Chưa rõ'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <p className="text-[11px] text-muted-foreground line-clamp-1 italic max-w-[240px]">
                        {d.needs_summary || 'Nhu cầu quan tâm dự án...'}
                      </p>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/sale/workspace?id=${d.dossier_id}`)
                        }}
                        className="h-6 px-2 text-[10px] font-semibold text-amber-600 hover:text-amber-700 hover:bg-amber-500/10 gap-1 rounded-md"
                      >
                        <Sparkles className="h-3 w-3" />
                        Hỏi Copilot
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )
            })
          )}
        </div>

        {/* Right: Detailed Customer Editor & View */}
        <div className="lg:col-span-7">
          {selectedLead ? (
            <CustomerCrmEditor
              dossier={selectedLead}
              onAskCopilot={() => navigate(`/sale/workspace?id=${selectedLead.dossier_id}`)}
              onDeleted={() => {
                setParams({})
              }}
            />
          ) : (
            <Card className="border-dashed p-12 text-center text-muted-foreground flex flex-col items-center justify-center min-h-[420px]">
              <Users className="h-10 w-10 text-muted-foreground/40 mb-3" />
              <p className="font-semibold text-sm text-foreground">Chọn một khách hàng từ danh sách</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                Xem và chỉnh sửa hồ sơ chi tiết, phân khúc, vốn tài chính, căn hộ mong muốn hoặc chuyển ngữ cảnh cho Trợ lý Copilot.
              </p>
              <Button
                size="sm"
                onClick={() => setIsCreateOpen(true)}
                className="mt-4 gap-1.5 h-8 text-xs bg-primary text-primary-foreground"
              >
                <UserPlus className="h-3.5 w-3.5" />
                Thêm khách hàng mới
              </Button>
            </Card>
          )}
        </div>
      </div>

      {/* 5. MODAL TẠO KHÁCH HÀNG NHANH */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="sm:max-w-[540px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-semibold">
              <UserPlus className="h-4 w-4 text-primary" />
              Thêm khách hàng mới vào CRM
            </DialogTitle>
            <DialogDescription className="text-xs">
              Nhập thông tin ban đầu của khách hàng để bắt đầu theo dõi trong CRM và nạp ngữ cảnh cho Trợ lý Copilot.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateSubmit} className="space-y-3.5 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Họ và tên khách hàng *</Label>
                <Input
                  value={newForm.customer_name}
                  onChange={(e) => setNewForm((prev) => ({ ...prev, customer_name: e.target.value }))}
                  placeholder="Ví dụ: Trần Đình Dường"
                  className="mt-1 h-8 text-xs"
                  required
                />
              </div>
              <div>
                <Label className="text-xs">Số điện thoại *</Label>
                <Input
                  value={newForm.customer_phone}
                  onChange={(e) => setNewForm((prev) => ({ ...prev, customer_phone: e.target.value }))}
                  placeholder="0939949959"
                  className="mt-1 h-8 text-xs"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Phân khúc</Label>
                <Select
                  value={newForm.customer_segment}
                  onValueChange={(val: CustomerSegment) =>
                    setNewForm((prev) => ({ ...prev, customer_segment: val }))
                  }
                >
                  <SelectTrigger className="mt-1 h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="NEW_CUSTOMER">Khách mới</SelectItem>
                    <SelectItem value="INVESTOR">Nhà đầu tư</SelectItem>
                    <SelectItem value="END_USER">Mua ở</SelectItem>
                    <SelectItem value="VIP">VIP</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-xs">Nhiệt độ lead</Label>
                <Select
                  value={newForm.temperature}
                  onValueChange={(val: LeadTemperature) =>
                    setNewForm((prev) => ({ ...prev, temperature: val }))
                  }
                >
                  <SelectTrigger className="mt-1 h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="HOT">🔥 HOT</SelectItem>
                    <SelectItem value="WARM">⛅ WARM</SelectItem>
                    <SelectItem value="COLD">❄️ COLD</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-xs">Căn hộ quan tâm</Label>
                <Input
                  value={newForm.preferred_unit_code || ''}
                  onChange={(e) =>
                    setNewForm((prev) => ({ ...prev, preferred_unit_code: e.target.value }))
                  }
                  placeholder="R-05.01"
                  className="mt-1 h-8 text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="flex items-center justify-between">
                  <Label className="text-xs">Vốn tự có sẵn sàng</Label>
                  <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                    {formatNumber(newForm.own_funds_vnd || 0)} ₫
                  </span>
                </div>
                <Input
                  type="text"
                  value={newForm.own_funds_vnd ? formatNumber(newForm.own_funds_vnd) : ''}
                  onChange={(e) => {
                    const raw = e.target.value.replace(/\D/g, '')
                    setNewForm((prev) => ({ ...prev, own_funds_vnd: raw ? parseInt(raw, 10) : 0 }))
                  }}
                  placeholder="5.000.000.000"
                  className="mt-1 h-8 text-xs font-semibold"
                />
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <Label className="text-xs">Khả năng chi trả/tháng</Label>
                  <span className="text-[11px] font-semibold text-primary">
                    {formatNumber(newForm.monthly_capacity_vnd || 0)} ₫
                  </span>
                </div>
                <Input
                  type="text"
                  value={newForm.monthly_capacity_vnd ? formatNumber(newForm.monthly_capacity_vnd) : ''}
                  onChange={(e) => {
                    const raw = e.target.value.replace(/\D/g, '')
                    setNewForm((prev) => ({ ...prev, monthly_capacity_vnd: raw ? parseInt(raw, 10) : 0 }))
                  }}
                  placeholder="25.000.000"
                  className="mt-1 h-8 text-xs font-semibold"
                />
              </div>
            </div>

            <div>
              <Label className="text-xs">Ghi chú nhu cầu khách hàng</Label>
              <Textarea
                rows={2}
                value={newForm.needs_summary || ''}
                onChange={(e) => setNewForm((prev) => ({ ...prev, needs_summary: e.target.value }))}
                placeholder="Ví dụ: Khách muốn mua căn 3 ngủ ~100m2 hướng Đông Nam, có sẵn tài chính 5 tỷ..."
                className="mt-1 text-xs"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsCreateOpen(false)}>
                Hủy bỏ
              </Button>
              <Button type="submit" size="sm" disabled={createLeadMutation.isPending} className="gap-1.5 bg-primary text-primary-foreground">
                <UserCheck className="h-4 w-4" />
                {createLeadMutation.isPending ? 'Đang lưu...' : 'Lưu vào CRM'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ============================================================================
// CUSTOMER CRM EDITOR (CHI TIẾT & CHỈNH SỬA THÔNG TIN KHÁCH HÀNG)
// ============================================================================

function CustomerCrmEditor({
  dossier,
  onAskCopilot,
  onDeleted,
}: {
  dossier: LeadDossier
  onAskCopilot: () => void
  onDeleted: () => void
}) {
  const navigate = useNavigate()
  const updateMutation = useUpdateLead()
  const deleteMutation = useDeleteLead()

  const c = dossier.constraints || {}

  // Editable fields
  const [customerName, setCustomerName] = useState(dossier.customer?.full_name || dossier.customer_name || '')
  const [customerPhone, setCustomerPhone] = useState(dossier.customer?.phone || dossier.customer_phone || '')
  const [segment, setSegment] = useState<CustomerSegment>(c.customer_segment || dossier.customer_segment || dossier.segment || 'NEW_CUSTOMER')
  const [temperature, setTemperature] = useState<LeadTemperature>(dossier.temperature || dossier.lead_temperature || 'WARM')
  const [status, setStatus] = useState<LeadDossierStatus>(dossier.status || 'NEW')
  const [preferredUnit, setPreferredUnit] = useState(c.preferred_unit_code || dossier.preferred_unit_code || dossier.unit_code || '')
  const [bedrooms, setBedrooms] = useState<number>(c.bedrooms || 2)
  const [ownFunds, setOwnFunds] = useState<number>(c.own_funds_vnd || 0)
  const [monthlyCapacity, setMonthlyCapacity] = useState<number>(c.monthly_capacity_vnd || 0)
  const [objective, setObjective] = useState<OptimizationObjective>(c.objective || 'MIN_INITIAL_OUTFLOW')
  const [needsSummary, setNeedsSummary] = useState(dossier.needs_summary || '')

  // Reset values when switching dossiers
  useEffect(() => {
    setCustomerName(dossier.customer?.full_name || dossier.customer_name || '')
    setCustomerPhone(dossier.customer?.phone || dossier.customer_phone || '')
    setSegment(c.customer_segment || dossier.customer_segment || dossier.segment || 'NEW_CUSTOMER')
    setTemperature(dossier.temperature || dossier.lead_temperature || 'WARM')
    setStatus(dossier.status || 'NEW')
    setPreferredUnit(c.preferred_unit_code || dossier.preferred_unit_code || dossier.unit_code || '')
    setBedrooms(c.bedrooms || 2)
    setOwnFunds(c.own_funds_vnd || 0)
    setMonthlyCapacity(c.monthly_capacity_vnd || 0)
    setObjective(c.objective || 'MIN_INITIAL_OUTFLOW')
    setNeedsSummary(dossier.needs_summary || '')
  }, [dossier.dossier_id])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!customerName.trim()) {
      toast.error('Họ tên khách hàng không được để trống')
      return
    }

    try {
      const payload: LeadUpdatePayload = {
        customer_name: customerName.trim(),
        customer_phone: customerPhone.trim() || undefined,
        customer_segment: segment,
        lead_temperature: temperature,
        status: status,
        preferred_unit_code: preferredUnit.trim() || undefined,
        bedrooms: bedrooms || undefined,
        own_funds_vnd: ownFunds,
        monthly_capacity_vnd: monthlyCapacity,
        objective: objective,
        needs_summary: needsSummary.trim() || undefined,
      }

      await updateMutation.mutateAsync({
        dossierId: dossier.dossier_id,
        payload,
      })
      toast.success('Đã lưu thông tin khách hàng', customerName)
    } catch (err: any) {
      toast.error('Lỗi khi lưu thông tin', err?.message || 'Không thể kết nối đến máy chủ')
    }
  }

  const handleDelete = async () => {
    if (confirm(`Bạn có chắc chắn muốn xóa hồ sơ khách hàng "${customerName}" không?`)) {
      try {
        await deleteMutation.mutateAsync(dossier.dossier_id)
        toast.success('Đã xóa hồ sơ khách hàng thành công')
        onDeleted()
      } catch (err: any) {
        toast.error('Không thể xóa khách hàng', err?.message)
      }
    }
  }

  return (
    <Card className="border-border bg-card shadow-sm">
      <CardHeader className="bg-muted/30 pb-3 pt-4 border-b border-border">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs font-semibold text-muted-foreground">{dossier.dossier_id}</span>
              <TemperatureBadge temperature={temperature} />
              <Badge variant="outline" className="text-xs">
                {DOSSIER_STATUS_LABEL[status] || status}
              </Badge>
            </div>
            <h2 className="font-display text-lg font-bold text-foreground mt-1">{customerName}</h2>
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onAskCopilot}
              className="h-8 text-xs border-amber-500/40 text-amber-700 dark:text-amber-300 hover:bg-amber-500/10 gap-1.5"
            >
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              Hỏi Copilot cho khách này
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="h-8 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive"
              title="Xóa hồ sơ"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-4">
        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <Label className="text-xs font-medium">Họ và tên khách hàng *</Label>
              <Input
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                className="mt-1 h-8 text-xs font-semibold"
                required
              />
            </div>
            <div>
              <Label className="text-xs font-medium">Số điện thoại liên hệ</Label>
              <Input
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                className="mt-1 h-8 text-xs"
                placeholder="0912345678"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            <div>
              <Label className="text-xs font-medium">Phân khúc khách hàng</Label>
              <Select value={segment} onValueChange={(val: CustomerSegment) => setSegment(val)}>
                <SelectTrigger className="mt-1 h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="NEW_CUSTOMER">Khách mới</SelectItem>
                  <SelectItem value="INVESTOR">Nhà đầu tư</SelectItem>
                  <SelectItem value="END_USER">Mua ở thực</SelectItem>
                  <SelectItem value="VIP">Khách VIP</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-xs font-medium">Nhiệt độ Lead</Label>
              <Select value={temperature} onValueChange={(val: LeadTemperature) => setTemperature(val)}>
                <SelectTrigger className="mt-1 h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="HOT">🔥 HOT (Rất tiềm năng)</SelectItem>
                  <SelectItem value="WARM">⛅ WARM (Quan tâm)</SelectItem>
                  <SelectItem value="COLD">❄️ COLD (Khảo sát)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-xs font-medium">Trạng thái hồ sơ</Label>
              <Select value={status} onValueChange={(val: LeadDossierStatus) => setStatus(val)}>
                <SelectTrigger className="mt-1 h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="NEW">Chờ tiếp nhận</SelectItem>
                  <SelectItem value="ASSIGNED">Đang chăm sóc/tư vấn</SelectItem>
                  <SelectItem value="CONVERTED_TO_QUOTE">Đã chuyển báo giá</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <Label className="text-xs font-medium">Căn hộ quan tâm</Label>
              <Input
                value={preferredUnit}
                onChange={(e) => setPreferredUnit(e.target.value)}
                className="mt-1 h-8 text-xs"
                placeholder="R-02.02, R-05.01..."
              />
            </div>
            <div>
              <Label className="text-xs font-medium">Số phòng ngủ mong muốn</Label>
              <Select
                value={bedrooms.toString()}
                onValueChange={(val) => setBedrooms(parseInt(val, 10))}
              >
                <SelectTrigger className="mt-1 h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 Phòng ngủ</SelectItem>
                  <SelectItem value="2">2 Phòng ngủ</SelectItem>
                  <SelectItem value="3">3 Phòng ngủ</SelectItem>
                  <SelectItem value="4">4 Phòng ngủ / Penthouse</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <div className="flex items-center justify-between">
                <Label className="text-xs font-medium">Vốn tự có sẵn sàng</Label>
                <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                  {formatNumber(ownFunds)} ₫
                </span>
              </div>
              <Input
                type="text"
                value={ownFunds ? formatNumber(ownFunds) : ''}
                onChange={(e) => {
                  const raw = e.target.value.replace(/\D/g, '')
                  setOwnFunds(raw ? parseInt(raw, 10) : 0)
                }}
                className="mt-1 h-8 text-xs font-semibold"
                placeholder="5.000.000.000"
              />
            </div>

            <div>
              <div className="flex items-center justify-between">
                <Label className="text-xs font-medium">Khả năng chi trả hàng tháng</Label>
                <span className="text-[11px] font-semibold text-primary">
                  {formatNumber(monthlyCapacity)} ₫
                </span>
              </div>
              <Input
                type="text"
                value={monthlyCapacity ? formatNumber(monthlyCapacity) : ''}
                onChange={(e) => {
                  const raw = e.target.value.replace(/\D/g, '')
                  setMonthlyCapacity(raw ? parseInt(raw, 10) : 0)
                }}
                className="mt-1 h-8 text-xs font-semibold"
                placeholder="25.000.000"
              />
            </div>
          </div>

          <div>
            <Label className="text-xs font-medium">Mục tiêu tài chính ưu tiên</Label>
            <Select value={objective} onValueChange={(val: OptimizationObjective) => setObjective(val)}>
              <SelectTrigger className="mt-1 h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="MIN_INITIAL_OUTFLOW">Giảm tối đa vốn bỏ ra ban đầu (HTLS 0%)</SelectItem>
                <SelectItem value="MAX_DISCOUNT">Hưởng chiết khấu cao nhất (Thanh toán sớm)</SelectItem>
                <SelectItem value="MIN_MONTHLY_PAYMENT">Giảm áp lực chi trả hàng tháng</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs font-medium">Ghi chú nhu cầu & khẩu vị khách hàng</Label>
            <Textarea
              rows={3}
              value={needsSummary}
              onChange={(e) => setNeedsSummary(e.target.value)}
              placeholder="Chi tiết yêu cầu về tầng, hướng, phong thủy, lịch sử trao đổi..."
              className="mt-1 text-xs"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-border">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => navigate(`/sale/quotes/new?dossier=${dossier.dossier_id}`)}
              className="h-8 text-xs gap-1.5 border-primary/40 text-primary hover:bg-primary/10"
            >
              <FilePlus2 className="h-3.5 w-3.5" />
              Lập báo giá căn này
            </Button>

            <Button
              type="submit"
              size="sm"
              disabled={updateMutation.isPending}
              className="h-8 text-xs gap-1.5 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              <Save className="h-3.5 w-3.5" />
              {updateMutation.isPending ? 'Đang lưu...' : 'Lưu cập nhật'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

export default LeadInboxPage
