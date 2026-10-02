import { http, HttpResponse } from 'msw'
import type { CopilotCitation, CopilotFinalPayload, CopilotStreamEvent, PolicyDocument, UnitSnapshot } from '@pricepolicy/api-client/contracts'
import { ENDPOINTS } from '@pricepolicy/api-client/endpoints'
import { computeScenarios } from '../engine/calculator'
import { selectPolicyForDate } from '../engine/conflicts'
import { rankScenarios } from '../engine/recommend'
import { PAYMENT_PLANS_FIXTURE } from '../fixtures/plans'
import { POLICIES_FIXTURE } from '../fixtures/policies'
import { UNITS_FIXTURE } from '../fixtures/units'
import { toMswPath } from './route'

/**
 * Sales Copilot giả lập — bản sao tất định của ReAct agent ở backend thật (C-??/SCR-S00).
 *
 * Mục đích: (1) hợp đồng mock phủ đủ endpoint trong `ENDPOINTS`; (2) demo offline không cần
 * API key vẫn cho Sale thấy tiến trình Thought → Action → Observation; (3) test UI stream.
 * Mọi con số đều lấy từ fixtures canonical / engine tất định — không bịa.
 */

const DEFAULT_DATE = '2026-09-26'

interface Intent {
  kind: 'policy' | 'units' | 'scenarios' | 'compose' | 'customer' | 'smalltalk'
  unitCode: string | null
  bedrooms: number | null
  customerName: string
}

function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
}

const UNIT_RE = /\b([A-Z]{2,4}-[A-Z0-9]{1,3}-\d{3,4}|[A-Z]{1,3}-\d{2}\.\d{2})\b/i

function parseIntent(message: string): Intent {
  const t = normalize(message)
  const unitMatch = UNIT_RE.exec(message)
  const bedrooms = /(\d)\s*(?:pn|phong ngu|ngu|br)\b/.exec(t)
  const phone = /0\d{9,10}/.exec(message)
  let name = message
    .replace(/^(tạo|thêm|mở|nhập|lưu|đăng\s*ký)\s*(khách(\s*hàng)?(\s*mới)?|lead|hồ\s*sơ)\s*/i, '')
    .replace(/^(mới\s*tên|mới\s*là|tên\s*là|tên|mới|anh|chị)\s*/i, '')
    .trim()
  if (phone && phone.index > 0) name = name.slice(0, phone.index)
  name = name.split(/[,;]/)[0].replace(/[,;:-]?\s*(sđt|sdt|phone)\s*$/i, '').trim()

  // So khớp trên chuỗi đã bỏ dấu (t) — từ khoá ở dạng không dấu để tránh bẫy như backend `_has()`.
  if (t.includes('tao khach') || t.includes('them khach') || t.includes('khach moi') || t.includes('tao lead')) {
    return { kind: 'customer', unitCode: unitMatch?.[1]?.toUpperCase() ?? null, bedrooms: null, customerName: name }
  }
  if (t.includes('bao gia') || t.includes('so sanh') || t.includes('phuong an') || t.includes('dong tien')) {
    return { kind: 'scenarios', unitCode: unitMatch?.[1]?.toUpperCase() ?? null, bedrooms: null, customerName: '' }
  }
  if (t.includes('soan tin') || t.includes('tin nhan')) {
    return { kind: 'compose', unitCode: unitMatch?.[1]?.toUpperCase() ?? null, bedrooms: null, customerName: '' }
  }
  if (t.includes('gio hang') || t.includes('ro hang') || bedrooms) {
    return { kind: 'units', unitCode: unitMatch?.[1]?.toUpperCase() ?? null, bedrooms: bedrooms ? Number(bedrooms[1]) : null, customerName: '' }
  }
  if (t.includes('chinh sach') || t.includes('chiet khau') || t.includes('hieu luc') || t.includes('dieu')) {
    return { kind: 'policy', unitCode: unitMatch?.[1]?.toUpperCase() ?? null, bedrooms: null, customerName: '' }
  }
  return { kind: 'smalltalk', unitCode: unitMatch?.[1]?.toUpperCase() ?? null, bedrooms: null, customerName: '' }
}

const vnd = (n: number) => `${n.toLocaleString('vi-VN')} ₫`

function policyCitation(policy: PolicyDocument, ruleCode: string): CopilotCitation | null {
  const rule = policy.rules.find((r) => r.rule_code === ruleCode)
  if (!rule) return null
  return {
    policy_id: policy.policy_id,
    policy_version: policy.policy_version,
    policy_title: policy.title,
    rule_code: rule.rule_code,
    section: rule.source.section,
    clause_id: rule.source.clause_id,
    quote: rule.source.quote,
    document_id: rule.source.document_id,
    document_hash: rule.source.document_hash,
  }
}

function activePolicy(): PolicyDocument | null {
  return selectPolicyForDate(POLICIES_FIXTURE, 'THE_ZEN_PARK', DEFAULT_DATE)
}

function findUnit(code: string | null): UnitSnapshot | null {
  if (!code) return null
  return UNITS_FIXTURE.find((u) => u.unit_code.toUpperCase() === code.toUpperCase()) ?? null
}

function answerPolicy(policy: PolicyDocument | null, citations: CopilotCitation[]) {
  const early = policy ? policyCitation(policy, 'EARLY_PAY_DISCOUNT') : null
  if (early && citations.length === 0) citations.push(early)
  const pct = early?.quote?.match(/(\d+([.,]\d+)?)\s*%/)?.[1] ?? '8.0'
  return (
    `Dạ, chính sách đang hiệu lực là ${policy?.policy_id ?? '—'} (${policy?.policy_version ?? '—'}), ` +
    `áp dụng từ ${policy?.effective_from ?? '?'} đến ${policy?.effective_to ?? '?'}. ` +
    `Khách thanh toán sớm 95% trong 15 ngày được chiết khấu ${pct}% trên giá trước thuế ` +
    `[${policy?.policy_id ?? '—'} · ${early?.section ?? 'Điều 4, Khoản 2b'}]. ` +
    `Anh/chị cần em tính thử cho căn cụ thể nào không ạ?`
  )
}

async function answerScenarios(unit: UnitSnapshot | null, policy: PolicyDocument | null, citations: CopilotCitation[]) {
  if (!unit || !policy) {
    return 'Em cần mã căn cụ thể (ví dụ ZEN-A-1205) để chạy engine tất định ạ. Anh/chị cho em mã căn nhé.'
  }
  const scenarios = await computeScenarios({
    unit,
    policy,
    plans: PAYMENT_PLANS_FIXTURE,
    selected_rule_codes: ['EARLY_PAY_DISCOUNT', 'BANK_LOAN_HTLS'],
    customer_segment: 'NEW_CUSTOMER',
    units_quantity: 1,
  })
  const rec = rankScenarios(scenarios, 'MIN_NET_PRICE')
  const lines = [`Dạ, em đã chạy engine tất định cho căn ${unit.unit_code} (giá niêm yết ${vnd(unit.listed_price_before_tax_vnd)}):`]
  for (const s of scenarios) {
    lines.push(
      `• ${s.label} (${s.scenario_code}): tổng HĐMB ${vnd(s.total_contract_price_vnd)}, đợt đầu ${vnd(s.initial_payment_vnd)}, ` +
        `tổng tự chi đến nhận nhà ${vnd(s.total_cash_outflow_vnd)}.`,
    )
  }
  if (rec) lines.push(`Đề xuất tối ưu theo mục tiêu giá Net: ${rec.recommended_scenario}.`)
  lines.push('Số liệu do Deterministic Math Engine tính, không phải LLM tự tính [FCS v2.6].')
  citations.push({
    policy_id: 'FCS-v2.6',
    section: `Deterministic Math Engine · ${unit.unit_code}`,
    quote: `3 phương án chuẩn tắc tính từ ${policy.policy_id}; khuyến nghị ${rec?.recommended_scenario ?? '—'}`,
    source: 'DETERMINISTIC_ENGINE',
  })
  const early = policyCitation(policy, 'EARLY_PAY_DISCOUNT')
  if (early) citations.push(early)
  return lines.join('\n')
}

function answerUnits(intent: Intent, citations: CopilotCitation[]) {
  let pool = UNITS_FIXTURE.filter((u) => u.status === 'AVAILABLE')
  if (intent.unitCode) {
    const one = findUnit(intent.unitCode)
    pool = one ? [one] : []
  } else if (intent.bedrooms) {
    pool = pool.filter((u) => u.bedrooms === intent.bedrooms)
  }
  if (!pool.length) return 'Dạ, hiện chưa có căn nào phù hợp tiêu chí trong giỏ hàng đang mở bán ạ.'
  const top = [...pool].sort((a, b) => a.listed_price_before_tax_vnd - b.listed_price_before_tax_vnd).slice(0, 3)
  for (const u of top) {
    citations.push({
      policy_id: 'CATALOG-UNITS',
      section: `Căn ${u.unit_code}`,
      quote: `${u.bedrooms}PN · ${u.area_m2}m² · ${vnd(u.listed_price_before_tax_vnd)} · ${u.status}`,
      source: 'CANONICAL_CATALOG',
    })
  }
  return (
    `Dạ, em tìm được ${top.length} căn phù hợp: ` +
    top.map((u) => `${u.unit_code} (${u.bedrooms}PN, ${u.area_m2}m², ${vnd(u.listed_price_before_tax_vnd)})`).join('; ') +
    '. Anh/chị muốn em tính phương án cho căn nào ạ?'
  )
}

function answerCompose(intent: Intent, citations: CopilotCitation[]) {
  const unit = findUnit(intent.unitCode) ?? findUnit('ZEN-A-1205')
  const draft =
    `Dạ em chào anh/chị, em gửi anh/chị phương án căn ${unit?.unit_code ?? 'đang quan tâm'} ạ. ` +
    `Chính sách ưu đãi áp dụng theo văn bản chính sách đang hiệu lực tại thời điểm giao dịch; ` +
    `em gửi anh/chị bảng tính chi tiết để mình xem qua nhé.`
  citations.push({ policy_id: 'F8-POL08', section: 'Kiểm tra phát ngôn', quote: 'Bản nháp không chứa cam kết trái quy định.', source: 'COMPLIANCE_GATE' })
  return `Em đã soạn nháp và tự kiểm F8 (không có phát ngôn bị chặn):\n\n“${draft}”`
}

async function buildTurn(message: string): Promise<CopilotFinalPayload & { reasoning: CopilotStreamEvent[] }> {
  const intent = parseIntent(message)
  const policy = intent.kind === 'scenarios' || intent.kind === 'policy' ? activePolicy() : null
  const citations: CopilotCitation[] = []
  const reasoning: CopilotStreamEvent[] = [
    { type: 'thought', text: `Em phân loại yêu cầu: ${intent.kind}.` },
  ]

  let reply: string
  let actionType: string | null = null
  let actionData: Record<string, unknown> | null = null

  switch (intent.kind) {
    case 'policy':
      reasoning.push({ type: 'action', tool: 'tra_cuu_chinh_sach', args: { cau_hoi: message } })
      reply = answerPolicy(policy, citations)
      break
    case 'scenarios': {
      const unit = findUnit(intent.unitCode) ?? findUnit('ZEN-A-1205')
      reasoning.push({ type: 'action', tool: 'tinh_phuong_an_thanh_toan', args: { ma_can: unit?.unit_code ?? null } })
      return await buildScenariosTurn(intent, unit, policy, citations, reasoning)
    }
    case 'units':
      reasoning.push({ type: 'action', tool: 'tra_cuu_gio_hang', args: { so_phong_ngu: intent.bedrooms } })
      reply = answerUnits(intent, citations)
      break
    case 'compose':
      reasoning.push({ type: 'action', tool: 'soan_tin_tu_van', args: { ma_can: intent.unitCode } })
      reply = answerCompose(intent, citations)
      actionType = 'smart_compose_message'
      actionData = { unit_code: intent.unitCode ?? 'ZEN-A-1205' }
      break
    case 'customer':
      reasoning.push({ type: 'action', tool: 'tra_cuu_gio_hang', args: { ma_can: intent.unitCode } })
      reply = `Em đã bóc tách hồ sơ khách ${intent.customerName || '(chưa rõ tên)'}. Anh/chị kiểm tra thẻ và bấm Khởi tạo ngay để lưu vào CRM nhé.`
      actionType = 'smart_customer_create'
      actionData = {
        customer_name: intent.customerName,
        customer_phone: '',
        preferred_unit_code: intent.unitCode,
        own_funds_vnd: 1_500_000_000,
        needs_summary: `Khách ${intent.customerName || 'mới'} quan tâm căn ${intent.unitCode ?? 'đang tư vấn'}.`,
      }
      break
    default:
      reply =
        'Dạ em là Sales Copilot. Em có thể tra chính sách đang hiệu lực, xem giỏ hàng, tính 3 phương án tất định, ' +
        'soạn tin tư vấn (tự kiểm F8) và tìm hồ sơ khách hàng. Anh/chị cần em hỗ trợ gì trước ạ?'
  }

  const lastAction = [...reasoning].reverse().find((event) => event.type === 'action')
  reasoning.push({
    type: 'observation',
    tool: (lastAction?.type === 'action' ? lastAction.tool : null) ?? 'copilot',
    ok: true,
    summary: reply.slice(0, 400),
    citations,
  })
  const final: CopilotFinalPayload = {
    reply,
    action_type: actionType,
    action_data: actionData,
    suggested_actions: actionType ? ['Lưu khách hàng vào CRM', 'Lập báo giá chi tiết'] : ['Tra cứu chính sách đang hiệu lực', 'Xem giỏ hàng còn căn nào'],
    citations,
    grounded: citations.length > 0 || intent.kind === 'smalltalk',
    tools_used: reasoning.filter((r) => r.type === 'action').map((r) => r.tool ?? ''),
    iterations: 2,
    mode: 'react',
  }
  reasoning.push({ type: 'final', ...final })
  return { ...final, reasoning }
}

async function buildScenariosTurn(
  intent: Intent,
  unit: UnitSnapshot | null,
  policy: PolicyDocument | null,
  citations: CopilotCitation[],
  reasoning: CopilotStreamEvent[],
): Promise<CopilotFinalPayload & { reasoning: CopilotStreamEvent[] }> {
  const reply = await answerScenarios(unit, policy, citations)
  reasoning.push({ type: 'observation', tool: 'tinh_phuong_an_thanh_toan', ok: true, summary: reply.slice(0, 400), citations })
  const final: CopilotFinalPayload = {
    reply,
    action_type: unit ? 'smart_scenario_compare' : null,
    action_data: unit ? { unit_code: unit.unit_code } : null,
    suggested_actions: ['Tạo báo giá cho căn này', 'Soạn tin nhắn gửi khách'],
    citations,
    grounded: citations.length > 0,
    tools_used: ['tinh_phuong_an_thanh_toan'],
    iterations: 2,
    mode: 'react',
  }
  reasoning.push({ type: 'final', ...final })
  return { ...final, reasoning }
}

interface FeedbackEntry {
  recorded_at: string
  rating: number
  message: string
  reply: string
  comment: string
  tags: string[]
  mode: string | null
}

const feedbackLog: FeedbackEntry[] = []

function feedbackSummary() {
  const up = feedbackLog.filter((e) => e.rating === 1).length
  const down = feedbackLog.filter((e) => e.rating === -1).length
  const neutral = feedbackLog.filter((e) => e.rating === 0).length
  const tagCounts = new Map<string, number>()
  for (const entry of feedbackLog) {
    if (entry.rating >= 0) continue
    for (const tag of entry.tags) tagCounts.set(tag, (tagCounts.get(tag) ?? 0) + 1)
  }
  return {
    total: feedbackLog.length,
    up,
    down,
    neutral,
    satisfaction_rate: up + down > 0 ? Number((up / (up + down)).toFixed(4)) : null,
    top_negative_tags: [...tagCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5),
  }
}

async function readMessage(request: Request): Promise<string> {
  try {
    const body = (await request.json()) as { message?: string }
    return body.message ?? ''
  } catch {
    return ''
  }
}

export const copilotHandlers = [
  http.post(toMswPath(ENDPOINTS.copilotChat.path), async ({ request }) => {
    const message = await readMessage(request)
    if (!message.trim()) return HttpResponse.json({ detail: 'Tin nhắn không được để trống.' }, { status: 422 })
    const turn = await buildTurn(message)
    return HttpResponse.json(turn)
  }),

  // Phản hồi của Sale (P2 — học từ phản hồi): mock lưu trong bộ nhớ phiên, đủ để demo + test UI.
  http.post(toMswPath(ENDPOINTS.copilotFeedback.path), async ({ request }) => {
    const body = (await request.json()) as {
      message?: string
      reply?: string
      rating?: number
      comment?: string
      tags?: string[]
      mode?: string | null
    }
    if (!body?.message || ![ -1, 0, 1 ].includes(Number(body.rating))) {
      return HttpResponse.json({ detail: 'Thiếu câu hỏi hoặc điểm đánh giá không hợp lệ.' }, { status: 422 })
    }
    const entry = {
      recorded_at: new Date().toISOString(),
      rating: Number(body.rating),
      message: body.message,
      reply: body.reply ?? '',
      comment: body.comment ?? '',
      tags: body.tags ?? [],
      mode: body.mode ?? null,
    }
    feedbackLog.push(entry)
    return HttpResponse.json({ ok: true, recorded_at: entry.recorded_at, summary: feedbackSummary() })
  }),

  http.get(toMswPath(ENDPOINTS.copilotFeedbackSummary.path), () =>
    HttpResponse.json(feedbackSummary()),
  ),

  http.post(toMswPath(ENDPOINTS.copilotChatStream.path), async ({ request }) => {
    const message = await readMessage(request)
    const turn = await buildTurn(message)
    const frames = turn.reasoning
      .map((event) => `event: copilot\ndata: ${JSON.stringify(event)}\n\n`)
      .join('')
    return new HttpResponse(frames, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    })
  }),
]
