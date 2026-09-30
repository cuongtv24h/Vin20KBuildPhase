import type {
  BenchmarkAmounts,
  CustomerSegment,
  Installment,
  PolicyDocument,
  RuleEvaluation,
  Scenario,
  UnitSnapshot,
} from '@pricepolicy/api-client/contracts'
import type { PaymentPlanConfig } from '../fixtures/plans'
import { canonicalJsonStringify, sha256Hex } from './hash'

/**
 * Deterministic Pricing Engine giả lập (bản tham chiếu của C-06 sidecar). Số nguyên VNĐ,
 * làm tròn từng bước:
 *   discount        = round(listed × Σ tỷ lệ ELIGIBLE)
 *   net_before_tax  = listed − discount
 *   VAT             = round(net_before_tax × 10%)
 *   KPBT            = round(net_before_tax × 2%)
 *   total_contract  = net_before_tax + VAT + KPBT
 */
export const VAT_RATE = 0.1
export const KPBT_RATE = 0.02

export function sumRates(rates: number[]): number {
  return Math.round(rates.reduce((s, r) => s + r, 0) * 1_000_000) / 1_000_000
}

export function calculateAmounts(listed: number, rates: number[]): BenchmarkAmounts & { total_discount_rate: number } {
  const total_discount_rate = sumRates(rates)
  const discount_vnd = Math.round(listed * total_discount_rate)
  const net_price_before_tax_vnd = listed - discount_vnd
  const vat_vnd = Math.round(net_price_before_tax_vnd * VAT_RATE)
  const kpbt_vnd = Math.round(net_price_before_tax_vnd * KPBT_RATE)
  return {
    total_discount_rate,
    discount_vnd,
    net_price_before_tax_vnd,
    vat_vnd,
    kpbt_vnd,
    total_contract_price_vnd: net_price_before_tax_vnd + vat_vnd + kpbt_vnd,
  }
}

/** Chia tổng giá theo lịch; phần lẻ làm tròn dồn vào đợt cuối để tổng luôn khớp. */
export function buildSchedule(total: number, plan: PaymentPlanConfig): Installment[] {
  let allocated = 0
  return plan.schedule.map((m, idx) => {
    const last = idx === plan.schedule.length - 1
    const amount_vnd = last ? total - allocated : Math.round(total * m.ratio)
    allocated += amount_vnd
    return { seq: idx + 1, label: m.label, milestone: m.milestone, ratio: m.ratio, amount_vnd, payer: m.payer }
  })
}

export interface ScenarioInput {
  unit: UnitSnapshot
  policy: PolicyDocument
  plans: PaymentPlanConfig[]
  selected_rule_codes: string[]
  customer_segment: CustomerSegment
  units_quantity: number
}

export async function computeScenarios(input: ScenarioInput): Promise<Scenario[]> {
  const { unit, policy, plans, customer_segment, units_quantity } = input
  const selected = new Set(input.selected_rule_codes)
  const listed = unit.listed_price_before_tax_vnd

  return Promise.all(
    plans.map(async (plan) => {
      const evaluations: RuleEvaluation[] = []
      const rates: number[] = []
      let gifts = 0
      for (const rule of policy.rules) {
        if (!rule.applicable_scenarios.includes(plan.scenario_code) || rule.is_ambiguous) continue
        if (rule.is_selectable && !selected.has(rule.rule_code)) continue
        let status: RuleEvaluation['status'] = 'ELIGIBLE'
        let reason = `Thoả điều kiện áp dụng theo ${rule.source.section}.`
        let amount = 0
        if (rule.required_segments && !rule.required_segments.includes(customer_segment)) {
          status = 'NOT_ELIGIBLE'
          reason = `Hồ sơ khách không thuộc đối tượng quy định tại ${rule.source.section}.`
        } else if (rule.min_units_purchased && units_quantity < rule.min_units_purchased) {
          status = 'NOT_ELIGIBLE'
          reason = `Khách mua ${units_quantity} căn, chưa đạt ngưỡng ${rule.min_units_purchased} căn theo ${rule.source.section}.`
        } else if (rule.kind === 'PERCENT_DISCOUNT' && rule.discount_rate) {
          rates.push(rule.discount_rate)
          amount = Math.round(listed * rule.discount_rate)
        } else if (rule.kind === 'GIFT' && rule.cash_equivalent_vnd) {
          gifts += rule.cash_equivalent_vnd
          amount = rule.cash_equivalent_vnd
        } else if (rule.kind === 'BANK_SUPPORT') {
          reason = `Hỗ trợ lãi suất 0% trong ${rule.interest_support_months} tháng, ân hạn nợ gốc theo ${rule.source.section}.`
        }
        const effect = rule.kind === 'GIFT' ? 'IN_KIND' : rule.kind === 'BANK_SUPPORT' ? 'FINANCING' : 'PRICE_REDUCTION'
        evaluations.push({ rule_code: rule.rule_code, title: rule.title, status, effect, amount_vnd: amount, reason, source: rule.source })
      }

      const amounts = calculateAmounts(listed, rates)
      const schedule = buildSchedule(amounts.total_contract_price_vnd, plan)
      // Dòng tiền khách tự chi: đợt đầu tiên + tổng các đợt đến bàn giao (phần ngân hàng giải ngân không tính).
      let initial: number | null = null
      let outflow = 0
      schedule.forEach((installment, i) => {
        const milestone = plan.schedule[i]
        if (milestone.payer !== 'CUSTOMER') return
        initial ??= installment.amount_vnd
        if (milestone.before_handover) outflow += installment.amount_vnd
      })

      const scenario: Omit<Scenario, 'calculation_hash'> = {
        scenario_code: plan.scenario_code,
        label: plan.label,
        listed_price_before_tax_vnd: listed,
        ...amounts,
        initial_payment_vnd: initial ?? 0,
        total_cash_outflow_vnd: outflow,
        benefit_value_vnd: amounts.discount_vnd + gifts,
        installments_count: schedule.length,
        payment_schedule: schedule,
        rule_evaluations: evaluations,
        feasible: true,
      }
      return { ...scenario, calculation_hash: `sha256:${await sha256Hex(canonicalJsonStringify(scenario))}` }
    }),
  )
}
