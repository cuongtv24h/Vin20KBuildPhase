import type { OptimizationObjective, Recommendation, Scenario, ScenarioCode } from '@pricepolicy/api-client/contracts'

const ORDER: ScenarioCode[] = ['PA-CHUDONG', 'PA-NHANH', 'PA-VAY']

/** Giá trị so sánh theo mục tiêu — nhỏ hơn là tốt hơn (MAX_BENEFIT_VALUE đảo dấu). */
export function metricOf(objective: OptimizationObjective, s: Pick<Scenario, 'total_contract_price_vnd' | 'initial_payment_vnd' | 'total_cash_outflow_vnd' | 'benefit_value_vnd'>): number {
  switch (objective) {
    case 'MIN_NET_PRICE':
      return s.total_contract_price_vnd
    case 'MIN_INITIAL_OUTFLOW':
      return s.initial_payment_vnd
    case 'MIN_TOTAL_CASH_OUTFLOW':
      return s.total_cash_outflow_vnd
    case 'MAX_BENEFIT_VALUE':
      return -s.benefit_value_vnd
  }
}

/**
 * Ranking tất định (D2-4, ADR-015). Phương án không khả thi không thể đứng đầu.
 * Tie-break TB-01: giá hợp đồng thấp hơn; TB-02: thứ tự PA-CHUDONG → PA-NHANH → PA-VAY.
 */
export function rankScenarios(
  scenarios: (Pick<Scenario, 'scenario_code' | 'total_contract_price_vnd' | 'initial_payment_vnd' | 'total_cash_outflow_vnd' | 'benefit_value_vnd' | 'feasible'>)[],
  objective: OptimizationObjective,
): Recommendation | null {
  const feasible = scenarios.filter((s) => s.feasible)
  if (feasible.length === 0) return null
  const sorted = [...feasible].sort(
    (a, b) =>
      metricOf(objective, a) - metricOf(objective, b) ||
      a.total_contract_price_vnd - b.total_contract_price_vnd ||
      ORDER.indexOf(a.scenario_code) - ORDER.indexOf(b.scenario_code),
  )
  const [winner, runnerUp] = sorted
  const winnerMetric = metricOf(objective, winner)
  const tieBreak =
    !runnerUp || metricOf(objective, runnerUp) !== winnerMetric
      ? 'NONE'
      : runnerUp.total_contract_price_vnd !== winner.total_contract_price_vnd
        ? 'TB-01'
        : 'TB-02'
  return {
    objective,
    recommended_scenario: winner.scenario_code,
    tie_break_rule_id: tieBreak,
    comparisons: scenarios.map((s) => ({
      scenario_code: s.scenario_code,
      metric_vnd: Math.abs(metricOf(objective, s)),
      delta_vnd: metricOf(objective, s) - winnerMetric,
    })),
  }
}
