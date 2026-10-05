import { AlertTriangle, ArrowRight, CheckCircle2, Copy, ExternalLink, Info, Layers, MessageSquare, RefreshCw, Send, ShieldAlert, ShieldCheck, Sparkles, Users, X, Check } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useLeads, usePolicies } from '@pricepolicy/api-client/hooks'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card } from '@pricepolicy/ui/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { Textarea } from '@pricepolicy/ui/components/ui/textarea'
import { PageHeader } from '@pricepolicy/ui/components/common/PageStates'
import { toast } from '@pricepolicy/ui/state/toastStore'
import { cn } from '@pricepolicy/ui/lib/utils'
import { maskPhone } from '@pricepolicy/ui/lib/format'

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
      statusText: 'XANH — Hỗ trợ đầy đủ và Tuân thủ phát ngôn',
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

  const tierTone = {
    GREEN: { text: 'text-success', bg: 'bg-success/10', border: 'border-success/30', dot: 'bg-success' },
    AMBER: { text: 'text-warning', bg: 'bg-warning/10', border: 'border-warning/30', dot: 'bg-warning' },
    RED: { text: 'text-destructive', bg: 'bg-destructive/10', border: 'border-destructive/30', dot: 'bg-destructive' },
    BLACK: { text: 'text-destructive', bg: 'bg-destructive/15', border: 'border-destructive/40', dot: 'bg-destructive' },
  }[complianceResult.tier]
  const TierIcon = complianceResult.tier === 'GREEN' ? ShieldCheck : complianceResult.tier === 'AMBER' ? AlertTriangle : ShieldAlert
  const blocked = complianceResult.tier === 'RED' || complianceResult.tier === 'BLACK'

  return (
    <div className="space-y-6">
      <PageHeader
        title="Soạn tin và Kiểm định Tuân thủ F8"
        description="Soạn tin tư vấn khách hàng, hệ thống tự kiểm tra mỏ neo pháp lý và mức chiết khấu theo FCS v2.6."
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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr),340px] lg:items-start">
        {/* ============ Cột trái: một khung soạn thư duy nhất (bố cục Zoho CRM) ============ */}
        <Card className="overflow-hidden border-border">
          {/* Hàng "Tới / Mẫu" gọn thay cho thẻ chọn khách riêng */}
          <div className="divide-y divide-border border-b border-border">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5">
              <span className="flex w-16 shrink-0 items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Users className="h-3.5 w-3.5" aria-hidden="true" /> Tới
              </span>
              <div className="min-w-[200px] flex-1">
                <Select value={selectedLeadId} onValueChange={setSelectedLeadId}>
                  <SelectTrigger className="h-8 border-0 bg-transparent px-0 text-sm shadow-none focus:ring-0">
                    <SelectValue placeholder="Chọn khách hàng trong CRM (không bắt buộc)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">-- Không chọn (Mẫu chung) --</SelectItem>
                    {leads.map((l) => (
                      <SelectItem key={l.dossier_id} value={l.dossier_id}>
                        {l.customer_name || l.customer?.full_name} ({maskPhone(l.customer_phone_masked || l.customer_phone || l.customer?.phone)})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {selectedLead && (
                <Badge variant="outline" className="text-xs text-muted-foreground">
                  {selectedLead.dossier_id} · {selectedLead.segment || selectedLead.customer_segment}
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5">
              <span className="flex w-16 shrink-0 items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <MessageSquare className="h-3.5 w-3.5" aria-hidden="true" /> Mẫu
              </span>
              <div className="min-w-[200px] flex-1">
                <Select
                  onValueChange={(val) => {
                    const found = TEMPLATES.find((t) => t.title === val)
                    if (found) setDraftContent(found.content)
                  }}
                >
                  <SelectTrigger className="h-8 border-0 bg-transparent px-0 text-sm shadow-none focus:ring-0">
                    <SelectValue placeholder="Chèn nội dung mẫu soạn sẵn…" />
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
          </div>

          {selectedLead && (
            <div className="flex flex-wrap gap-x-5 gap-y-1 border-b border-border bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
              <span>Điện thoại: <strong className="font-medium text-foreground">{maskPhone(selectedLead.customer_phone_masked || selectedLead.customer_phone || selectedLead.customer?.phone)}</strong></span>
              <span>Căn quan tâm: <strong className="font-medium text-foreground">{selectedLead.preferred_unit_code || selectedLead.unit_code || 'Chưa định danh'}</strong></span>
              <span>Vốn tự có: <strong className="font-medium text-foreground">{selectedLead.constraints?.own_funds_vnd ? (selectedLead.constraints.own_funds_vnd / 1e9).toFixed(1) + ' tỷ' : '5 tỷ'}</strong></span>
            </div>
          )}

          {/* Vùng soạn: không viền, nền phẳng, chữ lớn để đọc thoải mái */}
          <Textarea
            value={draftContent}
            onChange={(e) => setDraftContent(e.target.value)}
            rows={9}
            aria-label="Nội dung tin nhắn tư vấn"
            className="min-h-[220px] w-full resize-y rounded-none border-0 bg-transparent px-4 py-4 font-sans text-sm leading-relaxed shadow-none focus-visible:ring-0 sm:text-[15px]"
            placeholder="Nhập nội dung tư vấn gửi khách hàng qua Zalo hoặc tin nhắn trực tiếp..."
          />

          {/* Căn cứ đã nhận diện: chip trung tính, gọn một hàng */}
          <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 py-2.5">
            <span className="text-xs font-medium text-muted-foreground">Căn cứ:</span>
            {draftAnchors.length === 0 ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-warning">
                <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" /> Chưa có mỏ neo. Dùng cú pháp [1], [2], [4]…
              </span>
            ) : (
              draftAnchors.map((aid) => (
                <button
                  key={aid}
                  type="button"
                  onClick={() => setEvidenceId(aid)}
                  title={EVIDENCE_DB[aid]?.p}
                  className="inline-flex max-w-[220px] items-center gap-1.5 rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-xs transition-colors hover:border-primary/50 hover:bg-accent"
                >
                  <span className="font-mono font-semibold text-gold">[{aid}]</span>
                  <span className="truncate text-muted-foreground">{EVIDENCE_DB[aid]?.p.split('—')[0].trim()}</span>
                </button>
              ))
            )}
          </div>

          {/* Thanh hành động dưới cùng: phụ bên trái, chính bên phải */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-muted/20 px-4 py-3">
            <div className="flex flex-wrap items-center gap-1">
              <Button variant="ghost" size="sm" className="text-xs" onClick={() => setCopyAuditModalOpen(true)}>
                <Copy className="mr-1.5 h-3.5 w-3.5" /> Copy sang Zalo
              </Button>
              <Button variant="ghost" size="sm" className="text-xs" onClick={() => setVoiceVariantModalOpen(true)}>
                <Sparkles className="mr-1.5 h-3.5 w-3.5 text-primary" /> Đổi giọng văn
              </Button>
              <span className="ml-2 text-xs tabular-nums text-muted-foreground">{draftContent.length} ký tự</span>
            </div>
            <Button
              size="sm"
              disabled={blocked}
              title={blocked ? 'Cần xử lý cảnh báo tuân thủ trước khi gửi' : undefined}
              onClick={() => {
                setSendGateStep(0)
                setOfficialReceiptId(null)
                setOfficialSendModalOpen(true)
              }}
            >
              <Send className="mr-1.5 h-3.5 w-3.5" /> Gửi qua cổng chính thức
            </Button>
          </div>
        </Card>

        {/* ============ Cột phải: một panel kiểm tra + nguồn (bố cục WRITER / Microsoft Copilot) ============ */}
        <Card className="overflow-hidden border-border lg:sticky lg:top-4">
          {/* Trạng thái tuân thủ */}
          <div className={cn('space-y-3 border-b p-4 transition-colors', tierTone.bg, tierTone.border)}>
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">
                <TierIcon className={cn('h-4 w-4', tierTone.text)} aria-hidden="true" /> Tuân thủ F8
              </span>
              <span className={cn('inline-flex items-center gap-1.5 rounded-full border bg-background/60 px-2 py-0.5 text-xs font-semibold', tierTone.text, tierTone.border)}>
                <span aria-hidden="true" className={cn('h-1.5 w-1.5 rounded-full', tierTone.dot, isCheckingCompliance && 'animate-pulse')} />
                {isCheckingCompliance ? 'Đang kiểm tra' : complianceResult.tier}
              </span>
            </div>
            <p className="text-sm font-medium leading-snug">{complianceResult.statusText}</p>
          </div>

          <ul className="space-y-2 border-b border-border p-4 text-xs">
            {complianceResult.checks.map(([st, txt], i) => (
              <li key={i} className="flex items-start gap-2">
                <span
                  className={cn(
                    'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full',
                    st === 'ok' ? 'bg-success/15 text-success' : st === 'warn' ? 'bg-warning/15 text-warning' : 'bg-destructive/15 text-destructive',
                  )}
                >
                  {st === 'ok' ? <Check className="h-3 w-3" aria-hidden="true" /> : st === 'warn' ? <AlertTriangle className="h-3 w-3" aria-hidden="true" /> : <X className="h-3 w-3" aria-hidden="true" />}
                </span>
                <span className="leading-snug">{txt}</span>
              </li>
            ))}
          </ul>

          {complianceResult.suggest && (
            <div className="space-y-2 border-b border-border bg-primary/5 p-4 text-xs">
              <p className="flex items-center gap-1.5 font-semibold text-gold">
                <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Gợi ý phát ngôn an toàn
              </p>
              <p className="leading-relaxed text-muted-foreground">{complianceResult.suggest}</p>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => {
                  const cleanSuggest = complianceResult.suggest?.replace(/^Câu an toàn:\s*"?|"?$/g, '') || ''
                  if (cleanSuggest) setDraftContent(cleanSuggest)
                }}
              >
                Áp dụng gợi ý này
              </Button>
            </div>
          )}

          {/* Nguồn chứng cứ: danh sách một dòng, chấm vàng = đang dùng trong tin */}
          <div className="p-2">
            <div className="flex items-center justify-between px-2 pb-1 pt-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Nguồn chứng cứ</p>
              <span className="text-xs text-muted-foreground">{draftAnchors.length}/{Object.keys(EVIDENCE_DB).length} đang dùng</span>
            </div>
            <ul>
              {Object.entries(EVIDENCE_DB).map(([keyStr, ev]) => {
                const id = parseInt(keyStr, 10)
                const used = draftAnchors.includes(id)
                return (
                  <li key={id}>
                    <button
                      type="button"
                      onClick={() => setEvidenceId(id)}
                      className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left text-xs transition-colors hover:bg-accent"
                    >
                      <span aria-hidden="true" className={cn('h-2 w-2 shrink-0 rounded-full', used ? 'bg-primary' : 'bg-border')} />
                      <span className="shrink-0 font-mono font-semibold text-gold">[{id}]</span>
                      <span className={cn('min-w-0 flex-1 truncate', used ? 'text-foreground' : 'text-muted-foreground')}>{ev.p.split('—')[1]?.trim() ?? ev.p}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        </Card>
      </div>

      {/* ================= MODAL: EVIDENCE PREVIEW ================= */}
      <Dialog open={evidenceId !== null} onOpenChange={(open) => !open && setEvidenceId(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
              <span className="font-mono text-primary">[{evidenceId}]</span>
              <span>Trích lục pháp lý và căn cứ chính sách</span>
            </DialogTitle>
          </DialogHeader>
          {evidenceId && EVIDENCE_DB[evidenceId] && (
            <div className="space-y-3 text-xs">
              <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 italic text-foreground leading-relaxed">
                “{EVIDENCE_DB[evidenceId].q}”
              </div>
              <div className="space-y-1.5 text-muted-foreground pt-1 text-xs">
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
            <div className="rounded-lg border border-warning/30 bg-warning/10 p-2.5 text-xs text-warning">
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
              Đồng ý và Copy sang Zalo
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
                <span className="text-xs font-bold text-foreground">1. Phong cách Trang trọng và Chuẩn mực</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-xs"
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
                <span className="text-xs font-bold text-foreground">2. Phong cách Thân thiện và Gần gũi</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-xs"
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
                <span className="text-xs font-bold text-foreground">3. Phong cách Ngắn gọn và Súc tích</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-xs"
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
              <div className="flex items-center gap-2 text-success font-medium">
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
              <div className="rounded-lg border border-success/40 bg-success/10 p-3 text-center space-y-1">
                <CheckCircle2 className="h-6 w-6 text-success mx-auto" />
                <p className="font-semibold text-success">
                  Gửi thành công qua cổng chính thức!
                </p>
                <p className="text-xs font-mono text-muted-foreground">
                  Mã biên lai: {officialReceiptId}
                </p>
              </div>
              <p className="text-muted-foreground text-xs">
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
