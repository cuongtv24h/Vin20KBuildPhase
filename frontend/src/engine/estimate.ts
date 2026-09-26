import type { PlanEstimate, PublicPromotion } from '@/api/contracts'
import { computeScenarios } from '@/engine/calculator'
import type { ApartmentUnit, CustomerSegment, PaymentPlanConfig, PolicyRule, PolicyVersion } from '@/types/domain'

/**
 * Ưu đãi gắn liền với một phương án thanh toán duy nhất (ví dụ chiết khấu thanh toán sớm chỉ
 * áp dụng cho phương án 95%) — được tính sẵn trong giá tham khảo của phương án đó.
 */
function isPlanBoundRule(rule: PolicyRule): boolean {
  return rule.isSelectable && !rule.isAmbiguous && rule.kind !== 'GIFT' && rule.applicablePlans.length === 1
}

/** Giá tham khảo công khai cho khách: ưu đãi theo hồ sơ + ưu đãi gắn với từng phương án. */
export function estimatePlans(params: {
  unit: ApartmentUnit
  policy: PolicyVersion
  plans: PaymentPlanConfig[]
  customerSegment: CustomerSegment
}): PlanEstimate[] {
  const { unit, policy, plans, customerSegment } = params
  const planBound = policy.rules.filter(isPlanBoundRule).map((r) => r.ruleCode)

  const scenarios = computeScenarios({
    unit,
    policy,
    plans,
    selectedRuleCodes: planBound,
    customerSegment,
    unitsQuantity: 1,
  })

  return scenarios.map((s) => {
    const config = plans.find((p) => p.plan === s.plan)
    return {
      plan: s.plan,
      planLabel: s.planLabel,
      description: config?.description ?? '',
      totalDiscountRate: s.totalDiscountRate,
      netPrice: s.netPrice,
      initialPaymentVnd: s.initialPaymentVnd,
      installmentsCount: s.installmentsCount,
      appliedIncentives: s.ruleBreakdown.filter((r) => r.status === 'ELIGIBLE').map((r) => r.title),
    }
  })
}

export function listPublicPromotions(policy: PolicyVersion): PublicPromotion[] {
  return policy.rules
    .filter((r) => !r.isAmbiguous)
    .map((r) => ({
      ruleCode: r.ruleCode,
      title: r.title,
      summary: r.evidenceText,
      clauseTitle: r.source.clauseTitle,
    }))
}
