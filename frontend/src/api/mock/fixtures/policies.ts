import type { PaymentPlanType, PolicyRule, PolicyVersion, SourceCoordinate } from '@/types/domain'

/**
 * Chính sách bán hàng theo trục thời gian (Time-Travel Policy Versioning).
 * Số liệu CSBH-ZEN v3.1 khớp ví dụ PRD §7/§8 (ZEN-A-1205, 1.5% + 8.5% → 4.233.600.000đ).
 */

const ALL_PLANS: PaymentPlanType[] = ['STANDARD_PROGRESS', 'EARLY_PAYMENT_95', 'BANK_LOAN_SUPPORT']

interface DocMeta {
  policyId: string
  version: string
  sourceDocument: string
  sourceFileHash: string
}

function sourceOf(doc: DocMeta, clauseId: string, clauseTitle: string, page: number): SourceCoordinate {
  return {
    documentId: doc.policyId,
    policyVersion: doc.version,
    clauseId,
    clauseTitle,
    page,
    sourceDocument: doc.sourceDocument,
    sourceFileHash: doc.sourceFileHash,
  }
}

function rule(doc: DocMeta, r: Omit<PolicyRule, 'policyId' | 'policyVersion' | 'source'> & { clause: [string, string, number] }): PolicyRule {
  const { clause, ...rest } = r
  return { ...rest, policyId: doc.policyId, policyVersion: doc.version, source: sourceOf(doc, ...clause) }
}

const EARLY_VS_LOAN =
  'Điều 4 yêu cầu khách tự thanh toán ≥ 95% bằng vốn tự có, trong khi Điều 3 (Gói vay ngân hàng HTLS) yêu cầu ngân hàng giải ngân ≥ 70% — hai điều kiện thực thi mâu thuẫn nếu chọn đồng thời.'
const LOAN_VS_EARLY =
  'Gói vay yêu cầu ngân hàng giải ngân ≥ 70%, mâu thuẫn với Điều 4 (thanh toán sớm ≥ 95% bằng vốn tự có) nếu chọn đồng thời.'

// ─── The Zen Park v2.0 (đã hết hiệu lực, giữ để tra cứu lịch sử) ────────────

const ZEN_V2: DocMeta = {
  policyId: 'CSBH-ZEN-2026-V2',
  version: 'v2.0',
  sourceDocument: 'CSBH_TheZenPark_2026_V2_Stamped.pdf',
  sourceFileHash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b785e8a1',
}

const ZEN_V2_RULES: PolicyRule[] = [
  rule(ZEN_V2, {
    ruleCode: 'RESIDENT_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu cư dân tri ân',
    evidenceText:
      'Khách hàng là cư dân hiện hữu của VLandFuture có hợp đồng mua bán hợp lệ trước đó được hưởng chiết khấu tri ân 1.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.',
    clause: ['Dieu_2_Khoan_1', 'Điều 2, Khoản 1', 2],
    discountRate: 0.01,
    applicablePlans: ALL_PLANS,
    requiredSegments: ['EXISTING_RESIDENT'],
    isSelectable: false,
  }),
  rule(ZEN_V2, {
    ruleCode: 'EARLY_PAY_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu thanh toán sớm 95%',
    evidenceText:
      'Khách hàng lựa chọn thanh toán sớm 95% bằng vốn tự có trong vòng 15 ngày kể từ ngày ký HĐMB được hưởng chiết khấu 7.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.',
    clause: ['Dieu_4_Khoan_2b', 'Điều 4, Khoản 2b', 4],
    discountRate: 0.07,
    applicablePlans: ['EARLY_PAYMENT_95'],
    conditionalConflict: [{ ruleCode: 'BANK_LOAN_HTLS', reasonText: EARLY_VS_LOAN }],
    isSelectable: true,
  }),
  rule(ZEN_V2, {
    ruleCode: 'BANK_LOAN_HTLS',
    kind: 'BANK_SUPPORT',
    title: 'Gói vay ngân hàng hỗ trợ lãi suất 0% (12 tháng)',
    evidenceText:
      'Chủ đầu tư phối hợp Ngân hàng đối tác tài trợ gói vay hỗ trợ lãi suất 0% trong 12 tháng đầu, ân hạn nợ gốc trong thời gian xây dựng, áp dụng cho khách hàng vay tối thiểu 70% giá trị căn hộ.',
    clause: ['Dieu_3_Khoan_1', 'Điều 3, Khoản 1', 3],
    interestSupportMonths: 12,
    applicablePlans: ['BANK_LOAN_SUPPORT'],
    conditionalConflict: [{ ruleCode: 'EARLY_PAY_DISCOUNT', reasonText: LOAN_VS_EARLY }],
    isSelectable: true,
  }),
  rule(ZEN_V2, {
    ruleCode: 'BULK_PURCHASE_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu mua sỉ từ căn thứ 2',
    evidenceText:
      'Khách hàng mua từ 2 căn hộ trở lên trong cùng đợt mở bán được hưởng thêm chiết khấu 2.0% cho mỗi căn tính từ căn thứ 2.',
    clause: ['Dieu_5_Khoan_1', 'Điều 5, Khoản 1', 5],
    discountRate: 0.02,
    applicablePlans: ALL_PLANS,
    minUnitsPurchased: 2,
    isSelectable: true,
  }),
]

// ─── The Zen Park v3.1 (đang hiệu lực) ─────────────────────────────────────

const ZEN_V31: DocMeta = {
  policyId: 'CSBH-ZEN-2026-V3.1',
  version: 'v3.1',
  sourceDocument: 'CSBH_TheZenPark_2026_Official_Stamped.pdf',
  sourceFileHash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85',
}

function zenV3Rules(doc: DocMeta, earlyRate: number, loanMonths: number): PolicyRule[] {
  return [
    rule(doc, {
      ruleCode: 'RESIDENT_DISCOUNT',
      kind: 'PERCENT_DISCOUNT',
      title: 'Chiết khấu cư dân tri ân',
      evidenceText:
        'Khách hàng là cư dân hiện hữu của VLandFuture có hợp đồng mua bán hợp lệ trước đó được hưởng chiết khấu tri ân 1.5% trên Giá bán chưa bao gồm thuế GTGT và KPBT.',
      clause: ['Dieu_2_Khoan_1', 'Điều 2, Khoản 1', 2],
      discountRate: 0.015,
      applicablePlans: ALL_PLANS,
      requiredSegments: ['EXISTING_RESIDENT'],
      isSelectable: false,
    }),
    rule(doc, {
      ruleCode: 'EARLY_PAY_DISCOUNT',
      kind: 'PERCENT_DISCOUNT',
      title: 'Chiết khấu thanh toán sớm 95%',
      evidenceText: `Khách hàng lựa chọn thanh toán sớm 95% bằng vốn tự có trong vòng 15 ngày kể từ ngày ký HĐMB được hưởng mức chiết khấu ${(earlyRate * 100).toFixed(1)}% trên Giá bán chưa bao gồm thuế GTGT và KPBT.`,
      clause: ['Dieu_4_Khoan_2b', 'Điều 4, Khoản 2b', 4],
      discountRate: earlyRate,
      applicablePlans: ['EARLY_PAYMENT_95'],
      mutualExclusion: ['FURNITURE_GIFT'],
      conditionalConflict: [{ ruleCode: 'BANK_LOAN_HTLS', reasonText: EARLY_VS_LOAN }],
      isSelectable: true,
    }),
    rule(doc, {
      ruleCode: 'SMARTHOME_GIFT',
      kind: 'GIFT',
      title: 'Quà tặng gói thiết bị Smarthome',
      evidenceText:
        'Mọi khách hàng ký HĐMB trong đợt mở bán được tặng kèm gói thiết bị Smarthome (khoá cửa vân tay, camera an ninh, công tắc thông minh) trị giá quy đổi 30.000.000đ, không trừ vào giá bán.',
      clause: ['Dieu_7_Khoan_1', 'Điều 7, Khoản 1', 7],
      cashEquivalentVnd: 30_000_000,
      applicablePlans: ALL_PLANS,
      isSelectable: true,
    }),
    rule(doc, {
      ruleCode: 'FURNITURE_GIFT',
      kind: 'GIFT',
      title: 'Gói hỗ trợ nội thất 100 triệu',
      evidenceText:
        'Khách hàng không áp dụng chiết khấu thanh toán sớm được lựa chọn nhận gói hỗ trợ nội thất trị giá quy đổi 100.000.000đ. Gói hỗ trợ nội thất không được áp dụng đồng thời với Chiết khấu thanh toán sớm 95% (Điều 4, Khoản 2b).',
      clause: ['Dieu_6_Khoan_2', 'Điều 6, Khoản 2', 6],
      cashEquivalentVnd: 100_000_000,
      applicablePlans: ALL_PLANS,
      mutualExclusion: ['EARLY_PAY_DISCOUNT'],
      isSelectable: true,
    }),
    rule(doc, {
      ruleCode: 'BULK_PURCHASE_DISCOUNT',
      kind: 'PERCENT_DISCOUNT',
      title: 'Chiết khấu mua sỉ từ căn thứ 2',
      evidenceText:
        'Khách hàng mua từ 2 căn hộ trở lên trong cùng đợt mở bán được hưởng thêm chiết khấu 2.0% cho mỗi căn tính từ căn thứ 2.',
      clause: ['Dieu_5_Khoan_1', 'Điều 5, Khoản 1', 5],
      discountRate: 0.02,
      applicablePlans: ALL_PLANS,
      minUnitsPurchased: 2,
      isSelectable: true,
    }),
    rule(doc, {
      ruleCode: 'BANK_LOAN_HTLS',
      kind: 'BANK_SUPPORT',
      title: `Gói vay ngân hàng hỗ trợ lãi suất 0% (${loanMonths} tháng)`,
      evidenceText: `Chủ đầu tư phối hợp Ngân hàng đối tác tài trợ gói vay hỗ trợ lãi suất 0% trong ${loanMonths} tháng đầu kể từ ngày giải ngân, ân hạn nợ gốc trong thời gian xây dựng, áp dụng cho khách hàng vay tối thiểu 70% giá trị căn hộ.`,
      clause: ['Dieu_3_Khoan_1', 'Điều 3, Khoản 1', 3],
      interestSupportMonths: loanMonths,
      applicablePlans: ['BANK_LOAN_SUPPORT'],
      conditionalConflict: [{ ruleCode: 'EARLY_PAY_DISCOUNT', reasonText: LOAN_VS_EARLY }],
      isSelectable: true,
    }),
    rule(doc, {
      ruleCode: 'GOODWILL_SPECIAL',
      kind: 'AMBIGUOUS_CLAUSE',
      title: 'Ưu đãi bổ sung cho khách hàng thiện chí',
      evidenceText:
        'Ban Giám đốc có thể xem xét áp dụng thêm ưu đãi bổ sung cho một số trường hợp khách hàng thiện chí đặc biệt, tuỳ theo quyết định riêng của Ban Giám đốc trong từng thời điểm.',
      clause: ['Dieu_9_Khoan_1', 'Điều 9, Khoản 1', 9],
      applicablePlans: ALL_PLANS,
      isAmbiguous: true,
      isSelectable: true,
    }),
  ]
}

// ─── The Zen Park v4.0 (bản nháp — Admin Sale chuẩn bị cho đợt mở bán tiếp theo) ──

const ZEN_V4: DocMeta = {
  policyId: 'CSBH-ZEN-2026-V4.0',
  version: 'v4.0',
  sourceDocument: 'CSBH_TheZenPark_Dot4_Draft.pdf',
  sourceFileHash: '9f2c1a7be04d3e55c1b8a0f6d2e47c93a51b6e08d7f4c2a9e3b1d5f7a8c6e402',
}

// ─── VLandFuture Sapphire v1.0 ──────────────────────────────────────────────

const SAP_V1: DocMeta = {
  policyId: 'CSBH-SAP-2026-V1.0',
  version: 'v1.0',
  sourceDocument: 'CSBH_Sapphire_2026_Official_Stamped.pdf',
  sourceFileHash: '4a7d1ed414474e4033ac29ccb8653d9b3f1c5e8a2b6d0f9e7c4a1b3d5e7f9a20',
}

const SAP_V1_RULES: PolicyRule[] = [
  rule(SAP_V1, {
    ruleCode: 'RESIDENT_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu khách hàng thân thiết',
    evidenceText:
      'Khách hàng đã sở hữu sản phẩm của VLandFuture được hưởng chiết khấu 1.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.',
    clause: ['Dieu_2_Khoan_1', 'Điều 2, Khoản 1', 2],
    discountRate: 0.01,
    applicablePlans: ALL_PLANS,
    requiredSegments: ['EXISTING_RESIDENT'],
    isSelectable: false,
  }),
  rule(SAP_V1, {
    ruleCode: 'EARLY_PAY_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu thanh toán sớm 95%',
    evidenceText:
      'Khách hàng thanh toán 95% giá trị trong vòng 15 ngày kể từ ngày ký HĐMB được hưởng chiết khấu 6.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.',
    clause: ['Dieu_3_Khoan_1', 'Điều 3, Khoản 1', 3],
    discountRate: 0.06,
    applicablePlans: ['EARLY_PAYMENT_95'],
    conditionalConflict: [{ ruleCode: 'BANK_LOAN_HTLS', reasonText: EARLY_VS_LOAN }],
    isSelectable: true,
  }),
  rule(SAP_V1, {
    ruleCode: 'BANK_LOAN_HTLS',
    kind: 'BANK_SUPPORT',
    title: 'Gói vay ngân hàng hỗ trợ lãi suất 0% (18 tháng)',
    evidenceText:
      'Ngân hàng đối tác hỗ trợ lãi suất 0% trong 18 tháng kể từ ngày giải ngân đầu tiên, áp dụng cho khoản vay tối đa 70% giá trị căn hộ.',
    clause: ['Dieu_4_Khoan_1', 'Điều 4, Khoản 1', 4],
    interestSupportMonths: 18,
    applicablePlans: ['BANK_LOAN_SUPPORT'],
    conditionalConflict: [{ ruleCode: 'EARLY_PAY_DISCOUNT', reasonText: LOAN_VS_EARLY }],
    isSelectable: true,
  }),
  rule(SAP_V1, {
    ruleCode: 'MANAGEMENT_FEE_GIFT',
    kind: 'GIFT',
    title: 'Miễn phí quản lý 24 tháng',
    evidenceText:
      'Khách hàng ký HĐMB trong đợt mở bán được miễn phí quản lý vận hành 24 tháng đầu kể từ ngày bàn giao, trị giá quy đổi 45.000.000đ.',
    clause: ['Dieu_6_Khoan_1', 'Điều 6, Khoản 1', 6],
    cashEquivalentVnd: 45_000_000,
    applicablePlans: ALL_PLANS,
    isSelectable: true,
  }),
]

export const POLICIES_FIXTURE: PolicyVersion[] = [
  {
    ...ZEN_V2,
    title: 'Chính sách Bán hàng The Zen Park — Đợt mở bán đầu năm 2026',
    projectId: 'THE_ZEN_PARK',
    status: 'PUBLISHED',
    effectiveFrom: '2026-01-01',
    effectiveTo: '2026-07-31',
    createdAt: '2025-12-20T02:00:00.000Z',
    createdBy: 'Tuấn Minh',
    publishedAt: '2025-12-26T03:00:00.000Z',
    publishedBy: 'Tuấn Minh',
    rules: ZEN_V2_RULES,
  },
  {
    ...ZEN_V31,
    title: 'Chính sách Bán hàng The Zen Park — Đợt 3/2026',
    projectId: 'THE_ZEN_PARK',
    status: 'PUBLISHED',
    effectiveFrom: '2026-08-01',
    effectiveTo: '2026-10-31',
    createdAt: '2026-07-18T02:00:00.000Z',
    createdBy: 'Tuấn Minh',
    publishedAt: '2026-07-25T03:00:00.000Z',
    publishedBy: 'Tuấn Minh',
    rules: zenV3Rules(ZEN_V31, 0.085, 24),
  },
  {
    ...ZEN_V4,
    title: 'Chính sách Bán hàng The Zen Park — Đợt 4 (Tết 2027)',
    projectId: 'THE_ZEN_PARK',
    status: 'DRAFT',
    effectiveFrom: '2026-11-01',
    effectiveTo: '2027-02-28',
    createdAt: '2026-09-20T04:00:00.000Z',
    createdBy: 'Tuấn Minh',
    publishedAt: null,
    publishedBy: null,
    rules: zenV3Rules(ZEN_V4, 0.09, 24),
  },
  {
    ...SAP_V1,
    title: 'Chính sách Bán hàng VLandFuture Sapphire — Mở bán 2026',
    projectId: 'VLANDFUTURE_SAPPHIRE',
    status: 'PUBLISHED',
    effectiveFrom: '2026-07-01',
    effectiveTo: '2026-12-31',
    createdAt: '2026-06-10T02:00:00.000Z',
    createdBy: 'Tuấn Minh',
    publishedAt: '2026-06-20T03:00:00.000Z',
    publishedBy: 'Tuấn Minh',
    rules: SAP_V1_RULES,
  },
]
