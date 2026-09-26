import type {
  CustomerConstraints,
  EvidenceBackedClaim,
  OptimizationObjective,
  PolicyDocument,
  ReferencePlan,
  ReferenceScenario,
  UnitSnapshot,
} from '@/api/contracts'
import { PAYMENT_PLANS_FIXTURE } from '../fixtures/plans'
import { PROJECTS_FIXTURE } from '../fixtures/units'
import { computeScenarios } from './calculator'
import { snapshotRefOf } from './analyze'
import { selectPolicyForDate } from './conflicts'
import { rankScenarios } from './recommend'

/**
 * Pre-Sales Advisory giả lập (C-09 / F1–F3, F5). Trích ràng buộc tài chính từ câu trả lời tự do
 * (tiếng Việt), hỏi dẫn dắt phần còn thiếu, lập phương án THAM KHẢO có watermark — không bao giờ
 * ghi trạng thái duyệt, không gọi ký số / outbox PDF (INV-RT-09).
 */

export const EMPTY_CONSTRAINTS: CustomerConstraints = {
  own_funds_vnd: null,
  monthly_capacity_vnd: null,
  bedrooms: null,
  project_id: null,
  preferred_unit_code: null,
  objective: null,
  customer_segment: null,
}

export const REQUIRED: (keyof CustomerConstraints)[] = ['project_id', 'own_funds_vnd', 'monthly_capacity_vnd', 'customer_segment', 'objective']

const AMOUNT = /(\d+(?:[.,]\d+)?)\s*(tỷ|ty|triệu|trieu|tr)(?!\p{L})/giu

function toVnd(num: string, unit: string): number {
  const n = Number(num.replace(',', '.'))
  return Math.round(n * (/^t[ỷy]/i.test(unit) ? 1_000_000_000 : 1_000_000))
}

export function extractConstraints(text: string, current: CustomerConstraints, units: UnitSnapshot[]): CustomerConstraints {
  const next = { ...current }
  const lower = text.toLowerCase()

  for (const m of text.matchAll(AMOUNT)) {
    const value = toVnd(m[1], m[2])
    // Chỉ xét trong cùng mệnh đề (không vượt dấu phẩy) để "1,2 tỷ, mỗi tháng 25 triệu" tách đúng.
    const after = text.slice(m.index + m[0].length, m.index + m[0].length + 16).toLowerCase()
    const before = text.slice(Math.max(0, m.index - 24), m.index).toLowerCase()
    if (/^\s*(\/\s*1?\s*|mỗi |một |hàng |1 )tháng/.test(after) || /(mỗi tháng|hàng tháng|trả góp)[^,.;]*$/.test(before)) next.monthly_capacity_vnd = value
    else next.own_funds_vnd = value
  }

  const code = /\b(ZEN|SAP)-[A-D]-\d{4}\b/i.exec(text)?.[0]?.toUpperCase()
  const unit = code ? units.find((u) => u.unit_code === code) : undefined
  if (unit) {
    next.preferred_unit_code = unit.unit_code
    next.project_id = unit.project_id
    next.bedrooms ??= unit.bedrooms
  }
  if (/zen/.test(lower)) next.project_id = 'THE_ZEN_PARK'
  if (/sapphire|sap\b/.test(lower)) next.project_id = 'VLANDFUTURE_SAPPHIRE'

  const br = /(\d)\s*(pn|phòng ngủ|phong ngu)/i.exec(text)
  if (br) next.bedrooms = Number(br[1])

  const objectives: [RegExp, OptimizationObjective][] = [
    [/(trả trước ít|đợt đầu (thấp|ít)|ít vốn|vốn ban đầu|trả trước thấp)/, 'MIN_INITIAL_OUTFLOW'],
    [/(giá (mua )?thấp|rẻ nhất|tổng giá thấp|giá tốt nhất|chiết khấu cao)/, 'MIN_NET_PRICE'],
    [/(dòng tiền|tổng tiền (phải )?trả|chi ít nhất)/, 'MIN_TOTAL_CASH_OUTFLOW'],
    [/(quà|nhiều ưu đãi|nội thất|voucher)/, 'MAX_BENEFIT_VALUE'],
  ]
  for (const [re, objective] of objectives) if (re.test(lower)) next.objective = objective

  if (/(đã mua|cư dân|đã sở hữu|khách cũ|khách hàng cũ)/.test(lower)) next.customer_segment = 'EXISTING_RESIDENT'
  else if (/(lần đầu|chưa (từng )?(mua|sở hữu)|khách mới|mua mới)/.test(lower)) next.customer_segment = 'NEW_CUSTOMER'

  return next
}

export function missingOf(c: CustomerConstraints): (keyof CustomerConstraints)[] {
  return REQUIRED.filter((k) => c[k] === null)
}

const QUESTIONS: Record<string, { text: string; suggestions: string[] }> = {
  project_id: { text: 'Anh/chị đang quan tâm dự án nào ạ?', suggestions: ['The Zen Park', 'VLandFuture Sapphire'] },
  own_funds_vnd: { text: 'Hiện anh/chị có sẵn khoảng bao nhiêu vốn tự có cho căn hộ?', suggestions: ['800 triệu', '1,5 tỷ', '3 tỷ'] },
  monthly_capacity_vnd: { text: 'Mỗi tháng anh/chị có thể dành khoảng bao nhiêu để trả góp?', suggestions: ['15 triệu/tháng', '25 triệu/tháng', '40 triệu/tháng'] },
  customer_segment: { text: 'Anh/chị đã từng sở hữu sản phẩm của VLandFuture chưa?', suggestions: ['Tôi đã mua căn của VLandFuture', 'Đây là lần đầu tôi mua'] },
  objective: {
    text: 'Anh/chị ưu tiên điều gì nhất khi chọn phương án thanh toán?',
    suggestions: ['Trả trước ít nhất', 'Giá mua thấp nhất', 'Tổng dòng tiền thấp nhất', 'Nhiều quà tặng nhất'],
  },
}

export function nextQuestion(c: CustomerConstraints): { text: string; suggestions: string[] } | null {
  const missing = missingOf(c)[0]
  return missing ? QUESTIONS[missing] : null
}

const vnd = (n: number) => `${n.toLocaleString('vi-VN')} đ`

const PLAN_BOUND = (policy: PolicyDocument) =>
  policy.rules.filter((r) => r.is_selectable && !r.is_ambiguous && r.applicable_scenarios.length === 1).map((r) => r.rule_code)

/** Lập phương án tham khảo: chọn căn phù hợp vốn tự có, tính 3 phương án, đánh dấu khả thi. */
export async function buildReferencePlan(params: {
  constraints: CustomerConstraints
  units: UnitSnapshot[]
  policies: PolicyDocument[]
  today: string
  now: number
  planId: string
}): Promise<{ plan: ReferencePlan | null; unit: UnitSnapshot | null; reason: string | null }> {
  const { constraints: c, units, policies, today } = params
  const projectId = c.project_id ?? 'THE_ZEN_PARK'
  const policy = selectPolicyForDate(policies, projectId, today)
  if (!policy) return { plan: null, unit: null, reason: 'Dự án hiện chưa có chính sách bán hàng hiệu lực.' }

  const pool = units
    .filter((u) => u.project_id === projectId && u.status === 'AVAILABLE' && (!c.bedrooms || u.bedrooms === c.bedrooms))
    .filter((u) => u.listed_price_before_tax_vnd > 100_000_000)
    .sort((a, b) => a.listed_price_before_tax_vnd - b.listed_price_before_tax_vnd)
  const preferred = c.preferred_unit_code ? units.find((u) => u.unit_code === c.preferred_unit_code && u.status === 'AVAILABLE') : undefined
  const own = c.own_funds_vnd ?? 0
  // Căn giá cao nhất mà vốn tự có vẫn đủ trả đợt đầu phương án vay (15% giá hợp đồng ≈ 17% giá trước thuế).
  const affordable = [...pool].reverse().find((u) => u.listed_price_before_tax_vnd * 1.12 * 0.15 <= own)
  const unit = preferred ?? affordable ?? pool[0]
  if (!unit) return { plan: null, unit: null, reason: 'Không còn căn phù hợp số phòng ngủ đang mở bán.' }

  const scenarios = await computeScenarios({
    unit,
    policy,
    plans: PAYMENT_PLANS_FIXTURE,
    selected_rule_codes: PLAN_BOUND(policy),
    customer_segment: c.customer_segment ?? 'NEW_CUSTOMER',
    units_quantity: 1,
  })

  const refs: ReferenceScenario[] = scenarios.map((s) => {
    const feasible = s.initial_payment_vnd <= own
    const claims: EvidenceBackedClaim[] = s.rule_evaluations
      .filter((ev) => ev.status === 'ELIGIBLE')
      .map((ev, i) => ({
        claim_id: `${s.scenario_code}-EV-${i + 1}`,
        claim_type: 'POLICY_REASON',
        direction: 'WHY',
        text: `${ev.title}${ev.amount_vnd ? `: ${vnd(ev.amount_vnd)}` : ''}`,
        support_status: 'SUPPORTED',
        source_coordinates: [ev.source],
        calculation_refs: [],
        unsupported_fragment: null,
        rule_code: ev.rule_code,
        decision_status: 'ELIGIBLE',
      }))
    return {
      scenario_code: s.scenario_code,
      label: s.label,
      unit_code: unit.unit_code,
      total_contract_price_vnd: s.total_contract_price_vnd,
      initial_payment_vnd: s.initial_payment_vnd,
      total_cash_outflow_vnd: s.total_cash_outflow_vnd,
      benefit_value_vnd: s.benefit_value_vnd,
      feasible,
      infeasible_reason: feasible ? null : `Đợt đầu cần ${vnd(s.initial_payment_vnd)}, vượt vốn tự có ${vnd(own)}.`,
      claims,
    }
  })

  const objective = c.objective ?? 'MIN_INITIAL_OUTFLOW'
  const rec = rankScenarios(refs, objective)
  const project = PROJECTS_FIXTURE.find((p) => p.project_id === projectId)
  return {
    unit,
    reason: null,
    plan: {
      plan_id: params.planId,
      generated_at: new Date(params.now).toISOString(),
      expires_at: new Date(params.now + 24 * 3_600_000).toISOString(),
      watermark: 'PRE-SALES ESTIMATE — NOT AN OFFICIAL QUOTE',
      policy_snapshot_ref: await snapshotRefOf(policy),
      objective,
      recommended_scenario: rec?.recommended_scenario ?? null,
      scenarios: refs,
      assumptions: [
        `Căn ${unit.unit_code} — ${unit.bedrooms} phòng ngủ, ${unit.area_m2} m², ${project?.name ?? ''}`,
        `Vốn tự có ${vnd(own)}${c.monthly_capacity_vnd ? `, trả góp tối đa ${vnd(c.monthly_capacity_vnd)}/tháng` : ''}`,
        `Tính theo ${policy.title} (${policy.policy_version}) tại ngày ${today.split('-').reverse().join('/')}`,
      ],
      disclaimer:
        'Phương án tham khảo dựa trên chính sách đang hiệu lực và thông tin anh/chị cung cấp, không phải báo giá chính thức. Giá và ưu đãi được xác nhận lại khi chuyên viên lập báo giá.',
    },
  }
}

export function summarizeNeeds(c: CustomerConstraints, unitCode: string | null): string {
  const project = PROJECTS_FIXTURE.find((p) => p.project_id === c.project_id)?.name
  const parts = [
    `Quan tâm ${unitCode ? `căn ${unitCode}` : c.bedrooms ? `căn ${c.bedrooms}PN` : 'căn hộ'}${project ? ` tại ${project}` : ''}`,
    c.own_funds_vnd ? `vốn tự có ${vnd(c.own_funds_vnd)}` : null,
    c.monthly_capacity_vnd ? `trả góp ${vnd(c.monthly_capacity_vnd)}/tháng` : null,
  ]
  return parts.filter(Boolean).join(', ') + '.'
}
