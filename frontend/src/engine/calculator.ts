import type {
  ApartmentUnit,
  CalculationResult,
  CustomerSegment,
  PaymentPlanConfig,
  PolicyVersion,
  RuleEvaluationResult,
} from '@/types/domain'

/**
 * Deterministic Pricing Engine — thuần TypeScript, không LLM, không số thực gộp một lần.
 * Mọi phép tính đều làm tròn TỪNG BƯỚC bằng số nguyên VNĐ để khớp Formula Regression
 * Benchmark (xem src/engine/benchmark.ts).
 *
 * Công thức (bám đúng PRD §7 & TD-4.2):
 *   discountAmount = round(basePrice × tổng tỷ lệ ưu đãi ELIGIBLE)
 *   priceBeforeVAT = basePrice − discountAmount
 *   VAT            = round(priceBeforeVAT × 10%)
 *   KPBT           = round(priceBeforeVAT × 2%)
 *   netPrice       = priceBeforeVAT + VAT + KPBT
 */

export const DEFAULT_VAT_RATE = 0.1
export const DEFAULT_KPBT_RATE = 0.02

export interface NetPriceInput {
  basePrice: number
  /** Chỉ các tỷ lệ % của những ưu đãi đã được xác định ELIGIBLE. */
  eligibleDiscountRates: number[]
  vatRate?: number
  kpbtRate?: number
}

export interface NetPriceOutput {
  basePrice: number
  totalDiscountRate: number
  discountAmount: number
  priceBeforeVAT: number
  vatAmount: number
  kpbtAmount: number
  netPrice: number
}

/** Cộng dồn tỷ lệ ưu đãi, làm tròn 6 chữ số thập phân để tránh sai số dấu phẩy động khi hiển thị. */
function sumRates(rates: number[]): number {
  const total = rates.reduce((sum, r) => sum + r, 0)
  return Math.round(total * 1_000_000) / 1_000_000
}

export function calculateNetPrice(input: NetPriceInput): NetPriceOutput {
  const vatRate = input.vatRate ?? DEFAULT_VAT_RATE
  const kpbtRate = input.kpbtRate ?? DEFAULT_KPBT_RATE

  const totalDiscountRate = sumRates(input.eligibleDiscountRates)
  const discountAmount = Math.round(input.basePrice * totalDiscountRate)
  const priceBeforeVAT = input.basePrice - discountAmount
  const vatAmount = Math.round(priceBeforeVAT * vatRate)
  const kpbtAmount = Math.round(priceBeforeVAT * kpbtRate)
  const netPrice = priceBeforeVAT + vatAmount + kpbtAmount

  return {
    basePrice: input.basePrice,
    totalDiscountRate,
    discountAmount,
    priceBeforeVAT,
    vatAmount,
    kpbtAmount,
    netPrice,
  }
}

export interface ValidationResult {
  valid: boolean
  reasons: string[]
}

/**
 * Deterministic Financial Validation Gate (Sanity Check).
 * Chặn đứng bất kỳ kết quả nào vi phạm cận an toàn thương mại (FC-04).
 */
export function validatePricingResult(output: NetPriceOutput): ValidationResult {
  const reasons: string[] = []

  if (output.priceBeforeVAT <= 0) {
    reasons.push('Giá bán sau ưu đãi trước thuế phải lớn hơn 0.')
  }
  if (output.discountAmount < 0) {
    reasons.push('Số tiền chiết khấu không được âm.')
  }
  if (output.discountAmount > output.basePrice) {
    reasons.push('Tổng chiết khấu vượt quá giá niêm yết gốc.')
  }
  if (output.netPrice <= 0) {
    reasons.push('Giá bán sau ưu đãi (Net Price) phải lớn hơn 0.')
  }
  if (output.netPrice > output.basePrice * 1.3) {
    reasons.push('Giá bán sau ưu đãi vượt ngưỡng hợp lý (>130% giá niêm yết) so với giá niêm yết gốc.')
  }
  if (output.totalDiscountRate < 0 || output.totalDiscountRate > 0.6) {
    reasons.push('Tổng tỷ lệ ưu đãi vượt ngưỡng thẩm quyền cho phép (>60%).')
  }

  return { valid: reasons.length === 0, reasons }
}

export interface ComputeScenariosParams {
  unit: ApartmentUnit
  policy: PolicyVersion
  plans: PaymentPlanConfig[]
  selectedRuleCodes: string[]
  customerSegment: CustomerSegment
  unitsQuantity: number
}

/**
 * Mô phỏng song song 3 kịch bản thanh toán: với mỗi phương án, chỉ các điều khoản
 * ELIGIBLE (đã qua Preflight, không CONFLICT/AMBIGUOUS) và áp dụng được cho phương án
 * đó mới được cộng vào tổng tỷ lệ ưu đãi. Agent tuyệt đối không tự tính nhẩm — toàn bộ
 * số học đi qua calculateNetPrice()/validatePricingResult() ở trên.
 */
export function computeScenarios(params: ComputeScenariosParams): CalculationResult[] {
  const { unit, policy, plans, selectedRuleCodes, customerSegment, unitsQuantity } = params
  const selectedSet = new Set(selectedRuleCodes)

  return plans.map((planConfig) => {
    const applicableRules = policy.rules.filter((r) => r.applicablePlans.includes(planConfig.plan))
    const ruleBreakdown: RuleEvaluationResult[] = []
    const eligibleRates: number[] = []
    let benefitValueVnd = 0

    for (const rule of applicableRules) {
      const isRequested = !rule.isSelectable || selectedSet.has(rule.ruleCode)
      if (!isRequested) continue

      let status: RuleEvaluationResult['status'] = 'ELIGIBLE'
      let reasonText = `Thoả điều kiện áp dụng theo ${rule.source.clauseTitle}.`
      let amountVnd = 0

      if (rule.requiredSegments && !rule.requiredSegments.includes(customerSegment)) {
        status = 'NOT_ELIGIBLE'
        reasonText = `Hồ sơ khách hàng không thuộc phân khúc được quy định tại ${rule.source.clauseTitle}.`
      } else if (rule.minUnitsPurchased && unitsQuantity < rule.minUnitsPurchased) {
        status = 'NOT_ELIGIBLE'
        reasonText = `Số lượng căn mua (${unitsQuantity}) chưa đạt ngưỡng tối thiểu ${rule.minUnitsPurchased} căn theo ${rule.source.clauseTitle}.`
      } else {
        status = 'ELIGIBLE'
        if (rule.kind === 'PERCENT_DISCOUNT' && rule.discountRate) {
          eligibleRates.push(rule.discountRate)
        }
        if (rule.kind === 'GIFT' && rule.cashEquivalentVnd) {
          benefitValueVnd += rule.cashEquivalentVnd
          amountVnd = rule.cashEquivalentVnd
        }
        if (rule.kind === 'BANK_SUPPORT') {
          reasonText = `Hỗ trợ lãi suất 0% trong ${rule.interestSupportMonths} tháng theo ${rule.source.clauseTitle}, ân hạn nợ gốc đến khi bàn giao.`
        }
      }

      ruleBreakdown.push({
        ruleCode: rule.ruleCode,
        title: rule.title,
        status,
        amountVnd,
        reasonText,
        source: rule.source,
      })
    }

    const netPriceCalc = calculateNetPrice({ basePrice: unit.listedPrice, eligibleDiscountRates: eligibleRates })

    for (const line of ruleBreakdown) {
      const rule = applicableRules.find((r) => r.ruleCode === line.ruleCode)
      if (rule?.kind === 'PERCENT_DISCOUNT' && line.status === 'ELIGIBLE' && rule.discountRate) {
        line.amountVnd = Math.round(unit.listedPrice * rule.discountRate)
      }
    }

    const validation = validatePricingResult(netPriceCalc)

    return {
      plan: planConfig.plan,
      planLabel: planConfig.label,
      basePrice: unit.listedPrice,
      totalDiscountRate: netPriceCalc.totalDiscountRate,
      discountAmount: netPriceCalc.discountAmount,
      priceBeforeVAT: netPriceCalc.priceBeforeVAT,
      vatAmount: netPriceCalc.vatAmount,
      kpbtAmount: netPriceCalc.kpbtAmount,
      netPrice: netPriceCalc.netPrice,
      initialPaymentVnd: Math.round(netPriceCalc.netPrice * planConfig.initialPaymentRatio),
      totalCashOutflowToHandoverVnd: Math.round(netPriceCalc.netPrice * planConfig.totalCashOutflowRatio),
      benefitValueVnd,
      installmentsCount: planConfig.installmentsCount,
      ruleBreakdown,
      validation,
    }
  })
}
