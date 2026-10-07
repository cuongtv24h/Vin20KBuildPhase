import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
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
  ThumbsDown,
  ThumbsUp,
  Copy,
  Clock,
  ShieldCheck,
  Sparkles,
  Layers,
  RefreshCw,
  X,
  Search,
  ChevronRight,
  History,
  Volume2,
  Square,
  Mic,
  MicOff,
  PanelLeftClose,
  PanelLeftOpen,
  Trash2,
} from 'lucide-react'

// Hooks & Store
import { useQueryClient } from '@tanstack/react-query'
import { useSessionStore } from '@/auth/sessionStore'
import { api } from '@pricepolicy/api-client/client'
import {
  useLeads,
  useCreateLead,
  useQuotes,
  usePolicies,
  useProjectOverviews,
  useUnits,
  useCopilotTurn,
  useCopilotConversations,
  useCopilotConversation,
  useAppendCopilotTurnSync,
  useCreateCopilotConversation,
  useDeleteCopilotConversation,
  useTtsSettings,
  useTtsSpeak,
  useUpdateTtsSettings,
  useTtsVoiceFeedback,
} from '@pricepolicy/api-client/hooks'
import { turnToAppendPayload } from '@pricepolicy/api-client/copilotHistory'
import type {
  LeadDossier,
  LeadCreatePayload,
  CopilotCitation,
  CopilotAnchor,
  CopilotConversationMessage,
  CopilotFinalPayload,
  CopilotReasoningStep,
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
} from '@pricepolicy/ui/components/common/StatusBadge'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { EmptyState, ErrorState, LoadingState, QueryState } from '@pricepolicy/ui/components/common/PageStates'
import { FormattedAiMessage } from '@pricepolicy/ui/components/common/FormattedAiMessage'
import { CitationChips, ReasoningTrace } from '@pricepolicy/ui/components/common/ReasoningTrace'
import { SlashCommandPalette } from '@pricepolicy/ui/components/common/SlashCommandPalette'
import {
  ACTIVE_CONVERSATION_STORAGE_KEY,
  copilotChatStore,
  useCopilotChatConversationId,
  useCopilotChatMessages,
} from '@pricepolicy/api-client/copilotChatState'
import { customerReadyText } from '@pricepolicy/api-client/copilotHistory'
import {
  SPEECH_TO_TEXT_UNSUPPORTED_MESSAGE,
  createSpeechToText,
  isSpeechToTextSupported,
  type SpeechToTextController,
} from '@pricepolicy/ui/lib/speech'
import { filterCommands, type SlashCommand } from '@pricepolicy/ui/lib/slashCommands'
import { CopilotContextChips } from '@pricepolicy/ui/components/common/CopilotContextChips'
import { formatVnd } from '@pricepolicy/ui/lib/format'
import { speakText, stopSpeaking, isSpeechSupported, listLocalVoices } from '@pricepolicy/ui/lib/speech'
import { OBJECTIVE_LABEL, PROJECT_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'
import {
  NO_UNIT_LABEL,
  extractUnitCodeFromText,
  resolveQuoteCustomerName,
  resolveQuoteUnitCode,
} from './quoteContext'

// --- EVIDENCE KNOWLEDGE BASE ---
interface LegalEvidence {
  q: string
  p: string
  e: string
  h: string
  /** Điều/khoản đầy đủ (nếu có) — hiển thị riêng để Sale đối chiếu nhanh. */
  clause?: string
  /** Hash tài liệu đầy đủ — dùng cho nút sao chép đối soát. */
  hash?: string
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

/** Tier backend (`TIER_4_BLACK`) hoặc mock (`BLACK`) → nhãn UI. */
function normalizeTier(raw: string | undefined | null): ComplianceCheckState['tier'] {
  const value = String(raw || '').toUpperCase()
  if (value.includes('BLACK')) return 'BLACK'
  if (value.includes('RED')) return 'RED'
  if (value.includes('YELLOW') || value.includes('AMBER')) return 'AMBER'
  if (value.includes('GREEN')) return 'GREEN'
  return 'AMBER'
}

const TIER_STATUS_TEXT: Record<ComplianceCheckState['tier'], string> = {
  GREEN: 'XANH — Phát ngôn đạt chuẩn (POL-08)',
  AMBER: 'VÀNG — Cần bổ sung khuyến cáo bắt buộc',
  RED: 'ĐỎ — Thiếu chứng cứ / Vượt khung chính sách',
  BLACK: 'ĐEN — Cấm phát ngôn (POL-08 Điều 1)',
}

/**
 * Chuyển kết quả `/compliance/check-message` (thật hoặc mock) thành state UI.
 * Tầng này cố tình chịu được cả hai shape đang tồn tại: backend trả `compliance_tier` +
 * `claims[{claim_text, tier, reason}]`, mock trả `overall_status` + `claims[{claim_type,...}]`.
 */
function mapComplianceResponse(res: any): ComplianceCheckState {
  const tier = normalizeTier(res?.compliance_tier ?? res?.tier ?? res?.overall_status)
  const claims: any[] = Array.isArray(res?.claims) ? res.claims : []
  const checks: [string, string][] = claims.length
    ? claims.map((c) => [
        c?.status && /BLOCK|NEEDS_APPROVAL|PROHIBITED|UNSUPPORTED/i.test(String(c.status)) ? 'bad' : 'ok',
        [c?.claim_text || c?.claim_type || 'Nội dung kiểm tra', c?.reason || c?.rule_id].filter(Boolean).join(' — '),
      ])
    : [['ok', 'Không phát hiện phát ngôn rủi ro trong bản nháp']]

  return {
    tier,
    statusText: TIER_STATUS_TEXT[tier],
    checks,
    suggest:
      res?.required_action && res.required_action !== 'NONE'
        ? `Hành động cần làm: ${res.required_action}`
        : tier === 'BLACK' || tier === 'RED'
        ? 'Sửa lại câu chữ trước khi gửi: bỏ cam kết vượt thẩm quyền và bổ sung mỏ neo chứng cứ [n].'
        : undefined,
  }
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
  | 'reasoning'

const storedConversationId = () => {
  try {
    return window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)
  } catch {
    return null
  }
}

const rememberConversationId = (conversationId: string | null) => {
  try {
    if (conversationId) window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, conversationId)
    else window.localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY)
  } catch {
    /* chế độ riêng tư: bỏ qua */
  }
}

/** Giờ:phút của một mốc ISO — lịch sử lưu ISO, khung chat hiển thị HH:MM. */
const clockOf = (iso?: string | null) => {
  if (!iso) return new Date().toTimeString().slice(0, 5)
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? new Date().toTimeString().slice(0, 5) : d.toTimeString().slice(0, 5)
}

/**
 * Nhãn mốc thời gian dữ liệu `[Dữ liệu cập nhật: DD/MM/YYYY HH:mm]` (chốt P1.6).
 *
 * Hiển thị ở chrome của giao diện (không nằm trong câu trả lời) nên Sale copy nội dung gửi khách
 * không bị dính mốc kỹ thuật.
 */
const dataAsOfLabel = (iso: string): string => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * Dựng lại khung chat từ hội thoại đã lưu. Chỉ tái hiện phần "văn bản" (câu hỏi + câu trả lời kèm
 * trích dẫn) — các thẻ tương tác một lần (confirm/stepper/receipt) không lưu vào lịch sử nên không
 * dựng lại, tránh nút bấm trỏ tới trạng thái đã chết sau khi tải lại trang.
 */
const chatItemsFromConversation = (items: CopilotConversationMessage[]): StreamItem[] =>
  items.map((m, idx) => ({
    id: `hist-${idx}-${m.at ?? ''}`,
    type: m.role === 'user' ? 'user' : 'agent',
    text: m.content,
    time: clockOf(m.at),
    data:
      m.role === 'assistant'
        ? {
            citations: m.citations ?? [],
            grounded: (m.citations ?? []).length > 0,
            mode: 'react',
            // Ba trường dưới đây phải được lưu cùng lượt, nếu không mở lại lịch sử là mất:
            // mỏ neo bấm mở căn cứ, cảnh báo kiểm duyệt, và mốc thời gian dữ liệu.
            anchors: m.anchors ?? [],
            internal_notes: m.internal_notes ?? '',
            data_as_of: m.data_as_of ?? null,
          }
        : undefined,
  }))

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
  // Chưa biết vốn tự có thì để TRỐNG, không điền sẵn một con số — trước đây mặc định 1,5 tỷ khiến thẻ
  // hiển thị một khoản tiền Sale chưa từng nêu (cùng lỗi với "căn hộ quan tâm" bịa mã căn).
  const [funds, setFunds] = useState<number>(initialData?.own_funds_vnd || initialData?.funds || 0)
  const [notes, setNotes] = useState(initialData?.needs_summary || '')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  // Dự án mặc định = dự án THẬT đầu tiên trong danh mục (trước đây ghi cứng `P-001` — mã dự án
  // không tồn tại trong DB, khiến hồ sơ khách gắn vào một dự án ma).
  const projectsQuery = useProjectOverviews()
  const defaultProjectId = initialData?.project_id || projectsQuery.data?.[0]?.project.project_id

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // Chốt đợt 20: KHÔNG tự điền số điện thoại/khả năng chi trả "cho đủ trường" — hồ sơ khách chỉ chứa
    // thông tin Sale thật sự cung cấp (trước đây tự thêm 0900000000 và 25 triệu/tháng).
    if (!name.trim()) {
      setError('Anh/chị nhập tên khách hàng giúp em.')
      return
    }
    if (!phone.trim()) {
      setError('Anh/chị nhập số điện thoại khách hàng giúp em (bắt buộc khi lưu CRM).')
      return
    }
    setError('')
    setIsSubmitting(true)
    try {
      await onSave({
        customer_name: name.trim(),
        customer_phone: phone.trim(),
        customer_segment: 'NEW_CUSTOMER',
        project_id: defaultProjectId,
        preferred_unit_code: unit.trim() || null,
        bedrooms: initialData?.bedrooms ?? null,
        own_funds_vnd: Number(funds) || null,
        monthly_capacity_vnd: initialData?.monthly_capacity_vnd ?? null,
        objective: initialData?.objective ?? null,
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
              placeholder="Mã căn có trong giỏ hàng (không bắt buộc)"
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
          {error && <span className="mr-auto text-[11px] font-medium text-destructive">{error}</span>}
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

  // Danh mục căn lấy từ giỏ hàng THẬT (`/units`) — trước đây là map cứng 4 căn R-02.02… không tồn tại
  // trong dữ liệu vận hành, Sale chọn xong lại ra một báo giá cho căn không có thật.
  const unitsQuery = useUnits()
  const availableUnits = useMemo(
    () =>
      (unitsQuery.data ?? [])
        .filter((u) => u.status === 'AVAILABLE')
        .slice()
        .sort((a, b) => a.listed_price_before_tax_vnd - b.listed_price_before_tax_vnd),
    [unitsQuery.data],
  )

  const selectedUnit = unitCode ? availableUnits.find((u) => u.unit_code === unitCode) || null : null
  const listPrice = selectedUnit?.listed_price_before_tax_vnd ?? 0
  const discountAmount = selectedUnit && scenario === 'PA-SOM' ? Math.round(listPrice * 0.08) : 0
  const finalEstimate = selectedUnit ? listPrice - discountAmount : 0

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
              {availableUnits.map((u) => (
                <option key={u.unit_code} value={u.unit_code}>
                  {u.unit_code} ({u.project_name}
                  {u.bedrooms > 0 ? ` · ${u.bedrooms}PN` : ''}
                  {u.area_m2 ? ` · ${u.area_m2}m²` : ''} · {formatVnd(u.listed_price_before_tax_vnd)})
                </option>
              ))}
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
              <span className="font-semibold text-foreground">{formatVnd(listPrice)}</span>
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

/** Nhãn trạng thái căn theo dữ liệu vận hành (không còn nhãn demo "GIỮ CHỖ 24H"). */
const UNIT_STATUS_LABEL: Record<string, { label: string; className: string }> = {
  AVAILABLE: { label: 'CÒN TRỐNG', className: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30' },
  RESERVED: { label: 'ĐANG GIỮ CHỖ', className: 'bg-amber-500/10 text-amber-600 border-amber-500/30' },
  SOLD: { label: 'ĐÃ BÁN', className: 'bg-slate-500/10 text-slate-600 border-slate-500/30' },
}

/**
 * Rổ hàng đọc trực tiếp từ API `/units` (DB vận hành + fixture của dự án DB chưa có).
 *
 * Trước đây card này hardcode 4 căn `R-02.02 / R-03.05 / R-05.01 / R-01.08` của dự án
 * "VLand Future Riverside" — căn và dự án không tồn tại trong dữ liệu vận hành, Sale bấm "Báo giá căn này"
 * là tạo báo giá cho căn không có thật. Nay: chỉ hiện căn có trong dữ liệu, tên dự án lấy từ dữ liệu,
 * và ghi rõ nguồn.
 */
function SmartUnitsCard({
  onSelectUnit,
}: {
  onSelectUnit: (unitCode: string) => void
}) {
  const unitsQuery = useUnits()
  const units = useMemo(
    () =>
      (unitsQuery.data ?? [])
        .filter((u) => u.status === 'AVAILABLE')
        .slice()
        .sort((a, b) => a.listed_price_before_tax_vnd - b.listed_price_before_tax_vnd)
        .slice(0, 6),
    [unitsQuery.data],
  )

  return (
    <Card className="w-full max-w-[98%] border-sky-500/40 bg-sky-500/[0.02] shadow-sm">
      <CardHeader className="bg-sky-500/10 px-4 py-2.5 border-b border-sky-500/20">
        <CardTitle className="text-xs font-semibold text-sky-900 dark:text-sky-300 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Home className="h-4 w-4 text-sky-600" />
            Rổ hàng căn hộ đang mở bán
          </span>
          <Badge variant="outline" className="text-[10px] border-sky-500/30 text-sky-700 dark:text-sky-400 bg-sky-500/10">
            {unitsQuery.isLoading ? 'Đang tải…' : `${units.length} căn còn trống`}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3 space-y-2 text-xs">
        {unitsQuery.isError && (
          <p className="text-[11px] text-destructive">
            Không tải được giỏ hàng — anh/chị thử lại sau hoặc hỏi Copilot "Tra cứu rổ hàng căn hộ".
          </p>
        )}
        {!unitsQuery.isLoading && !unitsQuery.isError && units.length === 0 && (
          <p className="text-[11px] text-muted-foreground">Dữ liệu vận hành chưa có căn nào đang mở bán.</p>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {units.map((u) => {
            const status = UNIT_STATUS_LABEL[u.status] ?? {
              label: u.status,
              className: 'bg-muted text-muted-foreground border-border',
            }
            return (
              <div
                key={u.unit_code}
                className="flex items-center justify-between rounded-lg border border-border bg-card p-2.5 hover:border-primary/50 transition-colors"
              >
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-foreground text-xs">{u.unit_code}</span>
                    <Badge variant="outline" className={cn('text-[9px]', status.className)}>{status.label}</Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground truncate">
                    {u.project_name}
                    {u.bedrooms > 0 ? ` · ${u.bedrooms}PN` : ''}
                    {u.floor ? ` · Tầng ${u.floor}` : ''}
                    {/* DB vận hành chưa lưu diện tích/hướng ⇒ hiện "—", không suy diễn từ loại căn. */}
                    {` · ${u.area_m2 ? `${u.area_m2} m²` : '—'}`}
                  </div>
                  <div className="font-semibold text-primary text-xs">{formatVnd(u.listed_price_before_tax_vnd)}</div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px] shrink-0 border-primary/30 text-primary hover:bg-primary hover:text-primary-foreground ml-2"
                  onClick={() => onSelectUnit(u.unit_code)}
                >
                  Báo giá căn này
                </Button>
              </div>
            )
          })}
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
  const navigate = useNavigate()

  // Real backend queries
  const leadsQuery = useLeads()
  const createLeadMutation = useCreateLead()
  const queryClient = useQueryClient()
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
    // Để rỗng: khi mở form, Select tự chọn dự án thật đầu tiên trong danh mục; lúc gửi sẽ chốt
    // đúng dự án đó thay vì ghi cứng một mã dự án không có trong DB.
    project_id: '',
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

  // Ngữ cảnh Copilot: chip cho Sale kiểm tra/sửa trước khi gửi (D2)
  const [copilotUnit, setCopilotUnit] = useState<string | null>(null)
  // Mã căn Sale gõ ngay trong ô chat (ví dụ "phương án thanh toán SAP-D-4201") phải trở thành ngữ cảnh
  // của phiên — trước đây chỉ hồ sơ khách mới đặt được ngữ cảnh, nên thẻ "Xác nhận tham số tạo báo giá"
  // vẫn báo "Chưa chọn căn" dù câu hỏi vừa nêu rõ mã căn.
  const noteUnitFromText = (text: string): string | null => {
    const code = extractUnitCodeFromText(text)
    if (code) setCopilotUnit(code)
    return code
  }
  const [copilotTxDate, setCopilotTxDate] = useState<string | null>('2026-09-26')
  // Lệnh gạch chéo dùng gần đây (D1) — lưu cục bộ, không gửi lên server
  const [recentCommands, setRecentCommands] = useState<string[]>(() => {
    try {
      const raw = window.localStorage.getItem('copilot.recentSlash')
      return raw ? (JSON.parse(raw) as string[]) : []
    } catch {
      return []
    }
  })
  // Câu bị lỗi để Sale bấm "Thử lại" (C4) — chạy lại đúng câu + đúng ngữ cảnh cũ
  const [failedTurn, setFailedTurn] = useState<{ text: string; context: Record<string, string | null> } | null>(null)

  // Artifact panel: mặc định thu gọn, chỉ mở khi có ngữ cảnh (KPI/hành động từ Copilot)
  const [isMobilePanelOpen, setIsMobilePanelOpen] = useState(false)

  useEffect(() => {
    const preferred = selectedLead?.constraints?.preferred_unit_code ?? null
    setCopilotUnit(preferred)
  }, [selectedLead?.dossier_id, selectedLead?.constraints?.preferred_unit_code])

  // Chat Stream State — nằm trong store ngoài component (xem `copilotChatState.ts`): đổi trang
  // sang Báo giá rồi quay lại vẫn còn nguyên hội thoại, F5 cũng không mất.
  const [messages, setMessages] = useCopilotChatMessages<StreamItem>()
  const [inputVal, setInputVal] = useState('')
  const [slashOpen, setSlashOpen] = useState(false)
  const [slashIndex, setSlashIndex] = useState(0)

  // Interactive 8s Undo Timer State
  const [undoSeconds, setUndoSeconds] = useState(8)
  const [undoActive, setUndoActive] = useState(false)
  const [undoQuoteCode, setUndoQuoteCode] = useState('Q-00092 V1')
  const [undoQuoteVersion, setUndoQuoteVersion] = useState(1)

  // Evidence Modal State
  const [evidenceId, setEvidenceId] = useState<number | null>(null)
  /** Căn cứ động do Copilot trả về (citation) — mở cùng modal với EVIDENCE_DB tĩnh. */
  const [evidenceDetail, setEvidenceDetail] = useState<LegalEvidence | null>(null)

  // Copilot ReAct stream: lịch sử rút gọn gửi kèm để LLM giữ mạch hội thoại
  const copilotHistory = useMemo(
    () =>
      messages
        .filter((m) => (m.type === 'user' || m.type === 'agent') && (m.text || '').trim())
        .slice(-6)
        .map((m) => ({ role: m.type === 'user' ? ('user' as const) : ('assistant' as const), content: m.text || '' })),
    [messages],
  )
  const copilot = useCopilotTurn(copilotHistory)
  const reasoningMsgIdRef = useRef<string | null>(null)
  const appliedFinalRef = useRef<CopilotFinalPayload | null>(null)

  // ── Lịch sử hội thoại Copilot (lỗi P1 "đổi trang là mất hội thoại") ──────────
  // Nguồn sự thật là server: mở lại trang thì nạp lại đúng cuộc đang dở thay vì bắt đầu trắng.
  const [conversationId, setConversationId] = useCopilotChatConversationId()
  /**
   * Bản "mới nhất" của id cuộc hội thoại cho các callback bất đồng bộ.
   *
   * Vì sao cần: effect chốt lượt (chạy khi `copilot.final`/`copilot.steps` đổi) đọc biến `conversationId`
   * của lần render đã tạo ra nó — luôn trễ một nhịp. Nếu server vừa cấp id cho cuộc mới (hoặc Sale vừa
   * bấm "Phiên chat mới") mà lượt ghi còn cầm id cũ thì lượt đó bị ghi nhầm cuộc ⇒ Lịch sử trống đúng
   * như lỗi người dùng báo. Ref được cập nhật ngay tại chỗ gán id, không chờ render.
   */
  const conversationIdRef = useRef(conversationId)
  useEffect(() => {
    conversationIdRef.current = conversationId
  }, [conversationId])
  // Mặc định ẨN khung lịch sử cho gọn màn hình chat; Sale bấm nút "Lịch sử" mới mở.
  const [historyOpen, setHistoryOpen] = useState(false)
  /** Chỉ nạp lại khung chat khi đổi cuộc — không đè lên lượt đang gõ. */
  const loadedConversationRef = useRef<string | null | undefined>(undefined)
  const conversations = useCopilotConversations()
  const conversation = useCopilotConversation(conversationId)
  const historyWarnedRef = useRef(false)
  const appendTurn = useAppendCopilotTurnSync({
    onError: () => {
      // Lịch sử là phụ trợ nên KHÔNG chặn hội thoại, nhưng cũng không được im lặng: bản trước
      // nuốt lỗi nên Sale chỉ thấy Lịch sử trống mà không hiểu vì sao.
      if (historyWarnedRef.current) return
      historyWarnedRef.current = true
      showToast('Chưa lưu được lượt này vào Lịch sử — anh/chị kiểm tra kết nối giúp em.')
    },
  })
  const createConversation = useCreateCopilotConversation()
  const deleteConversation = useDeleteCopilotConversation()
  const pendingQuestionsRef = useRef<Record<string, string>>({})

  /**
   * `reloadNonce` tăng mỗi lần người dùng **chủ động mở lại** một cuộc (bấm vào lịch sử) — nhờ đó
   * bấm lại đúng cuộc đang mở vẫn nạp lại nội dung mới nhất, thay vì im lặng không làm gì.
   */
  const [reloadNonce, setReloadNonce] = useState(0)
  const reloadNonceRef = useRef(0)
  reloadNonceRef.current = reloadNonce

  useEffect(() => {
    if (!conversationId) {
      // Phiên mới (chưa có id): KHÔNG xoá khung chat — nội dung đang gõ nằm trong store và phải
      // sống tiếp khi người dùng đổi trang quay lại. Chỉ đánh dấu là chưa nạp từ server.
      loadedConversationRef.current = null
      return
    }
    const detail = conversation.data
    if (!detail || detail.conversation_id !== conversationId) return
    const stamp = `${conversationId}#${reloadNonce}`
    if (loadedConversationRef.current === stamp) return
    loadedConversationRef.current = stamp
    setMessages(chatItemsFromConversation(detail.messages ?? []))
    copilot.reset()
    scrollChatToEnd()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ nạp khi đổi cuộc/ có dữ liệu mới
  }, [conversationId, conversation.data, reloadNonce])

  /**
   * Không mở được cuộc cũ: 404 (đã bị xoá / của nhân viên khác) thì quên id đang nhớ để lần sau
   * vào trang không lặp lại lỗi cũ; lỗi mạng thì chỉ báo nhẹ, giữ nguyên id để thử lại.
   */
  useEffect(() => {
    if (!conversationId || !conversation.error) return
    const status = (conversation.error as { status?: number }).status
    if (status === 404) {
      rememberConversationId(null)
      setConversationId(null)
      loadedConversationRef.current = null
      showToast('Cuộc hội thoại cũ không còn — đã mở cuộc trò chuyện mới.')
    } else {
      showToast('Không tải được hội thoại cũ — anh mở lại trang giúp em.')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ chạy khi lỗi đổi
  }, [conversationId, conversation.error])

  /**
   * Mở phiên chat mới: **tạo cuộc mới trên máy chủ** rồi chuyển sang cuộc đó.
   *
   * Vì sao phải gọi server: bản trước chỉ xoá khung chat cục bộ, không tạo gì cả ⇒ Sale bấm nút mà
   * Lịch sử không thay đổi, và nếu lượt ghi đầu tiên lỗi thì cuộc mới không tồn tại ở đâu (lỗi người
   * dùng báo: "nhấn cả 2 nút tạo hội thoại mới / phiên mới cũng không được"). Nay cuộc mới có ngay
   * trong Lịch sử (số đếm cạnh nút Lịch sử tăng lên), lượt đầu tiên hỏi sẽ được ghi vào đúng cuộc đó.
   *
   * Chặn khi trợ lý đang trả lời — đổi phiên giữa chừng sẽ làm mất lượt đang chạy.
   */
  const startNewChatSession = async () => {
    if (copilot.streaming) {
      showToast('Trợ lý đang trả lời — anh/chị đợi một chút rồi mở phiên mới.')
      return
    }
    setFailedTurn(null)
    // Đang ở một hội thoại mới TINH (chưa có lượt nào trên máy chủ) ⇒ không tạo thêm hội thoại rỗng,
    // tránh Lịch sử đầy các cuộc "Cuộc trò chuyện mới" giống nhau khi Sale bấm nút vài lần.
    if (conversationId && conversation.data && conversation.data.messages.length === 0) {
      copilot.reset()
      setInputVal('')
      inputTextAreaRef.current?.focus()
      showToast('Anh/chị đang ở hội thoại mới — cứ đặt câu hỏi đầu tiên nhé.')
      return
    }
    copilot.reset()
    setInputVal('')
    try {
      const created = await createConversation.mutateAsync({})
      // Cuộc mới có trên server nhưng CHƯA có lượt nào ⇒ khung chat trống, không nạp lại từ máy chủ.
      copilotChatStore.setConversationId(created.conversation_id, { items: [] })
      conversationIdRef.current = created.conversation_id
      rememberConversationId(created.conversation_id)
      loadedConversationRef.current = `${created.conversation_id}#${reloadNonceRef.current}`
      showToast('Đã tạo hội thoại mới — anh/chị xem trong Lịch sử; cuộc vừa rồi vẫn còn nguyên.')
    } catch {
      // Máy chủ không tạo được (mất mạng / hết phiên đăng nhập): vẫn mở phiên trống cục bộ như trước,
      // nhưng NÓI RÕ để Sale biết vì sao Lịch sử chưa có cuộc mới.
      copilotChatStore.setConversationId(null)
      conversationIdRef.current = null
      rememberConversationId(null)
      loadedConversationRef.current = null
      showToast('Chưa tạo được hội thoại mới trên máy chủ — em mở phiên trống; hội thoại sẽ được lưu khi anh/chị hỏi câu đầu tiên.')
    }
    inputTextAreaRef.current?.focus()
  }

  /**
   * Đổi cuộc: lưu lựa chọn, đưa nội dung đã đọc vào khung chat ngay (cache trong store), rồi để
   * effect trên thay bằng bản mới nhất từ server.
   *
   * Bấm lại **đúng cuộc đang mở** cũng phải nạp lại (`reloadNonce`) — trước đây thao tác này không
   * làm gì cả, nên người dùng bấm vào lịch sử mà không thấy gì xảy ra.
   */
  const openConversation = (nextId: string | null, opts: { force?: boolean } = {}) => {
    const sameConversation = nextId === conversationId
    rememberConversationId(nextId)
    setConversationId(nextId)
    setFailedTurn(null)
    if (nextId) setHistoryOpen(true)
    if (nextId && (sameConversation || opts.force)) setReloadNonce((n) => n + 1)
  }

  // ── Đọc câu trả lời thành tiếng (TTS) ────────────────────────────────────────
  // Giọng đọc lấy từ server (/settings/tts) để mọi máy trong công ty đọc cùng một giọng khi
  // Admin cấu hình nhà cung cấp; chưa cấu hình thì đọc bằng giọng trình duyệt (0 đồng).
  const ttsSettings = useTtsSettings()
  const updateTtsSettings = useUpdateTtsSettings()
  const sendVoiceFeedback = useTtsVoiceFeedback()
  const speakViaProvider = useTtsSpeak()
  const [speakingId, setSpeakingId] = useState<string | null>(null)
  const [voicePickerOpen, setVoicePickerOpen] = useState(false)
  const [localVoices, setLocalVoices] = useState<Array<{ code: string; label: string }>>([])
  const tts = ttsSettings.data
  const ttsEffective = tts?.effective
  const ttsProvider = tts?.catalog.find((c) => c.provider === ttsEffective?.provider)
  /** Nhà cung cấp trình duyệt (hoặc chưa có thiết lập) ⇒ đọc tại máy, 0 đồng. */
  const usesBrowserVoice = !ttsProvider || ttsProvider.mode === 'browser'
  /** Thẻ <audio> đang phát bản tổng hợp từ backend — giữ để bấm lần hai là dừng được. */
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const stopAllVoices = () => {
    stopSpeaking()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
  }

  useEffect(() => {
    if (!isSpeechSupported()) return
    let alive = true
    void listLocalVoices().then((voices) => {
      if (alive) setLocalVoices(voices)
    })
    return () => {
      alive = false
      stopAllVoices()
    }
  }, [])

  /** Đọc bằng giọng máy (Web Speech API) — đường miễn phí, luôn sẵn sàng. */
  const speakWithBrowserVoice = (id: string, text: string, summaryOnly: boolean) => {
    if (!ttsEffective) return false
    const result = speakText(text, {
      voice: ttsEffective.voice,
      speed: ttsEffective.speed,
      maxChars: summaryOnly ? 240 : ttsEffective.max_chars_per_turn,
      onEnd: () => setSpeakingId((cur) => (cur === id ? null : cur)),
      onError: (reason) => {
        setSpeakingId(null)
        showToast(reason)
      },
    })
    if (!result.ok) return false
    setSpeakingId(id)
    if (result.reason) showToast(result.reason)
    return true
  }

  /**
   * Đọc qua nhà cung cấp TTS (backend gọi nhà cung cấp thật rồi trả audio).
   *
   * Lỗi thì **tự lùi về giọng máy** kèm lý do đọc được (đúng hành vi đã chốt trong kế hoạch §7) — Sale
   * không bao giờ bị “bấm mà không có gì xảy ra”.
   */
  const speakWithProvider = async (id: string, text: string, summaryOnly: boolean) => {
    setSpeakingId(id)
    try {
      const res = await speakViaProvider.mutateAsync({
        text,
        voice: ttsEffective?.voice,
        provider: ttsEffective?.provider,
        conversation_id: conversationId,
        summary_only: summaryOnly,
      })
      const audio = new Audio(`data:${res.mime};base64,${res.audio_base64}`)
      audioRef.current = audio
      audio.onended = () => setSpeakingId((cur) => (cur === id ? null : cur))
      audio.onerror = () => {
        setSpeakingId(null)
        showToast('Không phát được audio vừa tổng hợp — thử lại hoặc đổi nhà cung cấp.')
      }
      await audio.play()
      if (res.cached) showToast('Đọc lại từ bản đã lưu — không phát sinh thêm chi phí.')
      // Sao chép cơ chế dự phòng của LLM: nói rõ đã đọc bằng nhà cung cấp nào khi phải chuyển tiếp.
      if (res.fallback_used) {
        const failed = res.attempts.filter((a) => !a.ok).map((a) => a.label)
        showToast(`${failed.join(', ')} không đọc được — đã tự chuyển sang ${ttsProvider?.label ?? res.provider}.`)
      }
      return true
    } catch (err) {
      setSpeakingId(null)
      const reason = err instanceof Error ? err.message : 'Không gọi được nhà cung cấp TTS.'
      showToast(`${ttsProvider?.label ?? 'Nhà cung cấp TTS'}: ${reason} Đang đọc bằng giọng máy.`)
      return speakWithBrowserVoice(id, text, summaryOnly)
    }
  }

  /** Đọc một câu trả lời; bấm lần hai (hoặc câu khác) thì dừng/đổi câu. */
  const handleSpeak = (id: string, text: string) => {
    if (speakingId === id) {
      stopAllVoices()
      setSpeakingId(null)
      return
    }
    if (!ttsEffective?.enabled) {
      showToast('Tính năng đọc thành tiếng đang tắt — bật trong “Giọng đọc”.')
      return
    }
    stopAllVoices()
    if (usesBrowserVoice) {
      speakWithBrowserVoice(id, text, false)
      return
    }
    void speakWithProvider(id, text, false)
  }

  /** Tự đọc mỗi câu trả lời mới khi Sale bật chế độ rảnh tay (chỉ đọc phần đầu cho đỡ tốn tiền). */
  useEffect(() => {
    if (!ttsEffective?.auto_speak || !ttsEffective.enabled) return
    const last = [...messages].reverse().find((m) => m.type === 'agent' && (m.text || '').trim())
    if (!last || last.id === speakingId) return
    if (usesBrowserVoice) speakWithBrowserVoice(last.id, last.text || '', true)
    else void speakWithProvider(last.id, last.text || '', true)
    // Cố ý chỉ phụ thuộc vào câu trả lời cuối + thiết lập: không đọc lại khi gõ phím.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, ttsEffective?.auto_speak, ttsEffective?.enabled, ttsEffective?.voice, ttsEffective?.speed])

  /** Lưu lựa chọn giọng đọc (mặc định hệ thống cần ADMIN/MANAGER — server chặn). */
  const saveTts = async (payload: Record<string, unknown>, scope: 'user' | 'default' = 'user') => {
    try {
      await updateTtsSettings.mutateAsync({ scope, ...payload })
      showToast(scope === 'default' ? 'Đã lưu giọng đọc dùng chung' : 'Đã lưu giọng đọc của anh/chị')
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Không lưu được thiết lập giọng đọc')
    }
  }

  /** Phản hồi giọng vừa đọc — dữ liệu để chọn giọng theo thực tế thay vì cảm tính. */
  const rateVoice = async (rating: 1 | -1) => {
    if (!ttsEffective) return
    try {
      await sendVoiceFeedback.mutateAsync({
        rating,
        provider: ttsEffective.provider,
        voice: ttsEffective.voice,
        conversation_id: conversationId,
        reason: rating === -1 ? 'Sale chê giọng đọc trong workspace' : undefined,
      })
      showToast(rating === 1 ? 'Cảm ơn anh/chị đã xác nhận giọng đọc' : 'Đã ghi nhận — Admin sẽ xem lại giọng đọc')
    } catch {
      showToast('Không gửi được phản hồi giọng đọc')
    }
  }

  const handleDeleteConversation = async (id: string) => {
    try {
      await deleteConversation.mutateAsync(id)
    } catch {
      showToast('Không xoá được cuộc hội thoại — anh thử lại giúp em')
      return
    }
    copilotChatStore.forget(id)
    if (id === conversationId) openConversation(null)
  }


  // ── Nhập câu hỏi bằng giọng nói ("rảnh tay", Web Speech API) ─────────────────
  // Chrome/Edge/Cốc Cốc có sẵn, 0 đồng. Bật là nghe liên tục: nói xong một câu, trình duyệt tự
  // nghe lại cho tới khi Sale bấm dừng — Sale không phải chạm máy giữa các câu.
  const sttSupported = useMemo(() => isSpeechToTextSupported(), [])
  const [sttListening, setSttListening] = useState(false)
  const sttRef = useRef<SpeechToTextController | null>(null)
  /** Phần văn bản đã chốt trước khi bật micro — chữ đang nói được ghép vào sau phần này. */
  const sttBaseRef = useRef('')
  const showToastRef = useRef<(message: string) => void>(() => undefined)
  const inputValRef = useRef('')

  // Copilot Composer State
  const [draftContent, setDraftContent] = useState(
    'Dạ em chào anh An, em gửi anh phương án báo giá chuẩn căn R-02.02 ạ [2]. Khách hàng chọn thanh toán sớm 95% nhận chiết khấu 8% [1]. Anh quét mã QR trên báo giá để đối soát pháp lý nhé!'
  )
  const [draftAnchors] = useState<number[]>([2, 1])
  const [complianceResult, setComplianceResult] = useState<ComplianceCheckState>(runLocalComplianceCheck(draftContent))
  const [isCheckingCompliance, setIsCheckingCompliance] = useState(false)
  const complianceDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const complianceAbortRef = useRef<AbortController | null>(null)
  const [complianceOffline, setComplianceOffline] = useState(false)

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
  inputValRef.current = inputVal

  useEffect(() => {
    if (!sttSupported) return
    const controller = createSpeechToText({
      lang: 'vi-VN',
      continuous: true,
      // Chữ tạm hiện ngay trong ô nhập để Sale thấy máy đang nghe đúng.
      onPartial: (text) => setInputVal(`${sttBaseRef.current}${text}`.trimStart()),
      onFinal: (text) => {
        sttBaseRef.current = `${sttBaseRef.current}${text} `.replace(/\s+/g, ' ')
        setInputVal(sttBaseRef.current.trimStart())
      },
      onStateChange: setSttListening,
      onError: (message) => showToastRef.current(message),
    })
    sttRef.current = controller
    return () => {
      controller.stop()
      sttRef.current = null
    }
  }, [sttSupported])

  /** Bật/tắt micro. Trình duyệt không hỗ trợ (Safari/Firefox) thì nói rõ thay vì im lặng. */
  const toggleVoiceInput = () => {
    const controller = sttRef.current
    if (!controller?.supported) {
      showToast(SPEECH_TO_TEXT_UNSUPPORTED_MESSAGE)
      return
    }
    if (controller.isListening()) {
      controller.stop()
      showToast('Đã dừng nghe. Anh/chị kiểm tra lại câu hỏi rồi bấm gửi.')
      return
    }
    sttBaseRef.current = inputValRef.current ? `${inputValRef.current.trim()} ` : ''
    controller.start()
    showToast('Đang nghe… anh/chị nói câu hỏi; bấm micro lần nữa để dừng.')
  }

  const showToast = (text: string) => {
    setToastMessage(text)
    setTimeout(() => {
      setToastMessage((cur) => (cur === text ? null : cur))
    }, 3200)
  }
  // Bộ nhận dạng giọng nói được tạo một lần trong effect, cần gọi được hàm mới nhất.
  showToastRef.current = showToast

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

  /**
   * Live-check F8 thật: gọi `POST /compliance/check-message` (debounce 500 ms như UI hứa).
   * - Huỷ request đang bay khi Sale gõ tiếp (AbortController) để kết quả cũ không ghi đè kết quả mới.
   * - API lỗi → rơi về kiểm tra cục bộ và nói rõ là đang ở chế độ dự phòng, không im lặng.
   */
  const handleDraftTextChange = (text: string) => {
    setDraftContent(text)
    setIsCheckingCompliance(true)
    if (complianceDebounceRef.current) clearTimeout(complianceDebounceRef.current)
    complianceDebounceRef.current = setTimeout(() => {
      complianceAbortRef.current?.abort()
      const controller = new AbortController()
      complianceAbortRef.current = controller
      void api.compliance
        .check(
          { message_text: text, mode: 'ON_DRAFT' },
          controller.signal,
        )
        .then((res) => {
          setComplianceResult(mapComplianceResponse(res))
          setComplianceOffline(false)
        })
        .catch((err) => {
          if (controller.signal.aborted) return
          setComplianceResult(runLocalComplianceCheck(text))
          setComplianceOffline(true)
          void err
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsCheckingCompliance(false)
        })
    }, 500)
  }

  // Initialize Morning Briefing on Mount
  // LƯU Ý (lỗi thật đã gặp): đây từng là `setMessages([...])` trần trong effect deps rỗng, nên mỗi lần
  // quay lại trang Trợ lý là nó **ghi đè** hội thoại vừa khôi phục bằng đúng một tin chào — một phần
  // của triệu chứng "đổi trang là mất hết đoạn chat". Nay chỉ chào khi phiên chat còn trống.
  useEffect(() => {
    const time = new Date().toTimeString().slice(0, 5)
    setMessages((prev) =>
      prev.length > 0
        ? prev
        : [
            {
              id: 'msg-greeting',
              type: 'welcome',
              time,
            },
          ],
    )
    scrollChatToEnd()
  }, [])

  // ===== COPILOT REACT STREAM → CHAT STREAM =====
  // Đồng bộ tiến trình suy luận thật (thought/action/observation) vào bong bóng "reasoning",
  // rồi khi có `final` mới chèn câu trả lời + Smart Card + citation. Không còn stepper giả.
  const citationToEvidence = (citation: CopilotCitation): LegalEvidence => ({
    q: citation.quote || 'Chưa có trích dẫn nguyên văn cho căn cứ này.',
    p: `${citation.policy_id}${citation.section ? ` — ${citation.section}` : ''}${
      citation.policy_title ? ` (${citation.policy_title})` : ''
    }`,
    e:
      citation.effective_from || citation.effective_to
        ? `${citation.effective_from ?? '?'} → ${citation.effective_to ?? '?'}`
        : citation.source || 'Nguồn hệ thống',
    h: citation.document_hash ? `${citation.document_hash.slice(0, 12)}…` : citation.clause_id || citation.source || '—',
    clause: citation.clause_id || undefined,
    hash: citation.document_hash || undefined,
  })

  useEffect(() => {
    if (copilot.error && copilot.lastMessage) {
      setFailedTurn({ text: copilot.lastMessage, context: (copilot.lastContext ?? {}) as Record<string, string | null> })
    }
  }, [copilot.error, copilot.lastMessage, copilot.lastContext])

  useEffect(() => {
    const msgId = reasoningMsgIdRef.current
    if (!msgId) return
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId
          ? {
              ...m,
              data: {
                ...m.data,
                steps: copilot.steps,
                streaming: copilot.streaming,
                degraded: copilot.degraded,
                error: copilot.error,
              },
            }
          : m,
      ),
    )
  }, [copilot.steps, copilot.streaming, copilot.degraded, copilot.error])

  useEffect(() => {
    const final = copilot.final
    const msgId = reasoningMsgIdRef.current
    if (!final || !msgId || appliedFinalRef.current === final) return
    appliedFinalRef.current = final

    const time = new Date().toTimeString().slice(0, 5)
    setMessages((prev) => {
      const list = prev.map((m) =>
        m.id === msgId ? { ...m, data: { ...m.data, streaming: false, steps: copilot.steps } } : m,
      )
      list.push({
        id: `agent-${Date.now()}`,
        type: 'agent',
        time,
        text: final.reply,
        suggested_actions: final.suggested_actions,
        data: {
          citations: final.citations ?? [],
          grounded: final.grounded,
          mode: final.mode,
          critique: final.critique ?? null,
          anchors: final.anchors ?? [],
          internal_notes: final.internal_notes ?? '',
          data_as_of: final.data_as_of ?? null,
        },
      })
      if (final.action_type) {
        list.push({
          id: `card-${Date.now()}`,
          type: final.action_type as StreamItemType,
          time,
          data: final.action_data || {},
        })
      }
      return list
    })
    if (!final.grounded && final.mode !== 'react') {
      showToast('Câu trả lời chưa đối chiếu được dữ liệu — anh kiểm tra lại giúp em')
      // VẪN lưu vào lịch sử. Trước đây chỗ này `return` sớm với lý do "mở lại sẽ không còn cảnh báo",
      // nhưng hậu quả nặng hơn nhiều: khi backend chạy chế độ dự phòng (offline_react — không có khoá
      // LLM), KHÔNG lượt nào được lưu → khung lịch sử luôn rỗng và đổi trang là mất cả hội thoại.
      // Cảnh báo vẫn còn vì câu trả lời lưu kèm citations rỗng (UI hiển thị là chưa đối chiếu).
    }
    scrollChatToEnd()

    // Ghi lượt hỏi–đáp vào lịch sử server (không chặn UI). Câu hỏi gốc lấy từ hàng đợi theo id
    // lượt reasoning, nên câu trả lời luôn khớp đúng câu đã hỏi kể cả khi Sale bấm nhanh.
    const question = pendingQuestionsRef.current[msgId] ?? [...messages].reverse().find((m) => m.type === 'user')?.text
    delete pendingQuestionsRef.current[msgId]
    // Đọc id cuộc qua ref (giá trị mới nhất), không qua biến của closure đã cũ.
    const activeConversationId = conversationIdRef.current
    if (question) {
      // `turnToAppendPayload` là hàm thuần đã có test (packages/api-client/src/copilotHistory.ts):
      // lưu MỌI lượt, kể cả câu trả lời chế độ dự phòng — nếu không, lịch sử rỗng và đổi trang là mất hội thoại.
      appendTurn(
        turnToAppendPayload({ conversationId: activeConversationId, question, final }),
      ).then((detail) => {
        if (!detail) return
        // Lượt đầu tiên của cuộc mới: server đặt tên cuộc → ghi nhớ id để lần sau ghi tiếp.
        if (!conversationIdRef.current && detail.conversation_id) {
          conversationIdRef.current = detail.conversation_id
          rememberConversationId(detail.conversation_id)
          // DÙNG `assignConversationId` (KHÔNG phải `setConversationId`): server vừa cấp id cho CHÍNH
          // phiên đang mở nên nội dung đang hiển thị phải giữ nguyên và được cất vào cache theo id mới.
          // Bản trước gọi `setConversationId` ⇒ store hiểu là "đổi sang cuộc khác", xoá trắng khung chat
          // ngay sau lượt trả lời đầu tiên (lỗi người dùng báo: "đoạn hội thoại mới không được lưu
          // vào lịch sử"), và cũng vì khung chat đã trống nên bấm nút phiên mới trông như không có gì xảy ra.
          copilotChatStore.assignConversationId(detail.conversation_id)
          // Nội dung đã hiển thị chính là nội dung server vừa lưu → không cần nạp lại và không
          // được làm rơi mất các thẻ tương tác (confirm/stepper) chỉ có ở phía client.
          loadedConversationRef.current = `${detail.conversation_id}#${reloadNonceRef.current}`
        }
      })
    }
  }, [copilot.final, copilot.steps])

  // Câu hỏi của lượt đang chạy — effect chốt lượt ở trên đọc lại theo id lượt reasoning.
  const recordPendingQuestion = (reasoningId: string, question: string) => {
    pendingQuestionsRef.current[reasoningId] = question
  }

  /**
   * Nudge THẬT: khi danh sách báo giá (polling/SSE) cho thấy có hồ sơ cần Sale xử lý
   * (bị yêu cầu sửa / bị từ chối), chèn nhắc việc kèm lý do thật của quản lý.
   * Trước đây chỗ này là `setTimeout` bịa "Mr. Hùng đang xem Q-00092".
   */
  const nudgedQuotesRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    const needsAction = quotes.find((q) => q.status === 'NEEDS_REVISION' || q.status === 'REJECTED')
    if (!needsAction) return
    const key = `${needsAction.quote_id}#${needsAction.quote_version}#${needsAction.status}`
    if (nudgedQuotesRef.current.has(key)) return
    nudgedQuotesRef.current.add(key)
    const reason = needsAction.approval?.reason
    const decidedBy = needsAction.approval?.decided_by?.full_name
    setMessages((prev) => [
      ...prev,
      {
        id: `nudge-${key}`,
        type: 'nudge',
        time: new Date().toTimeString().slice(0, 5),
        data: {
          title: `Báo giá ${needsAction.quote_id} V${needsAction.quote_version} ${needsAction.status === 'REJECTED' ? 'bị từ chối' : 'cần chỉnh sửa'}`,
          sub:
            (decidedBy ? `${decidedBy}: ` : '') +
            (reason || 'Mở tab Báo giá để xem chi tiết và xử lý.'),
        },
      },
    ])
    scrollChatToEnd()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quotes])

  /**
   * Nudge chủ động theo SLA hồ sơ (P2): còn ≤ 10 phút tới hạn phản hồi thì nhắc trong khung chat.
   * Chạy lại mỗi phút; mỗi hồ sơ chỉ nhắc một lần cho mỗi mốc hạn (kể cả khi Sale đổi mốc SLA).
   */
  const slaNudgedRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    const check = () => {
      const now = Date.now()
      const urgent = leads.find((l) => {
        if (!l.sla_due_at) return false
        const remaining = new Date(l.sla_due_at).getTime() - now
        if (remaining <= 0 || remaining > 10 * 60_000) return false
        return !slaNudgedRef.current.has(`${l.dossier_id}#${l.sla_due_at}`)
      })
      if (!urgent) return
      slaNudgedRef.current.add(`${urgent.dossier_id}#${urgent.sla_due_at}`)
      const minutes = Math.max(1, Math.round((new Date(urgent.sla_due_at).getTime() - now) / 60_000))
      setMessages((prev) => [
        ...prev,
        {
          id: `sla-nudge-${urgent.dossier_id}-${urgent.sla_due_at}`,
          type: 'nudge',
          time: new Date().toTimeString().slice(0, 5),
          data: {
            title: `SLA còn ${minutes} phút — hồ sơ ${urgent.customer.full_name}`,
            sub: `${urgent.dossier_id} cần phản hồi trước ${new Date(urgent.sla_due_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}. Anh/chị mở hồ sơ để xử lý ngay.`,
          },
        },
      ])
    }
    check()
    const timer = setInterval(check, 60_000)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leads])

  /**
   * Gửi phản hồi (thumbs) về một lượt trả lời → backend log lại và dùng làm "điều cần tránh"
   * cho các lượt sau (P2 — học từ phản hồi). Ghi nhận lạc hậu không được chặn UI.
   */
  const handleCopilotFeedback = async (message: StreamItem, rating: 1 | -1) => {
    // Câu hỏi gần nhất trước lượt trả lời này (để đối chiếu khi đọc log phản hồi).
    const index = messages.findIndex((mm) => mm.id === message.id)
    const previous = index > 0 ? messages.slice(0, index).reverse().find((mm) => mm.type === 'user') : undefined
    setMessages((prev) => prev.map((mm) => (mm.id === message.id ? { ...mm, data: { ...mm.data, feedbackGiven: rating } } : mm)))
    try {
      await api.copilot.feedback({
        message: previous?.text || '(không rõ câu hỏi)',
        reply: message.text || '',
        rating,
        mode: (message.data?.mode as string) || null,
        tags: rating === -1 ? ['sale_danh_gia_chua_dat'] : [],
        tools_used: [],
        turn_id: message.id,
      })
      showToast(rating === 1 ? 'Cảm ơn anh/chị đã đánh giá hữu ích' : 'Đã ghi nhận — em sẽ tránh cách trả lời này')
    } catch {
      setMessages((prev) => prev.map((mm) => (mm.id === message.id ? { ...mm, data: { ...mm.data, feedbackGiven: undefined } } : mm)))
      showToast('Chưa gửi được đánh giá — anh/chị thử lại sau nhé')
    }
  }

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
  const startQuoteCreationFlow = (targetLeadName?: string, unitCodeOverride?: string) => {
    const time = new Date().toTimeString().slice(0, 5)
    const clientName = resolveQuoteCustomerName(targetLeadName, selectedLead?.customer.full_name)
    // Một hàm giải mã căn dùng chung cho MỌI luồng (thẻ xác nhận, chip gợi ý, ngăn hồ sơ) — chốt đợt 20.
    const cardUnitCode = resolveQuoteUnitCode({
      actionUnit: unitCodeOverride,
      sessionUnit: copilotUnit,
      leadUnit: selectedLead?.constraints?.preferred_unit_code,
    })
    if (unitCodeOverride && unitCodeOverride !== copilotUnit) setCopilotUnit(unitCodeOverride)
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, type: 'user', text: `tạo báo giá cho ${clientName}`, time },
      {
        id: `conf-${Date.now()}`,
        type: 'confirm',
        time,
        data: {
          clientName,
          // Chỉ ghi "Chưa chọn căn" khi THẬT SỰ chưa có căn trong ngữ cảnh — trước đây thẻ luôn đọc từ
          // hồ sơ khách nên bỏ qua mã căn vừa nêu trong câu hỏi.
          unitCode: cardUnitCode || NO_UNIT_LABEL,
          date: `${new Date().toLocaleDateString('vi-VN')} (hôm nay)`,
          goal: selectedLead?.constraints?.objective
            ? `Theo hồ sơ khách: ${selectedLead.constraints.objective}`
            : 'Ít vốn ban đầu nhất (mặc định của hệ thống)',
        },
      },
    ])
    scrollChatToEnd()
  }

  /**
   * Xác nhận lập báo giá — gọi API THẬT thay vì animation giả.
   *
   * Trước đây hàm này vẽ 4 bước bằng `setInterval` rồi in ra kết quả bịa ("Đề xuất PA-VAY…").
   * Nay: tra giá niêm yết thật của căn → gọi `POST /quotes` → cập nhật tiến trình theo đúng
   * vòng đời thật (gửi yêu cầu → engine trả kết quả). Không suy diễn thêm số liệu nào.
   */
  const handleConfirmQuoteAction = async (unitOverride?: string) => {
    const time = new Date().toTimeString().slice(0, 5)
    const stepMsgId = `step-${Date.now()}`
    // Cùng một nguồn ngữ cảnh với thẻ xác nhận (thẻ vừa vẽ mã căn nào thì lập báo giá đúng mã đó):
    // căn của lượt gọi hàm → căn ngữ cảnh Copilot → căn trong hồ sơ khách.
    const unitCode = resolveQuoteUnitCode({
      actionUnit: unitOverride,
      sessionUnit: copilotUnit,
      leadUnit: selectedLead?.constraints?.preferred_unit_code,
    })
    if (unitOverride) setCopilotUnit(unitOverride)

    if (!unitCode) {
      // Không đủ dữ kiện thì nói thẳng — không dựng tiến trình cho có.
      setMessages((prev) => [
        ...prev,
        {
          id: `need-unit-${Date.now()}`,
          type: 'agent',
          time,
          text: 'Anh/chị cho em **mã căn** trước khi lập báo giá nhé — em không tự suy diễn giá khi thiếu dữ liệu.',
        },
      ])
      showToast('Thiếu mã căn để lập báo giá')
      scrollChatToEnd()
      return
    }

    setMessages((prev) => [
      ...prev,
      {
        id: stepMsgId,
        type: 'stepper',
        time,
        data: {
          // 5 bước = đúng 5 lời gọi server của luồng hoàn chỉnh: tạo nháp → engine + bằng chứng →
          // trình Quản lý. Trước đây chỉ có 1 lời gọi rồi báo "đã gửi" nên báo giá chết ở DRAFT.
          steps: [
            'Đọc ràng buộc hồ sơ khách',
            `Tra giá niêm yết căn ${unitCode}`,
            'Tạo bản nháp báo giá',
            'Chạy engine định giá + phát hành bằng chứng',
            'Trình Quản lý duyệt (chờ thẩm định)',
          ],
          current: 0,
          failed: false,
        },
      },
    ])
    scrollChatToEnd()
    const advance = (current: number, failed = false) =>
      setMessages((prev) => prev.map((m) => (m.id === stepMsgId ? { ...m, data: { ...m.data, current, failed } } : m)))

    try {
      advance(1)
      // Dự án suy ra từ chính căn vừa tra được — hồ sơ khách thiếu `project_id` không còn chặn báo giá.
      const units = await api.catalog.units(
        selectedLead?.constraints?.project_id ? { project_id: selectedLead.constraints.project_id } : {},
      )
      const unit = units.find((u) => u.unit_code === unitCode)
      if (!unit) throw new Error(`Không tìm thấy căn ${unitCode} trong giỏ hàng`)

      advance(2)
      const created = await api.quotes.create(
        {
          project_id: unit.project_id,
          unit_code: unit.unit_code,
          listed_price_before_tax_vnd: unit.listed_price_before_tax_vnd,
          own_funds_vnd: selectedLead?.constraints?.own_funds_vnd ?? undefined,
          monthly_capacity_vnd: selectedLead?.constraints?.monthly_capacity_vnd ?? undefined,
          objective: 'MIN_INITIAL_CASH',
        },
        { idempotencyKey: crypto.randomUUID() },
      )
      const quoteId = (created as { quote_id: string }).quote_id
      const quoteVersion = 'quote_version' in created ? Number(created.quote_version) : 1

      // Bước 3 (BẮT BUỘC): chạy engine tất định + phát hành bộ chứng cứ C-04 cho phiên bản này.
      // Thiếu bước này thì cổng /submit-review của backend chặn (409) và Manager không thấy hồ sơ.
      advance(3)
      await api.quotes.calculate(quoteId, {
        idempotencyKey: crypto.randomUUID(),
        expectedVersion: quoteVersion,
      })

      // Bước 4: trình Quản lý duyệt — chỉ qua khi hồ sơ đã đủ (đã tính + có bằng chứng + qua F8).
      advance(4)
      const submitted = await api.quotes.submit(quoteId, {
        idempotencyKey: crypto.randomUUID(),
        expectedVersion: quoteVersion,
      })

      advance(5)
      const quoteCode = `${submitted.quote_id ?? quoteId} V${submitted.quote_version ?? quoteVersion}`
      setMessages((prev) => [
        ...prev,
        {
          id: `done-${Date.now()}`,
          type: 'agent',
          time: new Date().toTimeString().slice(0, 5),
          text:
            `✓ Bản báo giá **${quoteCode}** cho căn **${unit.unit_code}** đã hoàn chỉnh và **đang chờ Quản lý thẩm định**. ` +
            'Hồ sơ gồm 3 phương án tài chính, bộ chứng cứ đối chiếu điều khoản và dấu vết kiểm toán. ' +
            'Anh/chị xem chi tiết ở tab Báo giá.',
        },
      ])
      setActiveTab('baogia')
      setPanelView('quote_comparison')
      setIsMobilePanelOpen(true)
      showToast('→ Đã trình Quản lý duyệt báo giá')
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      scrollChatToEnd()
    } catch (err) {
      advance(5, true)
      // 409 QUOTE_NOT_READY: backend trả checklist — nói thẳng còn thiếu gì thay vì "thử lại".
      const checklist = (err as { details?: { checklist?: { label: string; ok: boolean }[] } })?.details?.checklist
      const missing = (checklist ?? []).filter((item) => !item.ok).map((item) => `• ${item.label}`)
      const message = err instanceof Error ? err.message : 'Không gọi được API lập báo giá'
      setMessages((prev) => [
        ...prev,
        {
          id: `quote-error-${Date.now()}`,
          type: 'agent',
          time: new Date().toTimeString().slice(0, 5),
          text: missing.length
            ? `⚠️ **Chưa trình được Quản lý** — hồ sơ còn thiếu:\n${missing.join('\n')}\n\n${message}`
            : `⚠️ Chưa lập được báo giá: ${message}. Anh/chị kiểm tra lại kết nối rồi thử lại giúp em.`,
        },
      ])
      showToast(missing.length ? 'Hồ sơ chưa đủ điều kiện trình duyệt' : 'Lập báo giá thất bại — xem chi tiết trong khung chat')
      scrollChatToEnd()
    }
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

  /**
   * Trình duyệt báo giá — gọi API THẬT (`POST /quotes/{id}/submit`).
   *
   * Trước đây hàm này chỉ chèn thẻ "đã trình Q-00092 cho Mr. Hùng" rồi hẹn giờ bịa một nudge SSE.
   * Nay: lấy đúng báo giá thật của hồ sơ đang chọn, gọi submit, và chỉ hiện receipt khi server
   * xác nhận. Không có báo giá nào đủ điều kiện → nói thẳng, không diễn.
   */
  const handleConfirmSubmitAction = async () => {
    const time = new Date().toTimeString().slice(0, 5)
    const targetQuote =
      quotes.find((q) => q.source_dossier_id && q.source_dossier_id === selectedLead?.dossier_id && q.status === 'READY_FOR_REVIEW') ??
      quotes.find((q) => q.status === 'READY_FOR_REVIEW') ??
      quotes.find((q) => q.status === 'DRAFT')

    if (!targetQuote) {
      setMessages((prev) => [
        ...prev,
        {
          id: `no-quote-${Date.now()}`,
          type: 'agent',
          time,
          text: 'Chưa có báo giá nào ở trạng thái sẵn sàng trình duyệt. Anh/chị lập báo giá trước rồi em gửi trình duyệt ngay.',
        },
      ])
      showToast('Chưa có báo giá đủ điều kiện trình duyệt')
      scrollChatToEnd()
      return
    }

    try {
      const submitted = await api.quotes.submit(targetQuote.quote_id, {
        idempotencyKey: crypto.randomUUID(),
        expectedVersion: targetQuote.quote_version,
      })
      setUndoSeconds(8)
      setUndoActive(true)
      setUndoQuoteCode(`${submitted.quote_id} V${submitted.quote_version}`)
      setUndoQuoteVersion(submitted.quote_version)
      setMessages((prev) => [
        ...prev,
        {
          id: `rcp-${Date.now()}`,
          type: 'receipt',
          time,
          data: {
            id: `${submitted.quote_id} V${submitted.quote_version}`,
            approver: submitted.approval?.decided_by?.full_name || 'Quản lý phụ trách',
          },
        },
      ])
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      showToast(`Đã trình duyệt ${submitted.quote_id} V${submitted.quote_version}`)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Không gửi được yêu cầu trình duyệt'
      // Cổng /submit-review trả 409 kèm checklist khi hồ sơ khuyết (chưa tính / chưa có bằng chứng /
      // chưa qua F8) — hiển thị đúng từng mục còn thiếu để Sale biết đường xử lý.
      const checklist = (err as { details?: { checklist?: { label: string; ok: boolean }[] } })?.details?.checklist
      const missing = (checklist ?? []).filter((item) => !item.ok).map((item) => `• ${item.label}`)
      setMessages((prev) => [
        ...prev,
        {
          id: `submit-error-${Date.now()}`,
          type: 'agent',
          time,
          text: missing.length
            ? `⚠️ **Chưa trình được Quản lý** — hồ sơ còn thiếu:\n${missing.join('\n')}\n\n${message}`
            : `⚠️ Trình duyệt thất bại: ${message}. Anh/chị thử lại giúp em.`,
        },
      ])
      showToast(missing.length ? 'Hồ sơ chưa đủ điều kiện trình duyệt' : 'Trình duyệt thất bại — xem chi tiết trong khung chat')
    }
    scrollChatToEnd()
  }

  /**
   * Trong 8 giây đầu sau khi trình, Sale được gửi YÊU CẦU SỬA (endpoint thật
   * `POST /quotes/{id}/revision`). Đây thay cho nút "Hoàn tác" trước đây vốn chỉ đổi state
   * phía UI trong khi hồ sơ đã nằm ở server — một lời hứa sai.
   */
  const handleRequestRevision = async () => {
    const quoteId = undoQuoteCode.split(' ')[0]
    try {
      await api.quotes.requestRevision(
        quoteId,
        { reason: 'Sale xin điều chỉnh ngay sau khi trình duyệt' },
        { idempotencyKey: crypto.randomUUID(), expectedVersion: undoQuoteVersion },
      )
      setUndoActive(false)
      setMessages((prev) => [
        ...prev,
        {
          id: `revision-${Date.now()}`,
          type: 'agent',
          time: new Date().toTimeString().slice(0, 5),
          text: `↩ Đã gửi **yêu cầu sửa** cho ${undoQuoteCode} tới quản lý — hồ sơ sẽ trở lại trạng thái cần chỉnh sửa.`,
        },
      ])
      void queryClient.invalidateQueries({ queryKey: ['quotes'] })
      showToast('Đã gửi yêu cầu sửa cho quản lý')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Không gửi được yêu cầu sửa'
      showToast(`Yêu cầu sửa thất bại: ${message}`)
    }
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
    const unitMatch = text.toUpperCase().match(/\b([A-Z]+-\d+\.\d+)\b/)
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

    // 2. Mọi câu lệnh còn lại đi vào ReAct Copilot (tool thật + stream tiến trình).
    //    Không còn câu trả lời hardcode theo kịch bản demo.
    const reasoningId = `reasoning-${Date.now()}`
    reasoningMsgIdRef.current = reasoningId
    appliedFinalRef.current = null
    recordPendingQuestion(reasoningId, text)
    setMessages((prev) => [
      ...prev,
      {
        id: reasoningId,
        type: 'reasoning',
        time,
        data: { steps: [] as CopilotReasoningStep[], streaming: true },
      },
    ])
    scrollChatToEnd()
    // Câu vừa gõ có mã căn ⇒ cập nhật ngữ cảnh phiên trước khi gọi Copilot (dùng ngay giá trị vừa bóc
    // được, vì state React chỉ cập nhật ở lần render sau).
    const notedUnit = noteUnitFromText(text)
    const context = {
      currentUnit: notedUnit ?? copilotUnit ?? ctxLead?.constraints?.preferred_unit_code ?? null,
      leadDossierId: ctxLead?.dossier_id ?? null,
      transactionDate: copilotTxDate,
      projectId: ctxLead?.constraints?.project_id ?? null,
    }
    setFailedTurn(null)
    copilot.send(text, context)
  }

  /** Thử lại đúng câu vừa lỗi với đúng ngữ cảnh cũ (C4). */
  const handleRetryFailedTurn = () => {
    if (!failedTurn) return
    setFailedTurn(null)
    copilot.send(failedTurn.text, failedTurn.context)
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

  // Danh mục lệnh gạch chéo (D1) — có từ khoá không dấu để gõ "bao gia" vẫn khớp "/baogia"
  const SLASH_COMMANDS: SlashCommand[] = useMemo(
    () => [
      { cmd: '/tao-khach', label: 'Khởi tạo hồ sơ khách hàng mới', icon: UserPlus, keywords: ['tao khach', 'khach moi', 'lead'] },
      { cmd: '/tim-khach', label: 'Tìm khách hàng theo tên / SĐT / mã hồ sơ', icon: Search, keywords: ['tim khach', 'tra cuu khach'] },
      { cmd: '/khach-hang', label: 'Xem danh sách hồ sơ khách', icon: Users, keywords: ['danh sach khach'] },
      { cmd: '/baogia', label: 'Mở pipeline báo giá', icon: FileStack, keywords: ['bao gia', 'pipeline'] },
      { cmd: '/soan-tin', label: 'Soạn tin nhắn Copilot (tự kiểm F8)', icon: MessageSquare, keywords: ['soan tin', 'zalo', 'tin nhan'] },
      { cmd: '/chinh-sach', label: 'Tra cứu chính sách đang hiệu lực', icon: ScrollText, keywords: ['chinh sach', 'chiet khau'] },
      { cmd: '/tinh-lai', label: 'Lập báo giá mới theo chính sách', icon: RotateCcw, keywords: ['tinh lai', 'lap bao gia'] },
      { cmd: '/gio-hang', label: 'Hỏi Copilot giỏ hàng còn căn nào', icon: Home, keywords: ['gio hang', 'ro hang', 'con can'] },
    ],
    [],
  )

  const filteredCommands = useMemo(() => filterCommands(SLASH_COMMANDS, inputVal), [SLASH_COMMANDS, inputVal])

  // Đổi từ khoá thì đưa con trỏ về dòng đầu, tránh chọn nhầm lệnh ngoài danh sách mới
  useEffect(() => {
    setSlashIndex(0)
  }, [inputVal])

  const rememberCommand = (cmd: string) => {
    setRecentCommands((prev) => {
      const next = [cmd, ...prev.filter((c) => c !== cmd)].slice(0, 4)
      try {
        window.localStorage.setItem('copilot.recentSlash', JSON.stringify(next))
      } catch {
        /* chế độ riêng tư: bỏ qua, không chặn thao tác */
      }
      return next
    })
  }

  const handleExecuteSlash = (cmd: string) => {
    setSlashOpen(false)
    setInputVal('')
    rememberCommand(cmd)
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
    } else if (cmd === '/gio-hang') {
      setInputVal('Giỏ hàng còn căn nào?')
      inputTextAreaRef.current?.focus()
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
          </div>
          {/* Nút Lịch sử nằm bên trái, cạnh tiêu đề: khung lịch sử mặc định ẩn, bấm đây mới mở. */}
          <Button
            size="sm"
            variant={historyOpen ? 'secondary' : 'outline'}
            onClick={() => setHistoryOpen((v) => !v)}
            title={historyOpen ? 'Ẩn lịch sử hội thoại' : 'Hiện lịch sử hội thoại'}
            aria-expanded={historyOpen}
            className="h-7 gap-1.5 text-xs"
          >
            {historyOpen ? <PanelLeftClose className="h-3.5 w-3.5" /> : <PanelLeftOpen className="h-3.5 w-3.5" />}
            <History className="h-3.5 w-3.5" />
            Lịch sử
            {conversations.data && conversations.data.total > 0 && (
              <Badge variant="secondary" className="ml-0.5 h-4 px-1.5 text-[10px]">
                {conversations.data.total}
              </Badge>
            )}
          </Button>
          {/* Phiên chat mới — luôn hiện, không nằm trong khung lịch sử (trước đây chỉ có nút "Mới"
              bên trong khung lịch sử nên Sale không biết có chức năng này). */}
          <Button
            size="sm"
            variant="outline"
            onClick={() => void startNewChatSession()}
            title="Tạo hội thoại mới (lưu ngay vào Lịch sử)"
            className="h-7 gap-1.5 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            Phiên chat mới
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={ttsEffective?.auto_speak ? 'default' : 'outline'}
            onClick={() => setVoicePickerOpen(true)}
            title="Chọn giọng đọc câu trả lời"
            className="h-7 gap-1.5 text-xs"
          >
            <Volume2 className="h-3.5 w-3.5" />
            {ttsEffective?.auto_speak ? 'Tự đọc' : 'Giọng đọc'}
          </Button>
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
        {/* ----- LỊCH SỬ HỘI THOẠI (thanh bên) ----- */}
        {historyOpen && (
          <aside
            aria-label="Lịch sử hội thoại Copilot"
            className="flex w-56 shrink-0 flex-col border-r border-border bg-muted/20"
          >
            <div className="flex items-center justify-between border-b border-border/70 px-3 py-2">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Hội thoại đã lưu</span>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-1.5 text-[11px]"
                onClick={() => void startNewChatSession()}
                title="Tạo hội thoại mới (lưu ngay vào Lịch sử)"
              >
                <Plus className="mr-1 h-3 w-3" /> Mới
              </Button>
            </div>
            <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
              {conversations.isLoading && <p className="px-1 py-2 text-[11px] text-muted-foreground">Đang tải lịch sử…</p>}
              {conversations.isError && (
                <p className="px-1 py-2 text-[11px] text-destructive">Không tải được lịch sử. Anh thử lại sau giúp em.</p>
              )}
              {conversations.data && conversations.data.items.length === 0 && (
                <p className="px-1 py-2 text-[11px] text-muted-foreground">
                  Chưa có hội thoại nào. Hội thoại sẽ được lưu tự động và xem lại được sau khi đổi trang.
                </p>
              )}
              {conversations.data?.items.map((c) => (
                <div
                  key={c.conversation_id}
                  className={cn(
                    'group cursor-pointer rounded-lg border px-2 py-1.5 transition-colors',
                    c.conversation_id === conversationId
                      ? 'border-primary/40 bg-primary/10'
                      : 'border-transparent hover:border-border hover:bg-muted/50',
                  )}
                  onClick={() => openConversation(c.conversation_id)}
                >
                  <div className="flex items-start justify-between gap-1">
                    <span className="line-clamp-2 text-[11px] font-medium text-foreground">{c.title}</span>
                    <button
                      type="button"
                      aria-label={`Xoá hội thoại ${c.title}`}
                      className="hidden shrink-0 rounded p-0.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive group-hover:block"
                      onClick={(e) => {
                        e.stopPropagation()
                        void handleDeleteConversation(c.conversation_id)
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground">
                    <Clock className="h-2.5 w-2.5" />
                    {clockOf(c.updated_at)}
                    <span>· {c.message_count} lượt</span>
                  </div>
                </div>
              ))}
            </div>
          </aside>
        )}

        {/* ----- AGENT CONVERSATION (MAIN) ----- */}
        <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-background">
          {/* Chat Stream Messages */}
          <div
            role="log"
            aria-live="polite"
            aria-label="Hội thoại với trợ lý Copilot"
            className="min-h-0 flex-1 space-y-3.5 overflow-y-auto p-4 scroll-smooth"
          >
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
                      <FormattedAiMessage
                        content={m.text || ''}
                        onCommandClick={(cmd) => triggerSmartAction(cmd)}
                        anchors={(m.data?.anchors as CopilotAnchor[] | undefined) ?? []}
                        onAnchorClick={(anchor) => {
                          // Chốt P2.1: bấm [n] mở đúng căn cứ — nguồn là citation thứ `citation_index`.
                          const meta = (m.data?.anchors as CopilotAnchor[] | undefined)?.find(
                            (a) => a.index === anchor.index,
                          )
                          const citations = (m.data?.citations as CopilotCitation[] | undefined) ?? []
                          const citation = meta ? citations[meta.citation_index] : undefined
                          if (citation) setEvidenceDetail(citationToEvidence(citation))
                          else showToast('Chưa tìm thấy căn cứ cho mỏ neo này.')
                        }}
                      />
                      {Array.isArray(m.data?.citations) && m.data.citations.length > 0 && (
                        <CitationChips
                          citations={m.data.citations as CopilotCitation[]}
                          onOpen={(citation) => setEvidenceDetail(citationToEvidence(citation))}
                        />
                      )}
                      {/* Mốc thời gian dữ liệu (chốt P1.6): hiển thị ở chrome giao diện, KHÔNG nằm trong
                          văn phong câu trả lời để Sale copy gửi khách được nguyên văn. */}
                      {m.data?.data_as_of && (
                        <div className="mt-1 text-[10px] text-muted-foreground/80 select-none">
                          Dữ liệu cập nhật: {dataAsOfLabel(m.data.data_as_of as string)}
                        </div>
                      )}
                      <div className="mt-1.5 flex items-center gap-2 border-t border-border/60 pt-1.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          className={cn(
                            'h-6 gap-1 px-2 text-[11px] text-muted-foreground hover:text-foreground',
                            speakingId === m.id && 'text-primary',
                          )}
                          title={speakingId === m.id ? 'Dừng đọc' : 'Đọc câu trả lời thành tiếng'}
                          onClick={() => handleSpeak(m.id, m.text || '')}
                        >
                          {speakingId === m.id ? (
                            <>
                              <Square className="h-3 w-3" /> Dừng đọc
                            </>
                          ) : (
                            <>
                              <Volume2 className="h-3 w-3" /> Đọc
                            </>
                          )}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 gap-1 px-2 text-[11px] text-muted-foreground hover:text-foreground"
                          title="Sao chép bản sạch để gửi khách (bỏ mỏ neo và ghi chú nội bộ)"
                          onClick={() => {
                            // Chốt P2.4/K2: nội dung gửi khách phải sạch — bỏ mỏ neo [n], nhãn
                            // "(ngân sách anh/chị nhập)" và ký hiệu markdown.
                            void navigator.clipboard
                              ?.writeText(customerReadyText(m.text || ''))
                              .then(() => showToast('Đã sao chép bản gửi khách (đã bỏ mỏ neo nội bộ).'))
                              .catch(() => showToast('Trình duyệt chặn sao chép — anh/chị chọn và copy thủ công.'))
                          }}
                        >
                          <Copy className="h-3 w-3" /> Copy cho khách
                        </Button>
                        {/* Gợi ý phím Enter/Ctrl+Enter đã bỏ theo yêu cầu — chỉ còn trạng thái tự đọc.
                            Phím tắt vẫn giữ nguyên (Enter gửi, Ctrl+Enter xuống dòng). */}
                        {ttsEffective?.auto_speak && (
                          <span className="text-[10px] text-muted-foreground">Đang tự đọc câu trả lời mới</span>
                        )}
                      </div>
                    </div>
                    {/* Ghi chú kiểm duyệt nội bộ (chốt P2.4): tách khỏi nội dung trả lời, hiện ở
                        banner riêng — Sale copy nội dung gửi khách không dính câu quy trình. */}
                    {(() => {
                      // MỘT khối ghi chú nội bộ duy nhất: cảnh báo số liệu (internal_notes) + lời nhắc
                      // phát ngôn của critic. Trước đây là 2–3 dòng rải rác làm câu trả lời trông hỏng.
                      const notes = String(m.data?.internal_notes || '').trim()
                      const hints: string[] =
                        m.data?.critique && m.data.critique.ok === false
                          ? (m.data.critique.hints as string[] | undefined)?.length
                            ? (m.data.critique.hints as string[])
                            : ['câu trả lời cần chỉnh lại trước khi gửi khách']
                          : []
                      if (!notes && hints.length === 0) return null
                      return (
                        <div
                          role="status"
                          className="max-w-[92%] flex items-start gap-1.5 rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 text-[11px] text-foreground"
                        >
                          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-600" />
                          <div className="space-y-0.5">
                            <span className="font-semibold">Ghi chú nội bộ (không gửi khách):</span>
                            {notes && <p>{notes}</p>}
                            {hints.map((hint, hIdx) => (
                              <p key={hIdx}>• {hint}</p>
                            ))}
                          </div>
                        </div>
                      )
                    })()}
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
                    {/* Critic vòng 2: lời nhắc đã được gộp vào banner "Ghi chú nội bộ" phía trên —
                        hiển thị lần nữa ở đây sẽ thành hai khối cảnh báo trùng nhau. */}
                    <div className="ml-1 flex items-center gap-2">
                      <span className="text-[10px] text-muted-foreground">Trợ lý AI · {m.time}</span>
                      {m.type === 'agent' && !m.id.startsWith('agent-critic') && (
                        <>
                          <button
                            type="button"
                            title="Câu trả lời hữu ích"
                            aria-label="Đánh giá hữu ích"
                            disabled={Boolean(m.data?.feedbackGiven)}
                            onClick={() => handleCopilotFeedback(m, 1)}
                            className={cn(
                              'rounded p-0.5 transition-colors hover:text-success',
                              m.data?.feedbackGiven === 1 ? 'text-success' : 'text-muted-foreground',
                            )}
                          >
                            <ThumbsUp className="h-3 w-3" />
                          </button>
                          <button
                            type="button"
                            title="Câu trả lời chưa đạt"
                            aria-label="Đánh giá chưa đạt"
                            disabled={Boolean(m.data?.feedbackGiven)}
                            onClick={() => handleCopilotFeedback(m, -1)}
                            className={cn(
                              'rounded p-0.5 transition-colors hover:text-destructive',
                              m.data?.feedbackGiven === -1 ? 'text-destructive' : 'text-muted-foreground',
                            )}
                          >
                            <ThumbsDown className="h-3 w-3" />
                          </button>
                          {m.data?.feedbackGiven && (
                            <span className="text-[10px] text-muted-foreground">đã ghi nhận cảm ơn anh/chị</span>
                          )}
                        </>
                      )}
                    </div>
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

              if (m.type === 'reasoning') {
                const steps = (m.data?.steps || []) as CopilotReasoningStep[]
                return (
                  <ReasoningTrace
                    key={m.id}
                    steps={steps}
                    streaming={Boolean(m.data?.streaming)}
                    degraded={Boolean(m.data?.degraded)}
                    error={(m.data?.error as string | null) ?? null}
                    onRetry={() => copilot.retry()}
                    onOpenCitation={(citation) => setEvidenceDetail(citationToEvidence(citation))}
                    compact
                  />
                )
              }

              if (m.type === 'stepper') {
                const current = m.data?.current || 0
                const failed = Boolean(m.data?.failed)
                return (
                  <div
                    key={m.id}
                    role="status"
                    aria-live="polite"
                    className={cn(
                      'flex flex-wrap gap-1.5 rounded-xl border bg-card p-3 shadow-xs',
                      failed ? 'border-destructive/40' : 'border-border',
                    )}
                  >
                    {m.data?.steps.map((st: string, idx: number) => {
                      const isFailed = failed && idx === current
                      const isDone = idx < current && !isFailed
                      const isRun = idx === current && !failed
                      return (
                        <span
                          key={st}
                          className={cn(
                            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all',
                            isFailed
                              ? 'bg-destructive/10 text-destructive border border-destructive/30 font-semibold'
                              : isDone
                              ? 'bg-success/10 text-success border border-success/30 font-semibold'
                              : isRun
                              ? 'bg-primary/10 text-primary border border-primary/30 font-semibold animate-pulse'
                              : 'bg-muted text-muted-foreground',
                          )}
                        >
                          {isFailed ? (
                            <AlertTriangle className="h-3 w-3" />
                          ) : isDone ? (
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
                          onClick={handleRequestRevision}
                          className="h-7 text-xs border-border bg-card text-foreground hover:text-destructive"
                        >
                          <RotateCcw className="mr-1 h-3.5 w-3.5" />
                          {undoActive ? `Yêu cầu sửa (${undoSeconds}s)` : 'Đã khóa'}
                        </Button>
                        <span className="text-[11px] text-muted-foreground">
                          {undoActive ? 'Gửi yêu cầu sửa cho quản lý trong 8s' : 'Hồ sơ đang chờ quản lý xử lý'}
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
                      <FormattedAiMessage content={m.data?.message || ''} className="text-[11.5px]" />
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
                      onGenerateQuote={() => {
                        const code = m.data?.unit_code || undefined
                        startQuoteCreationFlow(selectedLead?.customer.full_name, code)
                        handleConfirmQuoteAction(code)
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
                      onSelectScenario={() => {
                        // Thẻ so sánh phương án biết mã căn ⇒ chuyển thẳng mã đó vào luồng tạo báo giá.
                        const code = m.data?.unit_code || undefined
                        startQuoteCreationFlow(selectedLead?.customer.full_name, code)
                        handleConfirmQuoteAction(code)
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
          <div className="sticky bottom-0 z-10 relative shrink-0 border-t border-border bg-card p-3 shadow-xs">
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
            {/* Ngữ cảnh gửi kèm (D2) — Sale thấy đúng căn/hồ sơ/ngày trước khi hỏi */}
            <CopilotContextChips
              value={{
                unitCode: copilotUnit,
                dossierLabel: (contextLeadId !== 'auto' ? selectedLead?.customer.full_name : null) ?? null,
                transactionDate: copilotTxDate,
                projectLabel: selectedLead ? PROJECT_LABEL[selectedLead.constraints?.project_id ?? ''] ?? null : null,
              }}
              onClearUnit={() => setCopilotUnit(null)}
              onClearDossier={() => {
                setContextLeadId('none')
                setSelectedLeadId(null)
              }}
              onTransactionDateChange={setCopilotTxDate}
            />

            {/* Banner lỗi + thử lại (C4) — mọi lỗi mạng đều có đường thoát */}
            {(copilot.error || failedTurn) && (
              <div
                role="alert"
                className="mb-2 flex items-center justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-[11.5px] text-foreground"
              >
                <span className="flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-destructive" />
                  {copilot.error ? `Trợ lý gián đoạn: ${copilot.error}` : 'Lượt trả lời trước bị gián đoạn.'}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 shrink-0 px-2 text-[11px]"
                  onClick={handleRetryFailedTurn}
                  disabled={!failedTurn || copilot.streaming}
                >
                  <RefreshCw className="mr-1 h-3 w-3" /> Thử lại
                </Button>
              </div>
            )}

            {/* Input & Send Action */}
            <div className="relative flex items-center gap-2">
              <SlashCommandPalette
                open={slashOpen}
                commands={SLASH_COMMANDS}
                query={inputVal}
                recent={recentCommands}
                activeIndex={slashIndex}
                onActiveIndexChange={setSlashIndex}
                onSelect={(command) => handleExecuteSlash(command.cmd)}
              />
              <textarea
                ref={inputTextAreaRef}
                value={inputVal}
                onChange={(e) => {
                  const next = e.target.value
                  setInputVal(next)
                  setSlashOpen(next.startsWith('/'))
                }}
                onKeyDown={(e) => {
                  // Enter = gửi nhanh. Ctrl/Cmd + Enter = xuống dòng (soạn câu nhiều dòng).
                  // Ngoại lệ: khi menu lệnh gạch chéo đang mở, Enter để CHỌN lệnh — người dùng
                  // đang chọn trong danh sách chứ chưa gửi.
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault()
                    const el = e.currentTarget
                    const start = el.selectionStart ?? inputVal.length
                    const end = el.selectionEnd ?? start
                    const next = `${inputVal.slice(0, start)}\n${inputVal.slice(end)}`
                    setInputVal(next)
                    requestAnimationFrame(() => {
                      el.selectionStart = el.selectionEnd = start + 1
                    })
                    return
                  }
                  // Điều hướng menu gạch chéo bằng bàn phím (↑/↓/Enter/Esc).
                  if (slashOpen && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
                    e.preventDefault()
                    setSlashIndex((idx) =>
                      e.key === 'ArrowDown'
                        ? (idx + 1) % Math.max(filteredCommands.length, 1)
                        : (idx - 1 + filteredCommands.length) % Math.max(filteredCommands.length, 1),
                    )
                    return
                  }
                  if (slashOpen && e.key === 'Enter' && !e.shiftKey && filteredCommands[slashIndex]) {
                    e.preventDefault()
                    handleExecuteSlash(filteredCommands[slashIndex].cmd)
                    return
                  }
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendChatMessage()
                    return
                  }
                  if (e.key === 'Escape') {
                    e.preventDefault()
                    setSlashOpen(false)
                  }
                }}
                rows={1}
                aria-label="Nhập yêu cầu cho trợ lý Copilot"
                placeholder="Ra lệnh cho Copilot…"
                className="max-h-24 flex-1 resize-none rounded-xl border border-input bg-background px-3.5 py-2 text-xs leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              {/* Nhập bằng giọng nói: bật là nghe liên tục (rảnh tay) cho tới khi bấm dừng. */}
              <Button
                type="button"
                size="sm"
                variant={sttListening ? 'default' : 'outline'}
                onClick={toggleVoiceInput}
                disabled={copilot.streaming}
                className={cn('h-9 px-3', sttListening && 'animate-pulse')}
                title={
                  !sttSupported
                    ? SPEECH_TO_TEXT_UNSUPPORTED_MESSAGE
                    : sttListening
                      ? 'Đang nghe — bấm để dừng'
                      : 'Nói để nhập câu hỏi (rảnh tay)'
                }
                aria-label={sttListening ? 'Dừng nhập bằng giọng nói' : 'Nhập bằng giọng nói'}
                aria-pressed={sttListening}
              >
                {sttListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </Button>
              {copilot.streaming ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    copilot.cancel()
                    showToast('Đã dừng yêu cầu cho trợ lý')
                  }}
                  className="h-9 px-3"
                  title="Dừng suy luận"
                >
                  <X className="h-4 w-4" />
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  onClick={handleSendChatMessage}
                  className="h-9 px-3"
                  aria-label="Gửi yêu cầu"
                >
                  <Send className="h-4 w-4" />
                </Button>
              )}
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

                <QueryState
                  query={leadsQuery}
                  isEmpty={(data) => data.length === 0}
                  loadingLabel="Đang tải danh sách khách hàng…"
                  className="py-12"
                  empty={
                    <EmptyState
                      icon={Inbox}
                      title="Chưa có hồ sơ khách hàng mới"
                      description="Khi khách để lại thông tin ở kênh Pre-Sales, hồ sơ sẽ tự chảy về đây trong vòng 15 phút."
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
                  }
                >
                  {(data) => (
                  <div className="space-y-2">
                    {data.map((l) => (
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
                </QueryState>
              </div>
            )}

            {/* TAB HỒ SƠ: DOSSIER DETAIL — chưa chọn hồ sơ thì nói rõ, không để panel trống */}
            {activeTab === 'hoso' && panelView === 'dossier' && !selectedLead && (
              <EmptyState
                icon={Users}
                title="Chưa chọn hồ sơ khách hàng"
                description="Chọn một hồ sơ ở danh sách bên cạnh để xem ràng buộc tài chính và tiến trình chăm sóc."
                action={
                  <Button size="sm" variant="outline" onClick={() => setPanelView('leads')}>
                    Xem danh sách khách hàng
                  </Button>
                }
              />
            )}
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

                <QueryState
                  query={quotesQuery}
                  isEmpty={(data) => data.length === 0}
                  loadingLabel="Đang tải pipeline báo giá…"
                  className="py-12"
                  empty={
                    <EmptyState
                      icon={FileText}
                      title="Pipeline chưa có báo giá nào"
                      description="Lập báo giá cho một hồ sơ khách hàng, hồ sơ sẽ xuất hiện ở đây theo từng trạng thái."
                    />
                  }
                >
                {() => (
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
                )}
                </QueryState>
              </div>
            )}

            {/* TAB BÁO GIÁ: 3-PLAN COMPARISON TABLE */}
            {activeTab === 'baogia' && panelView === 'quote_comparison' && quotesQuery.isLoading && (
              <LoadingState label="Đang tải bảng phương án…" className="py-12" />
            )}

            {activeTab === 'baogia' && panelView === 'quote_comparison' && quotesQuery.error && quotes.length === 0 && (
              <ErrorState error={quotesQuery.error} onRetry={() => void quotesQuery.refetch()} />
            )}

            {activeTab === 'baogia' && panelView === 'quote_comparison' && !quotesQuery.isLoading && !(quotesQuery.error && quotes.length === 0) && quotes.length === 0 && (
              <EmptyState
                icon={FileText}
                title="Chưa có bảng phương án để so sánh"
                description="Bảng so sánh chỉ hiện khi đã có ít nhất một báo giá cho hồ sơ khách hàng."
                action={
                  <Button size="sm" onClick={() => setPanelView('pipeline')}>
                    Về pipeline báo giá
                  </Button>
                }
              />
            )}

            {activeTab === 'baogia' && panelView === 'quote_comparison' && quotes.length > 0 && (
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
                    {isCheckingCompliance ? 'F8 đang kiểm…' : complianceOffline ? 'F8 · chế độ dự phòng' : 'Live-check F8 (500ms)'}
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

                {complianceOffline && (
                  <div role="alert" className="flex items-center gap-1.5 rounded-lg border border-warning/40 bg-warning/10 px-2.5 py-1.5 text-[11px] text-foreground">
                    <AlertTriangle className="h-3 w-3 shrink-0 text-warning" />
                    Chưa gọi được máy chủ kiểm duyệt — đang dùng bộ luật dự phòng tại máy. Kết quả có thể thiếu.
                  </div>
                )}

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

                <QueryState
                  query={policiesQuery}
                  isEmpty={(data) => data.length === 0}
                  loadingLabel="Đang tải chính sách bán hàng…"
                  className="py-12"
                  empty={
                    <EmptyState
                      icon={ScrollText}
                      title="Chưa có dữ liệu chính sách bán hàng"
                      description="Chạy `python scripts/seed_data.py` hoặc kiểm tra kết nối máy chủ để nạp danh mục chính sách."
                    />
                  }
                >
                  {(data) => (
                  <div className="space-y-2">
                    {data.map((p) => (
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
                </QueryState>
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

      {/* ================= MODAL: CĂN CỨ ĐỘNG TỪ COPILOT ================= */}
      {evidenceDetail && (
        <div
          onClick={() => setEvidenceDetail(null)}
          className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4 backdrop-blur-xs"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Căn cứ pháp lý từ Copilot"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md overflow-hidden rounded-xl border border-border bg-card text-xs shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-3">
              <span className="font-semibold text-foreground">🔗 Căn cứ pháp lý</span>
              <button
                type="button"
                onClick={() => setEvidenceDetail(null)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Đóng"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-3 p-4">
              <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 leading-relaxed text-foreground">
                “{evidenceDetail.q}”
              </div>
              <div className="divide-y divide-border text-[11.5px]">
                <div className="flex justify-between gap-3 py-1.5">
                  <span className="shrink-0 text-muted-foreground">Văn bản:</span>
                  <span className="text-right font-semibold text-foreground">{evidenceDetail.p}</span>
                </div>
                <div className="flex justify-between gap-3 py-1.5">
                  <span className="shrink-0 text-muted-foreground">Hiệu lực / nguồn:</span>
                  <span className="text-right font-semibold text-foreground">{evidenceDetail.e}</span>
                </div>
                {evidenceDetail.clause && (
                  <div className="flex justify-between gap-3 py-1.5">
                    <span className="shrink-0 text-muted-foreground">Điều / khoản:</span>
                    <span className="text-right font-semibold text-foreground">{evidenceDetail.clause}</span>
                  </div>
                )}
                <div className="flex justify-between gap-3 py-1.5">
                  <span className="shrink-0 text-muted-foreground">Mã đối soát (hash):</span>
                  <span className="text-right font-mono text-foreground">{evidenceDetail.h}</span>
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between gap-2 border-t border-border p-3">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  const parts = [`Trích dẫn: ${evidenceDetail.q}`, `Văn bản: ${evidenceDetail.p}`, `Hiệu lực/nguồn: ${evidenceDetail.e}`]
                  if (evidenceDetail.clause) parts.push(`Điều/khoản: ${evidenceDetail.clause}`)
                  if (evidenceDetail.hash) parts.push(`Hash tài liệu: ${evidenceDetail.hash}`)
                  void navigator.clipboard?.writeText(parts.join('\n')).then(
                    () => showToast('Đã sao chép căn cứ kèm hash đối soát'),
                    () => showToast('Trình duyệt chặn clipboard — anh/chị sao chép thủ công'),
                  )
                }}
              >
                <Copy className="mr-1.5 h-3.5 w-3.5" /> Sao chép căn cứ
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setEvidenceDetail(null)}>
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
              executeCustomerCreation({
                ...customerForm,
                project_id: customerForm.project_id || projects[0]?.project.project_id || undefined,
              })
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
                  value={customerForm.project_id || projects[0]?.project.project_id || ''}
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
                      // Không hardcode tên dự án: dự án hiển thị phải có thật trong danh mục.
                      <SelectItem value="__none" disabled>
                        Chưa tải được danh mục dự án
                      </SelectItem>
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
                  placeholder="Ví dụ: ZEN-A-1205"
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

      {/* ================= GIỌNG ĐỌC CÂU TRẢ LỜI (TTS) ================= */}
      <Dialog open={voicePickerOpen} onOpenChange={setVoicePickerOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Volume2 className="h-5 w-5" /> Giọng đọc câu trả lời
            </DialogTitle>
            <DialogDescription>
              Copilot đọc câu trả lời thành tiếng để anh/chị không phải rời mắt khỏi khách. Mặc định dùng
              giọng có sẵn trên máy (0 đồng); khi Admin khai báo nhà cung cấp TTS, cả công ty đọc cùng một giọng.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 text-sm">
            <label className="flex items-center justify-between gap-3 rounded-lg border border-border p-3">
              <span>
                <span className="block font-medium">Tự đọc mỗi câu trả lời mới</span>
                <span className="block text-xs text-muted-foreground">
                  Chế độ rảnh tay — tiện khi đang dẫn khách xem căn hộ.
                </span>
              </span>
              <input
                type="checkbox"
                className="h-4 w-4"
                checked={Boolean(ttsEffective?.auto_speak)}
                onChange={(e) => void saveTts({ auto_speak: e.target.checked })}
              />
            </label>

            <div className="space-y-1.5">
              <Label>Nhà cung cấp giọng đọc</Label>
              <select
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                value={ttsEffective?.provider ?? 'browser'}
                onChange={(e) => {
                  const provider = tts?.catalog.find((c) => c.provider === e.target.value)
                  void saveTts({
                    provider: e.target.value,
                    voice: provider?.voices[0]?.code ?? 'vi-VN',
                    model: provider?.default_model ?? '',
                  })
                }}
              >
                {(tts?.catalog ?? []).map((c) => (
                  <option key={c.provider} value={c.provider}>
                    {c.label}
                    {c.mode === 'api' ? (c.api_key_configured ? ' — đã có khoá' : ' — chưa có khoá') : ' — miễn phí'}
                  </option>
                ))}
              </select>
              {ttsProvider && (
                <p className="text-[11px] text-muted-foreground">
                  {ttsProvider.price_per_1m_chars > 0
                    ? `Đơn giá ${ttsProvider.price_per_1m_chars.toLocaleString('vi-VN')} ${ttsProvider.currency}/1 triệu ký tự · kiểm chứng ${ttsProvider.verified_at}`
                    : 'Không phát sinh chi phí.'}{' '}
                  {ttsProvider.mode === 'api' && !ttsProvider.api_key_configured
                    ? 'Chưa có khoá cho nhà cung cấp này — quản trị viên khai báo ở Quản trị CP → Giọng đọc → Nhà cung cấp TTS (hoặc ENV của máy chủ).'
                    : ''}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label>Giọng đọc</Label>
              <select
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                value={ttsEffective?.voice ?? ''}
                onChange={(e) => void saveTts({ voice: e.target.value })}
              >
                {(ttsProvider?.voices ?? []).map((v) => (
                  <option key={v.code} value={v.code}>
                    {v.label}
                  </option>
                ))}
                {localVoices.map((v) => (
                  <option key={`local-${v.code}`} value={v.code}>
                    {v.label} (trên máy này)
                  </option>
                ))}
              </select>
              {localVoices.length === 0 && (
                <p className="text-[11px] text-amber-600">
                  Máy này chưa có giọng tiếng Việt — cài trong Cài đặt hệ thống để nghe đúng tiếng Việt.
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label>Tốc độ đọc: {ttsEffective?.speed?.toFixed(2) ?? '1.00'}×</Label>
              <input
                type="range"
                min={0.5}
                max={2}
                step={0.05}
                value={ttsEffective?.speed ?? 1}
                onChange={(e) => void saveTts({ speed: Number(e.target.value) })}
                className="w-full"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/40 p-3 text-xs">
              <Button size="sm" variant="outline" className="h-7 gap-1" onClick={() => handleSpeak('preview', 'Dạ, chính sách đang hiệu lực là CSBH The Zen Park, chiết khấu thanh toán sớm 3 phần trăm.')}>
                <Mic className="h-3.5 w-3.5" /> Nghe thử
              </Button>
              <span className="text-muted-foreground">
                Chi phí tối đa mỗi lượt đọc:{' '}
                <strong>
                  {tts ? `${tts.cost_hint.cost.toLocaleString('vi-VN', { maximumFractionDigits: 4 })} ${tts.cost_hint.currency}` : '—'}
                </strong>
                {tts && tts.cost_hint.chars > 0 ? ` cho ${tts.cost_hint.chars} ký tự` : ''}
              </span>
              <span className="ml-auto flex items-center gap-1">
                <span className="text-muted-foreground">Giọng này ổn không?</span>
                <Button size="sm" variant="ghost" className="h-6 px-1.5" title="Nghe ổn" onClick={() => void rateVoice(1)}>
                  👍
                </Button>
                <Button size="sm" variant="ghost" className="h-6 px-1.5" title="Nghe chưa ổn" onClick={() => void rateVoice(-1)}>
                  👎
                </Button>
              </span>
            </div>

            {tts?.feedback_summary.total ? (
              <p className="text-[11px] text-muted-foreground">
                Giọng này được đánh giá: {tts.feedback_summary.up} ổn / {tts.feedback_summary.down} chưa ổn
                {tts.feedback_summary.satisfaction != null
                  ? ` (${Math.round(tts.feedback_summary.satisfaction * 100)}% hài lòng)`
                  : ''}
                .
              </p>
            ) : null}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setVoicePickerOpen(false)}>
              Đóng
            </Button>
          </DialogFooter>
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
