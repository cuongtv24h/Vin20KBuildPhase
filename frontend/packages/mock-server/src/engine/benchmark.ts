import type { BenchmarkAmounts, BenchmarkCaseResult, BenchmarkRun } from '@pricepolicy/api-client/contracts'
import { calculateAmounts } from './calculator'

interface BenchmarkCase {
  id: string
  name: string
  listed_price_before_tax_vnd: number
  discount_rates: number[]
  expected: BenchmarkAmounts
}

/**
 * Formula Regression Benchmark Suite — 17 test cases cố định (input/expected-output
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
    id: 'BENCH-01',
    name: 'Căn R-02.02 (2BR) — Thanh toán Sớm 95% nhận chiết khấu 8% (Δ = 0 VNĐ)',
    listed_price_before_tax_vnd: 4_600_000_000,
    discount_rates: [0.08],
    expected: {
      discount_vnd: 368_000_000,
      net_price_before_tax_vnd: 4_232_000_000,
      vat_vnd: 423_200_000,
      kpbt_vnd: 84_640_000,
      total_contract_price_vnd: 4_739_840_000,
    },
  },
  {
    id: 'BENCH-02',
    name: 'Căn G-02.02 (3BR) — Tiến độ chuẩn 9 đợt nhận chiết khấu 2% + Quà tặng nội thất (Δ = 0 VNĐ)',
    listed_price_before_tax_vnd: 6_320_000_000,
    discount_rates: [0.02],
    expected: {
      discount_vnd: 126_400_000,
      net_price_before_tax_vnd: 6_193_600_000,
      vat_vnd: 619_360_000,
      kpbt_vnd: 123_872_000,
      total_contract_price_vnd: 6_936_832_000,
    },
  },
  {
    id: 'TC-01',
    name: 'PRD §7/§8 — Cư dân (1.5%) + Thanh toán sớm (8.5%), ZEN-A-1205',
    listed_price_before_tax_vnd: 4_200_000_000,
    discount_rates: [0.015, 0.085],
    expected: {
      discount_vnd: 420_000_000,
      net_price_before_tax_vnd: 3_780_000_000,
      vat_vnd: 378_000_000,
      kpbt_vnd: 75_600_000,
      total_contract_price_vnd: 4_233_600_000,
    },
  },
  {
    id: 'TC-02',
    name: 'Không có ưu đãi nào (baseline VAT + KPBT)',
    listed_price_before_tax_vnd: 3_000_000_000,
    discount_rates: [],
    expected: {
      discount_vnd: 0,
      net_price_before_tax_vnd: 3_000_000_000,
      vat_vnd: 300_000_000,
      kpbt_vnd: 60_000_000,
      total_contract_price_vnd: 3_360_000_000,
    },
  },
  {
    id: 'TC-03',
    name: 'Cư dân tri ân đơn lẻ (1.0%, chính sách v2.0)',
    listed_price_before_tax_vnd: 2_500_000_000,
    discount_rates: [0.01],
    expected: {
      discount_vnd: 25_000_000,
      net_price_before_tax_vnd: 2_475_000_000,
      vat_vnd: 247_500_000,
      kpbt_vnd: 49_500_000,
      total_contract_price_vnd: 2_772_000_000,
    },
  },
  {
    id: 'TC-04',
    name: 'Giá niêm yết số lẻ + cư dân v3.1 (1.5%) — kiểm tra làm tròn',
    listed_price_before_tax_vnd: 1_999_999_999,
    discount_rates: [0.015],
    expected: {
      discount_vnd: 30_000_000,
      net_price_before_tax_vnd: 1_969_999_999,
      vat_vnd: 197_000_000,
      kpbt_vnd: 39_400_000,
      total_contract_price_vnd: 2_206_399_999,
    },
  },
  {
    id: 'TC-05',
    name: 'Cư dân (1.5%) + Mua sỉ căn thứ 2 (2.0%)',
    listed_price_before_tax_vnd: 3_800_000_000,
    discount_rates: [0.015, 0.02],
    expected: {
      discount_vnd: 133_000_000,
      net_price_before_tax_vnd: 3_667_000_000,
      vat_vnd: 366_700_000,
      kpbt_vnd: 73_340_000,
      total_contract_price_vnd: 4_107_040_000,
    },
  },
  {
    id: 'TC-06',
    name: 'Cộng dồn tối đa 3 ưu đãi (1.5% + 8.5% + 2.0% = 12%)',
    listed_price_before_tax_vnd: 8_500_000_000,
    discount_rates: [0.015, 0.085, 0.02],
    expected: {
      discount_vnd: 1_020_000_000,
      net_price_before_tax_vnd: 7_480_000_000,
      vat_vnd: 748_000_000,
      kpbt_vnd: 149_600_000,
      total_contract_price_vnd: 8_377_600_000,
    },
  },
  {
    id: 'TC-07',
    name: 'Cư dân tri ân — chính sách v2.0 (1.0%)',
    listed_price_before_tax_vnd: 1_800_000_000,
    discount_rates: [0.01],
    expected: {
      discount_vnd: 18_000_000,
      net_price_before_tax_vnd: 1_782_000_000,
      vat_vnd: 178_200_000,
      kpbt_vnd: 35_640_000,
      total_contract_price_vnd: 1_995_840_000,
    },
  },
  {
    id: 'TC-08',
    name: 'Thanh toán sớm — chính sách v2.0 (7.0%)',
    listed_price_before_tax_vnd: 2_200_000_000,
    discount_rates: [0.07],
    expected: {
      discount_vnd: 154_000_000,
      net_price_before_tax_vnd: 2_046_000_000,
      vat_vnd: 204_600_000,
      kpbt_vnd: 40_920_000,
      total_contract_price_vnd: 2_291_520_000,
    },
  },
  {
    id: 'TC-09',
    name: 'Căn hộ giá trị nhỏ + cư dân (1.5%)',
    listed_price_before_tax_vnd: 500_000_000,
    discount_rates: [0.015],
    expected: {
      discount_vnd: 7_500_000,
      net_price_before_tax_vnd: 492_500_000,
      vat_vnd: 49_250_000,
      kpbt_vnd: 9_850_000,
      total_contract_price_vnd: 551_600_000,
    },
  },
  {
    id: 'TC-10',
    name: 'Biệt thự giá trị lớn + Cư dân & Mua sỉ (3.5%)',
    listed_price_before_tax_vnd: 15_750_000_000,
    discount_rates: [0.015, 0.02],
    expected: {
      discount_vnd: 551_250_000,
      net_price_before_tax_vnd: 15_198_750_000,
      vat_vnd: 1_519_875_000,
      kpbt_vnd: 303_975_000,
      total_contract_price_vnd: 17_022_600_000,
    },
  },
  {
    id: 'TC-11',
    name: 'Giá niêm yết số lẻ + Thanh toán sớm (8.5%) — kiểm tra làm tròn .xx5',
    listed_price_before_tax_vnd: 3_333_333_333,
    discount_rates: [0.085],
    expected: {
      discount_vnd: 283_333_333,
      net_price_before_tax_vnd: 3_050_000_000,
      vat_vnd: 305_000_000,
      kpbt_vnd: 61_000_000,
      total_contract_price_vnd: 3_416_000_000,
    },
  },
  {
    id: 'TC-12',
    name: 'Cộng dồn 3 ưu đãi — chính sách v2.0 (1.0% + 7.0% + 2.0% = 10%)',
    listed_price_before_tax_vnd: 4_600_000_000,
    discount_rates: [0.01, 0.07, 0.02],
    expected: {
      discount_vnd: 460_000_000,
      net_price_before_tax_vnd: 4_140_000_000,
      vat_vnd: 414_000_000,
      kpbt_vnd: 82_800_000,
      total_contract_price_vnd: 4_636_800_000,
    },
  },
  {
    id: 'TC-13',
    name: 'Căn cao cấp + Cư dân đơn lẻ (1.5%)',
    listed_price_before_tax_vnd: 6_200_000_000,
    discount_rates: [0.015],
    expected: {
      discount_vnd: 93_000_000,
      net_price_before_tax_vnd: 6_107_000_000,
      vat_vnd: 610_700_000,
      kpbt_vnd: 122_140_000,
      total_contract_price_vnd: 6_839_840_000,
    },
  },
  {
    id: 'TC-14',
    name: 'Cộng dồn thực tế Sapphire (1.5% + 8.5% + 2.0%)',
    listed_price_before_tax_vnd: 5_000_000_000,
    discount_rates: [0.015, 0.085, 0.02],
    expected: {
      discount_vnd: 600_000_000,
      net_price_before_tax_vnd: 4_400_000_000,
      vat_vnd: 440_000_000,
      kpbt_vnd: 88_000_000,
      total_contract_price_vnd: 4_928_000_000,
    },
  },
  {
    id: 'TC-15',
    name: 'Giá niêm yết số lẻ phức tạp + Cư dân & Mua sỉ (3.5%)',
    listed_price_before_tax_vnd: 1_234_567_890,
    discount_rates: [0.015, 0.02],
    expected: {
      discount_vnd: 43_209_876,
      net_price_before_tax_vnd: 1_191_358_014,
      vat_vnd: 119_135_801,
      kpbt_vnd: 23_827_160,
      total_contract_price_vnd: 1_334_320_975,
    },
  },
]

const FIELDS: (keyof BenchmarkAmounts)[] = ['discount_vnd', 'net_price_before_tax_vnd', 'vat_vnd', 'kpbt_vnd', 'total_contract_price_vnd']

/** Chạy 17 golden case — so khớp tuyệt đối từng trường (Δ = 0 VNĐ). */
export function runBenchmark(runId: string, startedAt: string, finishedAt: string): BenchmarkRun {
  const cases: BenchmarkCaseResult[] = BENCHMARK_CASES.map((c) => {
    const { total_discount_rate: _rate, ...actual } = calculateAmounts(c.listed_price_before_tax_vnd, c.discount_rates)
    const delta = FIELDS.reduce((sum, f) => sum + Math.abs(actual[f] - c.expected[f]), 0)
    return {
      case_id: c.id,
      name: c.name,
      listed_price_before_tax_vnd: c.listed_price_before_tax_vnd,
      discount_rates: c.discount_rates,
      expected: c.expected,
      actual,
      delta_vnd: delta,
      passed: delta === 0,
    }
  })
  const passed = cases.filter((c) => c.passed).length
  return { run_id: runId, started_at: startedAt, finished_at: finishedAt, total: cases.length, passed, exact_match_rate: passed / cases.length, cases }
}
