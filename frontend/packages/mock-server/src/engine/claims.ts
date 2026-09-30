import type { EvidenceBackedClaim, PolicyDocument, Recommendation, Scenario, TransactionContext } from '@pricepolicy/api-client/contracts'

const OBJECTIVE_TEXT: Record<Recommendation['objective'], string> = {
  MIN_NET_PRICE: 'giá mua thấp nhất',
  MIN_INITIAL_OUTFLOW: 'trả trước ít nhất',
  MIN_TOTAL_CASH_OUTFLOW: 'dòng tiền đến bàn giao thấp nhất',
  MAX_BENEFIT_VALUE: 'giá trị ưu đãi lớn nhất',
}

const vnd = (n: number) => `${n.toLocaleString('vi-VN')} đ`
const pct = (r: number) => `${(r * 100).toLocaleString('vi-VN', { maximumFractionDigits: 2 })}%`

/**
 * Claim-level evidence (F4 / C-04): mỗi luận điểm Why / Why-not mang SourceCoordinate do
 * server resolve từ registry, hoặc field path của calculation artifact. Claim vượt quá chứng cứ
 * bị tách phần không có căn cứ (PARTIALLY_SUPPORTED) thay vì bị làm mềm.
 */
export function buildQuoteClaims(
  policy: PolicyDocument,
  context: TransactionContext,
  scenarios: Scenario[],
  recommendation: Recommendation | null,
): EvidenceBackedClaim[] {
  const claims: EvidenceBackedClaim[] = []
  let n = 0
  const id = (prefix: string) => `${prefix}-${String(++n).padStart(3, '0')}`
  const base = { unsupported_fragment: null, rule_code: null, decision_status: null, calculation_refs: [] as string[], source_coordinates: [] as EvidenceBackedClaim['source_coordinates'] }

  // Why — ưu đãi được áp dụng (gộp theo điều khoản, ghi rõ phương án áp dụng)
  const byRule = new Map<string, { scenarios: string[]; ev: Scenario['rule_evaluations'][number] }>()
  for (const s of scenarios) {
    for (const ev of s.rule_evaluations) {
      if (ev.status !== 'ELIGIBLE') continue
      const entry = byRule.get(ev.rule_code) ?? { scenarios: [], ev }
      entry.scenarios.push(s.label)
      byRule.set(ev.rule_code, entry)
    }
  }
  for (const [code, { scenarios: labels, ev }] of byRule) {
    const rule = policy.rules.find((r) => r.rule_code === code)
    const value = rule?.kind === 'PERCENT_DISCOUNT' && rule.discount_rate ? `giảm ${pct(rule.discount_rate)}` : rule?.kind === 'GIFT' && rule.cash_equivalent_vnd ? `quà tặng quy đổi ${vnd(rule.cash_equivalent_vnd)}` : 'được áp dụng'
    claims.push({
      ...base,
      claim_id: id('WHY'),
      claim_type: 'POLICY_REASON',
      direction: 'WHY',
      text: `${ev.title}: ${value} (${labels.join(', ')}).`,
      support_status: 'SUPPORTED',
      source_coordinates: [ev.source],
      rule_code: code,
      decision_status: 'ELIGIBLE',
    })
    // Giải trình do LLM soạn cho gói vay diễn giải "ân hạn nợ gốc" thành "miễn nợ gốc" — N-14B tách phần vượt chứng cứ.
    if (rule?.kind === 'BANK_SUPPORT') {
      claims.push({
        ...base,
        claim_id: id('WHY'),
        claim_type: 'POLICY_REASON',
        direction: 'WHY',
        text: `Khách được hỗ trợ lãi suất 0% trong ${rule.interest_support_months} tháng và miễn trả nợ gốc đến khi bàn giao.`,
        support_status: 'PARTIALLY_SUPPORTED',
        unsupported_fragment: 'miễn trả nợ gốc',
        source_coordinates: [rule.source],
        rule_code: code,
        decision_status: 'ELIGIBLE',
      })
    }
  }

  // Why — kết quả tính toán
  for (const s of scenarios) {
    claims.push({
      ...base,
      claim_id: id('CALC'),
      claim_type: 'CALCULATION_RESULT',
      direction: 'WHY',
      text: `${s.label}: giá bán sau ưu đãi ${vnd(s.total_contract_price_vnd)}, thanh toán đợt đầu ${vnd(s.initial_payment_vnd)}.`,
      support_status: 'SUPPORTED',
      calculation_refs: [`scenarios[${s.scenario_code}].total_contract_price_vnd`, `scenarios[${s.scenario_code}].initial_payment_vnd`],
    })
  }

  if (recommendation) {
    const winner = scenarios.find((s) => s.scenario_code === recommendation.recommended_scenario)
    claims.push({
      ...base,
      claim_id: id('REC'),
      claim_type: 'DERIVED_RECOMMENDATION',
      direction: 'WHY',
      text: `Theo tiêu chí ${OBJECTIVE_TEXT[recommendation.objective]}, ${winner?.label ?? recommendation.recommended_scenario} xếp hạng 1${recommendation.tie_break_rule_id === 'NONE' ? '' : ` (hoà, áp quy tắc ${recommendation.tie_break_rule_id})`}.`,
      support_status: 'SUPPORTED',
      calculation_refs: ['recommendation.comparisons'],
    })
  }

  if (context.customer_segment === 'EXISTING_RESIDENT') {
    claims.push({
      ...base,
      claim_id: id('USR'),
      claim_type: 'USER_PROVIDED',
      direction: 'WHY',
      text: 'Khách hàng khai là cư dân hiện hữu của VLandFuture — chưa đính kèm chứng từ.',
      support_status: 'UNSUPPORTED',
      rule_code: 'RESIDENT_DISCOUNT',
    })
  }

  // Why-not — không đủ điều kiện
  const notEligible = new Map<string, Scenario['rule_evaluations'][number]>()
  for (const s of scenarios) for (const ev of s.rule_evaluations) if (ev.status === 'NOT_ELIGIBLE') notEligible.set(ev.rule_code, ev)
  for (const ev of notEligible.values()) {
    claims.push({
      ...base,
      claim_id: id('WHYNOT'),
      claim_type: 'POLICY_REASON',
      direction: 'WHY_NOT',
      text: `${ev.title}: ${ev.reason}`,
      support_status: 'SUPPORTED',
      source_coordinates: [ev.source],
      rule_code: ev.rule_code,
      decision_status: 'NOT_ELIGIBLE',
    })
  }

  // Why-not — bị loại trừ bởi ưu đãi đã áp dụng (PRD §7: nội thất bị loại theo Điều 6.2)
  const applied = new Set(byRule.keys())
  for (const code of applied) {
    const rule = policy.rules.find((r) => r.rule_code === code)
    for (const rel of rule?.relations ?? []) {
      if (rel.type !== 'MUTUALLY_EXCLUSIVE' || applied.has(rel.rule_code)) continue
      const excluded = policy.rules.find((r) => r.rule_code === rel.rule_code)
      if (!excluded || claims.some((c) => c.rule_code === excluded.rule_code && c.direction === 'WHY_NOT')) continue
      claims.push({
        ...base,
        claim_id: id('WHYNOT'),
        claim_type: 'POLICY_REASON',
        direction: 'WHY_NOT',
        text: `${excluded.title}: không áp dụng vì đã chọn ${rule?.title} — ${rel.reason ?? 'loại trừ lẫn nhau'}`,
        support_status: 'SUPPORTED',
        source_coordinates: [excluded.source],
        rule_code: excluded.rule_code,
        decision_status: 'CONFLICT',
      })
    }
  }

  return claims
}
