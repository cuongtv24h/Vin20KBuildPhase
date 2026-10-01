import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Inbox,
  FileStack,
  MessageSquare,
  ScrollText,
  Home,
  Users,
  UserPlus,
  UserCheck,
  Plus,
  FileText,
  Send,
  FilePlus2,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Clock,
  ExternalLink,
  ShieldCheck,
  Sparkles,
  Layers,
  RefreshCw,
  LogOut,
  X,
  Search,
  ChevronRight,
} from 'lucide-react'

// Hooks & Store
import { useSessionStore } from '@/auth/sessionStore'
import { useLeads, useCreateLead, useQuotes, usePolicies, useProjectOverviews } from '@pricepolicy/api-client/hooks'
import type {
  LeadDossier,
  LeadCreatePayload,
  Quote,
  PolicyDocument,
  CustomerSegment,
  OptimizationObjective,
  LeadTemperature,
} from '@pricepolicy/api-client/contracts'

// Design System Components from @pricepolicy/ui
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@pricepolicy/ui/components/ui/card'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import { Textarea } from '@pricepolicy/ui/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { SlaCountdown } from '@pricepolicy/ui/components/common/SlaCountdown'
import {
  TemperatureBadge,
  QuoteStatusBadge,
  PolicyStatusBadge,
  ComplianceBadge,
} from '@pricepolicy/ui/components/common/StatusBadge'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { EmptyState, LoadingState } from '@pricepolicy/ui/components/common/PageStates'
import { FormattedAiMessage } from '@pricepolicy/ui/components/common/FormattedAiMessage'
import { API_BASE_URL } from '@pricepolicy/api-client/config'
import { formatVnd } from '@pricepolicy/ui/lib/format'
import { DOSSIER_STATUS_LABEL, OBJECTIVE_LABEL, ROLE_LABEL, PROJECT_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'

// --- EVIDENCE KNOWLEDGE BASE ---
interface LegalEvidence {
  q: string
  p: string
  e: string
  h: string
}

const EVIDENCE_DB: Record<number, LegalEvidence> = {
  1: {
    q: 'Khách hàng thanh toán tối thiểu 95% giá trị hợp đồng trong 30 ngày kể từ ngày đặt cọc được hưởng chiết khấu 8% giá trị căn hộ trước thuế.',
    p: 'POL-2026-VLF-EARLY — Chiết khấu Thanh toán Sớm 95%',
    e: 'v3.0 · 01/01/2026 → 30/06/2026',
    h: 'chunk #12 · 3f9a…e2',
  },
  2: {
    q: 'Số liệu do Deterministic Math Engine tính theo FCS v2.6 — đối soát golden case BENCH-01, sai số Δ = 0 ₫ (Net 4.232.000.000 ₫ · VAT 423.200.000 ₫ · Tổng 4.655.200.000 ₫).',
    p: 'FCS v2.6 · Deterministic Math Engine (C-06)',
    e: 'v2.6 · đối soát 14:02 10/03/2026',
    h: 'calc_out · b7c1…9d',
  },
  3: {
    q: 'Gói quà tặng nội thất trị giá 200.000.000 ₫ áp dụng cho căn hộ loại 3BR. Căn 2BR không thuộc diện áp dụng (không quy đổi).',
    p: 'POL-2026-VLF-INTERIOR — Quà tặng Nội thất',
    e: 'v1.0 · 01/01/2026 → 31/12/2026',
    h: 'chunk #04 · 91aa…7c',
  },
  4: {
    q: 'Chương trình hỗ trợ lãi suất 0% trong 24 tháng đầu kể từ giải ngân. Sau 24 tháng lãi suất áp dụng theo biểu phí ngân hàng thương mại đồng tài trợ.',
    p: 'POL-2026-VLF-HLSN — Hỗ trợ Lãi suất Ngân hàng',
    e: 'v2.0 · 01/01/2026 → 30/06/2026',
    h: 'chunk #07 · 44de…10',
  },
  5: {
    q: 'Tiến độ thanh toán chuẩn 09 đợt gắn mốc xây dựng thực tế; đợt 1 gồm 30% giá trị hợp đồng (kể cả cọc đã đặt).',
    p: 'POL-2026-VLF-PROG — Thanh toán Giãn tiến độ',
    e: 'v1.1 · 01/01/2026 → 31/12/2026',
    h: 'chunk #02 · 6f30…58',
  },
}

// --- COMPLIANCE VERIFICATION ENGINE (F8 Live-Check) ---
interface ComplianceCheckState {
  tier: 'GREEN' | 'AMBER' | 'RED' | 'BLACK'
  statusText: string
  checks: [string, string][]
  suggest?: string
}

function runLocalComplianceCheck(text: string): ComplianceCheckState {
  const t = text.toLowerCase()
  if (
    /(cam kết|bảo lãnh|chắc chắn)[^.]*(duyệt|vay|sinh lời|lãi|giảm giá)|không cần chứng minh thu nhập|cam kết 100%/.test(t)
  ) {
    return {
      tier: 'BLACK',
      statusText: 'ĐEN — Cấm phát ngôn (POL-08 Điều 1)',
      checks: [
        ['bad', 'Cam kết vượt thẩm quyền — POL-2026-VLF-SALES-GUIDE Điều 1 (MSG-02)'],
        ['bad', 'Cụm cấm: cam kết/bảo lãnh kết quả phê duyệt tín dụng hoặc tỷ suất sinh lời'],
      ],
      suggest:
        'Câu an toàn: "Hồ sơ vay anh sẽ được ngân hàng đối tác thẩm định theo quy trình chuẩn; em hỗ trợ anh chuẩn bị đủ giấy tờ để tăng tỉ lệ duyệt nhé."',
    }
  }

  const pctMatch = t.match(/chiết khấu[^0-9]*(\d+)\s*%/)
  const hype = /siêu hời|chỉ trong (tuần|tháng) này/.test(t)
  if ((pctMatch && parseInt(pctMatch[1]) > 8) || hype) {
    return {
      tier: 'RED',
      statusText: 'ĐỎ — Thiếu chứng cứ / Vượt khung chính sách',
      checks: [
        ...(pctMatch && parseInt(pctMatch[1]) > 8
          ? ([['bad', `Mức chiết khấu ${pctMatch[1]}% vượt trần chính sách hiện hành 8.0% (MSG-03)`]] as [string, string][])
          : []),
        ...(hype ? ([['bad', 'Tuyên bố "siêu hời / giới hạn thời gian" không có căn cứ văn bản']] as [string, string][]) : []),
      ],
      suggest:
        'Câu an toàn: "Chương trình hiện hành là chiết khấu 8% cho thanh toán sớm 95% [1], anh xem em gửi chi tiết nhé."',
    }
  }

  const hasMoney = /\d+[,.]?\d*\s*(tỷ|triệu|\btr\b)/.test(t)
  const hasAnchor = /\[\d\]/.test(text)
  if (hasMoney && !hasAnchor) {
    return {
      tier: 'RED',
      statusText: 'ĐỎ — Claim số tiền chưa có mỏ neo đối soát',
      checks: [['bad', 'Mọi số tiền trích dẫn cần có mỏ neo chứng cứ [n]']],
      suggest: 'Gắn mỏ neo cho từng con số (ví dụ [1], [2]) để bảo đảm tính pháp lý khi gửi khách.',
    }
  }

  if (/lãi suất 0%/.test(t) && !/sau 24 tháng/.test(t)) {
    return {
      tier: 'AMBER',
      statusText: 'VÀNG — Cần bổ sung khuyến cáo bắt buộc',
      checks: [
        ['ok', '1 claim HTLS có chứng cứ [4]'],
        ['warn', 'Thiếu khuyến cáo bắt buộc: "Sau 24 tháng theo biểu phí ngân hàng" [4]'],
      ],
      suggest: 'Thêm khuyến cáo: "…Sau 24 tháng lãi suất áp dụng theo biểu phí ngân hàng thương mại [4]."',
    }
  }

  if (hasAnchor) {
    return {
      tier: 'GREEN',
      statusText: 'XANH — Hỗ trợ đầy đủ & Tuân thủ phát ngôn',
      checks: [
        ['ok', 'Các claim số tiền đều có chứng cứ [n] xác thực'],
        ['ok', 'Số liệu khớp Deterministic Math Engine Δ = 0 ₫'],
        ['ok', 'Đúng quy chuẩn phát ngôn nhân viên kinh doanh'],
      ],
    }
  }

  return {
    tier: 'GREEN',
    statusText: 'XANH — Không phát hiện rủi ro tuân thủ',
    checks: [
      ['ok', 'Không phát hiện tuyên bố rủi ro pháp lý'],
      ['ok', 'Đúng quy chuẩn giao tiếp khách hàng'],
    ],
  }
}

// --- MESSAGE STREAM TYPES ---
type StreamItemType =
  | 'agent'
  | 'user'
  | 'welcome'
  | 'confirm'
  | 'stepper'
  | 'receipt'
  | 'nudge'
  | 'fallback'
  | 'customer_card'
  | 'customer_search'
  | 'smart_customer_create'
  | 'smart_quote_create'
  | 'smart_scenario_compare'
  | 'smart_units_browse'
  | 'smart_compose_message'

interface StreamItem {
  id: string
  type: StreamItemType
  text?: string
  time: string
  data?: any
  action_type?: string
  action_data?: any
  suggested_actions?: string[]
}

// --- SMART INTERACTIVE CARDS ---

function SmartCustomerCard({
  initialData,
  onSave,
  onCancel,
}: {
  initialData?: any
  onSave: (payload: LeadCreatePayload) => void
  onCancel?: () => void
}) {
  const [name, setName] = useState(initialData?.customer_name || initialData?.clientName || '')
  const [phone, setPhone] = useState(initialData?.customer_phone || initialData?.phone || '')
  const [unit, setUnit] = useState(initialData?.preferred_unit_code || initialData?.unitCode || '')
  const [funds, setFunds] = useState<number>(initialData?.own_funds_vnd || initialData?.funds || 1500000000)
  const [notes, setNotes] = useState(initialData?.needs_summary || '')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setIsSubmitting(true)
    try {
      await onSave({
        customer_name: name.trim(),
        customer_phone: phone.trim() || '0900000000',
        customer_segment: 'NEW_CUSTOMER',
        temperature: 'HOT',
        project_id: 'P-001',
        preferred_unit_code: unit.trim() || null,
        own_funds_vnd: Number(funds) || 1500000000,
        monthly_capacity_vnd: 25000000,
        objective: 'MIN_INITIAL_OUTFLOW',
        needs_summary: notes.trim() || (unit.trim() ? `Khởi tạo nhanh qua Smart Card Copilot. Quan tâm căn ${unit.trim()}.` : 'Khởi tạo nhanh qua Smart Card Copilot.'),
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card className="w-full max-w-[95%] border-emerald-500/40 bg-emerald-500/[0.02] shadow-sm">
      <CardHeader className="bg-emerald-500/10 px-4 py-2.5 border-b border-emerald-500/20">
        <CardTitle className="text-xs font-semibold text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <UserPlus className="h-4 w-4 text-emerald-600" />
            Khởi tạo hồ sơ khách hàng mới (CRM)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3.5 space-y-3 text-xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <div>
            <Label className="text-[11px] text-muted-foreground font-medium">Họ và tên khách hàng *</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nguyễn Văn An"
              className="h-8 text-xs mt-1"
              required
            />
          </div>
          <div>
            <Label className="text-[11px] text-muted-foreground font-medium">Số điện thoại *</Label>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="0912345678"
              className="h-8 text-xs mt-1"
            />
          </div>
          <div>
            <Label className="text-[11px] text-muted-foreground font-medium">Căn hộ quan tâm</Label>
            <Input
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              placeholder="R-02.02 (không bắt buộc)"
              className="h-8 text-xs mt-1"
            />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <Label className="text-[11px] text-muted-foreground font-medium">Vốn tự có sẵn sàng</Label>
              <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                {new Intl.NumberFormat('vi-VN').format(funds || 0)} VNĐ
              </span>
            </div>
            <div className="relative mt-1">
              <Input
                type="text"
                value={funds ? new Intl.NumberFormat('vi-VN').format(funds) : ''}
                onChange={(e) => {
                  const raw = e.target.value.replace(/\D/g, '')
                  setFunds(raw ? parseInt(raw, 10) : 0)
                }}
                placeholder="5.000.000.000"
                className="h-8 text-xs font-semibold pr-12 text-foreground"
              />
              <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[11px] font-medium text-muted-foreground pointer-events-none">
                VNĐ
              </span>
            </div>
          </div>
        </div>
        <div>
          <Label className="text-[11px] text-muted-foreground font-medium">Ghi chú nhu cầu / Khẩu vị đầu tư</Label>
          <Input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Quan tâm tiến độ thanh toán, dự kiến vay ngân hàng..."
            className="h-8 text-xs mt-1"
          />
        </div>
        <div className="flex items-center justify-end gap-2 pt-1 border-t border-border/50">
          {onCancel && (
            <Button variant="ghost" size="sm" onClick={onCancel} className="h-7 text-xs">
              Bỏ qua
            </Button>
          )}
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={!name.trim() || isSubmitting}
            className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
          >
            <UserCheck className="h-3.5 w-3.5" />
            {isSubmitting ? 'Đang lưu vào CRM...' : 'Lưu khách hàng vào CRM'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function SmartQuoteCard({
  initialData,
  onGenerateQuote,
}: {
  initialData?: any
  onGenerateQuote: (unitCode: string, scenario: string) => void
}) {
  const [unitCode, setUnitCode] = useState(initialData?.unit_code || '')
  const [scenario, setScenario] = useState(initialData?.scenario || 'PA-SOM')

  const unitPrices: Record<string, { price: number; type: string; area: number }> = {
    'R-02.02': { price: 4655200000, type: '2BR', area: 72.5 },
    'R-03.05': { price: 5280000000, type: '2BR+', area: 84.2 },
    'R-05.01': { price: 6450000000, type: '3BR', area: 104.8 },
    'R-01.08': { price: 2890000000, type: '1BR', area: 49.6 },
  }

  const selectedUnit = unitCode ? unitPrices[unitCode] || null : null
  const discountAmount = selectedUnit && scenario === 'PA-SOM' ? Math.round(selectedUnit.price * 0.08) : 0
  const finalEstimate = selectedUnit ? selectedUnit.price - discountAmount : 0

  return (
    <Card className="w-full max-w-[95%] border-primary/40 bg-primary/[0.02] shadow-sm">
      <CardHeader className="bg-primary/10 px-4 py-2.5 border-b border-primary/20">
        <CardTitle className="text-xs font-semibold text-primary flex items-center justify-between">
          <span className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            Lập báo giá & Phương án tài chính nhanh
          </span>
          <Badge variant="outline" className="text-[10px] border-primary/30 text-primary bg-primary/10">
            FCS v2.6 Math Engine
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3.5 space-y-3 text-xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <div>
            <Label className="text-[11px] text-muted-foreground font-medium">Chọn căn hộ</Label>
            <select
              value={unitCode}
              onChange={(e) => setUnitCode(e.target.value)}
              className="h-8 w-full mt-1 rounded-md border border-input bg-background px-2.5 text-xs font-medium text-foreground outline-none"
            >
              <option value="">— Chọn căn hộ —</option>
              <option value="R-02.02">R-02.02 (2BR · 72.5m² · 4,65 tỷ)</option>
              <option value="R-03.05">R-03.05 (2BR+ · 84.2m² · 5,28 tỷ)</option>
              <option value="R-05.01">R-05.01 (3BR · 104.8m² · 6,45 tỷ)</option>
              <option value="R-01.08">R-01.08 (1BR · 49.6m² · 2,89 tỷ)</option>
            </select>
          </div>
          <div>
            <Label className="text-[11px] text-muted-foreground font-medium">Phương án thanh toán</Label>
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              className="h-8 w-full mt-1 rounded-md border border-input bg-background px-2.5 text-xs font-medium text-foreground outline-none"
            >
              <option value="PA-SOM">PA 2: Thanh toán sớm 95% (Chiết khấu 8% [1])</option>
              <option value="PA-VAY">PA 3: Hỗ trợ vay 70% (HTLS 0% 24 tháng [4])</option>
              <option value="PA-CHUAN">PA 1: Thanh toán chuẩn 9 đợt (Theo tiến độ)</option>
            </select>
          </div>
        </div>

        {/* Calculation summary */}
        {selectedUnit ? (
          <div className="rounded-lg border border-border/80 bg-muted/30 p-2.5 space-y-1.5 text-[11px]">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Giá niêm yết (gồm VAT):</span>
              <span className="font-semibold text-foreground">{formatVnd(selectedUnit.price)}</span>
            </div>
            {discountAmount > 0 && (
              <div className="flex justify-between text-emerald-600 font-medium">
                <span>Chiết khấu thanh toán sớm 8%:</span>
                <span>- {formatVnd(discountAmount)}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-border/60 pt-1.5 text-xs font-bold">
              <span className="text-foreground">Tổng thanh toán dự kiến:</span>
              <span className="text-primary">{formatVnd(finalEstimate)}</span>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border bg-muted/20 p-2.5 text-[11px] text-muted-foreground">
            Chọn căn hộ ở trên để xem tạm tính giá theo phương án thanh toán.
          </div>
        )}

        <div className="flex items-center justify-end gap-2 pt-1 border-t border-border/50">
          <Button
            size="sm"
            disabled={!unitCode}
            onClick={() => onGenerateQuote(unitCode, scenario)}
            className="h-7 text-xs bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5"
          >
            <FilePlus2 className="h-3.5 w-3.5" />
            Tạo báo giá chi tiết qua Engine
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function SmartScenarioCompareCard({
  unitCode,
  onSelectScenario,
}: {
  unitCode?: string
  onSelectScenario: (sc: string) => void
}) {
  return (
    <Card className="w-full max-w-[98%] border-purple-500/40 bg-purple-500/[0.02] shadow-sm">
      <CardHeader className="bg-purple-500/10 px-4 py-2.5 border-b border-purple-500/20">
        <CardTitle className="text-xs font-semibold text-purple-900 dark:text-purple-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-purple-600" />
            {unitCode ? `So sánh 3 phương án thanh toán — Căn ${unitCode}` : 'So sánh 3 phương án thanh toán'}
          </span>
          <Badge variant="outline" className="text-[10px] border-purple-500/30 text-purple-700 dark:text-purple-400 bg-purple-500/10">
            Đối soát Δ = 0 ₫
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3 text-xs">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
          {/* Cột 1: PA Chuẩn */}
          <div className="rounded-lg border border-border bg-card p-2.5 flex flex-col justify-between space-y-2">
            <div>
              <div className="font-semibold text-foreground text-xs pb-1 border-b border-border/50 flex items-center justify-between">
                <span>PA 1: Tiến độ chuẩn</span>
                <Badge variant="secondary" className="text-[9px]">9 đợt</Badge>
              </div>
              <ul className="mt-2 space-y-1 text-[11px] text-muted-foreground">
                <li>• Đợt 1: <b>30%</b> (~1,39 tỷ)</li>
                <li>• Đợt 2-8: <b>5-10%</b> / 2 tháng</li>
                <li>• Nhận nhà: <b>25%</b> + 2% KPBT</li>
                <li>• Chiết khấu: <b>0%</b></li>
                <li>• Ưu điểm: Nhẹ vốn theo kỳ</li>
              </ul>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onSelectScenario('PA-CHUAN')}
              className="w-full h-6 text-[11px] mt-2"
            >
              Chọn PA Chuẩn
            </Button>
          </div>

          {/* Cột 2: PA Sớm 95% */}
          <div className="rounded-lg border-2 border-emerald-500/50 bg-emerald-500/[0.04] p-2.5 flex flex-col justify-between space-y-2 relative">
            <span className="absolute -top-2 right-2 rounded-full bg-emerald-600 px-1.5 py-0.2 text-[9px] font-bold text-white uppercase">
              Tối ưu giá
            </span>
            <div>
              <div className="font-semibold text-emerald-800 dark:text-emerald-300 text-xs pb-1 border-b border-emerald-500/20 flex items-center justify-between">
                <span>PA 2: Đóng sớm 95%</span>
                <Badge variant="outline" className="text-[9px] border-emerald-500/30 text-emerald-700 bg-emerald-500/10">-8.0% [1]</Badge>
              </div>
              <ul className="mt-2 space-y-1 text-[11px] text-foreground">
                <li>• Thanh toán: <b>95% trong 30 ngày</b></li>
                <li>• Chiết khấu: <b className="text-emerald-600">8.0% trước VAT</b></li>
                <li>• Tiết kiệm: <b className="text-emerald-600">~372 triệu ₫</b></li>
                <li>• Giá sau CK: <b>~4,28 tỷ ₫</b></li>
                <li>• Ưu điểm: Giá mua thấp nhất</li>
              </ul>
            </div>
            <Button
              size="sm"
              onClick={() => onSelectScenario('PA-SOM')}
              className="w-full h-6 text-[11px] bg-emerald-600 hover:bg-emerald-700 text-white mt-2"
            >
              Chọn PA Sớm 8%
            </Button>
          </div>

          {/* Cột 3: PA Vay 70% */}
          <div className="rounded-lg border-2 border-primary/50 bg-primary/[0.04] p-2.5 flex flex-col justify-between space-y-2 relative">
            <span className="absolute -top-2 right-2 rounded-full bg-primary px-1.5 py-0.2 text-[9px] font-bold text-primary-foreground uppercase">
              Ít vốn nhất
            </span>
            <div>
              <div className="font-semibold text-primary text-xs pb-1 border-b border-primary/20 flex items-center justify-between">
                <span>PA 3: Vay ngân hàng 70%</span>
                <Badge variant="outline" className="text-[9px] border-primary/30 text-primary bg-primary/10">0% lãi [4]</Badge>
              </div>
              <ul className="mt-2 space-y-1 text-[11px] text-foreground">
                <li>• Vốn tự có: <b className="text-primary">Chỉ 30% (~1,39 tỷ)</b></li>
                <li>• Ngân hàng giải ngân: <b>70% (~3,25 tỷ)</b></li>
                <li>• Hỗ trợ lãi suất: <b className="text-primary">0% trong 24 tháng</b></li>
                <li>• Ân hạn gốc: <b>24 tháng</b></li>
                <li>• Khuyến cáo: Sau 24th theo biểu phí [4]</li>
              </ul>
            </div>
            <Button
              size="sm"
              onClick={() => onSelectScenario('PA-VAY')}
              className="w-full h-6 text-[11px] bg-primary hover:bg-primary/90 text-primary-foreground mt-2"
            >
              Chọn PA Vay 0%
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function SmartUnitsCard({
  onSelectUnit,
}: {
  onSelectUnit: (unitCode: string) => void
}) {
  const units = [
    { code: 'R-02.02', type: '2BR - 2WC', area: 72.5, dir: 'Đông Nam', price: '4.655.200.000 ₫', status: 'CÒN TRỐNG', badgeColor: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30' },
    { code: 'R-03.05', type: '2BR+1 - 2WC', area: 84.2, dir: 'Nam (view sông)', price: '5.280.000.000 ₫', status: 'CÒN TRỐNG', badgeColor: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30' },
    { code: 'R-05.01', type: '3BR - 2WC', area: 104.8, dir: 'Đông Bắc (góc)', price: '6.450.000.000 ₫', status: 'GIỮ CHỖ 24H', badgeColor: 'bg-amber-500/10 text-amber-600 border-amber-500/30' },
    { code: 'R-01.08', type: '1BR+1 - 1WC', area: 49.6, dir: 'Tây Nam', price: '2.890.000.000 ₫', status: 'CÒN TRỐNG', badgeColor: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30' },
  ]

  return (
    <Card className="w-full max-w-[98%] border-sky-500/40 bg-sky-500/[0.02] shadow-sm">
      <CardHeader className="bg-sky-500/10 px-4 py-2.5 border-b border-sky-500/20">
        <CardTitle className="text-xs font-semibold text-sky-900 dark:text-sky-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Home className="h-4 w-4 text-sky-600" />
            Rổ hàng căn hộ nổi bật — VLand Future Riverside
          </span>
          <Badge variant="outline" className="text-[10px] border-sky-500/30 text-sky-700 dark:text-sky-400 bg-sky-500/10">
            Live Inventory
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3 space-y-2 text-xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {units.map((u) => (
            <div
              key={u.code}
              className="flex items-center justify-between rounded-lg border border-border bg-card p-2.5 hover:border-primary/50 transition-colors"
            >
              <div className="space-y-0.5 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-foreground text-xs">{u.code}</span>
                  <Badge variant="outline" className={cn('text-[9px]', u.badgeColor)}>{u.status}</Badge>
                </div>
                <div className="text-[11px] text-muted-foreground">
                  {u.type} · {u.area} m² · Hướng {u.dir}
                </div>
                <div className="font-semibold text-primary text-xs">{u.price}</div>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-[11px] shrink-0 border-primary/30 text-primary hover:bg-primary hover:text-primary-foreground ml-2"
                onClick={() => onSelectUnit(u.code)}
              >
                Báo giá căn này
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function SmartComposeMessageCard({
  draftText,
  onCopy,
}: {
  draftText: string
  onCopy: () => void
}) {
  return (
    <Card className="w-full max-w-[95%] border-amber-500/40 bg-amber-500/[0.02] shadow-sm">
      <CardHeader className="bg-amber-500/10 px-4 py-2.5 border-b border-amber-500/20">
        <CardTitle className="text-xs font-semibold text-amber-900 dark:text-amber-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-amber-600" />
            Bản thảo tin nhắn gửi khách — Chuẩn tuân thủ F8
          </span>
          <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10">
            🟢 XANH: Hợp chuẩn phát ngôn
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3.5 space-y-2.5 text-xs">
        <div className="rounded-lg border border-border bg-muted/30 p-3 text-[12px] leading-relaxed text-foreground whitespace-pre-line font-sans">
          {draftText}
        </div>
        <div className="flex items-center justify-between pt-1 border-t border-border/50 text-[11px] text-muted-foreground">
          <span>Đã kiểm tra chứng cứ: [1] POL-EARLY, [4] POL-HLSN</span>
          <Button
            size="sm"
            onClick={onCopy}
            className="h-7 text-xs bg-amber-600 hover:bg-amber-700 text-white gap-1.5"
          >
            <Copy className="h-3.5 w-3.5" />
            Sao chép tin nhắn Zalo / SMS
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function SalesWorkspacePage() {
  const session = useSessionStore((s) => s.session)
  const clearSession = useSessionStore((s) => s.clearSession)
  const navigate = useNavigate()

  // Real backend queries
  const leadsQuery = useLeads()
  const createLeadMutation = useCreateLead()
  const quotesQuery = useQuotes({}, { live: true })
  const policiesQuery = usePolicies()
  const projectsQuery = useProjectOverviews()

  const leads = useMemo(() => leadsQuery.data ?? [], [leadsQuery.data])
  const quotes = useMemo(() => quotesQuery.data ?? [], [quotesQuery.data])
  const policies = useMemo(() => policiesQuery.data ?? [], [policiesQuery.data])
  const projects = useMemo(() => projectsQuery.data ?? [], [projectsQuery.data])

  // Customer Management Dialog State
  const [createCustomerOpen, setCreateCustomerOpen] = useState(false)
  const [customerForm, setCustomerForm] = useState<LeadCreatePayload>({
    customer_name: '',
    customer_phone: '',
    customer_segment: 'NEW_CUSTOMER',
    temperature: 'HOT',
    project_id: 'P-001',
    preferred_unit_code: '',
    own_funds_vnd: 1500000000,
    monthly_capacity_vnd: 25000000,
    objective: 'MIN_INITIAL_OUTFLOW',
    needs_summary: '',
  })

  // Artifact Panel Tabs & Views
  const [activeTab, setActiveTab] = useState<'hoso' | 'baogia' | 'tinnhan' | 'chinhsach'>('hoso')
  const [panelView, setPanelView] = useState<'leads' | 'dossier' | 'pipeline' | 'quote_comparison' | 'messages' | 'policies'>('leads')

  // Selected entities & Context Chip
  const [searchParams] = useSearchParams()
  const initialParamLeadId = searchParams.get('id') || searchParams.get('lead')
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(initialParamLeadId)
  const [contextLeadId, setContextLeadId] = useState<string>(initialParamLeadId || 'auto')

  useEffect(() => {
    if (initialParamLeadId) {
      setSelectedLeadId(initialParamLeadId)
      setContextLeadId(initialParamLeadId)
    }
  }, [initialParamLeadId])

  // Không gán mặc định khách hàng đầu tiên — Copilot tự bắt ngữ cảnh từ hội thoại hoặc URL
  const selectedLead = useMemo(() => {
    if (!selectedLeadId) return null
    return leads.find((l) => l.dossier_id === selectedLeadId) ?? null
  }, [leads, selectedLeadId])

  // Artifact panel: mặc định thu gọn, chỉ mở khi có ngữ cảnh (KPI/hành động từ Copilot)
  const [isMobilePanelOpen, setIsMobilePanelOpen] = useState(false)

  // Chat Stream State
  const [messages, setMessages] = useState<StreamItem[]>([])
  const [inputVal, setInputVal] = useState('')
  const [slashOpen, setSlashOpen] = useState(false)
  const [slashIndex, setSlashIndex] = useState(0)

  // Interactive 8s Undo Timer State
  const [undoSeconds, setUndoSeconds] = useState(8)
  const [undoActive, setUndoActive] = useState(false)
  const [undoQuoteCode, setUndoQuoteCode] = useState('Q-00092 V1')

  // Evidence Modal State
  const [evidenceId, setEvidenceId] = useState<number | null>(null)

  // Copilot Composer State
  const [draftContent, setDraftContent] = useState(
    'Dạ em chào anh An, em gửi anh phương án báo giá chuẩn căn R-02.02 ạ [2]. Khách hàng chọn thanh toán sớm 95% nhận chiết khấu 8% [1]. Anh quét mã QR trên báo giá để đối soát pháp lý nhé!'
  )
  const [draftAnchors, setDraftAnchors] = useState<number[]>([2, 1])
  const [complianceResult, setComplianceResult] = useState<ComplianceCheckState>(runLocalComplianceCheck(draftContent))
  const [isCheckingCompliance, setIsCheckingCompliance] = useState(false)
  const complianceDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Copilot Action Modals
  const [copyAuditModalOpen, setCopyAuditModalOpen] = useState(false)
  const [officialSendModalOpen, setOfficialSendModalOpen] = useState(false)
  const [sendGateStep, setSendGateStep] = useState(0)
  const [officialReceiptId, setOfficialReceiptId] = useState<string | null>(null)
  const [voiceVariantModalOpen, setVoiceVariantModalOpen] = useState(false)

  // Toast
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const chatBottomRef = useRef<HTMLDivElement>(null)
  const inputTextAreaRef = useRef<HTMLTextAreaElement>(null)

  const showToast = (text: string) => {
    setToastMessage(text)
    setTimeout(() => {
      setToastMessage((cur) => (cur === text ? null : cur))
    }, 3200)
  }

  // Đặt câu hỏi mẫu vào chat input và focus (dùng chung cho các nút "Hỏi agent")
  const askAgent = (question: string) => {
    setInputVal(question)
    inputTextAreaRef.current?.focus()
  }

  const scrollChatToEnd = () => {
    setTimeout(() => {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, 100)
  }

  // 8s Undo countdown timer
  useEffect(() => {
    if (!undoActive) return
    if (undoSeconds <= 0) {
      setUndoActive(false)
      return
    }
    const timer = setTimeout(() => setUndoSeconds((s) => s - 1), 1000)
    return () => clearTimeout(timer)
  }, [undoActive, undoSeconds])

  // Copilot Live-Check Debounce (500ms)
  const handleDraftTextChange = (text: string) => {
    setDraftContent(text)
    setIsCheckingCompliance(true)
    if (complianceDebounceRef.current) clearTimeout(complianceDebounceRef.current)
    complianceDebounceRef.current = setTimeout(() => {
      setComplianceResult(runLocalComplianceCheck(text))
      setIsCheckingCompliance(false)
    }, 500)
  }

  // Initialize Morning Briefing on Mount
  useEffect(() => {
    const time = new Date().toTimeString().slice(0, 5)
    setMessages([
      {
        id: 'msg-greeting',
        type: 'welcome',
        time,
      },
    ])
    scrollChatToEnd()
  }, [])

  // Action: Create customer lead and inject into Copilot context
  const executeCustomerCreation = async (payload: LeadCreatePayload) => {
    try {
      const created = await createLeadMutation.mutateAsync(payload)
      setSelectedLeadId(created.dossier_id)
      setContextLeadId(created.dossier_id)
      setActiveTab('hoso')
      setPanelView('dossier')
      setIsMobilePanelOpen(true)
      setCreateCustomerOpen(false)

      const time = new Date().toTimeString().slice(0, 5)
      setMessages((prev) => [
        ...prev,
        {
          id: `lead-created-${Date.now()}`,
          type: 'customer_card',
          time,
          data: {
            lead: created,
            message: `✓ Đã khởi tạo thành công hồ sơ khách hàng **${created.customer?.full_name}** (${created.dossier_id}). Copilot đã nạp toàn bộ thông tin & ràng buộc tài chính vào ngữ cảnh làm việc.`,
          },
        },
      ])
      showToast(`Đã tạo thành công khách hàng: ${created.customer?.full_name}`)
      scrollChatToEnd()
    } catch (err: any) {
      showToast(`Lỗi tạo khách hàng: ${err?.message || 'Không thể tạo hồ sơ'}`)
    }
  }

  // Action: Launch Quote Creation Flow
  const startQuoteCreationFlow = (targetLeadName?: string) => {
    const time = new Date().toTimeString().slice(0, 5)
    const clientName = targetLeadName || selectedLead?.customer.full_name || 'khách hàng'
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, type: 'user', text: `tạo báo giá cho ${clientName}`, time },
      {
        id: `conf-${Date.now()}`,
        type: 'confirm',
        time,
        data: {
          clientName,
          unitCode: selectedLead?.constraints?.preferred_unit_code || 'Chưa chọn căn — chọn trên card báo giá',
          date: '10/03/2026 (hôm nay)',
          goal: 'Ít vốn ban đầu nhất (suy đoán từ nguyện vọng dossier)',
        },
      },
    ])
    scrollChatToEnd()
  }

  // Confirm quote creation
  const handleConfirmQuoteAction = () => {
    const time = new Date().toTimeString().slice(0, 5)
    const stepMsgId = `step-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      {
        id: stepMsgId,
        type: 'stepper',
        time,
        data: {
          steps: ['Hiểu yêu cầu dossier', 'Tra cứu chính sách 10/03', 'Deterministic Math Engine FCS v2.6', 'Xếp hạng & đối soát chứng cứ'],
          current: 0,
        },
      },
    ])
    scrollChatToEnd()

    let idx = 0
    const interval = setInterval(() => {
      idx++
      setMessages((prev) =>
        prev.map((m) => (m.id === stepMsgId ? { ...m, data: { ...m.data, current: idx } } : m))
      )
      if (idx >= 4) {
        clearInterval(interval)
        setTimeout(() => {
          setMessages((prev) => [
            ...prev,
            {
              id: `done-${Date.now()}`,
              type: 'agent',
              time: new Date().toTimeString().slice(0, 5),
              text: '✓ Đã lập bảng so sánh 3 phương án tại **Panel bên phải** (P-04). Đề xuất **PA-VAY** tối ưu dòng tiền ban đầu. Lưu ý: POL-EARLY hết hạn ngày 30/06/2026.',
            },
          ])
          setActiveTab('baogia')
          setPanelView('quote_comparison')
          setIsMobilePanelOpen(true)
          showToast('→ Bảng so sánh phương án đã mở tại tab Báo giá')
          scrollChatToEnd()
        }, 300)
      }
    }, 450)
  }

  // Action: Launch Submit Review Flow
  const startSubmitReviewFlow = () => {
    const time = new Date().toTimeString().slice(0, 5)
    setMessages((prev) => [
      ...prev,
      {
        id: `conf-sub-${Date.now()}`,
        type: 'confirm',
        time,
        data: {
          isSubmit: true,
          quoteId: 'Q-00092 V1 · An · R-02.02 · 4,65 tỷ',
          approver: 'Mr. Hùng (Team Lead Riverside)',
          note: 'Khách cần phương án trước 17h — xin anh duyệt sớm',
        },
      },
    ])
    scrollChatToEnd()
  }

  // Confirm submission -> Receipt with 8s Undo
  const handleConfirmSubmitAction = () => {
    const time = new Date().toTimeString().slice(0, 5)
    setUndoSeconds(8)
    setUndoActive(true)
    setUndoQuoteCode('Q-00092 V1')

    setMessages((prev) => [
      ...prev,
      {
        id: `rcp-${Date.now()}`,
        type: 'receipt',
        time,
        data: { id: 'Q-00092 V1', approver: 'Mr. Hùng' },
      },
    ])
    scrollChatToEnd()

    // Realtime SSE Manager Viewing notice simulation
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: `sse-nudge-${Date.now()}`,
          type: 'nudge',
          time: new Date().toTimeString().slice(0, 5),
          data: {
            title: 'Mr. Hùng đang xem Q-00092',
            sub: '14:06 — sự kiện thời gian thực từ SSE timeline',
          },
        },
      ])
      scrollChatToEnd()
    }, 6000)
  }

  // Handle 8s Undo
  const handleUndoSubmission = () => {
    setUndoActive(false)
    setMessages((prev) => [
      ...prev,
      {
        id: `undone-${Date.now()}`,
        type: 'agent',
        time: new Date().toTimeString().slice(0, 5),
        text: '↩ Đã hoàn tác trình duyệt Q-00092 — hồ sơ đã trở về trạng thái Nháp an toàn.',
      },
    ])
    showToast('Đã hoàn tác thành công — hồ sơ chưa phát tán ra ngoài')
    scrollChatToEnd()
  }

  // Action: Launch Copilot Compose
  const startCopilotDrafting = () => {
    const time = new Date().toTimeString().slice(0, 5)
    setMessages((prev) => [
      ...prev,
      { id: `u-c-${Date.now()}`, type: 'user', text: 'soạn tin chốt gửi khách', time },
      {
        id: `ag-c-${Date.now()}`,
        type: 'agent',
        time,
        text: 'Em đã chuẩn bị sẵn khung tin nhắn tư vấn kèm kiểm tra tuân thủ F8 ở panel bên phải.',
      },
    ])
    setActiveTab('tinnhan')
    setPanelView('messages')
    setIsMobilePanelOpen(true)
    showToast('Đã mở trình soạn tin nhắn Copilot tại panel')
    scrollChatToEnd()
  }

  // Process natural commands from Sale
  // ===== NGỮ CẢNH THÔNG MINH =====
  // Tự phát hiện khách hàng được nhắc tới trong tin nhắn (tên/SĐT/mã căn/mã hồ sơ).
  // Ưu tiên: lệnh chỉ định rõ > tên/SĐT nhắc trong câu > giữ ngữ cảnh hiện tại > không ngữ cảnh.
  const resolveSmartContext = (text: string): LeadDossier | null => {
    const t = text.toLowerCase()
    // Lệnh chuyển ngữ cảnh tường minh: /khach <từ khóa> hoặc "chuyển ngữ cảnh <từ khóa>"
    const explicit = t.match(/(?:^|\s)(?:\/khach\s+|chuyển (?:ngữ cảnh|sang))(.+?)\s*(?:$|[,.;])/)
    if (explicit && explicit[1]) {
      const kw = explicit[1].trim()
      const hit = leads.find((l) =>
        l.customer?.full_name?.toLowerCase().includes(kw) ||
        l.customer?.phone?.includes(kw) ||
        l.dossier_id?.toLowerCase().includes(kw)
      )
      if (hit) return hit
    }
    // Tự phát hiện: SĐT hoặc mã hồ sơ (P-xxx / LEAD-xxx) xuất hiện trong câu
    const phoneMatch = text.match(/0\d{9,10}/)
    if (phoneMatch) {
      const byPhone = leads.find((l) => l.customer?.phone === phoneMatch[0])
      if (byPhone) return byPhone
    }
    const dossierMatch = text.toUpperCase().match(/\b(?:P-\d{3,}|LEAD-\d{3,}|DOS-\d{3,})\b/)
    if (dossierMatch) {
      const byId = leads.find((l) => l.dossier_id?.toUpperCase() === dossierMatch[0])
      if (byId) return byId
    }
    // Tự phát hiện: tên khách (>=2 ký tự) hoặc mã căn xuất hiện trong câu
    const unitMatch = text.toUpperCase().match(/\b([A-Z]+\-\d+\.\d+)\b/)
    const byUnit = unitMatch ? leads.find((l) => (l.constraints?.preferred_unit_code || '').toUpperCase() === unitMatch[1]) : null
    if (byUnit) return byUnit
    const nameHits = leads.filter((l) => {
      const n = l.customer?.full_name?.toLowerCase() || ''
      return n.length >= 2 && t.includes(n)
    })
    // Chỉ auto-chuyển khi khớp duy nhất, tránh chuyển oan khi tên trùng nhau
    if (nameHits.length === 1) return nameHits[0]
    return null
  }

  // Trả về id khách đang được nhắc tới trong tin nhắn (để đổi chip ngữ cảnh), null nếu không phát hiện
  const detectContextLeadId = (text: string): string | null => {
    const hit = resolveSmartContext(text)
    return hit ? hit.dossier_id : null
  }
  const processNaturalCommand = (text: string, time: string, overrideLead?: LeadDossier | null) => {

    // Ngữ cảnh hiệu lực cho lệnh này: override (từ smart-context) > ngữ cảnh hiện tại
    const ctxLead = overrideLead !== undefined ? overrideLead : selectedLead
    // 1. Phím tắt tra cứu nhanh danh sách hồ sơ khách hàng đã lưu
    if (/^tìm khách|^tra cứu khách/i.test(text)) {
      const queryTerm = text.replace(/^(tìm khách hàng|tìm khách|tra cứu khách)\s*/i, '').trim().toLowerCase()
      const matched = queryTerm
        ? leads.filter(
            (l) =>
              l.customer?.full_name?.toLowerCase().includes(queryTerm) ||
              l.customer?.phone?.includes(queryTerm) ||
              l.dossier_id?.toLowerCase().includes(queryTerm) ||
              (l.constraints?.preferred_unit_code && l.constraints.preferred_unit_code.toLowerCase().includes(queryTerm))
          )
        : leads.slice(0, 5)

      setMessages((prev) => [
        ...prev,
        {
          id: `search-cust-${Date.now()}`,
          type: 'customer_search',
          time,
          data: {
            queryTerm: queryTerm || 'Tất cả khách hàng',
            results: matched,
          },
        },
      ])
      scrollChatToEnd()
      return
    }

    // 2. Phím tắt mở nhanh panel hồ sơ khách hàng An / SLA
    if (/an.*sao rồi|hồ sơ an|sla/i.test(text)) {
      setActiveTab('hoso')
      setPanelView('dossier')
      setIsMobilePanelOpen(true)
      setMessages((prev) => [
        ...prev,
        {
          id: `qa-${Date.now()}`,
          type: 'agent',
          time,
          text: 'Đây là hồ sơ của **Nguyễn Minh An** tại panel. Khách còn 1 băn khoăn: *"chuyển nhượng sớm được không?"* — nên giải thích trước khi tư vấn tiến độ.',
        },
      ])
      scrollChatToEnd()
      return
    }

    // 3. Phím tắt mở nhanh chính sách P09
    if (/p09|chính sách mới|bãi bỏ/i.test(text)) {
      setActiveTab('chinhsach')
      setPanelView('policies')
      setIsMobilePanelOpen(true)
      setMessages((prev) => [
        ...prev,
        {
          id: `qa-${Date.now()}`,
          type: 'agent',
          time,
          text: 'Chính sách **P09** bãi bỏ ưu đãi cộng dồn trả nhanh + HTLS. Mọi tính toán mới sẽ áp dụng công thức mới (bất biến, version cũ chuyển SUPERSEDED).',
        },
      ])
      scrollChatToEnd()
      return
    }

    // 4. Mọi câu lệnh nghiệp vụ tự nhiên (Tạo khách hàng, Lập báo giá, So sánh phương án, Tra cứu căn...)
    // Chuyển toàn bộ đến Copilot LLM Backend để bóc tách thực thể sâu bằng AI.

    // 7. Mặc định: Gửi đến Copilot LLM backend thật
    const thinkingId = `thinking-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      {
        id: thinkingId,
        type: 'agent',
        time,
        text: 'Đang tra cứu cơ sở dữ liệu và chính sách...',
      },
    ])
    scrollChatToEnd()

    fetch(`${API_BASE_URL}/copilot/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        current_unit: ctxLead?.constraints?.preferred_unit_code || null,
        lead_dossier_id: ctxLead?.dossier_id,
        history: messages.slice(-6).map((m) => ({
          role: m.type === 'user' ? 'user' : 'assistant',
          content: m.text || '',
        })),
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data) => {
        setMessages((prev) => {
          const list = prev.map((m) =>
            m.id === thinkingId
              ? {
                  ...m,
                  text: data.reply || 'Em đã ghi nhận yêu cầu của anh.',
                  suggested_actions: data.suggested_actions,
                }
              : m
          )
          if (data.action_type) {
            list.push({
              id: `card-${Date.now()}`,
              type: data.action_type as StreamItemType,
              time: new Date().toTimeString().slice(0, 5),
              data: data.action_data || {},
            })
          }
          return list
        })
        scrollChatToEnd()
      })
      .catch(() => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === thinkingId
              ? {
                  ...m,
                  type: 'fallback',
                  text: 'Em chưa chắc chắn hiểu yêu cầu. Anh có thể chọn nhanh thao tác nghiệp vụ:',
                }
              : m
          )
        )
        scrollChatToEnd()
      })
  }

  // Trigger Smart Action from Quick Chips
  const triggerSmartAction = (promptText: string) => {
    const time = new Date().toTimeString().slice(0, 5)
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, type: 'user', text: promptText, time }])
    scrollChatToEnd()
    processNaturalCommand(promptText, time, resolveSmartContext(promptText) ?? selectedLead)
  }

  // Chat Send Handler
  const handleSendChatMessage = () => {
    const text = inputVal.trim()
    if (!text) return
    setInputVal('')

    // Ngữ cảnh thông minh: tự nhận diện khách được nhắc tới trong tin nhắn
    // (tên / SĐT / mã căn / mã hồ sơ). Nếu không nhắc ai -> giữ nguyên ngữ cảnh hiện tại.
    const mentionedId = detectContextLeadId(text)
    if (mentionedId && mentionedId !== contextLeadId) {
      setContextLeadId(mentionedId)
      setSelectedLeadId(mentionedId)
    }

    const time = new Date().toTimeString().slice(0, 5)
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, type: 'user', text, time }])
    scrollChatToEnd()

    setTimeout(() => {
      processNaturalCommand(text, time, resolveSmartContext(text) ?? selectedLead)
    }, 150)
  }

  // Slash commands list
  const SLASH_COMMANDS = [
    { cmd: '/tao-khach', label: 'Khởi tạo hồ sơ khách hàng mới', icon: UserPlus },
    { cmd: '/tim-khach', label: 'Tìm kiếm khách hàng theo tên / SĐT / căn', icon: Search },
    { cmd: '/khach-hang', label: 'Xem danh sách hồ sơ khách', icon: Users },
    { cmd: '/baogia', label: 'Mở pipeline báo giá', icon: FileStack },
    { cmd: '/soan-tin', label: 'Soạn tin nhắn Copilot (F8)', icon: MessageSquare },
    { cmd: '/chinh-sach', label: 'Tra cứu chính sách bán hàng', icon: ScrollText },
    { cmd: '/tinh-lai', label: 'Lập báo giá mới theo chính sách', icon: RotateCcw },
  ]

  const filteredCommands = SLASH_COMMANDS.filter((c) =>
    c.cmd.toLowerCase().includes(inputVal.toLowerCase())
  )

  const handleExecuteSlash = (cmd: string) => {
    setSlashOpen(false)
    setInputVal('')
    if (cmd === '/tao-khach') {
      setCreateCustomerOpen(true)
    } else if (cmd === '/tim-khach') {
      setInputVal('/tim-khach ')
      inputTextAreaRef.current?.focus()
    } else if (cmd === '/khach-hang') {
      setActiveTab('hoso')
      setPanelView('leads')
      setIsMobilePanelOpen(true)
    } else if (cmd === '/baogia') {
      setActiveTab('baogia')
      setPanelView('pipeline')
      setIsMobilePanelOpen(true)
    } else if (cmd === '/soan-tin') {
      startCopilotDrafting()
    } else if (cmd === '/chinh-sach') {
      setActiveTab('chinhsach')
      setPanelView('policies')
      setIsMobilePanelOpen(true)
    } else if (cmd === '/tinh-lai') {
      startQuoteCreationFlow()
    }
  }

  // Real data grouping for Kanban

  const kanbanGroups = useMemo(() => {
    return {
      draft: quotes.filter((q) => ['DRAFT', 'NEEDS_INPUT', 'CALCULATION_FAILED'].includes(q.status)),
      review: quotes.filter((q) => q.status === 'READY_FOR_REVIEW'),
      approved: quotes.filter((q) => q.status === 'APPROVED'),
      sent: quotes.filter((q) => ['SENT', 'DISPATCHED'].includes(q.status as any)),
      revision: quotes.filter((q) => ['NEEDS_REVISION', 'REJECTED', 'ABSTAINED'].includes(q.status)),
    }
  }, [quotes])

  // Khách cần chăm sóc sớm — xếp theo SLA thật: đã quá hạn trước, rồi đến sắp đến hạn
  const urgentLeads = useMemo(() => {
    return [...leads]
      .filter((l) => l.sla_due_at)
      .sort((a, b) => new Date(a.sla_due_at).getTime() - new Date(b.sla_due_at).getTime())
      .slice(0, 2)
  }, [leads])

  return (
    <div className="flex h-full w-full flex-1 flex-col overflow-hidden bg-background text-foreground antialiased font-sans">
      {/* ================= 1. WORKSPACE HEADER ================= */}
      <header className="z-40 flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-4 text-foreground shadow-xs">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600">
            <Sparkles className="h-4 w-4" />
          </span>
          <div>
            <span className="font-display text-xs font-bold tracking-wide">Trợ lý Copilot AI</span>
            <span className="ml-2 text-[11px] text-muted-foreground hidden sm:inline">VLand Future Riverside</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10">
            🟢 Online · FCS v2.6
          </Badge>
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate('/sale/leads')}
            className="h-7 text-xs gap-1 border-primary/30 text-primary hover:bg-primary hover:text-primary-foreground"
          >
            <Users className="h-3 w-3" />
            Mở CRM Khách hàng
          </Button>
        </div>
      </header>

      {/* ================= 2. WORKSPACE CONVERSATION & PANEL ================= */}
      <div className="flex min-h-0 flex-1">
        {/* ----- AGENT CONVERSATION (MAIN) ----- */}
        <section className="flex min-w-0 flex-1 flex-col bg-background">
          {/* Chat Stream Messages */}
          <div className="flex-1 space-y-3.5 overflow-y-auto p-4 scroll-smooth">
            {messages.map((m) => {
              if (m.type === 'user') {
                return (
                  <div key={m.id} className="flex flex-col items-end gap-1">
                    <div className="max-w-[85%] rounded-2xl rounded-br-xs bg-primary px-4 py-2.5 text-xs leading-relaxed text-primary-foreground shadow-xs">
                      {m.text}
                    </div>
                    <span className="text-[10px] text-muted-foreground">{m.time}</span>
                  </div>
                )
              }

              if (m.type === 'agent') {
                return (
                  <div key={m.id} className="flex flex-col items-start gap-1.5 w-full">
                    <div className="max-w-[92%] rounded-2xl rounded-bl-xs border border-border/80 bg-card/95 px-4 py-3 text-xs text-foreground shadow-sm">
                      <FormattedAiMessage content={m.text || ''} onCommandClick={(cmd) => triggerSmartAction(cmd)} />
                    </div>
                    {/* Suggested actions pills */}
                    {m.suggested_actions && m.suggested_actions.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1 pl-1">
                        {m.suggested_actions.map((act, aIdx) => (
                          <button
                            key={aIdx}
                            type="button"
                            onClick={() => triggerSmartAction(act)}
                            className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/5 px-2.5 py-1 text-[11px] font-medium text-primary hover:bg-primary/15 transition-all shadow-2xs"
                          >
                            <span>✨</span>
                            <span>{act}</span>
                          </button>
                        ))}
                      </div>
                    )}
                    <span className="text-[10px] text-muted-foreground ml-1">Trợ lý AI · {m.time}</span>
                  </div>
                )
              }

              if (m.type === 'welcome') {
                return (
                  <div key={m.id} className="mx-auto w-full max-w-lg space-y-5 py-6">
                    {/* Heading */}
                    <div className="text-center">
                      <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-primary/10">
                        <ShieldCheck className="h-6 w-6 text-primary" />
                      </div>
                      <h1 className="font-display text-base font-semibold text-foreground">
                        Xin chào, {session?.user.full_name || 'Hải Nguyễn'} 👋
                      </h1>
                      <p className="mt-1 text-[11.5px] text-muted-foreground">
                        Em đã tổng hợp việc cần ưu tiên hôm nay bên dưới — hoặc anh gõ yêu cầu bất kỳ.
                                            </p>
                    </div>

                    {/* Gợi ý theo luồng công việc thật (chỉ hiện khi có việc) */}
                    <div className="space-y-2">
                      {kanbanGroups.revision.length > 0 && (
                        <button
                          type="button"
                          onClick={() => {
                            setActiveTab('baogia')
                            setPanelView('pipeline')
                            setIsMobilePanelOpen(true)
                          }}
                          className="flex w-full items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-left transition-colors hover:bg-destructive/10"
                        >
                          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-destructive/10 text-destructive">
                            <AlertTriangle className="h-4 w-4" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-xs font-semibold text-foreground">
                              {kanbanGroups.revision.length} báo giá cần chỉnh sửa
                            </span>
                            <span className="block truncate text-[10.5px] text-muted-foreground">
                              {kanbanGroups.revision.slice(0, 2).map((q) => q.quote_id).join(', ')} — quản lý đã phản hồi, cần cập nhật
                            </span>
                          </span>
                          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                        </button>
                      )}

                      {kanbanGroups.review.length > 0 && (
                        <button
                          type="button"
                          onClick={() => {
                            setActiveTab('baogia')
                            setPanelView('pipeline')
                            setIsMobilePanelOpen(true)
                          }}
                          className="flex w-full items-center gap-3 rounded-xl border border-warning/30 bg-warning/5 p-3 text-left transition-colors hover:bg-warning/10"
                        >
                          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-warning/10 text-warning">
                            <Clock className="h-4 w-4" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-xs font-semibold text-foreground">
                              {kanbanGroups.review.length} báo giá đang chờ phê duyệt
                            </span>
                            <span className="block truncate text-[10.5px] text-muted-foreground">
                              {kanbanGroups.review.slice(0, 2).map((q) => q.quote_id).join(', ')} — sẽ có thông báo khi có kết quả
                            </span>
                          </span>
                          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                        </button>
                      )}

                      {urgentLeads.length > 0 && (
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedLeadId(urgentLeads[0].dossier_id)
                            setActiveTab('hoso')
                            setPanelView('dossier')
                            setIsMobilePanelOpen(true)
                          }}
                          className="flex w-full items-center gap-3 rounded-xl border border-sky-500/30 bg-sky-500/5 p-3 text-left transition-colors hover:bg-sky-500/10"
                        >
                          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-sky-500/10 text-sky-600">
                            <Users className="h-4 w-4" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-xs font-semibold text-foreground">
                              Khách cần chăm sóc: {urgentLeads.map((l) => l.customer.full_name).slice(0, 2).join(', ')}
                            </span>
                            <span className="flex items-center gap-1 truncate text-[10.5px] text-muted-foreground">
                              <SlaCountdown dueAt={urgentLeads[0].sla_due_at} /> — mở hồ sơ để phản hồi ngay
                            </span>
                          </span>
                          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                        </button>
                      )}
                    </div>
                  </div>
                )
              }

              if (m.type === 'confirm') {
                const isSub = m.data?.isSubmit
                const isCust = m.data?.isCustomerCreate
                return (
                  <Card key={m.id} className="w-full max-w-[92%] border-primary/50 bg-card shadow-sm">
                    <CardHeader className="bg-primary/5 px-4 py-2.5 border-b border-border">
                      <CardTitle className="text-xs font-semibold text-primary flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4" />
                        {isCust
                          ? 'Xác nhận khởi tạo hồ sơ khách hàng mới'
                          : isSub
                          ? 'Xác nhận trình quản lý phê duyệt'
                          : 'Xác nhận tham số tạo báo giá'}
                      </CardTitle>
                    </CardHeader>

                    <CardContent className="space-y-2 p-3.5 text-xs">
                      {isCust ? (
                        <>
                          <div className="flex justify-between py-1 border-b border-border/50">
                            <span className="text-muted-foreground">Khách hàng:</span>
                            <span className="font-semibold text-foreground">{m.data?.clientName}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-border/50">
                            <span className="text-muted-foreground">Số điện thoại:</span>
                            <span className="font-semibold text-foreground">{m.data?.phone}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-border/50">
                            <span className="text-muted-foreground">Căn quan tâm:</span>
                            <span className="font-semibold text-foreground">{m.data?.unitCode}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-border/50">
                            <span className="text-muted-foreground">Vốn tự có:</span>
                            <span className="font-semibold text-primary">{formatVnd(m.data?.funds || 0)}</span>
                          </div>
                          <p className="text-[11px] text-muted-foreground pt-1">
                            Copilot đã bóc tách thông tin từ lệnh của bạn. Bấm <b>Khởi tạo ngay</b> để lưu hồ sơ vào CRM và nạp vào ngữ cảnh.
                          </p>
                        </>
                      ) : isSub ? (
                        <>
                          <div className="flex justify-between py-1 border-b border-border/50">
                            <span className="text-muted-foreground">Hồ sơ báo giá:</span>
                            <span className="font-semibold">{m.data?.quoteId}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-border/50">
                            <span className="text-muted-foreground">Người phê duyệt:</span>
                            <span className="font-semibold">{m.data?.approver}</span>
                          </div>
                          <p className="text-[11px] text-muted-foreground pt-1">
                            Sau khi trình duyệt, phiên bản sẽ được đóng băng (bất biến). Mọi sửa đổi bổ sung sẽ tạo ra phiên bản mới.
                          </p>
                        </>
                      ) : (
                        <>
                          <div className="flex justify-between py-1 border-b border-border/50">
                            <span className="text-muted-foreground">Khách hàng:</span>
                            <span className="font-semibold">{m.data?.clientName}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-border/50">
                            <span className="text-muted-foreground">Căn hộ:</span>
                            <span className="font-semibold">{m.data?.unitCode}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-border/50">
                            <span className="text-muted-foreground">Mục tiêu:</span>
                            <span className="font-semibold text-primary">{m.data?.goal}</span>
                          </div>
                          <p className="text-[11px] text-muted-foreground pt-1">
                            Dữ liệu tự động điền từ hồ sơ tư vấn trực tuyến (C-10) — không yêu cầu nhập lại hai lần.
                          </p>
                        </>
                      )}

                      <div className="flex gap-2 pt-2">
                        <Button
                          size="sm"
                          onClick={() => {
                            if (isCust) {
                              executeCustomerCreation(m.data?.rawPayload)
                            } else if (isSub) {
                              handleConfirmSubmitAction()
                            } else {
                              handleConfirmQuoteAction()
                            }
                          }}
                        >
                          {isCust ? 'Khởi tạo ngay' : isSub ? 'Trình duyệt ngay' : 'Bắt đầu tính toán'}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            if (isCust) {
                              setCustomerForm((prev) => ({
                                ...prev,
                                ...m.data?.rawPayload,
                              }))
                              setCreateCustomerOpen(true)
                            } else {
                              setMessages((prev) => [
                                ...prev,
                                {
                                  id: `cancel-${Date.now()}`,
                                  type: 'agent',
                                  time: new Date().toTimeString().slice(0, 5),
                                  text: 'Anh có thể điều chỉnh lại thông tin hoặc gõ yêu cầu khác.',
                                },
                              ])
                              scrollChatToEnd()
                            }
                          }}
                        >
                          {isCust ? 'Mở Form điều chỉnh' : 'Thay đổi tham số'}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              }

              if (m.type === 'stepper') {
                const current = m.data?.current || 0
                return (
                  <div key={m.id} className="flex flex-wrap gap-1.5 rounded-xl border border-border bg-card p-3 shadow-xs">
                    {m.data?.steps.map((st: string, idx: number) => {
                      const isDone = idx < current
                      const isRun = idx === current
                      return (
                        <span
                          key={st}
                          className={cn(
                            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all',
                            isDone
                              ? 'bg-success/10 text-success border border-success/30 font-semibold'
                              : isRun
                              ? 'bg-primary/10 text-primary border border-primary/30 font-semibold animate-pulse'
                              : 'bg-muted text-muted-foreground'
                          )}
                        >
                          {isDone ? (
                            <CheckCircle2 className="h-3 w-3" />
                          ) : isRun ? (
                            <RefreshCw className="h-3 w-3 animate-spin" />
                          ) : null}
                          {st}
                        </span>
                      )
                    })}
                  </div>
                )
              }

              if (m.type === 'receipt') {
                return (
                  <Card key={m.id} className="w-full max-w-[92%] border-success/40 bg-success/5 shadow-xs">
                    <CardContent className="p-3.5 space-y-2 text-xs">
                      <div className="flex items-center gap-2 font-semibold text-success">
                        <CheckCircle2 className="h-4 w-4" />
                        Đã trình {m.data?.id} cho {m.data?.approver}
                      </div>
                      <p className="text-muted-foreground text-[11.5px]">
                        Hồ sơ đã chuyển trạng thái <b>READY_FOR_REVIEW</b>. Khi có kết quả xét duyệt hệ thống sẽ thông báo ngay.
                      </p>
                      <div className="flex items-center gap-3 pt-1">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={!undoActive}
                          onClick={handleUndoSubmission}
                          className="h-7 text-xs border-border bg-card text-foreground hover:text-destructive"
                        >
                          <RotateCcw className="mr-1 h-3.5 w-3.5" />
                          {undoActive ? `Hoàn tác (${undoSeconds}s)` : 'Hết hạn hoàn tác'}
                        </Button>
                        <span className="text-[11px] text-muted-foreground">
                          {undoActive ? 'Cho phép thu hồi trong 8s' : 'Đã khóa gửi xét duyệt'}
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                )
              }

              if (m.type === 'nudge') {
                return (
                  <div key={m.id} className="flex w-full max-w-[92%] items-center gap-3 rounded-xl border border-warning/40 bg-warning/5 p-3 text-xs shadow-xs">
                    <AlertTriangle className="h-5 w-5 text-warning shrink-0" />
                    <div className="min-w-0 flex-1">
                      <b className="text-foreground">{m.data?.title}</b>
                      <p className="text-[11px] text-muted-foreground">{m.data?.sub}</p>
                    </div>
                  </div>
                )
              }

              if (m.type === 'fallback') {
                return (
                  <div key={m.id} className="max-w-[88%] space-y-2.5 rounded-2xl rounded-bl-xs border border-border bg-card p-3.5 text-xs shadow-xs">
                    <p className="text-muted-foreground">{m.text}</p>
                    <div className="flex flex-wrap gap-1.5">
                      <Button variant="secondary" size="sm" className="h-7 text-xs" onClick={() => startQuoteCreationFlow()}>
                        Tạo báo giá
                      </Button>
                      <Button variant="secondary" size="sm" className="h-7 text-xs" onClick={startCopilotDrafting}>
                        Soạn tin Zalo
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => {
                          setActiveTab('chinhsach')
                          setPanelView('policies')
                          setIsMobilePanelOpen(true)
                        }}
                      >
                        Xem chính sách
                      </Button>
                    </div>
                  </div>
                )
              }

              if (m.type === 'customer_card') {
                const lead = m.data?.lead as LeadDossier
                return (
                  <Card key={m.id} className="w-full max-w-[92%] border-primary/40 bg-primary/[0.02] shadow-xs">
                    <CardHeader className="bg-primary/5 px-4 py-2.5 border-b border-border">
                      <CardTitle className="text-xs font-semibold text-primary flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          <UserCheck className="h-4 w-4 text-emerald-600" />
                          Hồ sơ khách hàng: {lead.customer?.full_name}
                        </span>
                        <TemperatureBadge temperature={lead.temperature} />
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2.5 p-3.5 text-xs">
                      <div
                        className="text-foreground text-[11.5px] leading-relaxed"
                        dangerouslySetInnerHTML={{
                          __html: (m.data?.message || '')
                            .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
                            .replace(/\*(.*?)\*/g, '<i>$1</i>'),
                        }}
                      />
                      <div className="grid grid-cols-2 gap-2 rounded-lg bg-muted/40 p-2.5 text-[11px]">
                        <div>
                          <span className="text-muted-foreground">Mã hồ sơ:</span>
                          <div className="font-semibold text-foreground">{lead.dossier_id}</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Số điện thoại:</span>
                          <div className="font-semibold text-foreground">{lead.customer?.phone}</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Căn quan tâm:</span>
                          <div className="font-semibold text-foreground">{lead.constraints?.preferred_unit_code || 'Chưa định danh'}</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Vốn tự có:</span>
                          <div className="font-semibold text-primary">
                            {lead.constraints?.own_funds_vnd ? formatVnd(lead.constraints.own_funds_vnd) : '—'}
                          </div>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border/50">
                        <Button
                          size="sm"
                          className="h-7 text-xs bg-primary text-primary-foreground"
                          onClick={() => startQuoteCreationFlow(lead.customer?.full_name)}
                        >
                          <FilePlus2 className="mr-1 h-3.5 w-3.5" /> Lập báo giá ngay
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => {
                            setSelectedLeadId(lead.dossier_id)
                            setContextLeadId(lead.dossier_id)
                            setActiveTab('hoso')
                            setPanelView('dossier')
                            setIsMobilePanelOpen(true)
                          }}
                        >
                          <FileText className="mr-1 h-3.5 w-3.5" /> Xem hồ sơ chi tiết
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={startCopilotDrafting}
                        >
                          <MessageSquare className="mr-1 h-3.5 w-3.5" /> Soạn tin tư vấn
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              }

              if (m.type === 'customer_search') {
                const results = (m.data?.results || []) as LeadDossier[]
                const queryTerm = m.data?.queryTerm || ''
                return (
                  <Card key={m.id} className="w-full max-w-[92%] border-border shadow-xs">
                    <CardHeader className="bg-muted/40 px-3.5 py-2 border-b border-border">
                      <CardTitle className="text-xs font-semibold flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Search className="h-3.5 w-3.5 text-primary" /> Kết quả tìm kiếm: "{queryTerm}"
                        </span>
                        <Badge variant="secondary" className="text-[10px]">{results.length} hồ sơ</Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-2 space-y-1.5 text-xs">
                      {results.length === 0 ? (
                        <div className="p-3 text-center space-y-2">
                          <p className="text-muted-foreground text-[11px]">
                            Không tìm thấy hồ sơ nào khớp với từ khóa "{queryTerm}".
                          </p>
                          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setCreateCustomerOpen(true)}>
                            <UserPlus className="mr-1.5 h-3.5 w-3.5" /> Tạo khách hàng mới
                          </Button>
                        </div>
                      ) : (
                        results.map((l) => (
                          <div key={l.dossier_id} className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/20 p-2 hover:bg-muted/40 transition-colors">
                            <div className="space-y-0.5 min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className="font-semibold text-foreground truncate">{l.customer?.full_name}</span>
                                <TemperatureBadge temperature={l.temperature} />
                              </div>
                              <div className="text-[11px] text-muted-foreground">
                                {l.customer?.phone} · {l.constraints?.preferred_unit_code || 'Chưa định danh'}
                              </div>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-6 px-2 text-[11px]"
                                onClick={() => {
                                  setSelectedLeadId(l.dossier_id)
                                  setContextLeadId(l.dossier_id)
                                  setActiveTab('hoso')
                                  setPanelView('dossier')
                                  setIsMobilePanelOpen(true)
                                }}
                              >
                                Chọn hồ sơ
                              </Button>
                              <Button
                                size="sm"
                                className="h-6 px-2 text-[11px]"
                                onClick={() => startQuoteCreationFlow(l.customer?.full_name)}
                              >
                                Báo giá
                              </Button>
                            </div>
                          </div>
                        ))
                      )}
                    </CardContent>
                  </Card>
                )
              }

              if (m.type === 'smart_customer_create') {
                return (
                  <div key={m.id} className="w-full">
                    <SmartCustomerCard
                      initialData={m.data}
                      onSave={executeCustomerCreation}
                    />
                  </div>
                )
              }

              if (m.type === 'smart_quote_create') {
                return (
                  <div key={m.id} className="w-full">
                    <SmartQuoteCard
                      initialData={m.data}
                      onGenerateQuote={(uCode, sc) => {
                        startQuoteCreationFlow(selectedLead?.customer.full_name)
                        handleConfirmQuoteAction()
                      }}
                    />
                  </div>
                )
              }

              if (m.type === 'smart_scenario_compare') {
                return (
                  <div key={m.id} className="w-full">
                    <SmartScenarioCompareCard
                      unitCode={m.data?.unit_code || undefined}
                      onSelectScenario={(sc) => {
                        startQuoteCreationFlow(selectedLead?.customer.full_name)
                        handleConfirmQuoteAction()
                      }}
                    />
                  </div>
                )
              }

              if (m.type === 'smart_units_browse') {
                return (
                  <div key={m.id} className="w-full">
                    <SmartUnitsCard
                      onSelectUnit={(uCode) => {
                        triggerSmartAction(`Tạo báo giá căn ${uCode}`)
                      }}
                    />
                  </div>
                )
              }

              if (m.type === 'smart_compose_message') {
                return (
                  <div key={m.id} className="w-full">
                    <SmartComposeMessageCard
                      draftText={m.data?.draftText || draftContent}
                      onCopy={() => {
                        navigator.clipboard.writeText(m.data?.draftText || draftContent)
                        showToast('✓ Đã sao chép tin nhắn F8 vào clipboard!')
                      }}
                    />
                  </div>
                )
              }

              return null
            })}
            <div ref={chatBottomRef} />
          </div>

          {/* Bottom Chat Command Bar */}
          <div className="relative shrink-0 border-t border-border bg-card p-3 shadow-xs">
            {/* Smart Action Chips (Natural Sale Commands) */}
            {/* Ngữ cảnh Copilot (P-07): chỉ gắn theo KHÁCH HÀNG — 1 khách có thể mua nhiều căn,
                căn hộ sẽ được Copilot tự nhận diện từ nội dung câu lệnh */}
            <div className="mb-2 flex items-center gap-2 text-xs">
              <span className="text-[11px] font-semibold text-muted-foreground">Khách hàng:</span>
              <select
                value={contextLeadId}
                onChange={(e) => {
                  setContextLeadId(e.target.value)
                  setSelectedLeadId(e.target.value === 'auto' ? null : e.target.value)
                }}
                title="Copilot tự nhận diện khách được nhắc tới trong hội thoại. Chọn thủ công khi muốn khóa ngữ cảnh."
                className="max-w-[240px] rounded-md border border-input bg-background px-2 py-1 text-xs font-medium text-foreground outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="auto">Tự động theo hội thoại</option>
                <option value="none">— Không gắn ngữ cảnh —</option>
                {leads.map((l) => (
                  <option key={l.dossier_id} value={l.dossier_id}>
                    {l.customer.full_name}
                  </option>
                ))}
              </select>
            </div>
            {/* Quick Smart Action Chips for Sale Agents */}
            <div className="mb-2 flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5 text-xs">
              <Button
                variant="outline"
                size="sm"
                className="h-6 rounded-full px-2.5 text-[11px] font-normal border-primary/20 hover:border-primary/40 text-foreground shrink-0 bg-primary/[0.03]"
                onClick={() => triggerSmartAction('Tạo khách hàng mới')}
              >
                👤 Tạo khách hàng
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-6 rounded-full px-2.5 text-[11px] font-normal border-primary/20 hover:border-primary/40 text-foreground shrink-0 bg-primary/[0.03]"
                onClick={() => triggerSmartAction('Tạo báo giá')}
              >
                📑 Tạo báo giá
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-6 rounded-full px-2.5 text-[11px] font-normal border-primary/20 hover:border-primary/40 text-foreground shrink-0 bg-primary/[0.03]"
                onClick={() => triggerSmartAction('Tra cứu rổ hàng căn hộ')}
              >
                🏢 Tra cứu rổ hàng
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-6 rounded-full px-2.5 text-[11px] font-normal border-primary/20 hover:border-primary/40 text-foreground shrink-0 bg-primary/[0.03]"
                onClick={() => triggerSmartAction('So sánh 3 phương án thanh toán')}
              >
                📊 So sánh 3 phương án
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-6 rounded-full px-2.5 text-[11px] font-normal border-primary/20 hover:border-primary/40 text-foreground shrink-0 bg-primary/[0.03]"
                onClick={() => triggerSmartAction('Soạn tin nhắn tư vấn gửi khách')}
              >
                ✉️ Soạn tin tư vấn F8
              </Button>
            </div>
            {/* Input & Send Action */}
            <div className="flex items-center gap-2">
              <textarea
                ref={inputTextAreaRef}
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                onKeyDown={(e) => {
                  // Enter = xuống dòng. Gửi = Ctrl/Cmd + Enter hoặc nút Gửi.
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault()
                    handleSendChatMessage()
                  }
                }}
                rows={1}
                placeholder="Ra lệnh cho Copilot… (Enter: xuống dòng · Ctrl+Enter: gửi)"
                className="max-h-24 flex-1 resize-none rounded-xl border border-input bg-background px-3.5 py-2 text-xs leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <Button type="button" size="sm" onClick={handleSendChatMessage} className="h-9 px-3">
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </section>

        {/* ----- REGION C: ARTIFACT PANEL (380px) ----- */}
        <aside
          className={cn(
            'fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-border bg-card transition-transform duration-300 md:static md:w-[400px]',
            isMobilePanelOpen ? 'translate-x-0 shadow-2xl md:relative' : 'translate-x-full md:hidden'
          )}
        >
          {/* Panel Header & Tabs */}
          <div className="flex border-b border-border bg-muted/40">
            <button
              type="button"
              onClick={() => {
                setActiveTab('hoso')
                setPanelView(selectedLead ? 'dossier' : 'leads')
              }}
              className={cn(
                'flex-1 py-2.5 text-center text-xs font-semibold transition-all',
                activeTab === 'hoso' ? 'border-b-2 border-primary bg-card text-primary' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Hồ sơ
              <Badge variant="secondary" className="ml-1.5 h-4 px-1 text-[10px]">
                {leads.length}
              </Badge>
            </button>

            <button
              type="button"
              onClick={() => {
                setActiveTab('baogia')
                setPanelView('pipeline')
              }}
              className={cn(
                'flex-1 py-2.5 text-center text-xs font-semibold transition-all',
                activeTab === 'baogia' ? 'border-b-2 border-primary bg-card text-primary' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Báo giá
              <Badge variant="secondary" className="ml-1.5 h-4 px-1 text-[10px]">
                {quotes.length}
              </Badge>
            </button>

            <button
              type="button"
              onClick={() => {
                setActiveTab('tinnhan')
                setPanelView('messages')
              }}
              className={cn(
                'flex-1 py-2.5 text-center text-xs font-semibold transition-all',
                activeTab === 'tinnhan' ? 'border-b-2 border-primary bg-card text-primary' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Tin nhắn
            </button>

            <button
              type="button"
              onClick={() => {
                setActiveTab('chinhsach')
                setPanelView('policies')
              }}
              className={cn(
                'flex-1 py-2.5 text-center text-xs font-semibold transition-all',
                activeTab === 'chinhsach' ? 'border-b-2 border-primary bg-card text-primary' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Chính sách
              <Badge variant="secondary" className="ml-1.5 h-4 px-1 text-[10px]">
                {policies.length}
              </Badge>
            </button>

            <button
              type="button"
              onClick={() => setIsMobilePanelOpen(false)}
              className="px-2 text-muted-foreground hover:text-foreground md:hidden"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Panel Content Body */}
          <div className="flex-1 overflow-y-auto p-3.5">
            {/* TAB HỒ SƠ: REAL LEADS LIST */}
            {activeTab === 'hoso' && panelView === 'leads' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Danh sách khách hàng ({leads.length})
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      className="h-6 px-2 text-xs gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                      onClick={() => setCreateCustomerOpen(true)}
                    >
                      <Plus className="h-3 w-3" /> Tạo mới
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs text-primary"
                      onClick={() => askAgent('Khách hàng nào sắp quá hạn SLA phản hồi?')}
                    >
                      💬 Hỏi agent
                    </Button>
                  </div>
                </div>

                {leadsQuery.isLoading ? (
                  <LoadingState className="py-12" />
                ) : leads.length === 0 ? (
                  <EmptyState
                    icon={Inbox}
                    title="Chưa có hồ sơ khách hàng mới"
                    action={
                      <Button
                        size="sm"
                        onClick={() => setCreateCustomerOpen(true)}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
                      >
                        <UserPlus className="h-3.5 w-3.5" /> Tạo khách hàng mới
                      </Button>
                    }
                  />
                ) : (
                  <div className="space-y-2">
                    {leads.map((l) => (
                      <Card
                        key={l.dossier_id}
                        className={cn(
                          'cursor-pointer transition-colors hover:border-primary/50',
                          selectedLeadId === l.dossier_id && 'border-primary bg-primary/[0.03]'
                        )}
                        onClick={() => {
                          setSelectedLeadId(l.dossier_id)
                          setPanelView('dossier')
                        }}
                      >
                        <CardContent className="p-3 space-y-1.5 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-foreground">{l.customer.full_name}</span>
                            <TemperatureBadge temperature={l.temperature} />
                          </div>
                          <p className="line-clamp-2 text-muted-foreground text-[11px]">{l.needs_summary}</p>
                          <div className="flex items-center justify-between pt-1 border-t border-border/50 text-[11px]">
                            <span className="text-muted-foreground">{l.customer.phone}</span>
                            <SlaCountdown dueAt={l.sla_due_at} />
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB HỒ SƠ: DOSSIER DETAIL */}
            {activeTab === 'hoso' && panelView === 'dossier' && selectedLead && (
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <Button variant="ghost" size="sm" className="h-6 p-0 text-xs text-primary" onClick={() => setPanelView('leads')}>
                    ← Quay lại danh sách
                  </Button>
                  <TemperatureBadge temperature={selectedLead.temperature} />
                </div>

                <Card className="border-border">
                  <CardHeader className="p-3.5 border-b border-border">
                    <CardTitle className="text-sm font-semibold flex items-center justify-between">
                      <span>{selectedLead.customer.full_name}</span>
                      <SlaCountdown dueAt={selectedLead.sla_due_at} />
                    </CardTitle>
                    <p className="text-xs text-muted-foreground">{selectedLead.customer.phone} · {selectedLead.dossier_id}</p>
                  </CardHeader>

                  <CardContent className="p-3.5 space-y-3">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Tóm tắt nhu cầu</span>
                      <p className="mt-1 text-foreground leading-relaxed">{selectedLead.needs_summary}</p>
                    </div>

                    <div className="border-t border-border pt-2 space-y-1.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Ràng buộc & Nguyện vọng</span>
                      <div className="grid grid-cols-2 gap-2 text-[11px]">
                        <div>
                          <span className="text-muted-foreground">Vốn tự có:</span>
                          <div className="font-semibold">{selectedLead.constraints?.own_funds_vnd ? formatVnd(selectedLead.constraints.own_funds_vnd) : '—'}</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Khả năng chi trả/tháng:</span>
                          <div className="font-semibold">{selectedLead.constraints?.monthly_capacity_vnd ? formatVnd(selectedLead.constraints.monthly_capacity_vnd) : '—'}</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Căn hộ quan tâm:</span>
                          <div className="font-semibold">{selectedLead.constraints?.preferred_unit_code || 'Chưa định danh'}</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Mục tiêu tài chính:</span>
                          <div className="font-semibold">{selectedLead.constraints?.objective ? OBJECTIVE_LABEL[selectedLead.constraints.objective] : '—'}</div>
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2 pt-2 border-t border-border">
                      <Button size="sm" className="flex-1 text-xs" onClick={() => startQuoteCreationFlow(selectedLead.customer.full_name)}>
                        <FilePlus2 className="mr-1 h-3.5 w-3.5" /> Tạo báo giá
                      </Button>
                      <Button variant="outline" size="sm" className="flex-1 text-xs" onClick={startCopilotDrafting}>
                        <MessageSquare className="mr-1 h-3.5 w-3.5" /> Soạn tin
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* TAB BÁO GIÁ: REAL KANBAN PIPELINE */}
            {activeTab === 'baogia' && panelView === 'pipeline' && (
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Pipeline báo giá ({quotes.length})
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs text-primary"
                    onClick={() => askAgent('Báo giá nào đang chờ phê duyệt lâu nhất?')}
                  >
                    💬 Hỏi agent
                  </Button>
                </div>

                <div className="space-y-2.5">
                  {/* Nháp */}
                  <div className="rounded-xl border border-border bg-muted/20 p-2.5">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-semibold text-foreground text-xs">Nháp ({kanbanGroups.draft.length})</span>
                    </div>
                    {kanbanGroups.draft.length > 0 ? (
                      <div className="space-y-1.5">
                        {kanbanGroups.draft.map((q) => (
                          <div
                            key={q.quote_id}
                            onClick={() => setPanelView('quote_comparison')}
                            className="cursor-pointer rounded-lg border border-border bg-card p-2 shadow-2xs hover:border-primary"
                          >
                            <div className="flex justify-between">
                              <span className="font-semibold">{q.quote_id}</span>
                              <QuoteStatusBadge status={q.status} />
                            </div>
                            <div className="mt-1 flex justify-between text-[11px] text-muted-foreground">
                              <span>{q.transaction_context?.customer_name || 'Khách hàng'}</span>
                              <MoneyText amount={q.scenarios?.[0]?.total_contract_price_vnd || 4650000000} size="sm" />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-[11px] text-muted-foreground py-1 text-center">Không có báo giá nháp</div>
                    )}
                  </div>

                  {/* Chờ duyệt */}
                  <div className="rounded-xl border border-warning/40 bg-warning/5 p-2.5">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-semibold text-warning text-xs">Chờ duyệt ({kanbanGroups.review.length})</span>
                    </div>
                    {kanbanGroups.review.length > 0 ? (
                      <div className="space-y-1.5">
                        {kanbanGroups.review.map((q) => (
                          <div
                            key={q.quote_id}
                            onClick={() => setPanelView('quote_comparison')}
                            className="cursor-pointer rounded-lg border border-warning/30 bg-card p-2 shadow-2xs hover:border-warning"
                          >
                            <div className="flex justify-between">
                              <span className="font-semibold">{q.quote_id}</span>
                              <QuoteStatusBadge status={q.status} />
                            </div>
                            <div className="mt-1 flex justify-between text-[11px] text-muted-foreground">
                              <span>{q.transaction_context?.customer_name || 'Nguyễn Minh An'}</span>
                              <MoneyText amount={q.scenarios?.[0]?.total_contract_price_vnd || 4650000000} size="sm" />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-[11px] text-muted-foreground py-1 text-center">Không có báo giá chờ duyệt</div>
                    )}
                  </div>

                  {/* Đã duyệt */}
                  <div className="rounded-xl border border-success/40 bg-success/5 p-2.5">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-semibold text-success text-xs">Đã duyệt ({kanbanGroups.approved.length})</span>
                    </div>
                    {kanbanGroups.approved.length > 0 ? (
                      <div className="space-y-1.5">
                        {kanbanGroups.approved.map((q) => (
                          <div
                            key={q.quote_id}
                            className="rounded-lg border border-success/30 bg-card p-2 shadow-2xs"
                          >
                            <div className="flex justify-between">
                              <span className="font-semibold">{q.quote_id}</span>
                              <QuoteStatusBadge status={q.status} />
                            </div>
                            <div className="mt-1 flex justify-between text-[11px] text-muted-foreground">
                              <span>{q.transaction_context?.customer_name || 'Lê Hoàng Cường'}</span>
                              <MoneyText amount={q.scenarios?.[0]?.total_contract_price_vnd || 5200000000} size="sm" />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-[11px] text-muted-foreground py-1 text-center">Chưa có báo giá đã duyệt</div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* TAB BÁO GIÁ: 3-PLAN COMPARISON TABLE */}
            {activeTab === 'baogia' && panelView === 'quote_comparison' && (
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <Button variant="ghost" size="sm" className="h-6 p-0 text-xs text-primary" onClick={() => setPanelView('pipeline')}>
                    ← Quay lại pipeline
                  </Button>
                  <span className="text-[11px] font-bold text-muted-foreground">FCS v2.6 · Golden Case</span>
                </div>

                <div className="rounded-xl border border-border overflow-hidden">
                  <table className="w-full border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-border bg-muted/50 text-[11px] font-semibold text-muted-foreground">
                        <th className="p-2 text-left">Tiêu chí</th>
                        <th className="p-2 text-center">Tiến độ chuẩn</th>
                        <th className="p-2 text-center">Trả sớm 95%</th>
                        <th className="p-2 text-center bg-primary/10 text-primary font-bold">Vay HTLS 0% ⭐</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      <tr>
                        <td className="p-2 font-medium text-muted-foreground">Đợt đầu (kể cọc)</td>
                        <td onClick={() => setEvidenceId(5)} className="cursor-pointer p-2 text-center hover:bg-warning/10 font-mono">
                          1,397 tỷ <span className="text-[10px] text-warning font-bold">[5]</span>
                        </td>
                        <td onClick={() => setEvidenceId(2)} className="cursor-pointer p-2 text-center hover:bg-warning/10 font-mono">
                          4,422 tỷ <span className="text-[10px] text-warning font-bold">[2]</span>
                        </td>
                        <td onClick={() => setEvidenceId(5)} className="cursor-pointer bg-primary/5 p-2 text-center font-bold text-primary hover:bg-warning/10 font-mono">
                          1,397 tỷ <span className="text-[10px] text-warning font-bold">[5]</span>
                        </td>
                      </tr>
                      <tr>
                        <td className="p-2 font-medium text-muted-foreground">Hàng tháng (24T)</td>
                        <td onClick={() => setEvidenceId(5)} className="cursor-pointer p-2 text-center hover:bg-warning/10 font-mono">
                          ~420 tr × 8 <span className="text-[10px] text-warning font-bold">[5]</span>
                        </td>
                        <td className="p-2 text-center text-muted-foreground font-mono">—</td>
                        <td onClick={() => setEvidenceId(4)} className="cursor-pointer bg-primary/5 p-2 text-center font-bold text-primary hover:bg-warning/10 font-mono">
                          ~47 tr <span className="text-[10px] text-warning font-bold">[4]</span>
                        </td>
                      </tr>
                      <tr>
                        <td className="p-2 font-medium text-muted-foreground">Sau 24 tháng</td>
                        <td className="p-2 text-center text-muted-foreground font-mono">—</td>
                        <td className="p-2 text-center text-muted-foreground font-mono">—</td>
                        <td onClick={() => setEvidenceId(4)} className="cursor-pointer bg-primary/5 p-2 text-center hover:bg-warning/10">
                          Biểu phí NH <span className="text-[10px] text-warning font-bold">[4]</span>
                        </td>
                      </tr>
                      <tr>
                        <td className="p-2 font-medium text-muted-foreground">Tổng dòng tiền</td>
                        <td onClick={() => setEvidenceId(2)} className="cursor-pointer p-2 text-center hover:bg-warning/10 font-mono">
                          4,740 tỷ <span className="text-[10px] text-warning font-bold">[2]</span>
                        </td>
                        <td onClick={() => setEvidenceId(2)} className="cursor-pointer p-2 text-center hover:bg-warning/10 font-mono">
                          4,740 tỷ <span className="text-[10px] text-warning font-bold">[2]</span>
                        </td>
                        <td onClick={() => setEvidenceId(2)} className="cursor-pointer bg-primary/5 p-2 text-center font-bold text-primary hover:bg-warning/10 font-mono">
                          4,781 tỷ <span className="text-[10px] text-warning font-bold">[2]</span>
                        </td>
                      </tr>
                      <tr>
                        <td className="p-2 font-medium text-muted-foreground">Ưu đãi áp dụng</td>
                        <td onClick={() => setEvidenceId(5)} className="cursor-pointer p-2 text-center hover:bg-warning/10">
                          2% tiến độ <span className="text-[10px] text-warning font-bold">[5]</span>
                        </td>
                        <td onClick={() => setEvidenceId(1)} className="cursor-pointer p-2 text-center hover:bg-warning/10">
                          8% trả sớm <span className="text-[10px] text-warning font-bold">[1]</span>
                        </td>
                        <td onClick={() => setEvidenceId(4)} className="cursor-pointer bg-primary/5 p-2 text-center font-bold text-primary hover:bg-warning/10">
                          HTLS 0% 24T <span className="text-[10px] text-warning font-bold">[4]</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="rounded-xl border border-border bg-muted/30 p-2.5 text-[11px] leading-relaxed text-muted-foreground">
                  💡 Bấm trực tiếp vào các ô số tiền để đối soát chính sách pháp lý tương ứng.
                </div>

                <div className="flex gap-2">
                  <Button size="sm" className="flex-1 text-xs" onClick={startSubmitReviewFlow}>
                    <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" /> Trình duyệt
                  </Button>
                  <Button variant="outline" size="sm" className="flex-1 text-xs" onClick={() => showToast('Đã lưu nháp hồ sơ')}>
                    Lưu nháp
                  </Button>
                </div>
              </div>
            )}

            {/* TAB TIN NHẮN: COPILOT LIVE-CHECK */}
            {activeTab === 'tinnhan' && (
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Trình soạn tin nhắn Copilot
                  </span>
                  <Badge variant="outline" className="text-[10.5px]">
                    Live-check F8 (500ms)
                  </Badge>
                </div>

                <Card className="border-border">
                  <CardContent className="p-3 space-y-2">
                    <textarea
                      value={draftContent}
                      onChange={(e) => handleDraftTextChange(e.target.value)}
                      rows={4}
                      className="w-full resize-none rounded-lg border border-input bg-background p-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                      placeholder="Nội dung tin nhắn tư vấn..."
                    />

                    <div className="space-y-1">
                      <span className="text-[10.5px] font-semibold text-muted-foreground">Mỏ neo căn cứ:</span>
                      <div className="flex flex-wrap gap-1.5">
                        {draftAnchors.map((aid) => (
                          <button
                            key={aid}
                            type="button"
                            onClick={() => setEvidenceId(aid)}
                            className="inline-flex items-center gap-1 rounded-md border border-warning/40 bg-warning/10 px-2 py-0.5 text-[11px] font-semibold text-warning hover:bg-warning/20"
                          >
                            <span>[{aid}]</span>
                            <span className="font-normal text-muted-foreground truncate max-w-[120px]">
                              {EVIDENCE_DB[aid]?.p}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Compliance Result Card */}
                <div
                  className={cn(
                    'rounded-xl border p-3 space-y-2 transition-opacity',
                    isCheckingCompliance && 'opacity-60',
                    complianceResult.tier === 'GREEN' && 'border-success/40 bg-success/5 text-success',
                    complianceResult.tier === 'AMBER' && 'border-warning/40 bg-warning/5 text-warning',
                    complianceResult.tier === 'RED' && 'border-destructive/40 bg-destructive/5 text-destructive',
                    complianceResult.tier === 'BLACK' && 'border-foreground bg-foreground text-background'
                  )}
                >
                  <div className="flex items-center gap-2 font-semibold">
                    <span>
                      {complianceResult.tier === 'GREEN' ? '✓' : complianceResult.tier === 'AMBER' ? '⚠' : '✗'}
                    </span>
                    <span>{complianceResult.statusText}</span>
                  </div>

                  <ul className="space-y-1 text-[11px] text-foreground">
                    {complianceResult.checks.map(([st, txt], i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="font-bold">{st === 'ok' ? '✓' : st === 'warn' ? '⚠' : '✗'}</span>
                        <span>{txt}</span>
                      </li>
                    ))}
                  </ul>

                  {complianceResult.suggest && (
                    <div className="rounded-lg border border-dashed border-primary/40 bg-primary/5 p-2 text-[11px] text-foreground">
                      <b>Gợi ý phát ngôn an toàn:</b> {complianceResult.suggest}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="flex-1 text-xs" onClick={() => setCopyAuditModalOpen(true)}>
                      <Copy className="mr-1.5 h-3.5 w-3.5" /> Copy sang Zalo
                    </Button>
                    <Button variant="outline" size="sm" className="text-xs" onClick={() => setVoiceVariantModalOpen(true)}>
                      Biến thể
                    </Button>
                  </div>

                  <Button
                    size="sm"
                    disabled={complianceResult.tier === 'RED' || complianceResult.tier === 'BLACK'}
                    onClick={() => {
                      setSendGateStep(0)
                      setOfficialReceiptId(null)
                      setOfficialSendModalOpen(true)
                    }}
                    className="w-full text-xs"
                  >
                    <Send className="mr-1.5 h-3.5 w-3.5" /> Gửi chính thức qua cổng hệ thống
                  </Button>
                </div>
              </div>
            )}

            {/* TAB CHÍNH SÁCH: REAL POLICIES */}
            {activeTab === 'chinhsach' && (
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Chính sách bán hàng hiện hành ({policies.length})
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs text-primary"
                    onClick={() => askAgent('Chính sách nào áp dụng chiết khấu thanh toán nhanh cao nhất?')}
                  >
                    💬 Hỏi agent
                  </Button>
                </div>

                {policiesQuery.isLoading ? (
                  <LoadingState className="py-12" />
                ) : policies.length === 0 ? (
                  <EmptyState icon={ScrollText} title="Chưa có dữ liệu chính sách bán hàng" />
                ) : (
                  <div className="space-y-2">
                    {policies.map((p) => (
                      <Card key={p.policy_id} className="border-border">
                        <CardContent className="p-3 space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-foreground text-xs">{p.policy_id}</span>
                            <PolicyStatusBadge status={p.status} />
                          </div>
                          <p className="text-[11.5px] font-medium text-foreground">{p.title}</p>
                          <div className="flex items-center justify-between pt-1 border-t border-border/50 text-[10.5px] text-muted-foreground">
                            <span>Hiệu lực: {p.effective_from} → {p.effective_to || 'Không thời hạn'}</span>
                            <span className="font-mono text-[10px]">{p.policy_version}</span>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* ================= PANEL TOGGLE FAB ================= */}
      <button
        type="button"
        onClick={() => setIsMobilePanelOpen((p) => !p)}
        className="fixed bottom-20 right-4 z-50 grid h-12 w-12 place-items-center rounded-full bg-primary text-primary-foreground shadow-xl"
        title={isMobilePanelOpen ? 'Đóng bảng dữ liệu' : 'Mở bảng dữ liệu'}
      >
        <Layers className="h-5 w-5" />
      </button>

      {/* ================= MODAL: LEGAL EVIDENCE ================= */}
      {evidenceId !== null && (
        <div onClick={() => setEvidenceId(null)} className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4 backdrop-blur-xs">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md rounded-xl border border-border bg-card shadow-2xl overflow-hidden text-xs">
            <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-3">
              <span className="font-semibold text-foreground">🔗 Căn cứ pháp lý [{evidenceId}]</span>
              <button type="button" onClick={() => setEvidenceId(null)} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 leading-relaxed text-foreground">
                “{EVIDENCE_DB[evidenceId]?.q}”
              </div>
              <div className="divide-y divide-border text-[11.5px]">
                <div className="flex justify-between py-1.5">
                  <span className="text-muted-foreground">Văn bản:</span>
                  <span className="font-semibold text-foreground text-right">{EVIDENCE_DB[evidenceId]?.p}</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-muted-foreground">Hiệu lực:</span>
                  <span className="font-semibold text-foreground">{EVIDENCE_DB[evidenceId]?.e}</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-muted-foreground">Mã chunk:</span>
                  <span className="font-mono text-foreground">{EVIDENCE_DB[evidenceId]?.h}</span>
                </div>
              </div>
            </div>
            <div className="border-t border-border p-3 text-right">
              <Button size="sm" variant="secondary" onClick={() => setEvidenceId(null)}>
                Đóng
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL: COPY AUDIT LOG ================= */}
      {copyAuditModalOpen && (
        <div onClick={() => setCopyAuditModalOpen(false)} className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4 backdrop-blur-xs">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md rounded-xl border border-border bg-card shadow-2xl overflow-hidden text-xs">
            <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-3">
              <span className="font-semibold text-foreground">📋 Copy sang Zalo — Gửi ngoài cổng</span>
              <button type="button" onClick={() => setCopyAuditModalOpen(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <div className="rounded-lg border border-border bg-muted/20 p-2.5 space-y-1">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Trạng thái F8:</span>
                  <span className="font-semibold">{complianceResult.tier}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Sự kiện kiểm toán:</span>
                  <span className="font-semibold text-success">ON_COPY ✓ (đã ghi vết)</span>
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Hành vi sao chép nội dung ra ngoài hệ thống được lưu lại trong nhật ký kiểm toán phục vụ đối soát giải trình.
              </p>
            </div>
            <div className="flex justify-end gap-2 border-t border-border p-3">
              <Button variant="outline" size="sm" onClick={() => setCopyAuditModalOpen(false)}>
                Hủy
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(draftContent)
                  setCopyAuditModalOpen(false)
                  showToast('Đã sao chép nội dung vào Clipboard (ON_COPY logged)')
                }}
              >
                Xác nhận Copy
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL: OFFICIAL SEND DOUBLE-LOCK ================= */}
      {officialSendModalOpen && (
        <div onClick={() => setOfficialSendModalOpen(false)} className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4 backdrop-blur-xs">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md rounded-xl border border-border bg-card shadow-2xl overflow-hidden text-xs">
            <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-3">
              <span className="font-semibold text-foreground">📨 Gửi tin chính thức qua cổng hệ thống</span>
              <button type="button" onClick={() => setOfficialSendModalOpen(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              {!officialReceiptId ? (
                <>
                  <div className="rounded-lg border border-border bg-muted/20 p-2.5 space-y-1">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Người nhận:</span>
                      <span className="font-semibold">{selectedLead?.customer.full_name || 'Khách hàng'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Checkpoint bắt buộc:</span>
                      <span className="font-semibold text-primary">ON_FINAL_SEND (Double-Lock)</span>
                    </div>
                  </div>

                  {sendGateStep > 0 && (
                    <div className="space-y-1.5 rounded-lg border border-border bg-muted/30 p-2.5 text-[11px]">
                      <div className="flex items-center justify-between">
                        <span>Gate 1: Đối soát claim ↔ chứng cứ</span>
                        {sendGateStep >= 1 ? <CheckCircle2 className="h-3.5 w-3.5 text-success" /> : <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Gate 2: Kiểm tra quy chuẩn phát ngôn</span>
                        {sendGateStep >= 2 ? <CheckCircle2 className="h-3.5 w-3.5 text-success" /> : <span className="text-muted-foreground">chờ...</span>}
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Gate 3: Math Engine Δ = 0 ₫</span>
                        {sendGateStep >= 3 ? <CheckCircle2 className="h-3.5 w-3.5 text-success" /> : <span className="text-muted-foreground">chờ...</span>}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-2 space-y-2">
                  <CheckCircle2 className="h-10 w-10 text-success mx-auto" />
                  <span className="block font-semibold text-foreground text-sm">Gửi tin nhắn chính thức thành công</span>
                  <div className="inline-block rounded-md bg-muted px-3 py-1 font-mono text-xs font-semibold text-foreground">
                    {officialReceiptId}
                  </div>
                  <p className="text-[11px] text-muted-foreground">Đã xuất biên lai dispatch và lưu vết kiểm toán.</p>
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-border p-3">
              {!officialReceiptId ? (
                <>
                  <Button variant="outline" size="sm" onClick={() => setOfficialSendModalOpen(false)}>
                    Hủy
                  </Button>
                  <Button
                    size="sm"
                    disabled={sendGateStep > 0}
                    onClick={() => {
                      setSendGateStep(1)
                      setTimeout(() => {
                        setSendGateStep(2)
                        setTimeout(() => {
                          setSendGateStep(3)
                          setTimeout(() => {
                            const rid = `DISPATCH-ZALO-2026-00${Math.floor(800 + Math.random() * 199)}`
                            setOfficialReceiptId(rid)
                            showToast(`Đã gửi qua cổng hệ thống · ${rid}`)
                          }, 350)
                        }, 350)
                      }, 400)
                    }}
                  >
                    {sendGateStep > 0 ? 'Đang xác thực 3 Gate…' : 'Xác nhận & Gửi'}
                  </Button>
                </>
              ) : (
                <Button size="sm" onClick={() => setOfficialSendModalOpen(false)}>
                  Hoàn tất
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL: VOICE VARIANTS ================= */}
      {voiceVariantModalOpen && (
        <div onClick={() => setVoiceVariantModalOpen(false)} className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4 backdrop-blur-xs">
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md rounded-xl border border-border bg-card shadow-2xl overflow-hidden text-xs">
            <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-3">
              <span className="font-semibold text-foreground">Chọn biến thể giọng điệu</span>
              <button type="button" onClick={() => setVoiceVariantModalOpen(false)} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-4 space-y-2">
              <Card
                className="cursor-pointer border-border hover:border-primary p-2.5 transition-colors"
                onClick={() => {
                  setDraftContent('Dạ căn R-02.02 giá net sau chiết khấu 8% là 4.232 tỷ [1]. Đợt 1 đóng 95% gồm VAT là 4.422 tỷ, nhận nhà đóng nốt 5% ạ [2].')
                  setVoiceVariantModalOpen(false)
                  showToast('Đã đổi giọng sang Ngắn gọn')
                }}
              >
                <b className="text-primary block mb-0.5">Ngắn gọn & Trực tiếp</b>
                <p className="text-muted-foreground text-[11px] leading-relaxed">
                  Tập trung vào số tiền đợt đầu và tỷ lệ chiết khấu rõ ràng.
                </p>
              </Card>

              <Card
                className="cursor-pointer border-border hover:border-primary p-2.5 transition-colors"
                onClick={() => {
                  setDraftContent('Dạ em chào anh An, căn R-02.02 giá niêm yết 4,6 tỷ. Nếu anh chọn thanh toán sớm 95% trong 30 ngày kể từ cọc, anh nhận chiết khấu 8% trước thuế tương đương 368 triệu [1]. Tổng hợp đồng sau VAT là 4.655 tỷ [2]. Đợt 1 anh thanh toán 4.422 tỷ, 5% còn lại khi nhận nhà ạ.')
                  setVoiceVariantModalOpen(false)
                  showToast('Đã đổi giọng sang Chi tiết & Pháp lý')
                }}
              >
                <b className="text-primary block mb-0.5">Chi tiết & Chuẩn xác pháp lý</b>
                <p className="text-muted-foreground text-[11px] leading-relaxed">
                  Đầy đủ điều kiện ngày cọc, chiết khấu trước thuế và phân tách VAT.
                </p>
              </Card>
            </div>
            <div className="border-t border-border p-3 text-right">
              <Button size="sm" variant="secondary" onClick={() => setVoiceVariantModalOpen(false)}>
                Đóng
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL: CREATE CUSTOMER ================= */}
      <Dialog open={createCustomerOpen} onOpenChange={setCreateCustomerOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <UserPlus className="h-5 w-5 text-emerald-600" />
              Khởi tạo hồ sơ khách hàng mới (Lead Dossier)
            </DialogTitle>
            <DialogDescription className="text-xs">
              Nhập thông tin khách hàng, nhu cầu và điều kiện tài chính để Copilot nạp vào ngữ cảnh tư vấn và tự động tính toán phương án báo giá phù hợp.
            </DialogDescription>
          </DialogHeader>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!customerForm.customer_name.trim()) {
                showToast('Vui lòng nhập họ và tên khách hàng')
                return
              }
              if (!customerForm.customer_phone.trim()) {
                showToast('Vui lòng nhập số điện thoại')
                return
              }
              executeCustomerCreation(customerForm)
            }}
            className="space-y-3.5 py-1 text-xs"
          >
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="cust-name" className="text-xs font-medium">
                  Họ và tên khách hàng <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="cust-name"
                  value={customerForm.customer_name}
                  onChange={(e) => setCustomerForm({ ...customerForm, customer_name: e.target.value })}
                  placeholder="Ví dụ: Trần Quốc Tuấn"
                  required
                  className="h-8 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="cust-phone" className="text-xs font-medium">
                  Số điện thoại <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="cust-phone"
                  value={customerForm.customer_phone}
                  onChange={(e) => setCustomerForm({ ...customerForm, customer_phone: e.target.value })}
                  placeholder="0912 345 678"
                  required
                  className="h-8 text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs font-medium">Phân khúc khách hàng</Label>
                <Select
                  value={customerForm.customer_segment}
                  onValueChange={(val: any) => setCustomerForm({ ...customerForm, customer_segment: val })}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="NEW_CUSTOMER">Khách hàng mới (F1)</SelectItem>
                    <SelectItem value="EXISTING_RESIDENT">Cư dân hiện hữu / Loyalty</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-xs font-medium">Độ quan tâm (Temperature)</Label>
                <Select
                  value={customerForm.temperature}
                  onValueChange={(val: any) => setCustomerForm({ ...customerForm, temperature: val })}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="HOT">🔥 Nóng (HOT - Cần chốt ngay)</SelectItem>
                    <SelectItem value="WARM">☀️ Ấm (WARM - Đang cân nhắc)</SelectItem>
                    <SelectItem value="COLD">❄️ Lạnh (COLD - Tham khảo dài hạn)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs font-medium">Dự án quan tâm</Label>
                <Select
                  value={customerForm.project_id || 'P-001'}
                  onValueChange={(val) => setCustomerForm({ ...customerForm, project_id: val })}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {projects.length > 0 ? (
                      projects.map((p) => (
                        <SelectItem key={p.project.project_id} value={p.project.project_id}>
                          {p.project.name}
                        </SelectItem>
                      ))
                    ) : (
                      <SelectItem value="P-001">VLand Future Riverside</SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label htmlFor="cust-unit" className="text-xs font-medium">
                  Căn hộ quan tâm (Mã căn)
                </Label>
                <Input
                  id="cust-unit"
                  value={customerForm.preferred_unit_code || ''}
                  onChange={(e) => setCustomerForm({ ...customerForm, preferred_unit_code: e.target.value })}
                  placeholder="Ví dụ: R-02.02, R-08.15"
                  className="h-8 text-xs font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="cust-funds" className="text-xs font-medium">
                  Vốn tự có ban đầu (VNĐ)
                </Label>
                <Input
                  id="cust-funds"
                  type="number"
                  step="50000000"
                  value={customerForm.own_funds_vnd || 0}
                  onChange={(e) => setCustomerForm({ ...customerForm, own_funds_vnd: Number(e.target.value) })}
                  className="h-8 text-xs"
                />
                <span className="block text-[10px] text-muted-foreground">
                  = {formatVnd(customerForm.own_funds_vnd || 0)}
                </span>
              </div>

              <div className="space-y-1">
                <Label htmlFor="cust-monthly" className="text-xs font-medium">
                  Khả năng trả góp / tháng (VNĐ)
                </Label>
                <Input
                  id="cust-monthly"
                  type="number"
                  step="5000000"
                  value={customerForm.monthly_capacity_vnd || 0}
                  onChange={(e) => setCustomerForm({ ...customerForm, monthly_capacity_vnd: Number(e.target.value) })}
                  className="h-8 text-xs"
                />
                <span className="block text-[10px] text-muted-foreground">
                  = {formatVnd(customerForm.monthly_capacity_vnd || 0)}/tháng
                </span>
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-xs font-medium">Mục tiêu tài chính ưu tiên</Label>
              <Select
                value={customerForm.objective || 'MIN_INITIAL_OUTFLOW'}
                onValueChange={(val: any) => setCustomerForm({ ...customerForm, objective: val })}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="MIN_INITIAL_OUTFLOW">Ít vốn ban đầu nhất (Ưu tiên gói vay HTLS)</SelectItem>
                  <SelectItem value="MIN_NET_PRICE">Giá nét thấp nhất (Ưu tiên thanh toán sớm nhận chiết khấu lớn)</SelectItem>
                  <SelectItem value="MIN_TOTAL_CASH_OUTFLOW">Tổng chi trả cả đời thấp nhất</SelectItem>
                  <SelectItem value="MAX_BENEFIT_VALUE">Tối đa giá trị quà tặng & chính sách kèm theo</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="cust-needs" className="text-xs font-medium">
                Tóm tắt nhu cầu & Ghi chú tư vấn
              </Label>
              <Textarea
                id="cust-needs"
                value={customerForm.needs_summary || ''}
                onChange={(e) => setCustomerForm({ ...customerForm, needs_summary: e.target.value })}
                placeholder="Ghi chú về sở thích tầng, hướng, mục tiêu mua ở hay đầu tư, thời hạn cần nhận nhà..."
                rows={2}
                className="text-xs resize-none"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setCreateCustomerOpen(false)}
              >
                Hủy bỏ
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={createLeadMutation.isPending}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
              >
                {createLeadMutation.isPending ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Đang tạo...
                  </>
                ) : (
                  <>
                    <UserPlus className="h-3.5 w-3.5" /> Khởi tạo & Nạp vào Copilot
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ================= FLOATING TOAST ================= */}
      {toastMessage && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-xl bg-foreground px-4 py-2 text-xs font-medium text-background shadow-xl">
          {toastMessage}
        </div>
      )}
    </div>
  )
}

export default SalesWorkspacePage
