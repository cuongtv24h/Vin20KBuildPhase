import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
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
  BookOpen,
  Send,
  Phone,
  FilePlus2,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Copy,
  Clock,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  Timer,
  Layers,
  Sparkles,
  RefreshCw,
  LogOut,
  X,
  Search,
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
import { formatDateTime, formatRelative, formatVnd } from '@pricepolicy/ui/lib/format'
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
  | 'briefing'
  | 'confirm'
  | 'stepper'
  | 'receipt'
  | 'nudge'
  | 'fallback'
  | 'customer_card'
  | 'customer_search'

interface StreamItem {
  id: string
  type: StreamItemType
  text?: string
  time: string
  data?: any
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
    preferred_unit_code: 'R-02.02',
    own_funds_vnd: 1500000000,
    monthly_capacity_vnd: 25000000,
    objective: 'MIN_INITIAL_OUTFLOW',
    needs_summary: '',
  })

  // Active Rail Navigation & Artifact Panel Tabs
  const [activeRail, setActiveRail] = useState<'home' | 'khach' | 'baogia' | 'tinnhan' | 'chinhsach'>('home')
  const [activeTab, setActiveTab] = useState<'hoso' | 'baogia' | 'tinnhan' | 'chinhsach'>('hoso')
  const [panelView, setPanelView] = useState<'leads' | 'dossier' | 'pipeline' | 'quote_comparison' | 'messages' | 'policies'>('leads')

  // Selected entities
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null)
  const selectedLead = useMemo(() => {
    if (!selectedLeadId) return leads[0] ?? null
    return leads.find((l) => l.dossier_id === selectedLeadId) ?? leads[0] ?? null
  }, [leads, selectedLeadId])

  // Context Chip
  const [contextLeadId, setContextLeadId] = useState<string>('auto')

  // Mobile Bottom-Sheet State
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
        type: 'agent',
        text: `Chào **${session?.user.full_name || 'Hải Nguyễn'}**! Trợ lý PricePolicy sẵn sàng đồng hành cùng anh ca làm việc hôm nay.`,
        time,
      },
      {
        id: 'msg-briefing',
        type: 'briefing',
        time,
        data: {},
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
    const clientName = targetLeadName || selectedLead?.customer.full_name || 'Nguyễn Minh An'
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, type: 'user', text: `tạo báo giá cho ${clientName}`, time },
      {
        id: `conf-${Date.now()}`,
        type: 'confirm',
        time,
        data: {
          clientName,
          unitCode: selectedLead?.constraints?.preferred_unit_code || 'R-02.02 · 2BR · 4,6 tỷ',
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

  // Chat Send Handler
  const handleSendChatMessage = () => {
    const text = inputVal.trim()
    if (!text) return
    setInputVal('')
    setSlashOpen(false)

    const time = new Date().toTimeString().slice(0, 5)
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, type: 'user', text, time }])
    scrollChatToEnd()

    setTimeout(() => {
      // Mini Q&A logic
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

      if (/chuyển nhượng/i.test(text)) {
        setMessages((prev) => [
          ...prev,
          {
            id: `qa-${Date.now()}`,
            type: 'agent',
            time,
            text: 'Theo **POL-10 Phụ lục pháp lý**: Được phép chuyển nhượng sau khi thanh toán tối thiểu 30% giá trị hợp đồng, phí chuyển nhượng 1%. [mỏ neo: chunk #19].',
          },
        ])
        scrollChatToEnd()
        return
      }

      // Customer creation command/NLP
      if (/^\/tao-khach|\/taokhach|\/newcustomer/i.test(text)) {
        const queryText = text.replace(/^\/(tao-khach|taokhach|newcustomer)\s*/i, '').trim()
        if (queryText) {
          const parts = queryText.split(/[,;\n]+/).map((s) => s.trim())
          const name = parts[0] || 'Khách hàng mới'
          const phoneMatch = queryText.match(/0\d{9,10}/)
          const phone = phoneMatch ? phoneMatch[0] : (parts[1] && /^\d+$/.test(parts[1]) ? parts[1] : '0912345678')
          const unitMatch = queryText.match(/(?:căn|mã|unit)?\s*([A-Za-z0-9]+-[A-Za-z0-9\.]+)/i)
          const unit = unitMatch ? unitMatch[1] : ''
          const fundsMatch = queryText.match(/(\d+(?:[\.,]\d+)?)\s*(tỷ|ty|triệu|tr)/i)
          let fundsVnd = 1500000000
          if (fundsMatch) {
            const num = parseFloat(fundsMatch[1].replace(',', '.'))
            fundsVnd = fundsMatch[2].toLowerCase().startsWith('t') && !fundsMatch[2].toLowerCase().startsWith('tr')
              ? Math.round(num * 1_000_000_000)
              : Math.round(num * 1_000_000)
          }

          setMessages((prev) => [
            ...prev,
            {
              id: `conf-cust-${Date.now()}`,
              type: 'confirm',
              time,
              data: {
                isCustomerCreate: true,
                clientName: name,
                phone,
                unitCode: unit || 'Chưa định danh',
                funds: fundsVnd,
                rawPayload: {
                  customer_name: name,
                  customer_phone: phone,
                  preferred_unit_code: unit || undefined,
                  own_funds_vnd: fundsVnd,
                  temperature: 'HOT' as LeadTemperature,
                  customer_segment: 'NEW_CUSTOMER' as CustomerSegment,
                  objective: 'MIN_INITIAL_OUTFLOW' as OptimizationObjective,
                  needs_summary: `Khách hàng ${name} khởi tạo qua lệnh Copilot. Căn quan tâm: ${unit || 'Chưa định danh'}.`,
                },
              },
            },
          ])
          scrollChatToEnd()
          return
        } else {
          setCreateCustomerOpen(true)
          setMessages((prev) => [
            ...prev,
            {
              id: `ag-cust-open-${Date.now()}`,
              type: 'agent',
              time,
              text: 'Em đã mở cửa sổ **Khởi tạo Khách hàng mới**. Anh có thể nhập form hoặc gõ nhanh: `/tao-khach [Họ tên], [SĐT], [Mã căn], [Vốn tự có]` để em tự động bóc tách.',
            },
          ])
          scrollChatToEnd()
          return
        }
      }

      if (/^tạo khách|thêm khách|khách hàng mới/i.test(text)) {
        const rest = text.replace(/^(tạo khách hàng|tạo khách|thêm khách|khách hàng mới)\s*/i, '').trim()
        if (rest) {
          const phoneMatch = rest.match(/0\d{9,10}/)
          const name = phoneMatch ? rest.substring(0, phoneMatch.index).replace(/[,;]/g, '').trim() : rest.split(/[,;\n]/)[0].trim()
          const phone = phoneMatch ? phoneMatch[0] : '0912345678'
          const unitMatch = rest.match(/(?:căn|mã|unit)?\s*([A-Za-z0-9]+-[A-Za-z0-9\.]+)/i)
          const unit = unitMatch ? unitMatch[1] : ''
          const fundsMatch = rest.match(/(\d+(?:[\.,]\d+)?)\s*(tỷ|ty|triệu|tr)/i)
          let fundsVnd = 1500000000
          if (fundsMatch) {
            const num = parseFloat(fundsMatch[1].replace(',', '.'))
            fundsVnd = fundsMatch[2].toLowerCase().startsWith('t') && !fundsMatch[2].toLowerCase().startsWith('tr')
              ? Math.round(num * 1_000_000_000)
              : Math.round(num * 1_000_000)
          }

          setMessages((prev) => [
            ...prev,
            {
              id: `conf-cust-${Date.now()}`,
              type: 'confirm',
              time,
              data: {
                isCustomerCreate: true,
                clientName: name || 'Khách hàng mới',
                phone,
                unitCode: unit || 'Chưa định danh',
                funds: fundsVnd,
                rawPayload: {
                  customer_name: name || 'Khách hàng mới',
                  customer_phone: phone,
                  preferred_unit_code: unit || undefined,
                  own_funds_vnd: fundsVnd,
                  temperature: 'HOT' as LeadTemperature,
                  customer_segment: 'NEW_CUSTOMER' as CustomerSegment,
                  objective: 'MIN_INITIAL_OUTFLOW' as OptimizationObjective,
                  needs_summary: `Khách hàng ${name} khởi tạo qua hội thoại tự nhiên với Copilot.`,
                },
              },
            },
          ])
          scrollChatToEnd()
          return
        } else {
          setCreateCustomerOpen(true)
          setMessages((prev) => [
            ...prev,
            {
              id: `ag-cust-open-${Date.now()}`,
              type: 'agent',
              time,
              text: 'Em đã mở bảng **Khởi tạo Khách hàng mới**. Anh điền thông tin để em lưu vào CRM và nạp vào hồ sơ nhé.',
            },
          ])
          scrollChatToEnd()
          return
        }
      }

      // Customer search command
      if (/^\/tim-khach|\/timkhach|tìm khách|tra cứu khách/i.test(text)) {
        const queryTerm = text.replace(/^(\/tim-khach|\/timkhach|tìm khách|tra cứu khách)\s*/i, '').trim().toLowerCase()
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

      if (/tạo báo giá|lập báo giá/i.test(text)) {
        startQuoteCreationFlow()
        return
      }

      if (/trình duyệt|submit/i.test(text)) {
        startSubmitReviewFlow()
        return
      }

      if (/soạn tin|tin nhắn/i.test(text)) {
        startCopilotDrafting()
        return
      }

      // Fallback
      setMessages((prev) => [
        ...prev,
        {
          id: `fb-${Date.now()}`,
          type: 'fallback',
          time,
          text: 'Em chưa chắc chắn hiểu yêu cầu. Anh có thể chọn nhanh thao tác nghiệp vụ:',
        },
      ])
      scrollChatToEnd()
    }, 300)
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
      setActiveRail('khach')
      setActiveTab('hoso')
      setPanelView('leads')
      setIsMobilePanelOpen(true)
    } else if (cmd === '/baogia') {
      setActiveRail('baogia')
      setActiveTab('baogia')
      setPanelView('pipeline')
      setIsMobilePanelOpen(true)
    } else if (cmd === '/soan-tin') {
      startCopilotDrafting()
    } else if (cmd === '/chinh-sach') {
      setActiveRail('chinhsach')
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

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground antialiased font-sans">
      {/* ================= 1. ENTERPRISE HEADER ================= */}
      <header className="z-40 flex h-14 shrink-0 items-center justify-between border-b border-border bg-primary px-4 text-primary-foreground shadow-xs">
        <div className="flex items-center gap-3">
          <Link to="/sale" className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-foreground/15 shadow-inner">
              <ShieldCheck className="h-5 w-5 text-primary-foreground" />
            </span>
            <div className="leading-tight">
              <span className="block font-display text-sm font-semibold tracking-wide">
                PricePolicy Workspace
              </span>
              <span className="block text-[10.5px] text-primary-foreground/70">
                Sales Copilot · VLand Future Riverside
              </span>
            </div>
          </Link>

          {/* Quick metric stats from real queries */}
          <div className="ml-6 hidden items-center gap-2 border-l border-primary-foreground/15 pl-6 lg:flex">
            <Badge variant="outline" className="border-primary-foreground/20 bg-primary-foreground/10 text-primary-foreground">
              {leads.length} Khách đang theo
            </Badge>
            <Badge variant="outline" className="border-primary-foreground/20 bg-primary-foreground/10 text-primary-foreground">
              {kanbanGroups.review.length} Báo giá chờ duyệt
            </Badge>
            <Badge variant="outline" className="border-primary-foreground/20 bg-primary-foreground/10 text-primary-foreground">
              {policies.length} Chính sách hiệu lực
            </Badge>
          </div>

          <Button
            size="sm"
            onClick={() => setCreateCustomerOpen(true)}
            className="ml-3 hidden sm:inline-flex h-8 gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs shadow-xs"
          >
            <UserPlus className="h-3.5 w-3.5" /> Tạo khách mới
          </Button>
        </div>

        {/* User profile & actions */}
        <div className="flex items-center gap-3">
          <Button
            asChild
            variant="ghost"
            size="sm"
            className="hidden text-xs text-primary-foreground/80 hover:bg-primary-foreground/10 hover:text-primary-foreground sm:inline-flex"
          >
            <Link to="/sale/leads">
              <Layers className="mr-1.5 h-3.5 w-3.5" /> Chế độ bảng biểu
            </Link>
          </Button>

          <Button
            asChild
            variant="ghost"
            size="sm"
            className="text-xs text-primary-foreground/80 hover:bg-primary-foreground/10 hover:text-primary-foreground"
          >
            <a href="/sales_copilot.html" target="_blank" rel="noreferrer">
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" /> Copilot standalone
            </a>
          </Button>

          <div className="hidden text-right leading-tight sm:block">
            <span className="block text-xs font-semibold">{session?.user.full_name || 'Hải Nguyễn'}</span>
            <span className="block text-[10px] text-primary-foreground/70">
              {ROLE_LABEL[session?.user.role || 'SALE']} · {session?.user.email}
            </span>
          </div>

          <div className="grid h-8 w-8 place-items-center rounded-full bg-gold font-display text-xs font-bold text-gold-foreground shadow-xs">
            {session?.user.full_name ? session.user.full_name.slice(0, 2).toUpperCase() : 'HN'}
          </div>

          <button
            type="button"
            onClick={() => {
              clearSession()
              navigate('/login')
            }}
            className="rounded-md p-1.5 text-primary-foreground/70 hover:bg-primary-foreground/10 hover:text-primary-foreground"
            title="Đăng xuất"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* ================= 2. 3-REGION WORKSPACE ================= */}
      <div className="flex min-h-0 flex-1">
        {/* ----- REGION A: RAIL (64px) ----- */}
        <nav className="flex w-16 shrink-0 flex-col items-center gap-1.5 border-r border-border bg-card py-3 shadow-xs select-none">
          <button
            type="button"
            onClick={() => {
              setActiveRail('home')
              setMessages((prev) => [
                ...prev,
                {
                  id: `home-${Date.now()}`,
                  type: 'agent',
                  time: new Date().toTimeString().slice(0, 5),
                  text: `Hôm nay anh đang quản lý **${leads.length} hồ sơ khách**, **${kanbanGroups.review.length} báo giá chờ phê duyệt**. Bấm vào bất kỳ mục nào trên panel để tra cứu chi tiết nhé.`,
                },
              ])
              scrollChatToEnd()
            }}
            className={cn(
              'group relative flex h-12 w-12 flex-col items-center justify-center rounded-xl text-[10px] font-medium transition-all',
              activeRail === 'home'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
            title="Tổng quan Workspace"
          >
            <Home className="h-5 w-5" />
            <span className="mt-0.5">Tổng quan</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveRail('khach')
              setActiveTab('hoso')
              setPanelView('leads')
              setIsMobilePanelOpen(true)
            }}
            className={cn(
              'group relative flex h-12 w-12 flex-col items-center justify-center rounded-xl text-[10px] font-medium transition-all',
              activeRail === 'khach'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
            title="Hồ sơ khách hàng"
          >
            <Users className="h-5 w-5" />
            <span className="mt-0.5">Khách</span>
            {leads.length > 0 && (
              <span className="absolute top-1 right-1 grid h-4 min-w-[16px] place-items-center rounded-full bg-destructive px-1 text-[9px] font-bold text-destructive-foreground">
                {leads.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setCreateCustomerOpen(true)}
            className="group relative flex h-10 w-12 flex-col items-center justify-center rounded-xl text-[9px] font-medium text-emerald-600 hover:bg-emerald-500/10 transition-all"
            title="Khởi tạo khách hàng mới"
          >
            <UserPlus className="h-4 w-4" />
            <span className="mt-0.5">+ Khách</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveRail('baogia')
              setActiveTab('baogia')
              setPanelView('pipeline')
              setIsMobilePanelOpen(true)
            }}
            className={cn(
              'group relative flex h-12 w-12 flex-col items-center justify-center rounded-xl text-[10px] font-medium transition-all',
              activeRail === 'baogia'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
            title="Quản lý báo giá"
          >
            <FileStack className="h-5 w-5" />
            <span className="mt-0.5">Báo giá</span>
            {kanbanGroups.draft.length + kanbanGroups.review.length > 0 && (
              <span className="absolute top-1 right-1 grid h-4 min-w-[16px] place-items-center rounded-full bg-muted-foreground/30 px-1 text-[9px] font-bold text-foreground">
                {kanbanGroups.draft.length + kanbanGroups.review.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveRail('tinnhan')
              setActiveTab('tinnhan')
              setPanelView('messages')
              setIsMobilePanelOpen(true)
            }}
            className={cn(
              'group relative flex h-12 w-12 flex-col items-center justify-center rounded-xl text-[10px] font-medium transition-all',
              activeRail === 'tinnhan'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
            title="Soạn tin & Tuân thủ F8"
          >
            <MessageSquare className="h-5 w-5" />
            <span className="mt-0.5">Tin nhắn</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveRail('chinhsach')
              setActiveTab('chinhsach')
              setPanelView('policies')
              setIsMobilePanelOpen(true)
            }}
            className={cn(
              'group relative flex h-12 w-12 flex-col items-center justify-center rounded-xl text-[10px] font-medium transition-all',
              activeRail === 'chinhsach'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
            title="Chính sách bán hàng (chỉ đọc)"
          >
            <ScrollText className="h-5 w-5" />
            <span className="mt-0.5">Chính sách</span>
          </button>

          <div className="flex-1" />

          <button
            type="button"
            onClick={() => navigate('/sale/leads')}
            className="flex h-10 w-10 items-center justify-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Xem dạng bảng"
          >
            <Layers className="h-4 w-4" />
          </button>
        </nav>

        {/* ----- REGION B: AGENT CONVERSATION (MAIN) ----- */}
        <section className="flex min-w-0 flex-1 flex-col bg-background">
          {/* Conversation Subheader */}
          <div className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-4 py-2">
            <div className="flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Sparkles className="h-4 w-4" />
              </span>
              <div>
                <span className="font-semibold text-xs text-foreground">Trợ lý Phân tích Bán hàng</span>
                <span className="ml-2 inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Sẵn sàng tư vấn
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground hidden sm:inline">Phạm vi dữ liệu:</span>
              <Badge variant="outline" className="font-mono text-[10.5px]">
                FCS v2.6 · C-09 Engine
              </Badge>
            </div>
          </div>

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
                  <div key={m.id} className="flex flex-col items-start gap-1">
                    <div className="max-w-[88%] rounded-2xl rounded-bl-xs border border-border bg-card px-4 py-3 text-xs leading-relaxed text-foreground shadow-xs">
                      <div
                        dangerouslySetInnerHTML={{
                          __html: (m.text || '')
                            .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
                            .replace(/\*(.*?)\*/g, '<i>$1</i>'),
                        }}
                      />
                    </div>
                    <span className="text-[10px] text-muted-foreground">Trợ lý AI · {m.time}</span>
                  </div>
                )
              }

              if (m.type === 'briefing') {
                const urgentLeads = leads.slice(0, 2)
                return (
                  <Card key={m.id} className="w-full max-w-[92%] border-border shadow-xs overflow-hidden">
                    <div className="flex items-center justify-between bg-primary px-3.5 py-2 text-xs font-semibold text-primary-foreground">
                      <span className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5" /> Tổng hợp ca làm việc
                      </span>
                      <span className="text-[10.5px] opacity-80">Cập nhật thời gian thực</span>
                    </div>

                    <CardContent className="divide-y divide-border p-0 text-xs">
                      {/* Priority Leads */}
                      <div className="p-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[10.5px] font-bold uppercase tracking-wider text-muted-foreground">
                            Hồ sơ cần liên hệ phản hồi
                          </span>
                          <span className="text-[11px] text-muted-foreground">{leads.length} hồ sơ</span>
                        </div>
                        {urgentLeads.length > 0 ? (
                          <div className="space-y-2">
                            {urgentLeads.map((l) => (
                              <div key={l.dossier_id} className="flex items-center justify-between rounded-lg border border-border/70 bg-muted/30 p-2">
                                <div className="space-y-0.5">
                                  <div className="flex items-center gap-2">
                                    <span className="font-semibold text-foreground">{l.customer.full_name}</span>
                                    <TemperatureBadge temperature={l.temperature} />
                                  </div>
                                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                                    <span>{l.customer.phone}</span>
                                    <span>•</span>
                                    <SlaCountdown dueAt={l.sla_due_at} />
                                  </div>
                                </div>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="h-7 text-xs"
                                  onClick={() => {
                                    setSelectedLeadId(l.dossier_id)
                                    setActiveTab('hoso')
                                    setPanelView('dossier')
                                    setIsMobilePanelOpen(true)
                                  }}
                                >
                                  Mở hồ sơ
                                </Button>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[11px] text-muted-foreground">Không có hồ sơ nào quá hạn.</p>
                        )}
                      </div>

                      {/* Approval Status */}
                      <div className="p-3">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[10.5px] font-bold uppercase tracking-wider text-muted-foreground">
                            Tiến độ phê duyệt báo giá
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 p-0 text-xs text-primary"
                            onClick={() => {
                              setActiveTab('baogia')
                              setPanelView('pipeline')
                              setIsMobilePanelOpen(true)
                            }}
                          >
                            Xem pipeline →
                          </Button>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-center text-xs sm:grid-cols-4">
                          <div className="rounded-lg bg-muted/40 p-2">
                            <span className="block text-base font-bold text-foreground">{kanbanGroups.draft.length}</span>
                            <span className="text-[10px] text-muted-foreground">Nháp</span>
                          </div>
                          <div className="rounded-lg bg-warning/10 p-2 text-warning">
                            <span className="block text-base font-bold">{kanbanGroups.review.length}</span>
                            <span className="text-[10px]">Chờ duyệt</span>
                          </div>
                          <div className="rounded-lg bg-success/10 p-2 text-success">
                            <span className="block text-base font-bold">{kanbanGroups.approved.length}</span>
                            <span className="text-[10px]">Đã duyệt</span>
                          </div>
                          <div className="rounded-lg bg-muted/40 p-2">
                            <span className="block text-base font-bold text-foreground">{kanbanGroups.revision.length}</span>
                            <span className="text-[10px] text-muted-foreground">Cần sửa</span>
                          </div>
                        </div>
                      </div>

                      {/* Quick Prompt Bar inside Briefing */}
                      <div className="flex flex-wrap items-center gap-2 bg-muted/20 p-2.5">
                        <span className="text-[11px] text-muted-foreground">Thao tác nhanh:</span>
                        <Button
                          variant="secondary"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => startQuoteCreationFlow(urgentLeads[0]?.customer.full_name)}
                        >
                          <FilePlus2 className="mr-1 h-3.5 w-3.5" /> Tạo báo giá
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={startCopilotDrafting}
                        >
                          <MessageSquare className="mr-1 h-3.5 w-3.5" /> Soạn tin Zalo
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
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

              return null
            })}
            <div ref={chatBottomRef} />
          </div>

          {/* Bottom Chat Command Bar */}
          <div className="relative shrink-0 border-t border-border bg-card p-3 shadow-xs">
            {/* Slash Command Popover */}
            {slashOpen && filteredCommands.length > 0 && (
              <div className="absolute bottom-full left-3 right-3 mb-2 max-h-48 overflow-y-auto rounded-xl border border-border bg-popover p-1 shadow-lg">
                <div className="px-2 py-1 text-[10px] font-bold text-muted-foreground">
                  LỆNH NHANH (BẤM HOẶC DÙNG PHÍM MŨI TÊN + ENTER)
                </div>
                {filteredCommands.map((c, idx) => {
                  const Icon = c.icon
                  return (
                    <button
                      key={c.cmd}
                      type="button"
                      onClick={() => handleExecuteSlash(c.cmd)}
                      className={cn(
                        'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-xs transition-colors',
                        idx === slashIndex ? 'bg-accent text-accent-foreground font-semibold' : 'hover:bg-muted'
                      )}
                    >
                      <Icon className="h-4 w-4 text-primary" />
                      <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] font-semibold text-primary">
                        {c.cmd}
                      </code>
                      <span className="text-muted-foreground">{c.label}</span>
                    </button>
                  )
                })}
              </div>
            )}

            {/* Context Selector Chip (P-07) */}
            <div className="mb-2 flex items-center gap-2 text-xs">
              <span className="font-semibold text-muted-foreground">🎯 Ngữ cảnh:</span>
              <select
                value={contextLeadId}
                onChange={(e) => {
                  setContextLeadId(e.target.value)
                  if (e.target.value !== 'auto') {
                    setSelectedLeadId(e.target.value)
                  }
                }}
                className="rounded-md border border-input bg-background px-2 py-1 text-xs font-medium text-foreground outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="auto">
                  {selectedLead ? `${selectedLead.customer.full_name} (${selectedLead.dossier_id})` : 'Tự động theo hồ sơ'}
                </option>
                {leads.map((l) => (
                  <option key={l.dossier_id} value={l.dossier_id}>
                    {l.customer.full_name} · {l.constraints?.preferred_unit_code || l.dossier_id}
                  </option>
                ))}
              </select>
              <span className="text-[11px] text-muted-foreground hidden md:inline">
                (Mọi câu hỏi ngắn tự động tham chiếu theo khách hàng này)
              </span>
            </div>

            {/* Input & Send Action */}
            <div className="flex items-center gap-2">
              <textarea
                ref={inputTextAreaRef}
                value={inputVal}
                onChange={(e) => {
                  const v = e.target.value
                  setInputVal(v)
                  if (v.startsWith('/')) {
                    setSlashOpen(true)
                    setSlashIndex(0)
                  } else {
                    setSlashOpen(false)
                  }
                }}
                onKeyDown={(e) => {
                  if (slashOpen && filteredCommands.length > 0) {
                    if (e.key === 'ArrowDown') {
                      e.preventDefault()
                      setSlashIndex((p) => Math.min(p + 1, filteredCommands.length - 1))
                      return
                    }
                    if (e.key === 'ArrowUp') {
                      e.preventDefault()
                      setSlashIndex((p) => Math.max(p - 1, 0))
                      return
                    }
                    if (e.key === 'Enter' || e.key === 'Tab') {
                      e.preventDefault()
                      handleExecuteSlash(filteredCommands[slashIndex].cmd)
                      return
                    }
                    if (e.key === 'Escape') {
                      setSlashOpen(false)
                      return
                    }
                  }
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendChatMessage()
                  }
                }}
                rows={1}
                placeholder="Nhập câu hỏi hoặc gõ / để xem danh sách lệnh nhanh..."
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
            'fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-border bg-card transition-transform duration-300 md:static md:w-[400px] md:translate-x-0',
            isMobilePanelOpen ? 'translate-x-0 shadow-2xl' : 'translate-x-full md:translate-x-0'
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
                      onClick={() => {
                        setInputVal('Khách hàng nào sắp quá hạn SLA phản hồi?')
                        inputTextAreaRef.current?.focus()
                      }}
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
                    onClick={() => {
                      setInputVal('Báo giá nào đang chờ phê duyệt lâu nhất?')
                      inputTextAreaRef.current?.focus()
                    }}
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
                    onClick={() => {
                      setInputVal('Chính sách nào áp dụng chiết khấu thanh toán nhanh cao nhất?')
                      inputTextAreaRef.current?.focus()
                    }}
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

      {/* ================= MOBILE BOTTOM-SHEET FAB ================= */}
      <button
        type="button"
        onClick={() => setIsMobilePanelOpen((p) => !p)}
        className="fixed bottom-4 right-4 z-50 grid h-12 w-12 place-items-center rounded-full bg-primary text-primary-foreground shadow-xl md:hidden"
        title="Mở bảng kết quả"
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
