import type { CalculationValidation, Scenario, UnitSnapshot } from '@pricepolicy/api-client/contracts'
import { PRICE_BAND_PER_M2 } from '../fixtures/units'
import { KPBT_RATE, VAT_RATE } from './calculator'

/** Trần thẩm quyền: tổng chiết khấu % cộng dồn không vượt quá mức này. */
export const MAX_STACKED_DISCOUNT_RATE = 0.2

type ValidationError = CalculationValidation['errors'][number]

const err = (code: string, field: string, message: string, expected: number | null = null, actual: number | null = null): ValidationError => ({
  code,
  field,
  message,
  expected_vnd: expected,
  actual_vnd: actual,
})

/**
 * 6 sanity check kế toán (Implement plan D2-3). Lệch 1 VNĐ là FAIL — không làm tròn cho qua.
 */
export function validateScenarios(unit: UnitSnapshot, scenarios: Scenario[]): CalculationValidation {
  const errors: ValidationError[] = []
  const band = PRICE_BAND_PER_M2[unit.project_id]

  for (const s of scenarios) {
    const at = (f: string) => `scenarios[${s.scenario_code}].${f}`

    // 1. Không có số tiền âm
    const amounts: [string, number][] = [
      ['discount_vnd', s.discount_vnd],
      ['net_price_before_tax_vnd', s.net_price_before_tax_vnd],
      ['vat_vnd', s.vat_vnd],
      ['kpbt_vnd', s.kpbt_vnd],
      ...s.payment_schedule.map((p): [string, number] => [`payment_schedule[${p.seq}].amount_vnd`, p.amount_vnd]),
    ]
    for (const [field, value] of amounts) if (value < 0) errors.push(err('NEGATIVE_AMOUNT', at(field), 'Số tiền âm.', 0, value))

    // 2. Tổng lịch thanh toán khớp tổng giá hợp đồng
    const scheduled = s.payment_schedule.reduce((sum, p) => sum + p.amount_vnd, 0)
    if (scheduled !== s.total_contract_price_vnd) {
      errors.push(err('PAYMENT_SCHEDULE_SUM_MISMATCH', at('payment_schedule'), 'Tổng các đợt không khớp giá hợp đồng.', s.total_contract_price_vnd, scheduled))
    }

    // 3. Giá net nằm trong khung giá dự án (đơn giá/m²) và không vượt giá niêm yết
    if (s.net_price_before_tax_vnd > s.listed_price_before_tax_vnd) {
      errors.push(err('NET_PRICE_ABOVE_LISTED', at('net_price_before_tax_vnd'), 'Giá sau ưu đãi vượt giá niêm yết.', s.listed_price_before_tax_vnd, s.net_price_before_tax_vnd))
    }
    if (band) {
      const perM2 = Math.round(s.net_price_before_tax_vnd / unit.area_m2)
      if (perM2 < band.min || perM2 > band.max) {
        errors.push(
          err('NET_PRICE_OUT_OF_BOUNDARY', at('net_price_before_tax_vnd'), `Đơn giá ${perM2.toLocaleString('vi-VN')} đ/m² nằm ngoài khung giá dự án.`, band.min * unit.area_m2, s.net_price_before_tax_vnd),
        )
      }
    }

    // 4. VAT / KPBT khớp thuế suất snapshot
    const vat = Math.round(s.net_price_before_tax_vnd * VAT_RATE)
    const kpbt = Math.round(s.net_price_before_tax_vnd * KPBT_RATE)
    if (vat !== s.vat_vnd) errors.push(err('VAT_MISMATCH', at('vat_vnd'), 'Thuế GTGT không khớp thuế suất.', vat, s.vat_vnd))
    if (kpbt !== s.kpbt_vnd) errors.push(err('KPBT_MISMATCH', at('kpbt_vnd'), 'KPBT không khớp tỷ lệ.', kpbt, s.kpbt_vnd))

    // 5. Tỷ lệ các đợt hợp lệ (tổng = 100%)
    const ratio = Math.round(s.payment_schedule.reduce((sum, p) => sum + p.ratio, 0) * 10_000) / 10_000
    if (ratio !== 1) errors.push(err('INSTALLMENT_RATIO_INVALID', at('payment_schedule'), `Tổng tỷ lệ các đợt là ${ratio * 100}%.`))

    // 6. Ưu đãi không vượt trần chính sách
    if (s.total_discount_rate > MAX_STACKED_DISCOUNT_RATE || s.discount_vnd > s.listed_price_before_tax_vnd) {
      errors.push(err('DISCOUNT_EXCEEDS_POLICY_BOUND', at('total_discount_rate'), 'Tổng ưu đãi vượt trần thẩm quyền.', Math.round(s.listed_price_before_tax_vnd * MAX_STACKED_DISCOUNT_RATE), s.discount_vnd))
    }
  }

  return { valid: errors.length === 0, errors }
}
