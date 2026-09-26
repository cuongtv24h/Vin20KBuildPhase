import type { ScheduledPayment } from '@/api/contracts'
import type { PaymentPlanConfig } from '@/types/domain'

/**
 * Chia Net Price theo lịch thanh toán của phương án. Làm tròn từng đợt về số nguyên VNĐ;
 * phần chênh lệch làm tròn dồn vào đợt cuối để tổng luôn đúng bằng Net Price.
 */
export function buildPaymentSchedule(netPrice: number, plan: PaymentPlanConfig): ScheduledPayment[] {
  let allocated = 0
  return plan.schedule.map((milestone, idx) => {
    const isLast = idx === plan.schedule.length - 1
    const amountVnd = isLast ? netPrice - allocated : Math.round(netPrice * milestone.ratio)
    allocated += amountVnd
    return { ...milestone, amountVnd }
  })
}
