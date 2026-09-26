import type { PaymentPlanConfig } from '@/types/domain'

/**
 * 3 phương án thanh toán chuẩn. Net Price và Dòng tiền là hai khái niệm khác nhau:
 * các tỷ lệ dưới đây chỉ chi phối lịch chi trả, không ảnh hưởng Net Price.
 */
export const PAYMENT_PLANS_FIXTURE: PaymentPlanConfig[] = [
  {
    plan: 'STANDARD_PROGRESS',
    label: 'Tiến độ chuẩn',
    description: 'Thanh toán 8 đợt theo tiến độ xây dựng, đặt cọc 30% khi ký HĐMB.',
    installmentsCount: 8,
    initialPaymentRatio: 0.3,
    totalCashOutflowRatio: 0.95,
    schedule: [
      { label: 'Đợt 1', milestone: 'Ký Hợp đồng mua bán', ratio: 0.3, payer: 'CUSTOMER' },
      { label: 'Đợt 2', milestone: 'Hoàn thành móng', ratio: 0.1, payer: 'CUSTOMER' },
      { label: 'Đợt 3', milestone: 'Hoàn thành sàn tầng 10', ratio: 0.1, payer: 'CUSTOMER' },
      { label: 'Đợt 4', milestone: 'Hoàn thành sàn tầng 20', ratio: 0.1, payer: 'CUSTOMER' },
      { label: 'Đợt 5', milestone: 'Cất nóc', ratio: 0.1, payer: 'CUSTOMER' },
      { label: 'Đợt 6', milestone: 'Hoàn thiện mặt ngoài', ratio: 0.1, payer: 'CUSTOMER' },
      { label: 'Đợt 7', milestone: 'Nhận bàn giao căn hộ', ratio: 0.15, payer: 'CUSTOMER' },
      { label: 'Đợt 8', milestone: 'Nhận Giấy chứng nhận quyền sở hữu', ratio: 0.05, payer: 'CUSTOMER' },
    ],
  },
  {
    plan: 'EARLY_PAYMENT_95',
    label: 'Thanh toán sớm 95%',
    description: 'Thanh toán 95% giá trị trong 15 ngày kể từ ngày ký HĐMB để nhận chiết khấu tối đa.',
    installmentsCount: 2,
    initialPaymentRatio: 0.95,
    totalCashOutflowRatio: 1.0,
    schedule: [
      { label: 'Đợt 1', milestone: 'Trong 15 ngày kể từ ngày ký HĐMB', ratio: 0.95, payer: 'CUSTOMER' },
      { label: 'Đợt 2', milestone: 'Nhận bàn giao căn hộ', ratio: 0.05, payer: 'CUSTOMER' },
    ],
  },
  {
    plan: 'BANK_LOAN_SUPPORT',
    label: 'Vay ngân hàng HTLS 0%',
    description:
      'Khách tự có tối thiểu 15%, ngân hàng đối tác giải ngân phần còn lại theo tiến độ, hỗ trợ lãi suất 0% và ân hạn nợ gốc đến khi bàn giao.',
    installmentsCount: 3,
    initialPaymentRatio: 0.15,
    totalCashOutflowRatio: 0.15,
    schedule: [
      { label: 'Đợt 1', milestone: 'Ký Hợp đồng mua bán (vốn tự có)', ratio: 0.15, payer: 'CUSTOMER' },
      { label: 'Đợt 2', milestone: 'Ngân hàng giải ngân theo tiến độ', ratio: 0.5, payer: 'BANK' },
      { label: 'Đợt 3', milestone: 'Ngân hàng giải ngân khi bàn giao', ratio: 0.35, payer: 'BANK' },
    ],
  },
]
