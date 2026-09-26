import type { ScenarioCode } from '@/api/contracts'

export interface MilestoneConfig {
  label: string
  milestone: string
  ratio: number
  payer: 'CUSTOMER' | 'BANK'
  /** true = đợt phải trả trước/khi bàn giao (tính vào tổng dòng tiền đến bàn giao). */
  before_handover: boolean
}

export interface PaymentPlanConfig {
  scenario_code: ScenarioCode
  label: string
  description: string
  schedule: MilestoneConfig[]
}

const m = (label: string, milestone: string, ratio: number, payer: 'CUSTOMER' | 'BANK' = 'CUSTOMER', before_handover = true): MilestoneConfig => ({
  label,
  milestone,
  ratio,
  payer,
  before_handover,
})

/**
 * 3 phương án chuẩn FCS v2.6 (ScenarioCode PA-CHUDONG / PA-NHANH / PA-VAY). Tỷ lệ chỉ chi phối
 * lịch dòng tiền, không ảnh hưởng Giá bán sau ưu đãi (PRD §1.3.1).
 */
export const PAYMENT_PLANS_FIXTURE: PaymentPlanConfig[] = [
  {
    scenario_code: 'PA-CHUDONG',
    label: 'Tiến độ chuẩn',
    description: '9 đợt theo tiến độ xây dựng (POL-04).',
    schedule: [
      m('Đợt 1', 'Ký Hợp đồng mua bán', 0.3),
      m('Đợt 2', 'Hoàn thành móng', 0.1),
      m('Đợt 3', 'Hoàn thành sàn tầng 10', 0.1),
      m('Đợt 4', 'Hoàn thành sàn tầng 20', 0.1),
      m('Đợt 5', 'Cất nóc', 0.1),
      m('Đợt 6', 'Hoàn thiện mặt ngoài', 0.05),
      m('Đợt 7', 'Nghiệm thu PCCC', 0.05),
      m('Đợt 8', 'Nhận bàn giao căn hộ', 0.15),
      m('Đợt 9', 'Nhận Giấy chứng nhận', 0.05, 'CUSTOMER', false),
    ],
  },
  {
    scenario_code: 'PA-NHANH',
    label: 'Thanh toán sớm 95%',
    description: 'Thanh toán 95% trong 15 ngày kể từ ngày ký HĐMB.',
    schedule: [m('Đợt 1', 'Trong 15 ngày kể từ ngày ký HĐMB', 0.95), m('Đợt 2', 'Nhận Giấy chứng nhận', 0.05, 'CUSTOMER', false)],
  },
  {
    scenario_code: 'PA-VAY',
    label: 'Vay ngân hàng HTLS 0%',
    description: 'Vốn tự có 15%, ngân hàng giải ngân phần còn lại theo tiến độ.',
    schedule: [
      m('Đợt 1', 'Ký Hợp đồng mua bán (vốn tự có)', 0.15),
      m('Đợt 2', 'Ngân hàng giải ngân theo tiến độ', 0.5, 'BANK'),
      m('Đợt 3', 'Ngân hàng giải ngân khi bàn giao', 0.35, 'BANK'),
    ],
  },
]
