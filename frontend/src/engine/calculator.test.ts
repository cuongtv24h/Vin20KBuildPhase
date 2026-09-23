import { describe, expect, it } from 'vitest'
import { BENCHMARK_CASES, runBenchmarkSuite, summarizeBenchmark } from '@/engine/benchmark'
import { calculateNetPrice, validatePricingResult } from '@/engine/calculator'

describe('calculateNetPrice', () => {
  it('khớp chính xác ví dụ minh hoạ PRD §7/§8 (ZEN-A-1205)', () => {
    const result = calculateNetPrice({
      basePrice: 4_200_000_000,
      eligibleDiscountRates: [0.015, 0.085],
    })
    expect(result.discountAmount).toBe(420_000_000)
    expect(result.priceBeforeVAT).toBe(3_780_000_000)
    expect(result.vatAmount).toBe(378_000_000)
    expect(result.kpbtAmount).toBe(75_600_000)
    expect(result.netPrice).toBe(4_233_600_000)
  })

  it('trả về đúng basePrice khi không có ưu đãi nào', () => {
    const result = calculateNetPrice({ basePrice: 3_000_000_000, eligibleDiscountRates: [] })
    expect(result.discountAmount).toBe(0)
    expect(result.netPrice).toBe(3_360_000_000)
  })

  it('làm tròn từng bước độc lập, không gộp một lần', () => {
    const result = calculateNetPrice({
      basePrice: 3_333_333_333,
      eligibleDiscountRates: [0.085],
    })
    expect(result.discountAmount).toBe(283_333_333)
    expect(result.netPrice).toBe(3_416_000_000)
  })
})

describe('validatePricingResult', () => {
  it('chặn kết quả có priceBeforeVAT <= 0', () => {
    const bad = calculateNetPrice({ basePrice: 1_000_000_000, eligibleDiscountRates: [1.5] })
    const validation = validatePricingResult(bad)
    expect(validation.valid).toBe(false)
    expect(validation.reasons.length).toBeGreaterThan(0)
  })

  it('chấp nhận kết quả hợp lệ trong biên an toàn', () => {
    const ok = calculateNetPrice({ basePrice: 4_200_000_000, eligibleDiscountRates: [0.015, 0.085] })
    const validation = validatePricingResult(ok)
    expect(validation.valid).toBe(true)
    expect(validation.reasons).toHaveLength(0)
  })
})

describe('Formula Regression Benchmark Suite', () => {
  it('có đúng 15 test cases cố định', () => {
    expect(BENCHMARK_CASES).toHaveLength(15)
  })

  it('đạt Exact Match 100% trên toàn bộ 15 test cases', () => {
    const results = runBenchmarkSuite()
    const summary = summarizeBenchmark(results)

    const failed = results.filter((r) => !r.passed)
    expect(failed, `Các test case lệch: ${failed.map((f) => f.case.id).join(', ')}`).toHaveLength(0)
    expect(summary.exactMatchRate).toBe(1)
    expect(summary.passedCount).toBe(summary.total)
  })
})
