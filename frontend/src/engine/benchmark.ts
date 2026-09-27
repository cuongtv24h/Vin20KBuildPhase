import { calculateNetPrice } from '@/engine/calculator'
import type { BenchmarkCase, BenchmarkRunResult } from '@/types/domain'

/**
 * Formula Regression Benchmark Suite — 15 test cases cố định (input/expected-output
 * khoá cứng trong code, không tự sinh ngẫu nhiên — theo đúng yêu cầu OP-02/MVP-05).
 *
 * TC-01 tái sử dụng nguyên số liệu minh hoạ tại PRD §7/§8 (căn ZEN-A-1205, chiết khấu
 * 1.5% cư dân + 8.5% thanh toán sớm → Net Price 4.233.600.000đ) để đối soát trực tiếp
 * với tài liệu nghiệp vụ gốc. Các test case còn lại bao phủ: không ưu đãi, ưu đãi đơn lẻ,
 * cộng dồn nhiều ưu đãi, chính sách v2.0 (tỷ lệ cũ), giá trị cực nhỏ/cực lớn và các mức
 * giá lẻ để kiểm tra tính đúng đắn của việc làm tròn từng bước.
 */
export const BENCHMARK_CASES: BenchmarkCase[] = [
  {
    id: 'TC-01',
    name: 'PRD §7/§8 — Cư dân (1.5%) + Thanh toán sớm (8.5%), ZEN-A-1205',
    basePrice: 4_200_000_000,
    eligibleDiscountRates: [0.015, 0.085],
    expected: {
      discountAmount: 420_000_000,
      priceBeforeVAT: 3_780_000_000,
      vatAmount: 378_000_000,
      kpbtAmount: 75_600_000,
      netPrice: 4_233_600_000,
    },
  },
  {
    id: 'TC-02',
    name: 'Không có ưu đãi nào (baseline VAT + KPBT)',
    basePrice: 3_000_000_000,
    eligibleDiscountRates: [],
    expected: {
      discountAmount: 0,
      priceBeforeVAT: 3_000_000_000,
      vatAmount: 300_000_000,
      kpbtAmount: 60_000_000,
      netPrice: 3_360_000_000,
    },
  },
  {
    id: 'TC-03',
    name: 'Cư dân tri ân đơn lẻ (1.0%, chính sách v2.0)',
    basePrice: 2_500_000_000,
    eligibleDiscountRates: [0.01],
    expected: {
      discountAmount: 25_000_000,
      priceBeforeVAT: 2_475_000_000,
      vatAmount: 247_500_000,
      kpbtAmount: 49_500_000,
      netPrice: 2_772_000_000,
    },
  },
  {
    id: 'TC-04',
    name: 'Giá niêm yết số lẻ + cư dân v3.1 (1.5%) — kiểm tra làm tròn',
    basePrice: 1_999_999_999,
    eligibleDiscountRates: [0.015],
    expected: {
      discountAmount: 30_000_000,
      priceBeforeVAT: 1_969_999_999,
      vatAmount: 197_000_000,
      kpbtAmount: 39_400_000,
      netPrice: 2_206_399_999,
    },
  },
  {
    id: 'TC-05',
    name: 'Cư dân (1.5%) + Mua sỉ căn thứ 2 (2.0%)',
    basePrice: 3_800_000_000,
    eligibleDiscountRates: [0.015, 0.02],
    expected: {
      discountAmount: 133_000_000,
      priceBeforeVAT: 3_667_000_000,
      vatAmount: 366_700_000,
      kpbtAmount: 73_340_000,
      netPrice: 4_107_040_000,
    },
  },
  {
    id: 'TC-06',
    name: 'Cộng dồn tối đa 3 ưu đãi (1.5% + 8.5% + 2.0% = 12%)',
    basePrice: 8_500_000_000,
    eligibleDiscountRates: [0.015, 0.085, 0.02],
    expected: {
      discountAmount: 1_020_000_000,
      priceBeforeVAT: 7_480_000_000,
      vatAmount: 748_000_000,
      kpbtAmount: 149_600_000,
      netPrice: 8_377_600_000,
    },
  },
  {
    id: 'TC-07',
    name: 'Cư dân tri ân — chính sách v2.0 (1.0%)',
    basePrice: 1_800_000_000,
    eligibleDiscountRates: [0.01],
    expected: {
      discountAmount: 18_000_000,
      priceBeforeVAT: 1_782_000_000,
      vatAmount: 178_200_000,
      kpbtAmount: 35_640_000,
      netPrice: 1_995_840_000,
    },
  },
  {
    id: 'TC-08',
    name: 'Thanh toán sớm — chính sách v2.0 (7.0%)',
    basePrice: 2_200_000_000,
    eligibleDiscountRates: [0.07],
    expected: {
      discountAmount: 154_000_000,
      priceBeforeVAT: 2_046_000_000,
      vatAmount: 204_600_000,
      kpbtAmount: 40_920_000,
      netPrice: 2_291_520_000,
    },
  },
  {
    id: 'TC-09',
    name: 'Căn hộ giá trị nhỏ + cư dân (1.5%)',
    basePrice: 500_000_000,
    eligibleDiscountRates: [0.015],
    expected: {
      discountAmount: 7_500_000,
      priceBeforeVAT: 492_500_000,
      vatAmount: 49_250_000,
      kpbtAmount: 9_850_000,
      netPrice: 551_600_000,
    },
  },
  {
    id: 'TC-10',
    name: 'Biệt thự giá trị lớn + Cư dân & Mua sỉ (3.5%)',
    basePrice: 15_750_000_000,
    eligibleDiscountRates: [0.015, 0.02],
    expected: {
      discountAmount: 551_250_000,
      priceBeforeVAT: 15_198_750_000,
      vatAmount: 1_519_875_000,
      kpbtAmount: 303_975_000,
      netPrice: 17_022_600_000,
    },
  },
  {
    id: 'TC-11',
    name: 'Giá niêm yết số lẻ + Thanh toán sớm (8.5%) — kiểm tra làm tròn .xx5',
    basePrice: 3_333_333_333,
    eligibleDiscountRates: [0.085],
    expected: {
      discountAmount: 283_333_333,
      priceBeforeVAT: 3_050_000_000,
      vatAmount: 305_000_000,
      kpbtAmount: 61_000_000,
      netPrice: 3_416_000_000,
    },
  },
  {
    id: 'TC-12',
    name: 'Cộng dồn 3 ưu đãi — chính sách v2.0 (1.0% + 7.0% + 2.0% = 10%)',
    basePrice: 4_600_000_000,
    eligibleDiscountRates: [0.01, 0.07, 0.02],
    expected: {
      discountAmount: 460_000_000,
      priceBeforeVAT: 4_140_000_000,
      vatAmount: 414_000_000,
      kpbtAmount: 82_800_000,
      netPrice: 4_636_800_000,
    },
  },
  {
    id: 'TC-13',
    name: 'Căn cao cấp + Cư dân đơn lẻ (1.5%)',
    basePrice: 6_200_000_000,
    eligibleDiscountRates: [0.015],
    expected: {
      discountAmount: 93_000_000,
      priceBeforeVAT: 6_107_000_000,
      vatAmount: 610_700_000,
      kpbtAmount: 122_140_000,
      netPrice: 6_839_840_000,
    },
  },
  {
    id: 'TC-14',
    name: 'Cộng dồn thực tế Sapphire (1.5% + 8.5% + 2.0%)',
    basePrice: 5_000_000_000,
    eligibleDiscountRates: [0.015, 0.085, 0.02],
    expected: {
      discountAmount: 600_000_000,
      priceBeforeVAT: 4_400_000_000,
      vatAmount: 440_000_000,
      kpbtAmount: 88_000_000,
      netPrice: 4_928_000_000,
    },
  },
  {
    id: 'TC-15',
    name: 'Giá niêm yết số lẻ phức tạp + Cư dân & Mua sỉ (3.5%)',
    basePrice: 1_234_567_890,
    eligibleDiscountRates: [0.015, 0.02],
    expected: {
      discountAmount: 43_209_876,
      priceBeforeVAT: 1_191_358_014,
      vatAmount: 119_135_801,
      kpbtAmount: 23_827_160,
      netPrice: 1_334_320_975,
    },
  },
]

export function runBenchmarkSuite(): BenchmarkRunResult[] {
  return BENCHMARK_CASES.map((testCase) => {
    const actual = calculateNetPrice({
      basePrice: testCase.basePrice,
      eligibleDiscountRates: testCase.eligibleDiscountRates,
    })
    const actualOut = {
      discountAmount: actual.discountAmount,
      priceBeforeVAT: actual.priceBeforeVAT,
      vatAmount: actual.vatAmount,
      kpbtAmount: actual.kpbtAmount,
      netPrice: actual.netPrice,
    }
    const deltaVnd = Math.abs(actualOut.netPrice - testCase.expected.netPrice)
    const passed =
      deltaVnd === 0 &&
      actualOut.discountAmount === testCase.expected.discountAmount &&
      actualOut.priceBeforeVAT === testCase.expected.priceBeforeVAT &&
      actualOut.vatAmount === testCase.expected.vatAmount &&
      actualOut.kpbtAmount === testCase.expected.kpbtAmount

    return { case: testCase, actual: actualOut, deltaVnd, passed }
  })
}

export function summarizeBenchmark(results: BenchmarkRunResult[]): {
  total: number
  passedCount: number
  exactMatchRate: number
} {
  const total = results.length
  const passedCount = results.filter((r) => r.passed).length
  return { total, passedCount, exactMatchRate: total === 0 ? 0 : passedCount / total }
}
