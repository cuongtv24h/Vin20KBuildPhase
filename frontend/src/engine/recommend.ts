import { formatVnd } from '@/lib/format'
import type { CalculationResult, OptimizationObjective, RecommendationRecord } from '@/types/domain'

/**
 * Hàm toán học tất định xếp hạng 3 phương án theo đúng 1 trong 4 tiêu chí người dùng
 * chỉ định (ADR-015 — Deterministic Recommendation Ranking Boundary). LLM/Agent chỉ
 * xác định mục tiêu của khách; việc so sánh số học để chọn kịch bản chiến thắng do
 * hàm này thực hiện, không phán xét chủ quan.
 */

const OBJECTIVE_LABEL: Record<OptimizationObjective, string> = {
  MIN_NET_PRICE: 'Giá mua sau ưu đãi thấp nhất',
  MIN_INITIAL_OUTFLOW: 'Số tiền thanh toán đợt 1 thấp nhất',
  MIN_TOTAL_CASH_OUTFLOW: 'Tổng dòng tiền thanh toán thực tế thấp nhất',
  MAX_BENEFIT_VALUE: 'Giá trị ưu đãi & quà tặng quy đổi lớn nhất',
}

function metricFor(objective: OptimizationObjective, s: CalculationResult): number {
  switch (objective) {
    case 'MIN_NET_PRICE':
      return s.netPrice
    case 'MIN_INITIAL_OUTFLOW':
      return s.initialPaymentVnd
    case 'MIN_TOTAL_CASH_OUTFLOW':
      return s.totalCashOutflowToHandoverVnd
    case 'MAX_BENEFIT_VALUE':
      return -s.benefitValueVnd
  }
}

function metricLabel(objective: OptimizationObjective): string {
  switch (objective) {
    case 'MIN_NET_PRICE':
      return 'giá mua sau ưu đãi'
    case 'MIN_INITIAL_OUTFLOW':
      return 'tiền thanh toán đợt 1'
    case 'MIN_TOTAL_CASH_OUTFLOW':
      return 'tổng dòng tiền thực tế đến bàn giao'
    case 'MAX_BENEFIT_VALUE':
      return 'giá trị ưu đãi quy đổi'
  }
}

export function recommendScenario(
  scenarios: CalculationResult[],
  objective: OptimizationObjective,
): RecommendationRecord {
  if (scenarios.length === 0) {
    throw new Error('Không có kịch bản nào để xếp hạng.')
  }

  const sorted = [...scenarios].sort((a, b) => {
    const diff = metricFor(objective, a) - metricFor(objective, b)
    if (diff !== 0) return diff
    return a.netPrice - b.netPrice
  })
  const winner = sorted[0]
  const winnerMetric = metricFor(objective, winner)

  const comparisons = scenarios
    .filter((s) => s.plan !== winner.plan)
    .map((s) => {
      const rawDelta = metricFor(objective, s) - winnerMetric
      const displayDelta = objective === 'MAX_BENEFIT_VALUE' ? -rawDelta : rawDelta
      return {
        plan: s.plan,
        deltaVnd: Math.abs(rawDelta),
        deltaLabel:
          objective === 'MAX_BENEFIT_VALUE'
            ? displayDelta >= 0
              ? `Phương án đề xuất có giá trị ưu đãi cao hơn ${formatVnd(Math.abs(displayDelta))}`
              : `${s.planLabel} có giá trị ưu đãi cao hơn ${formatVnd(Math.abs(displayDelta))}`
            : rawDelta > 0
              ? `Phương án đề xuất tiết kiệm hơn ${formatVnd(Math.abs(rawDelta))} về ${metricLabel(objective)}`
              : `${s.planLabel} thấp hơn ${formatVnd(Math.abs(rawDelta))} về ${metricLabel(objective)}`,
      }
    })

  const savingsText = comparisons
    .map((c) => `${formatVnd(c.deltaVnd)} so với ${scenarioLabelOf(scenarios, c.plan)}`)
    .join('; ')

  const rationale = `Dựa trên tiêu chí tối ưu hóa "${OBJECTIVE_LABEL[objective]}" bạn đã chỉ định, Phương án "${winner.planLabel}" được đề xuất vì có ${metricLabel(
    objective,
  )} tốt nhất, chênh lệch ${savingsText || 'không đáng kể so với các phương án còn lại'}.`

  return {
    objective,
    recommendedPlan: winner.plan,
    rationale,
    comparisons,
  }
}

function scenarioLabelOf(scenarios: CalculationResult[], plan: CalculationResult['plan']): string {
  return scenarios.find((s) => s.plan === plan)?.planLabel ?? plan
}

export { OBJECTIVE_LABEL }
