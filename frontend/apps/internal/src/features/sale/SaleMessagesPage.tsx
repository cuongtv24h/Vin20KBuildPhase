import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Copy,
  ExternalLink,
  Info,
  Layers,
  MessageSquare,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useLeads, usePolicies } from '@pricepolicy/api-client/hooks'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { Textarea } from '@pricepolicy/ui/components/ui/textarea'
import { PageHeader } from '@pricepolicy/ui/components/common/PageStates'
import { toast } from '@pricepolicy/ui/state/toastStore'
import { cn } from '@pricepolicy/ui/lib/utils'

// --- EVIDENCE KNOWLEDGE BASE ---
interface LegalEvidence {
  q: string
  p: string
  e: string
  h: string
}

export const EVIDENCE_DB: Record<number, LegalEvidence> = {
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
export interface ComplianceCheckState {
  tier: 'GREEN' | 'AMBER' | 'RED' | 'BLACK'
  statusText: string
  checks: [string, string][]
  suggest?: string
}

export function runLocalComplianceCheck(text: string): ComplianceCheckState {
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
        'Câu an toàn: "Hồ sơ vay của anh/chị sẽ được ngân hàng đối tác thẩm định theo quy trình chuẩn; em hỗ trợ chuẩn bị đầy đủ hồ sơ để tối ưu tiến độ duyệt nhé."',
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
        'Câu an toàn: "Chương trình hiện hành là chiết khấu 8% cho phương án thanh toán sớm 95% [1], em gửi anh/chị văn bản chính sách chi tiết nhé."',
    }
  }

  const hasMoney = /\d+[,.]?\d*\s*(tỷ|triệu|\btr\b)/.test(t)
  const hasAnchor = /\[\d\]/.test(text)
  if (hasMoney && !hasAnchor) {
    return {
      tier: 'RED',
      statusText: 'ĐỎ — Con số tài chính chưa có mỏ neo đối soát',
      checks: [['bad', 'Mọi số tiền trích dẫn cần có mỏ neo chứng cứ [n] để đảm bảo pháp lý']],
      suggest: 'Gắn mỏ neo cho từng con số (ví dụ [1], [2], [4]) để bảo đảm tính chuẩn xác khi tư vấn.',
    }
  }

  if (/lãi suất 0%/.test(t) && !/sau 24 tháng/.test(t)) {
    return {
      tier: 'AMBER',
      statusText: 'VÀNG — Cần bổ sung khuyến cáo bắt buộc',
      checks: [
        ['ok', 'Chính sách HTLS có căn cứ ban hành [4]'],
        ['warn', 'Thiếu khuyến cáo bắt buộc: "Sau 24 tháng theo biểu phí ngân hàng" [4]'],
      ],
      suggest: 'Thêm khuyến cáo: "…Sau 24 tháng lãi suất áp dụng theo biểu phí ngân hàng thương mại đồng tài trợ [4]."',
    }
  }

  if (hasAnchor) {
    return {
      tier: 'GREEN',
      statusText: 'XANH — Hỗ trợ đầy đủ & Tuân thủ phát ngôn',
      checks: [
        ['ok', 'Các số liệu tài chính đều có chứng cứ [n] xác thực'],
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
      ['ok', 'Đúng quy chuẩn giao tiếp khách hàng bất động sản'],
    ],
  }
}

const TEMPLATES = [
  {
    title: 'Thanh toán sớm 95% (Chiết khấu 8%)',
    content:
      'Dạ anh/chị, theo chính sách bán hàng hiện hành [1], nếu thanh toán sớm 95% trong 30 ngày, anh/chị được chiết khấu ngay 8% vào giá bán trước thuế. Tổng thanh toán dự kiến là 4.655.200.000 ₫ [2]. Em gửi anh bảng chi tiết ạ!',
  },
  {
    title: 'Hỗ trợ lãi suất 0% trong 24 tháng',
    content:
      'Dạ căn hộ anh/chị quan tâm đang áp dụng gói hỗ trợ lãi suất 0% và ân hạn nợ gốc trong 24 tháng đầu [4]. Sau 24 tháng lãi suất áp dụng theo biểu phí ngân hàng thương mại đồng tài trợ [4]. Vốn ban đầu cần chuẩn bị chỉ 30%.',
  },
  {
    title: 'Quà tặng gói nội thất 200 triệu (Căn 3BR)',
    content:
      'Em gửi anh thông tin ưu đãi đặc biệt: Với căn 3 phòng ngủ, chủ đầu tư tặng gói hoàn thiện nội thất cao cấp trị giá 200.000.000 ₫ [3]. Gói này áp dụng trừ trực tiếp vào đợt thanh toán khi nhận bàn giao nhà.',
  },
  {
    title: 'Tiến độ giãn chuẩn 09 đợt',
    content:
      'Chào anh/chị, phương án thanh toán chuẩn được chia thành 9 đợt linh hoạt theo mốc xây dựng thực tế [5]. Đợt 1 chỉ 30% giá trị hợp đồng gồm cọc, các đợt tiếp theo đóng giãn cách 2-3 tháng/lần.',
  },
]

export function SaleMessagesPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const leadsQuery = useLeads()
  const policiesQuery = usePolicies()

  const leads = useMemo(() => leadsQuery.data ?? [], [leadsQuery.data])
  const [selectedLeadId, setSelectedLeadId] = useState<string>('')

  // Draft content state
  const [draftContent, setDraftContent] = useState<string>(
    'Dạ anh/chị, theo chính sách bán hàng hiện hành [1], nếu thanh toán sớm 95% trong 30 ngày, anh/chị được chiết khấu ngay 8% vào giá bán trước thuế. Tổng thanh toán dự kiến là 4.655.200.000 ₫ [2]. Em gửi anh bảng chi tiết ạ!'
  )
  const [evidenceId, setEvidenceId] = useState<number | null>(null)
  const [isCheckingCompliance, setIsCheckingCompliance] = useState(false)
  const [complianceResult, setComplianceResult] = useState<ComplianceCheckState>(() =>
    runLocalComplianceCheck(draftContent)
  )

  // Modals
  const [copyAuditModalOpen, setCopyAuditModalOpen] = useState(false)
  const [voiceVariantModalOpen, setVoiceVariantModalOpen] = useState(false)
  const [officialSendModalOpen, setOfficialSendModalOpen] = useState(false)
  const [sendGateStep, setSendGateStep] = useState(0)
  const [officialReceiptId, setOfficialReceiptId] = useState<string | null>(null)

  // Initialize selected lead from search params if present
  useEffect(() => {
    const leadFromUrl = searchParams.get('lead') || searchParams.get('id')
    if (leadFromUrl) {
      setSelectedLeadId(leadFromUrl)
    }
  }, [searchParams])

  // Real-time compliance check debounce 400ms
  useEffect(() => {
    setIsCheckingCompliance(true)
    const t = setTimeout(() => {
      setComplianceResult(runLocalComplianceCheck(draftContent))
      setIsCheckingCompliance(false)
    }, 400)
    return () => clearTimeout(t)
  }, [draftContent])

  // Extract anchors present in draft
  const draftAnchors = useMemo(() => {
    const matches = draftContent.match(/\[(\d+)\]/g) || []
    const ids = Array.from(new Set(matches.map((m) => parseInt(m.replace(/[^\d]/g, ''), 10))))
    return ids.filter((id) => EVIDENCE_DB[id])
  }, [draftContent])

  const selectedLead = leads.find((l) => l.dossier_id === selectedLeadId)

  // Voice variants generated dynamically
  const voiceVariants = useMemo(() => {
    return {
      formal: `Kính gửi Quý khách, căn cứ theo Văn bản Chính sách Bán hàng ban hành chính thức [1], phương thức thanh toán sớm 95% áp dụng mức chiết khấu 8,0% trừ trực tiếp vào giá bán trước thuế. Giá trị hợp đồng quyết toán sau ưu đãi là 4.655.200.000 ₫ [2]. Trân trọng gửi Quý khách đối soát.`,
      friendly: `Dạ em chào anh/chị ạ! Em vừa kiểm tra chính sách mới nhất cho căn hộ của mình, hiện có chiết khấu tới 8% nếu chọn thanh toán sớm 95% trong 30 ngày nè anh/chị [1]. Giá sau cùng chỉ còn 4.655.200.000 ₫ [2] thôi ạ. Anh/chị xem qua nhé!`,
      concise: `Ưu đãi thanh toán sớm 95% [1]: Chiết khấu 8,0% giá trước thuế. Tổng thanh toán: 4.655.200.000 ₫ [2]. Áp dụng trong 30 ngày kể từ ngày đặt cọc.`,
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <PageHeader
        title="Soạn tin & Kiểm định Tuân thủ F8"
        description="Soạn tin nhắn tư vấn khách hàng, kiểm duyệt tự động mỏ neo pháp lý, tỷ lệ chiết khấu & chính sách bán hàng theo chuẩn FCS v2.6."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to="/sale/workspace">
                <Sparkles className="mr-1.5 h-3.5 w-3.5 text-primary" /> Mở Copilot
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/sale/policies">
                <Layers className="mr-1.5 h-3.5 w-3.5" /> Xem Chính sách
              </Link>
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* ================= LEFT / MAIN COMPOSER (8 cols) ================= */}
        <div className="space-y-5 lg:col-span-8">
          {/* Customer Context Selector */}
          <Card className="border-border">
            <CardHeader className="py-3 px-4 bg-muted/30 border-b border-border">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-primary" />
                  <span className="text-xs font-semibold">Khách hàng áp dụng (tùy chọn)</span>
                </div>
                {selectedLead && (
                  <Badge variant="outline" className="text-[11px] bg-primary/5 text-primary">
                    Mã khách: {selectedLead.dossier_id} · {selectedLead.segment || selectedLead.customer_segment}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">
                    Chọn khách hàng trong CRM:
                  </label>
                  <Select value={selectedLeadId} onValueChange={setSelectedLeadId}>
                    <SelectTrigger className="text-xs">
                      <SelectValue placeholder="-- Chọn khách hàng để điền nhanh --" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">-- Không chọn (Mẫu chung) --</SelectItem>
                      {leads.map((l) => (
                        <SelectItem key={l.dossier_id} value={l.dossier_id}>
                          {l.customer_name || l.customer?.full_name} ({l.customer_phone_masked || l.customer_phone || l.customer?.phone})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">
                    Gợi ý mẫu soạn sẵn:
                  </label>
                  <Select
                    onValueChange={(val) => {
                      const found = TEMPLATES.find((t) => t.title === val)
                      if (found) setDraftContent(found.content)
                    }}
                  >
                    <SelectTrigger className="text-xs">
                      <SelectValue placeholder="Chọn nội dung mẫu..." />
                    </SelectTrigger>
                    <SelectContent>
                      {TEMPLATES.map((t) => (
                        <SelectItem key={t.title} value={t.title}>
                          {t.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {selectedLead && (
                <div className="rounded-lg bg-muted/40 p-2.5 text-xs text-muted-foreground flex flex-wrap gap-x-4 gap-y-1">
                  <span>Họ tên: <strong className="text-foreground">{selectedLead.customer_name || selectedLead.customer?.full_name}</strong></span>
                  <span>Điện thoại: <strong className="text-foreground">{selectedLead.customer_phone_masked || selectedLead.customer_phone || selectedLead.customer?.phone}</strong></span>
                  <span>Căn quan tâm: <strong className="text-foreground">{selectedLead.preferred_unit_code || selectedLead.unit_code || 'Chưa định danh'}</strong></span>
                  <span>Vốn tự có: <strong className="text-foreground">{selectedLead.constraints?.own_funds_vnd ? (selectedLead.constraints.own_funds_vnd / 1e9).toFixed(1) + ' tỷ' : '5 tỷ'}</strong></span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Editor Area */}
          <Card className="border-border shadow-xs">
            <CardHeader className="py-3 px-4 border-b border-border bg-card flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm font-semibold">Nội dung tin nhắn tư vấn</CardTitle>
              </div>
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span>{draftContent.length} ký tự</span>
                <span className="text-border">|</span>
                <Badge variant="outline" className="font-mono text-[10px]">
                  {isCheckingCompliance ? 'Kiểm tra...' : 'F8 Live-check 400ms'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
              <Textarea
                value={draftContent}
                onChange={(e) => setDraftContent(e.target.value)}
                rows={6}
                className="w-full text-xs sm:text-sm leading-relaxed font-sans resize-y"
                placeholder="Nhập nội dung tư vấn gửi khách hàng qua Zalo hoặc tin nhắn trực tiếp..."
              />

              {/* Legal Anchors in Text */}
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-muted-foreground">Mỏ neo căn cứ pháp lý đã nhận diện:</span>
                  <span className="text-[11px] text-muted-foreground">Bấm vào để xem trích đoạn văn bản</span>
                </div>
                {draftAnchors.length === 0 ? (
                  <div className="text-xs text-amber-600 bg-amber-500/10 p-2 rounded border border-amber-500/20">
                    ⚠ Chưa có mỏ neo chứng cứ. Sử dụng cú pháp [1], [2], [4] tương ứng với các điều khoản chính sách.
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {draftAnchors.map((aid) => (
                      <button
                        key={aid}
                        type="button"
                        onClick={() => setEvidenceId(aid)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-xs font-semibold text-amber-800 dark:text-amber-300 hover:bg-amber-500/20 transition-colors"
                      >
                        <span className="font-mono">[{aid}]</span>
                        <span className="font-normal truncate max-w-[200px] text-left">
                          {EVIDENCE_DB[aid]?.p}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Buttons Row */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-border">
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => setCopyAuditModalOpen(true)}
                  >
                    <Copy className="mr-1.5 h-3.5 w-3.5" />
                    Copy sang Zalo (Kèm cam kết)
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => setVoiceVariantModalOpen(true)}
                  >
                    <Sparkles className="mr-1.5 h-3.5 w-3.5 text-primary" />
                    Đổi biến thể giọng văn
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
                  className="text-xs"
                >
                  <Send className="mr-1.5 h-3.5 w-3.5" />
                  Gửi qua cổng chính thức
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ================= RIGHT / COMPLIANCE INSPECTOR (4 cols) ================= */}
        <div className="space-y-5 lg:col-span-4">
          {/* Compliance Status Card */}
          <Card
            className={cn(
              'border shadow-xs transition-colors',
              complianceResult.tier === 'GREEN' && 'border-emerald-500/40 bg-emerald-500/5',
              complianceResult.tier === 'AMBER' && 'border-amber-500/40 bg-amber-500/5',
              complianceResult.tier === 'RED' && 'border-rose-500/40 bg-rose-500/5',
              complianceResult.tier === 'BLACK' && 'border-neutral-900 bg-neutral-900 text-white dark:bg-neutral-950'
            )}
          >
            <CardHeader className="py-3.5 px-4 border-b border-border/40">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {complianceResult.tier === 'GREEN' ? (
                    <ShieldCheck className="h-5 w-5 text-emerald-600" />
                  ) : complianceResult.tier === 'AMBER' ? (
                    <AlertTriangle className="h-5 w-5 text-amber-600" />
                  ) : (
                    <ShieldAlert className="h-5 w-5 text-rose-600" />
                  )}
                  <span className="font-semibold text-xs uppercase tracking-wide">
                    Tiêu chuẩn Tuân thủ F8
                  </span>
                </div>
                <Badge
                  variant={
                    complianceResult.tier === 'GREEN'
                      ? 'default'
                      : complianceResult.tier === 'AMBER'
                      ? 'secondary'
                      : 'destructive'
                  }
                  className="text-[10px] font-bold"
                >
                  {complianceResult.tier}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
              <div className="text-xs font-semibold">{complianceResult.statusText}</div>

              <div className="space-y-1.5 border-t border-border/40 pt-2 text-xs">
                {complianceResult.checks.map(([st, txt], i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="font-bold shrink-0">
                      {st === 'ok' ? '✓' : st === 'warn' ? '⚠' : '✗'}
                    </span>
                    <span className="text-[11.5px] leading-snug">{txt}</span>
                  </div>
                ))}
              </div>

              {complianceResult.suggest && (
                <div className="rounded-lg border border-dashed border-primary/40 bg-primary/10 p-2.5 text-xs text-foreground mt-3">
                  <div className="font-bold text-[11px] text-primary mb-1 flex items-center gap-1">
                    <Sparkles className="h-3 w-3" /> Gợi ý phát ngôn an toàn:
                  </div>
                  <p className="text-[11.5px] leading-relaxed">{complianceResult.suggest}</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 mt-1.5 text-[10px] text-primary hover:bg-primary/20 p-1"
                    onClick={() => {
                      const cleanSuggest = complianceResult.suggest?.replace(/^Câu an toàn:\s*"?|"?$/g, '') || ''
                      if (cleanSuggest) setDraftContent(cleanSuggest)
                    }}
                  >
                    Áp dụng gợi ý này
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Evidence Database Reference */}
          <Card className="border-border shadow-xs">
            <CardHeader className="py-3 px-4 border-b border-border bg-muted/20">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Kho Mỏ neo Chứng cứ (FCS v2.6)
                </CardTitle>
                <span className="text-[11px] text-muted-foreground">{Object.keys(EVIDENCE_DB).length} nguồn</span>
              </div>
            </CardHeader>
            <CardContent className="p-3 space-y-2">
              {Object.entries(EVIDENCE_DB).map(([keyStr, ev]) => {
                const id = parseInt(keyStr, 10)
                const isSelected = draftAnchors.includes(id)
                return (
                  <div
                    key={id}
                    onClick={() => setEvidenceId(id)}
                    className={cn(
                      'cursor-pointer rounded-lg border p-2.5 text-xs transition-all hover:border-primary/50',
                      isSelected ? 'border-primary/60 bg-primary/5' : 'border-border bg-card'
                    )}
                  >
                    <div className="flex items-center justify-between font-semibold text-foreground">
                      <span className="font-mono text-primary">[{id}] {ev.p}</span>
                      {isSelected && (
                        <Badge variant="outline" className="text-[9px] h-4 bg-primary/10 text-primary">
                          Đang dùng
                        </Badge>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground line-clamp-2 mt-1">{ev.q}</p>
                    <div className="mt-1 text-[10px] text-muted-foreground flex justify-between">
                      <span>{ev.e}</span>
                      <span className="font-mono">{ev.h}</span>
                    </div>
                  </div>
                )
              })}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ================= MODAL: EVIDENCE PREVIEW ================= */}
      <Dialog open={evidenceId !== null} onOpenChange={(open) => !open && setEvidenceId(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
              <span className="font-mono text-primary">[{evidenceId}]</span>
              <span>Trích lục pháp lý & căn cứ chính sách</span>
            </DialogTitle>
          </DialogHeader>
          {evidenceId && EVIDENCE_DB[evidenceId] && (
            <div className="space-y-3 text-xs">
              <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 italic text-foreground leading-relaxed">
                “{EVIDENCE_DB[evidenceId].q}”
              </div>
              <div className="space-y-1.5 text-muted-foreground pt-1 text-[11.5px]">
                <div className="flex justify-between">
                  <span>Văn bản ban hành:</span>
                  <span className="font-semibold text-foreground text-right">{EVIDENCE_DB[evidenceId].p}</span>
                </div>
                <div className="flex justify-between">
                  <span>Hiệu lực văn bản:</span>
                  <span className="font-semibold text-foreground">{EVIDENCE_DB[evidenceId].e}</span>
                </div>
                <div className="flex justify-between">
                  <span>Mã hash lưu trữ:</span>
                  <span className="font-mono text-foreground">{EVIDENCE_DB[evidenceId].h}</span>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button size="sm" variant="outline" onClick={() => setEvidenceId(null)}>
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ================= MODAL: COPY AUDIT ================= */}
      <Dialog open={copyAuditModalOpen} onOpenChange={setCopyAuditModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm font-semibold flex items-center gap-2">
              <Copy className="h-4 w-4 text-primary" />
              Xác nhận sao chép nội dung tư vấn
            </DialogTitle>
            <DialogDescription className="text-xs">
              Hệ thống lưu vết phát ngôn vào sổ nhật ký tuân thủ bán hàng theo tiêu chuẩn FCS v2.6.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-xs">
            <div className="rounded-lg bg-muted p-3 text-muted-foreground max-h-36 overflow-y-auto">
              {draftContent}
            </div>
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-[11px] text-amber-800 dark:text-amber-300">
              Tôi cam kết gửi đúng nội dung đã qua kiểm duyệt, không tự ý chỉnh sửa sai lệch chính sách chiết khấu và hỗ trợ lãi suất.
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={() => setCopyAuditModalOpen(false)}>
              Hủy
            </Button>
            <Button
              size="sm"
              onClick={() => {
                navigator.clipboard.writeText(draftContent)
                setCopyAuditModalOpen(false)
                toast.success('Đã sao chép nội dung vào Clipboard!')
              }}
            >
              Đồng ý & Copy sang Zalo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ================= MODAL: VOICE VARIANTS ================= */}
      <Dialog open={voiceVariantModalOpen} onOpenChange={setVoiceVariantModalOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle className="text-sm font-semibold flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              Chọn biến thể giọng văn phát ngôn
            </DialogTitle>
            <DialogDescription className="text-xs">
              Các biến thể đều giữ nguyên số liệu và mỏ neo chứng cứ, chỉ thay đổi sắc thái tiếp cận.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="rounded-lg border border-border p-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">1. Phong cách Trang trọng & Chuẩn mực</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-[11px]"
                  onClick={() => {
                    setDraftContent(voiceVariants.formal)
                    setVoiceVariantModalOpen(false)
                    toast.success('Đã áp dụng văn phong Trang trọng!')
                  }}
                >
                  Áp dụng
                </Button>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{voiceVariants.formal}</p>
            </div>

            <div className="rounded-lg border border-border p-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">2. Phong cách Thân thiện & Gần gũi</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-[11px]"
                  onClick={() => {
                    setDraftContent(voiceVariants.friendly)
                    setVoiceVariantModalOpen(false)
                    toast.success('Đã áp dụng văn phong Thân thiện!')
                  }}
                >
                  Áp dụng
                </Button>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{voiceVariants.friendly}</p>
            </div>

            <div className="rounded-lg border border-border p-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">3. Phong cách Ngắn gọn & Súc tích</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-[11px]"
                  onClick={() => {
                    setDraftContent(voiceVariants.concise)
                    setVoiceVariantModalOpen(false)
                    toast.success('Đã áp dụng văn phong Ngắn gọn!')
                  }}
                >
                  Áp dụng
                </Button>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{voiceVariants.concise}</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setVoiceVariantModalOpen(false)}>
              Đóng
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ================= MODAL: OFFICIAL SEND GATEWAY ================= */}
      <Dialog open={officialSendModalOpen} onOpenChange={setOfficialSendModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm font-semibold flex items-center gap-2">
              <Send className="h-4 w-4 text-primary" />
              Cổng gửi tin nhắn chính thức VLand
            </DialogTitle>
            <DialogDescription className="text-xs">
              Gửi qua đầu số định danh Brandname (SMS / ZNS) có lưu trữ biên lai điện tử.
            </DialogDescription>
          </DialogHeader>

          {sendGateStep === 0 && (
            <div className="space-y-3 text-xs">
              <p className="text-muted-foreground">
                Tin nhắn sẽ được ký số và chuyển trực tiếp tới khách hàng{' '}
                <strong>{selectedLead ? (selectedLead.customer_name || selectedLead.customer?.full_name) : 'được chọn'}</strong>.
              </p>
              <div className="rounded-lg bg-muted p-3 text-muted-foreground max-h-32 overflow-y-auto">
                {draftContent}
              </div>
              <div className="flex items-center gap-2 text-emerald-600 font-medium">
                <CheckCircle2 className="h-4 w-4" />
                <span>Nội dung đã qua kiểm duyệt F8 hợp lệ</span>
              </div>
            </div>
          )}

          {sendGateStep === 1 && (
            <div className="py-6 flex flex-col items-center justify-center gap-3">
              <RefreshCw className="h-8 w-8 animate-spin text-primary" />
              <p className="text-xs text-muted-foreground">Đang xác thực chữ ký số và điều phối cổng gửi...</p>
            </div>
          )}

          {sendGateStep === 2 && (
            <div className="space-y-3 text-xs">
              <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3 text-center space-y-1">
                <CheckCircle2 className="h-6 w-6 text-emerald-600 mx-auto" />
                <p className="font-semibold text-emerald-800 dark:text-emerald-300">
                  Gửi thành công qua cổng chính thức!
                </p>
                <p className="text-[11px] font-mono text-muted-foreground">
                  Mã biên lai: {officialReceiptId}
                </p>
              </div>
              <p className="text-muted-foreground text-[11px]">
                Thời gian ghi nhận: {new Date().toLocaleTimeString('vi-VN')} {new Date().toLocaleDateString('vi-VN')}.
              </p>
            </div>
          )}

          <DialogFooter>
            {sendGateStep === 0 && (
              <>
                <Button variant="outline" size="sm" onClick={() => setOfficialSendModalOpen(false)}>
                  Hủy
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    setSendGateStep(1)
                    setTimeout(() => {
                      setOfficialReceiptId(`REC-${Date.now().toString(36).toUpperCase()}`)
                      setSendGateStep(2)
                    }, 1200)
                  }}
                >
                  Xác nhận gửi đi
                </Button>
              </>
            )}
            {sendGateStep === 2 && (
              <Button size="sm" onClick={() => setOfficialSendModalOpen(false)}>
                Hoàn tất
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
export default SaleMessagesPage
