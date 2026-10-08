import { http, HttpResponse } from 'msw'
import type { CopilotCitation, CopilotFinalPayload, CopilotStreamEvent, PolicyDocument, UnitSnapshot } from '@pricepolicy/api-client/contracts'
import { ENDPOINTS } from '@pricepolicy/api-client/endpoints'
import { computeScenarios } from '../engine/calculator'
import { selectPolicyForDate } from '../engine/conflicts'
import { rankScenarios } from '../engine/recommend'
import { PAYMENT_PLANS_FIXTURE } from '../fixtures/plans'
import { POLICIES_FIXTURE } from '../fixtures/policies'
import { PROJECTS_FIXTURE, UNITS_FIXTURE } from '../fixtures/units'
import { recordMockLlmCall } from './llmAdmin'
import { route, toMswPath } from './route'

/**
 * Sales Copilot giả lập — bản sao tất định của ReAct agent ở backend thật (C-??/SCR-S00).
 *
 * Mục đích: (1) hợp đồng mock phủ đủ endpoint trong `ENDPOINTS`; (2) demo offline không cần
 * API key vẫn cho Sale thấy tiến trình Thought → Action → Observation; (3) test UI stream.
 * Mọi con số đều lấy từ fixtures canonical / engine tất định — không bịa.
 */

const DEFAULT_DATE = '2026-09-26'

interface Intent {
  kind: 'policy' | 'units' | 'scenarios' | 'compose' | 'customer' | 'proposal' | 'smalltalk'
  unitCode: string | null
  bedrooms: number | null
  customerName: string
  /** Diện tích khách nêu ("70m²") — lọc ±10% vì Sale nói theo khoảng, không phải đúng 70.0m². */
  areaM2: number | null
  /** Trần ngân sách khách nêu ("tầm 3 tỷ" ⇒ 3.000.000.000). */
  maxPriceVnd: number | null
}

function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
}

const UNIT_RE = /\b([A-Z]{2,4}-[A-Z0-9]{1,3}-\d{3,4}|[A-Z]{1,3}-\d{2}\.\d{2})\b/i

/** Diện tích khách nêu: `70m²`, `70 m2`, `70 mét vuông` (chạy trên chuỗi ĐÃ bỏ dấu). */
// Không dùng `\b` sau đơn vị: `²` không phải ký tự chữ-số nên `70m² ` không có ranh giới từ ở đó
// (bẫy đã gặp cả ở backend — `70m²` sẽ không khớp nếu để `\b`).
const AREA_RE = /\b(\d{2,3}(?:[.,]\d+)?)\s*(?:m2|m²|met\s*vuong|mv)(?![a-z0-9])/i
/** Trần ngân sách: `3 tỷ`, `3.5 tỷ`, `900 triệu` (chạy trên chuỗi ĐÃ bỏ dấu). */
const PRICE_RE = /\b(\d+(?:[.,]\d+)?)\s*(ty|trieu|tr)\b/i
/**
 * Câu nhờ tìm căn có từ đệm giữa động từ và "căn" — "tìm **giúp em** căn 70m² tầm 3 tỷ" từng rơi vào
 * nhánh xã giao nên không trả về căn nào (lỗi người dùng báo). Đồng bộ mẫu với backend
 * (`intents.wants_browse_units`), chỉ khác là TỪ CHỐI câu có "khách" chen giữa (đó là tra hồ sơ khách).
 */
const BROWSE_VERB_RE = /\b(tim|tra|kiem|xem|liet ke|loc|mo)\b[^.!?]{0,24}\b(can|ro hang|gio hang)\b/

function parseArea(normalized: string): number | null {
  const match = AREA_RE.exec(normalized)
  if (!match) return null
  const value = Number(match[1].replace(',', '.'))
  return value >= 10 && value <= 500 ? value : null
}

function parseMaxPrice(normalized: string): number | null {
  const match = PRICE_RE.exec(normalized)
  if (!match) return null
  const value = Number(match[1].replace(',', '.'))
  const unit = match[2].toLowerCase()
  return Math.round(value * (unit === 'ty' ? 1_000_000_000 : 1_000_000))
}

/** Bảng lệnh gạch chéo → câu lệnh tự nhiên (đồng bộ với `SLASH_COMMAND_MAP` phía backend). */
const SLASH_HINTS: Array<[RegExp, (rest: string) => string]> = [
  [/^\/tao-khach/i, (rest) => `Tạo khách hàng mới${rest}`],
  [/^\/tim-khach/i, (rest) => `Tìm khách hàng${rest}`],
  [/^\/khach-hang/i, () => 'Xem danh sách hồ sơ khách'],
  [/^\/baogia/i, (rest) => `Xem pipeline báo giá${rest}`],
  [/^\/soan-tin/i, () => 'Soạn tin tư vấn cho khách'],
  [/^\/chinh-sach/i, (rest) => `Tra cứu chính sách đang hiệu lực${rest}`],
  [/^\/tinh-lai/i, (rest) => `Tính lại báo giá${rest}`],
  [/^\/gio-hang/i, () => 'Xem giỏ hàng còn căn nào'],
]

/**
 * Chuẩn hoá câu Sale gửi: lệnh gạch chéo (kể cả viết tắt như `/ch`) phải được dịch thành câu lệnh
 * tự nhiên **trước khi** phân tích ý định, nếu không từ khoá sẽ lọt vào câu trả lời.
 */
export function translateSlash(message: string): string {
  const trimmed = message.trim()
  const matched = SLASH_HINTS.find(([re]) => re.test(trimmed))
  if (matched) return matched[1](trimmed.replace(matched[0], ' ').replace(/\s+/g, ' ').trimEnd()).trim()
  if (!trimmed.startsWith('/')) return message
  const typed = trimmed.replace(/^\/+/, '').replace(/-/g, ' ').trim()
  // Gõ tắt (/ch, /baogi…) không khớp bảng đầy đủ: vẫn bỏ phần lệnh để không lộ vào câu trả lời.
  if (typed.length <= 3) return ''
  return typed.charAt(0).toUpperCase() + typed.slice(1)
}

function parseIntent(rawMessage: string): Intent {
  const message = translateSlash(rawMessage)
  const t = normalize(message)
  const unitMatch = UNIT_RE.exec(message)
  const bedrooms = /(\d)\s*(?:pn|phong ngu|ngu|br)\b/.exec(t)
  const areaM2 = parseArea(t)
  const maxPriceVnd = parseMaxPrice(t)
  const base = { unitCode: unitMatch?.[1]?.toUpperCase() ?? null, areaM2, maxPriceVnd }
  const phone = /0\d{9,10}/.exec(message)
  let name = message
    .replace(/^(tạo|thêm|mở|nhập|lưu|đăng\s*ký)\s*(khách(\s*hàng)?(\s*mới)?|lead|hồ\s*sơ)\s*/i, '')
    .replace(/^(mới\s*tên|mới\s*là|tên\s*là|tên|mới|anh|chị)\s*/i, '')
    .trim()
  if (phone && phone.index > 0) name = name.slice(0, phone.index)
  name = name.split(/[,;]/)[0].replace(/[,;:-]?\s*(sđt|sdt|phone)\s*$/i, '').trim()

  // So khớp trên chuỗi đã bỏ dấu (t) — từ khoá ở dạng không dấu để tránh bẫy như backend `_has()`.
  if (t.includes('tao khach') || t.includes('them khach') || t.includes('khach moi') || t.includes('tao lead')) {
    return { kind: 'customer', ...base, bedrooms: null, customerName: name }
  }
  // Nhánh "hồ sơ đề xuất" đứng TRƯỚC nhánh "báo giá" — đồng bộ với thứ tự nhánh trong
  // `src/agents/copilot/intents.py::detect_intent` phía backend.
  if (
    t.includes('ho so de xuat') ||
    t.includes('de xuat trinh') ||
    t.includes('soan de xuat') ||
    t.includes('lap de xuat') ||
    t.includes('ho so trinh duyet') ||
    t.includes('chuan bi ho so')
  ) {
    return { kind: 'proposal', ...base, bedrooms: bedrooms ? Number(bedrooms[1]) : null, customerName: '' }
  }
  if (t.includes('bao gia') || t.includes('so sanh') || t.includes('phuong an') || t.includes('dong tien')) {
    return { kind: 'scenarios', ...base, bedrooms: null, customerName: '' }
  }
  if (t.includes('soan tin') || t.includes('tin nhan')) {
    return { kind: 'compose', ...base, bedrooms: null, customerName: '' }
  }
  if (t.includes('gio hang') || t.includes('ro hang') || bedrooms) {
    return { kind: 'units', ...base, bedrooms: bedrooms ? Number(bedrooms[1]) : null, customerName: '' }
  }
  // Câu nhờ tìm căn có từ đệm ("tìm giúp em căn 70m² tầm 3 tỷ") — không có từ khoá "giỏ hàng" nên trước
  // đây rơi vào nhánh xã giao. Từ chối khi có "khách" chen giữa (đó là tra hồ sơ khách hàng).
  const browse = BROWSE_VERB_RE.exec(t)
  if (browse && !browse[0].includes('khach')) {
    return { kind: 'units', ...base, bedrooms: bedrooms ? Number(bedrooms[1]) : null, customerName: '' }
  }
  if (t.includes('chinh sach') || t.includes('chiet khau') || t.includes('hieu luc') || t.includes('dieu')) {
    return { kind: 'policy', ...base, bedrooms: null, customerName: '' }
  }
  return { kind: 'smalltalk', ...base, bedrooms: null, customerName: '' }
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

/** Khoảng diện tích đang lọc (nới ±10% cho một con số đơn) — dùng cho cả câu trả lời và bộ lọc. */
function areaWindow(intent: Intent): { min: number; max: number } | null {
  if (!intent.areaM2) return null
  return { min: intent.areaM2 * 0.9, max: intent.areaM2 * 1.1 }
}

const areaLabel = (value: number) => `${Math.round(value)}m²`
/** Nhãn khoảng diện tích: `63–77m²` (đơn vị ghi MỘT lần, không lặp `m²` ở cả hai đầu). */
const areaWindowLabel = (window: { min: number; max: number }) => `${Math.round(window.min)}–${Math.round(window.max)}m²`

/** Phễu dữ liệu khi lọc rỗng — đồng bộ tinh thần với `inventory_funnel.render_empty_funnel` phía backend. */
function emptyFunnelText(intent: Intent, citations: CopilotCitation[]) {
  const available = UNITS_FIXTURE.filter((u) => u.status === 'AVAILABLE')
  const histogram = new Map<number, number>()
  for (const unit of available) histogram.set(unit.bedrooms, (histogram.get(unit.bedrooms) ?? 0) + 1)
  const spread = [...histogram.entries()].sort((a, b) => a[0] - b[0]).map(([b, c]) => `${b}PN: ${c} căn`).join(', ')
  const softest = [...available].sort((a, b) => a.listed_price_before_tax_vnd - b.listed_price_before_tax_vnd)[0]
  const window = areaWindow(intent)
  const nearest = window
    ? [...available].filter((u) => Number(u.area_m2) > 0).sort((a, b) => Math.abs(a.area_m2 - intent.areaM2!) - Math.abs(b.area_m2 - intent.areaM2!))[0]
    : undefined

  const lines = ['Không có căn nào khớp đúng tiêu chí lọc.']
  if (intent.maxPriceVnd) lines.push(`Tiêu chí ngân sách: tối đa ${vnd(intent.maxPriceVnd)} (giá niêm yết trước thuế).`)
  if (window) lines.push(`Tiêu chí diện tích: ${areaWindowLabel(window)} (quanh ${intent.areaM2}m² khách nêu).`)
  if (softest) {
    lines.push(`Căn giá mềm nhất toàn giỏ: căn ${softest.unit_code} (${softest.area_m2}m², ${softest.project_name}) với giá ${vnd(softest.listed_price_before_tax_vnd)}.`)
    citations.push({ policy_id: 'CATALOG-UNITS', section: `Căn ${softest.unit_code}`, quote: `${softest.bedrooms}PN · ${softest.area_m2}m² · ${vnd(softest.listed_price_before_tax_vnd)} · ${softest.status}`, source: 'CANONICAL_CATALOG' })
  }
  if (nearest) {
    lines.push(`Căn gần khoảng diện tích này nhất: căn ${nearest.unit_code} (${nearest.area_m2}m², ${nearest.project_name}) — giá niêm yết ${vnd(nearest.listed_price_before_tax_vnd)}.`)
    citations.push({ policy_id: 'CATALOG-UNITS', section: `Căn ${nearest.unit_code}`, quote: `${nearest.bedrooms}PN · ${nearest.area_m2}m² · ${vnd(nearest.listed_price_before_tax_vnd)} · ${nearest.status}`, source: 'CANONICAL_CATALOG' })
  }
  lines.push(`Toàn giỏ đang mở bán có ${available.length} căn (${spread}) — đây là số liệu của TOÀN GIỎ.`)
  lines.push('Hướng tiếp theo: giữ nguyên tiêu chí hiện tại (diện tích/ngân sách) và xem phương án vốn tự có/vay cho căn gần nhất.')
  lines.push('Hướng tiếp theo: nới khoảng diện tích hoặc ngân sách nếu khách linh hoạt.')
  return lines.join('\n')
}

function answerUnits(intent: Intent, citations: CopilotCitation[]) {
  let pool = UNITS_FIXTURE.filter((u) => u.status === 'AVAILABLE')
  if (intent.unitCode) {
    const one = findUnit(intent.unitCode)
    pool = one ? [one] : []
  } else {
    if (intent.bedrooms) pool = pool.filter((u) => u.bedrooms === intent.bedrooms)
    if (intent.maxPriceVnd) pool = pool.filter((u) => u.listed_price_before_tax_vnd <= intent.maxPriceVnd!)
    const window = areaWindow(intent)
    if (window) pool = pool.filter((u) => u.area_m2 >= window.min && u.area_m2 <= window.max)
  }
  if (!pool.length) return emptyFunnelText(intent, citations)
  // Khoảng diện tích đang lọc phải hiện trong câu trả lời: Sale cần biết vì sao căn 52m² không có mặt.
  const criteria: string[] = []
  if (intent.bedrooms) criteria.push(`phân khúc ${intent.bedrooms}PN`)
  const window = areaWindow(intent)
  if (window) criteria.push(`khớp diện tích ${areaWindowLabel(window)}`)
  if (intent.maxPriceVnd) criteria.push(`trong ngân sách ${vnd(intent.maxPriceVnd)}`)
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
    `Dạ, em tìm được ${top.length} căn phù hợp${criteria.length ? ` (${criteria.join(', ')})` : ''}: ` +
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

/** Bản sao mock của tool `soan_ho_so_de_xuat` phía backend — hồ sơ NỘI BỘ trình Quản lý, không gửi khách. */
async function answerProposal(
  intent: Intent,
  unitCode: string | null,
  policy: PolicyDocument | null,
  citations: CopilotCitation[],
): Promise<string> {
  let unit = findUnit(unitCode)
  let autoPicked = false
  if (!unit && unitCode) {
    return `Em chưa tìm thấy mã căn ${unitCode} trong giỏ hàng đang mở bán ạ. Anh/chị kiểm tra lại mã căn giúp em nhé.`
  }
  if (!unit && intent.bedrooms) {
    unit =
      [...UNITS_FIXTURE]
        .filter((u) => u.status === 'AVAILABLE' && u.bedrooms === intent.bedrooms)
        .sort((a, b) => a.listed_price_before_tax_vnd - b.listed_price_before_tax_vnd)[0] ?? null
    autoPicked = Boolean(unit)
  }
  if (!unit) {
    return 'Em chưa xác định được căn để soạn hồ sơ đề xuất ạ. Anh/chị cho em mã căn cụ thể (ví dụ ZEN-A-1205) nhé.'
  }
  if (!policy) {
    return `Em chưa tra được chính sách hiệu lực cho căn ${unit.unit_code} tại thời điểm giao dịch nên chưa soạn được hồ sơ đề xuất ạ.`
  }

  const project = PROJECTS_FIXTURE.find((p) => p.project_id === unit.project_id)?.name ?? unit.project_id
  const scenarios = await computeScenarios({
    unit,
    policy,
    plans: PAYMENT_PLANS_FIXTURE,
    selected_rule_codes: ['EARLY_PAY_DISCOUNT', 'BANK_LOAN_HTLS'],
    customer_segment: 'NEW_CUSTOMER',
    units_quantity: 1,
  })
  const rec = rankScenarios(scenarios, 'MIN_NET_PRICE')
  const lines = [
    `HỒ SƠ ĐỀ XUẤT TRÌNH QUẢN LÝ — căn ${unit.unit_code} · ${project}`,
    ...(autoPicked ? [`[Lưu ý: căn được chọn tự động theo ${intent.bedrooms} phòng ngủ — Sale kiểm tra lại nhé]`] : []),
    '',
    `1. CĂN HỘ: ${unit.bedrooms}PN · ${unit.area_m2}m² · giá niêm yết ${vnd(unit.listed_price_before_tax_vnd)} · ${unit.status}`,
    '2. PHƯƠNG ÁN ĐỀ XUẤT (ưu tiên giá Net):',
  ]
  for (const s of scenarios) {
    lines.push(
      `• ${s.scenario_code} (${s.label}): giá Net ${vnd(s.net_price_before_tax_vnd)}, tổng HĐMB ${vnd(s.total_contract_price_vnd)}, ` +
        `đợt đầu ${vnd(s.initial_payment_vnd)}, tổng tự chi đến nhận nhà ${vnd(s.total_cash_outflow_vnd)}.`,
    )
  }
  lines.push(`Đề xuất tối ưu theo mục tiêu giá Net: ${rec?.recommended_scenario ?? '—'}.`)
  lines.push(`3. CHÍNH SÁCH ÁP DỤNG: ${policy.policy_id} (${policy.policy_version}) — hiệu lực ${policy.effective_from} → ${policy.effective_to}.`)
  for (const code of ['EARLY_PAY_DISCOUNT', 'BANK_LOAN_HTLS']) {
    const citation = policyCitation(policy, code)
    if (citation) {
      citations.push(citation)
      lines.push(`• ${citation.section} — ${citation.quote ?? ''}`)
    }
  }
  lines.push('4. VIỆC CẦN BỔ SUNG TRƯỚC KHI TRÌNH:')
  lines.push('• Vốn tự có của khách (để chốt phương án tối ưu theo dòng tiền).')
  citations.push({
    policy_id: 'FCS-v2.6',
    section: `Deterministic Math Engine · ${unit.unit_code}`,
    quote: `Hồ sơ đề xuất dựng từ ${scenarios.length} phương án chuẩn tắc; khuyến nghị ${rec?.recommended_scenario ?? '—'}`,
    source: 'DETERMINISTIC_ENGINE',
    document_hash: scenarios[0]?.calculation_hash,
  })
  lines.push('Số liệu do Deterministic Math Engine tính, không phải LLM tự tính [FCS v2.6].')
  return lines.join('\n')
}

async function buildTurn(message: string): Promise<CopilotFinalPayload & { reasoning: CopilotStreamEvent[] }> {
  const intent = parseIntent(message)
  const policy =
    intent.kind === 'scenarios' || intent.kind === 'policy' || intent.kind === 'proposal' ? activePolicy() : null
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
    case 'proposal':
      reasoning.push({
        type: 'action',
        tool: 'soan_ho_so_de_xuat',
        args: { ma_can: intent.unitCode, so_phong_ngu: intent.bedrooms },
      })
      reply = await answerProposal(intent, intent.unitCode, policy, citations)
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
  tools_used: string[]
  turn_id: string | null
}

const feedbackLog: FeedbackEntry[] = []

/** Che SĐT/email — bản sao hành vi `feedback.mask_pii` của backend thật. */
function maskPii(text: string): string {
  return text
    .replace(/\b0\d{8,10}\b/g, (m) => `${m.slice(0, 3)}***${m.slice(-2)}`)
    .replace(/\b[\w.+-]+@[\w-]+\.[\w.]+\b/g, '***@***')
}

/** Bản ghi đã che PII để trả cho trang quản trị chất lượng. */
function toEntryView(entry: FeedbackEntry, mask = true) {
  return {
    recorded_at: entry.recorded_at,
    rating: entry.rating,
    label: entry.rating > 0 ? 'up' : entry.rating < 0 ? 'down' : 'neutral',
    message: mask ? maskPii(entry.message) : entry.message,
    reply: mask ? maskPii(entry.reply) : entry.reply,
    comment: mask ? maskPii(entry.comment) : entry.comment,
    tags: entry.tags,
    mode: entry.mode,
    tools_used: entry.tools_used,
    turn_id: entry.turn_id,
  }
}

function feedbackSummary() {
  const up = feedbackLog.filter((e) => e.rating === 1).length
  const down = feedbackLog.filter((e) => e.rating === -1).length
  const neutral = feedbackLog.filter((e) => e.rating === 0).length
  const negatives = feedbackLog.filter((e) => e.rating < 0)
  const tagCounts = new Map<string, number>()
  const toolCounts = new Map<string, number>()
  const modeCounts = new Map<string, number>()
  const dayCounts = new Map<string, { up: number; down: number }>()
  for (const entry of feedbackLog) {
    modeCounts.set(entry.mode ?? 'không rõ', (modeCounts.get(entry.mode ?? 'không rõ') ?? 0) + 1)
    const day = entry.recorded_at.slice(0, 10)
    const bucket = dayCounts.get(day) ?? { up: 0, down: 0 }
    if (entry.rating > 0) bucket.up += 1
    if (entry.rating < 0) bucket.down += 1
    dayCounts.set(day, bucket)
  }
  for (const entry of negatives) {
    for (const tag of entry.tags) tagCounts.set(tag, (tagCounts.get(tag) ?? 0) + 1)
    for (const tool of entry.tools_used) toolCounts.set(tool, (toolCounts.get(tool) ?? 0) + 1)
  }
  return {
    total: feedbackLog.length,
    up,
    down,
    neutral,
    satisfaction_rate: up + down > 0 ? Number((up / (up + down)).toFixed(4)) : null,
    top_negative_tags: [...tagCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5),
    by_mode: [...modeCounts.entries()].map(([mode, count]) => ({ mode, count })),
    by_day: [...dayCounts.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([date, v]) => ({ date, ...v })),
    top_failing_tools: [...toolCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5),
    recent_negative: negatives.slice(-5).reverse().map((e) => toEntryView(e)),
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
    recordMockLlmCall('openai', 'gpt-4o-mini', message.length + turn.reply.length, turn.reply.length, 380 + (message.length % 120))
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
      tools_used?: string[]
      turn_id?: string | null
    }
    if (!body?.message || ![ -1, 0, 1 ].includes(Number(body.rating))) {
      return HttpResponse.json({ detail: 'Thiếu câu hỏi hoặc điểm đánh giá không hợp lệ.' }, { status: 422 })
    }
    const entry: FeedbackEntry = {
      recorded_at: new Date().toISOString(),
      rating: Number(body.rating),
      message: body.message,
      reply: body.reply ?? '',
      comment: body.comment ?? '',
      tags: body.tags ?? [],
      mode: body.mode ?? null,
      tools_used: body.tools_used ?? [],
      turn_id: body.turn_id ?? null,
    }
    feedbackLog.push(entry)
    return HttpResponse.json({ ok: true, recorded_at: entry.recorded_at, summary: feedbackSummary() })
  }),

  // Hai endpoint ĐỌC đi qua `route()` để được áp xác thực + phân quyền theo khai báo trong
  // `ENDPOINTS` (summary: mọi nhân viên; recent: chỉ ADMIN/POLICY_ADMIN).
  route('copilotFeedbackSummary', () => ({ body: feedbackSummary() })),

  // Trang quản trị chất lượng: danh sách chi tiết, mới nhất trước, đã che PII.
  route('copilotFeedbackRecent', ({ query }) => {
    const limit = Math.min(Math.max(Number(query.get('limit') ?? 50), 1), 200)
    const ratingParam = query.get('rating')
    const filtered = ratingParam === null ? feedbackLog : feedbackLog.filter((e) => e.rating === Number(ratingParam))
    const items = filtered.slice(-limit).reverse().map((e) => toEntryView(e))
    return { body: { total: items.length, items } }
  }),

  http.post(toMswPath(ENDPOINTS.copilotChatStream.path), async ({ request }) => {
    const message = await readMessage(request)
    const turn = await buildTurn(message)
    // Mock chạy offline nên không có LLM thật: ghi một lượt "gọi" tất định để tab
    // Chi phí & hiệu năng có số liệu thật để tính thay vì bảng rỗng.
    recordMockLlmCall('openai', 'gpt-4o-mini', message.length + turn.reply.length, turn.reply.length, 380 + (message.length % 120))
    const frames = turn.reasoning
      .map((event) => `event: copilot\ndata: ${JSON.stringify(event)}\n\n`)
      .join('')
    return new HttpResponse(frames, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    })
  }),
]
