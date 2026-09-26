import type {
  ComplianceCheckMode,
  ComplianceCheckResponse,
  ComplianceClaim,
  ComplianceRequiredAction,
  ComplianceStatus,
  PolicyDocument,
  Quote,
  SourceCoordinate,
} from '@/api/contracts'
import { sha256Hex } from './hash'

/**
 * Claim Compliance Service giả lập (F8 / C-11, quy chuẩn POL-08). Dùng chung cho tin Agent soạn và
 * tin Sale tự gõ (ADR-019 Zero-Trust). Rule-based: bóc tách claim rủi ro rồi đối chiếu với số liệu
 * quote + điều khoản chính sách.
 */

const RANK: Record<ComplianceStatus, number> = { SUPPORTED: 0, CONDITIONAL: 1, UNSUPPORTED: 2, PROHIBITED: 3 }

interface Pattern {
  re: RegExp
  status: ComplianceStatus
  reason: string
  rewrite: string | null
  sourceRule?: string
}

const PROHIBITED: Pattern[] = [
  {
    re: /(chắc chắn|đảm bảo|cam kết|100%)[^.!?\n]{0,40}(được vay|duyệt vay|giải ngân|được ngân hàng duyệt|vay được)[^.!?\n]{0,25}/gi,
    status: 'PROHIBITED',
    reason: 'Cam kết phê duyệt tín dụng — vượt thẩm quyền (POL-08). Việc cho vay do ngân hàng thẩm định.',
    rewrite: 'Ngân hàng đối tác sẽ thẩm định hồ sơ; tỷ lệ vay tối đa theo chính sách là 70% giá trị căn hộ.',
  },
  {
    re: /(cam kết|đảm bảo|chắc chắn)[^.!?\n]{0,30}(lợi nhuận|sinh lời|tăng giá|lãi \d)[^.!?\n]{0,25}/gi,
    status: 'PROHIBITED',
    reason: 'Cam kết lợi nhuận / tăng giá — phát ngôn bị cấm (POL-08).',
    rewrite: null,
  },
  {
    re: /(miễn|không phải trả)[^.!?\n]{0,15}(cả )?(gốc (và|lẫn) lãi|lãi (và|lẫn) gốc)/gi,
    status: 'PROHIBITED',
    reason: 'Chính sách chỉ ân hạn nợ gốc và hỗ trợ lãi suất có thời hạn, không miễn cả gốc và lãi.',
    rewrite: 'hỗ trợ lãi suất 0% và ân hạn nợ gốc trong thời gian quy định',
    sourceRule: 'BANK_LOAN_HTLS',
  },
]

const MONEY_RE = /(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(?:(tỷ|triệu|tr|đồng|đ|vnđ|vnd)(?!\p{L}))?/giu
const PERCENT_RE = /(chiết khấu|giảm|ưu đãi)\s*(?:thêm\s*)?(\d+(?:[.,]\d+)?)\s*%/gi
const LOAN_RE = /(hỗ trợ lãi suất|lãi suất 0\s?%)[^!?\n]{0,60}/gi

function parseMoney(num: string, unit: string | undefined): number | null {
  const u = (unit ?? '').toLowerCase()
  if (u === 'tỷ' || u === 'triệu' || u === 'tr') {
    const n = Number(num.replace(',', '.'))
    if (!Number.isFinite(n)) return null
    return Math.round(n * (u === 'tỷ' ? 1_000_000_000 : 1_000_000))
  }
  if (/^\d{1,3}([.,]\d{3})+$/.test(num)) return Number(num.replace(/[.,]/g, ''))
  return null
}

/** So khớp theo độ chính xác người viết dùng ("4,23 tỷ" khớp 4.233.600.000). */
function matchesAmount(stated: number, actual: number, unit: string | undefined): boolean {
  const u = (unit ?? '').toLowerCase()
  if (u === 'tỷ') return Math.abs(stated - actual) < 5_000_000 || Math.abs(Math.round(actual / 10_000_000) * 10_000_000 - stated) < 10_000_000
  if (u === 'triệu' || u === 'tr') return Math.abs(stated - actual) < 500_000
  return stated === actual
}

export async function checkMessage(params: {
  text: string
  mode: ComplianceCheckMode
  quote: Quote
  policy: PolicyDocument | null
  checkId: string
}): Promise<ComplianceCheckResponse> {
  const { text, quote, policy } = params
  const claims: ComplianceClaim[] = []
  const covered: [number, number][] = []
  const overlaps = (s: number, e: number) => covered.some(([a, b]) => s < b && e > a)
  const ruleSource = (code?: string): SourceCoordinate[] => {
    const r = code ? policy?.rules.find((x) => x.rule_code === code) : undefined
    return r ? [r.source] : []
  }
  const push = (start: number, end: number, status: ComplianceStatus, reason: string, rewrite: string | null, sources: SourceCoordinate[] = []) => {
    if (overlaps(start, end)) return
    covered.push([start, end])
    claims.push({
      claim_id: `CLM-${String(claims.length + 1).padStart(2, '0')}`,
      text: text.slice(start, end),
      span_start: start,
      span_end: end,
      status,
      reason,
      source_coordinates: sources,
      suggested_rewrite: rewrite,
    })
  }

  for (const p of PROHIBITED) for (const m of text.matchAll(p.re)) push(m.index, m.index + m[0].length, p.status, p.reason, p.rewrite, ruleSource(p.sourceRule))

  // Hỗ trợ lãi suất: phải kèm điều kiện vay tối thiểu 70% → CONDITIONAL nếu thiếu.
  const loanRule = policy?.rules.find((r) => r.kind === 'BANK_SUPPORT')
  for (const m of text.matchAll(LOAN_RE)) {
    // Dấu chấm trong số tiền (4.233.600.000) không kết thúc câu.
    const sentenceEnd = text.slice(m.index).search(/[!?\n]|\.(?!\d)/)
    const sentence = text.slice(m.index, sentenceEnd === -1 ? undefined : m.index + sentenceEnd)
    const hasCondition = /70\s?%/.test(sentence)
    const months = loanRule?.interest_support_months
    const monthsStated = /(\d+)\s*tháng/.exec(sentence)?.[1]
    if (monthsStated && months && Number(monthsStated) !== months) {
      push(m.index, m.index + sentence.length, 'UNSUPPORTED', `Chính sách hỗ trợ ${months} tháng, tin nhắn ghi ${monthsStated} tháng.`, `hỗ trợ lãi suất 0% trong ${months} tháng`, ruleSource(loanRule?.rule_code))
    } else if (hasCondition) {
      push(m.index, m.index + sentence.length, 'SUPPORTED', 'Khớp điều khoản hỗ trợ lãi suất, đã nêu điều kiện vay tối thiểu 70%.', null, ruleSource(loanRule?.rule_code))
    } else {
      push(m.index, m.index + sentence.length, 'CONDITIONAL', 'Ưu đãi có điều kiện — cần nêu rõ áp dụng khi vay tối thiểu 70% giá trị căn hộ.', `${sentence.trim()} (áp dụng khi vay tối thiểu 70% giá trị căn hộ)`, ruleSource(loanRule?.rule_code))
    }
  }

  // Tỷ lệ chiết khấu phải khớp điều khoản đã áp dụng trong quote.
  const appliedRates = new Map<number, string>()
  for (const s of quote.scenarios)
    for (const ev of s.rule_evaluations) {
      const rule = policy?.rules.find((r) => r.rule_code === ev.rule_code)
      if (ev.status === 'ELIGIBLE' && rule?.discount_rate) appliedRates.set(Math.round(rule.discount_rate * 10_000), rule.rule_code)
    }
  for (const m of text.matchAll(PERCENT_RE)) {
    const rate = Math.round(Number(m[2].replace(',', '.')) * 100)
    const total = quote.scenarios.some((s) => Math.round(s.total_discount_rate * 10_000) === rate)
    const code = appliedRates.get(rate)
    if (code || total) push(m.index, m.index + m[0].length, 'SUPPORTED', 'Khớp tỷ lệ ưu đãi trong hồ sơ đã duyệt.', null, ruleSource(code))
    else push(m.index, m.index + m[0].length, 'UNSUPPORTED', `Hồ sơ không có ưu đãi ${m[2]}%.`, null)
  }

  // Số tiền phải khớp calculation artifact của phiên bản quote.
  const amounts = quote.scenarios.flatMap((s) => [
    s.total_contract_price_vnd,
    s.initial_payment_vnd,
    s.total_cash_outflow_vnd,
    s.discount_vnd,
    s.net_price_before_tax_vnd,
    s.listed_price_before_tax_vnd,
    ...s.rule_evaluations.map((r) => r.amount_vnd),
    ...s.payment_schedule.map((p) => p.amount_vnd),
  ])
  for (const m of text.matchAll(MONEY_RE)) {
    const value = parseMoney(m[1], m[2])
    if (value === null || value < 1_000_000) continue
    const ok = amounts.some((a) => a > 0 && matchesAmount(value, a, m[2]))
    push(
      m.index,
      m.index + m[0].length,
      ok ? 'SUPPORTED' : 'UNSUPPORTED',
      ok ? `Khớp số liệu tính toán của ${quote.quote_id} v${quote.quote_version}.` : 'Số tiền không khớp bất kỳ số liệu nào trong báo giá đã duyệt.',
      null,
    )
  }

  claims.sort((a, b) => a.span_start - b.span_start)
  const overall = claims.reduce<ComplianceStatus>((w, c) => (RANK[c.status] > RANK[w] ? c.status : w), 'SUPPORTED')
  const action: ComplianceRequiredAction =
    overall === 'PROHIBITED' ? 'REMOVE_PROHIBITED' : overall === 'UNSUPPORTED' ? 'REWRITE_UNSUPPORTED' : overall === 'CONDITIONAL' ? 'KEEP_REQUIRED_CONDITION' : 'NONE'

  return {
    check_id: params.checkId,
    message_hash: `sha256:${await sha256Hex(text)}`,
    mode: params.mode,
    overall_status: overall,
    quote_id: quote.quote_id,
    quote_version: quote.quote_version,
    policy_version_refs: quote.policy_snapshot_ref ? [`${quote.policy_snapshot_ref.policy_id}:${quote.policy_snapshot_ref.policy_version}`] : [],
    claims,
    required_action: action,
  }
}

const vnd = (n: number) => `${n.toLocaleString('vi-VN')} đ`

/** Tin đề xuất do Agent soạn — chỉ dùng số liệu của phiên bản quote, vẫn phải qua check như tin Sale gõ. */
export function draftMessage(quote: Quote, policy: PolicyDocument | null): string {
  const rec = quote.scenarios.find((s) => s.scenario_code === quote.recommendation?.recommended_scenario) ?? quote.scenarios[0]
  const loan = rec?.scenario_code === 'PA-VAY' ? policy?.rules.find((r) => r.kind === 'BANK_SUPPORT') : undefined
  const lines = [
    `Chào anh/chị ${quote.transaction_context.customer_name},`,
    `VLandFuture gửi anh/chị báo giá chính thức căn ${quote.unit.unit_code} (${quote.unit.project_name}), mã ${quote.quote_id}.`,
    rec ? `Phương án ${rec.label}: giá bán sau ưu đãi ${vnd(rec.total_contract_price_vnd)} (đã gồm VAT và KPBT), thanh toán đợt đầu ${vnd(rec.initial_payment_vnd)}.` : '',
    loan ? `Gói vay hỗ trợ lãi suất 0% trong ${loan.interest_support_months} tháng áp dụng khi vay tối thiểu 70% giá trị căn hộ.` : '',
    'Anh/chị cần giải thích thêm khoản nào, em sẵn sàng hỗ trợ.',
  ]
  return lines.filter(Boolean).join('\n')
}
