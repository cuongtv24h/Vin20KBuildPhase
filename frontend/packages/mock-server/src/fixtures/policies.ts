import type { ActorRef, PolicyDocument, PolicyRule, RuleRelation, ScenarioCode, SourceCoordinate } from '@pricepolicy/api-client/contracts'

/**
 * Chính sách bán hàng theo trục thời gian (Time-Travel). Số liệu CSBH-ZEN v3.1 khớp ví dụ
 * PRD §7/§8 (ZEN-A-1205, 1.5% + 8.5% → 4.233.600.000đ). Điều 6.2 loại trừ nội thất ↔ thanh toán sớm.
 */

const ALL: ScenarioCode[] = ['PA-CHUDONG', 'PA-NHANH', 'PA-VAY']
const ADMIN: ActorRef = { user_id: 'USR-ADM-001', full_name: 'Tuấn Minh', role: 'POLICY_ADMIN' }

interface DocMeta {
  policy_id: string
  policy_version: string
  document_id: string
  document_hash: string
  source_document: string
}

type RuleInput = Omit<PolicyRule, 'source' | 'relations' | 'validation_status' | 'discount_rate' | 'cash_equivalent_vnd' | 'interest_support_months' | 'required_segments' | 'min_units_purchased' | 'is_ambiguous'> &
  Partial<Pick<PolicyRule, 'discount_rate' | 'cash_equivalent_vnd' | 'interest_support_months' | 'required_segments' | 'min_units_purchased' | 'is_ambiguous'>> & {
    clause: [clauseId: string, section: string, page: number, quote: string]
    relations?: RuleRelation[]
  }

function rule(doc: DocMeta, input: RuleInput): PolicyRule {
  const { clause, relations = [], ...rest } = input
  const source: SourceCoordinate = {
    document_id: doc.document_id,
    document_version: doc.policy_version,
    document_hash: doc.document_hash,
    clause_id: clause[0],
    section: clause[1],
    page: clause[2],
    quote: clause[3],
  }
  return {
    discount_rate: null,
    cash_equivalent_vnd: null,
    interest_support_months: null,
    required_segments: null,
    min_units_purchased: null,
    is_ambiguous: false,
    ...rest,
    relations,
    validation_status: 'APPROVED_FOR_USE',
    source,
  }
}

const EARLY_VS_LOAN =
  'Thanh toán sớm yêu cầu khách tự thanh toán ≥ 95% bằng vốn tự có, gói vay yêu cầu ngân hàng giải ngân ≥ 70% — hai điều kiện thực thi mâu thuẫn.'

const conflict = (rule_code: string, reason: string): RuleRelation => ({ type: 'CONDITIONAL_CONFLICT', rule_code, reason })
const exclusive = (rule_code: string, reason: string): RuleRelation => ({ type: 'MUTUALLY_EXCLUSIVE', rule_code, reason })

// ─── The Zen Park v2.0 (hết hiệu lực 31/07/2026) ─────────────────────────────

const ZEN_V2: DocMeta = {
  policy_id: 'CSBH-ZEN-2026-V2.0',
  policy_version: 'v2.0',
  document_id: 'DOC-ZEN-2026-02',
  document_hash: 'a3f1c9e27b04d85f6c1e2a9b7d30f48e5c6a1b2d9e8f7a6c5b4d3e2f1a0b9c8d',
  source_document: 'CSBH_TheZenPark_2026_V2_Stamped.pdf',
}

const ZEN_V2_RULES: PolicyRule[] = [
  rule(ZEN_V2, {
    rule_code: 'RESIDENT_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu cư dân tri ân',
    clause: ['Dieu_2_Khoan_1', 'Điều 2, Khoản 1', 2, 'Khách hàng là cư dân hiện hữu của VLandFuture có hợp đồng mua bán hợp lệ trước đó được hưởng chiết khấu tri ân 1.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.'],
    discount_rate: 0.01,
    applicable_scenarios: ALL,
    required_segments: ['EXISTING_RESIDENT'],
    is_selectable: false,
  }),
  rule(ZEN_V2, {
    rule_code: 'EARLY_PAY_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu thanh toán sớm 95%',
    clause: ['Dieu_4_Khoan_2b', 'Điều 4, Khoản 2b', 4, 'Khách hàng lựa chọn thanh toán sớm 95% bằng vốn tự có trong vòng 15 ngày kể từ ngày ký HĐMB được hưởng chiết khấu 7.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.'],
    discount_rate: 0.07,
    applicable_scenarios: ['PA-NHANH'],
    relations: [conflict('BANK_LOAN_HTLS', EARLY_VS_LOAN)],
    is_selectable: true,
  }),
  rule(ZEN_V2, {
    rule_code: 'BANK_LOAN_HTLS',
    kind: 'BANK_SUPPORT',
    title: 'Gói vay hỗ trợ lãi suất 0% (12 tháng)',
    clause: ['Dieu_3_Khoan_1', 'Điều 3, Khoản 1', 3, 'Chủ đầu tư phối hợp Ngân hàng đối tác tài trợ gói vay hỗ trợ lãi suất 0% trong 12 tháng đầu, ân hạn nợ gốc trong thời gian xây dựng, áp dụng cho khách hàng vay tối thiểu 70% giá trị căn hộ.'],
    interest_support_months: 12,
    applicable_scenarios: ['PA-VAY'],
    relations: [conflict('EARLY_PAY_DISCOUNT', EARLY_VS_LOAN)],
    is_selectable: true,
  }),
  rule(ZEN_V2, {
    rule_code: 'BULK_PURCHASE_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu mua sỉ từ căn thứ 2',
    clause: ['Dieu_5_Khoan_1', 'Điều 5, Khoản 1', 5, 'Khách hàng mua từ 2 căn hộ trở lên trong cùng đợt mở bán được hưởng thêm chiết khấu 2.0% cho mỗi căn tính từ căn thứ 2.'],
    discount_rate: 0.02,
    applicable_scenarios: ALL,
    min_units_purchased: 2,
    is_selectable: true,
  }),
]

// ─── The Zen Park v3.1 (hiệu lực 01/08 – 31/10/2026) ────────────────────────

function zenV3Rules(doc: DocMeta, earlyRate: number, loanMonths: number): PolicyRule[] {
  const earlyPct = (earlyRate * 100).toFixed(1)
  return [
    rule(doc, {
      rule_code: 'RESIDENT_DISCOUNT',
      kind: 'PERCENT_DISCOUNT',
      title: 'Chiết khấu cư dân tri ân',
      clause: ['Dieu_2_Khoan_1', 'Điều 2, Khoản 1', 2, 'Khách hàng là cư dân hiện hữu của VLandFuture có hợp đồng mua bán hợp lệ trước đó được hưởng chiết khấu tri ân 1.5% trên Giá bán chưa bao gồm thuế GTGT và KPBT.'],
      discount_rate: 0.015,
      applicable_scenarios: ALL,
      required_segments: ['EXISTING_RESIDENT'],
      is_selectable: false,
    }),
    rule(doc, {
      rule_code: 'EARLY_PAY_DISCOUNT',
      kind: 'PERCENT_DISCOUNT',
      title: 'Chiết khấu thanh toán sớm 95%',
      clause: ['Dieu_4_Khoan_2b', 'Điều 4, Khoản 2b', 4, `Khách hàng lựa chọn thanh toán sớm 95% bằng vốn tự có trong vòng 15 ngày kể từ ngày ký HĐMB được hưởng mức chiết khấu ${earlyPct}% trên Giá bán chưa bao gồm thuế GTGT và KPBT.`],
      discount_rate: earlyRate,
      applicable_scenarios: ['PA-NHANH'],
      relations: [
        exclusive('FURNITURE_GIFT', 'Điều 6, Khoản 2: gói hỗ trợ nội thất không áp dụng đồng thời với chiết khấu thanh toán sớm.'),
        conflict('BANK_LOAN_HTLS', EARLY_VS_LOAN),
      ],
      is_selectable: true,
    }),
    rule(doc, {
      rule_code: 'SMARTHOME_GIFT',
      kind: 'GIFT',
      title: 'Quà tặng gói thiết bị Smarthome',
      clause: ['Dieu_7_Khoan_1', 'Điều 7, Khoản 1', 7, 'Mọi khách hàng ký HĐMB trong đợt mở bán được tặng kèm gói thiết bị Smarthome trị giá quy đổi 30.000.000đ, không trừ vào giá bán.'],
      cash_equivalent_vnd: 30_000_000,
      applicable_scenarios: ALL,
      is_selectable: true,
    }),
    rule(doc, {
      rule_code: 'FURNITURE_GIFT',
      kind: 'GIFT',
      title: 'Gói hỗ trợ nội thất 100 triệu',
      clause: ['Dieu_6_Khoan_2', 'Điều 6, Khoản 2', 6, 'Khách hàng không áp dụng chiết khấu thanh toán sớm được nhận gói hỗ trợ nội thất trị giá quy đổi 100.000.000đ. Gói hỗ trợ nội thất không được áp dụng đồng thời với Chiết khấu thanh toán sớm 95% (Điều 4, Khoản 2b).'],
      cash_equivalent_vnd: 100_000_000,
      applicable_scenarios: ALL,
      relations: [exclusive('EARLY_PAY_DISCOUNT', 'Điều 6, Khoản 2: không áp dụng đồng thời với chiết khấu thanh toán sớm 95%.')],
      is_selectable: true,
    }),
    rule(doc, {
      rule_code: 'BULK_PURCHASE_DISCOUNT',
      kind: 'PERCENT_DISCOUNT',
      title: 'Chiết khấu mua sỉ từ căn thứ 2',
      clause: ['Dieu_5_Khoan_1', 'Điều 5, Khoản 1', 5, 'Khách hàng mua từ 2 căn hộ trở lên trong cùng đợt mở bán được hưởng thêm chiết khấu 2.0% cho mỗi căn tính từ căn thứ 2.'],
      discount_rate: 0.02,
      applicable_scenarios: ALL,
      min_units_purchased: 2,
      is_selectable: true,
    }),
    rule(doc, {
      rule_code: 'BANK_LOAN_HTLS',
      kind: 'BANK_SUPPORT',
      title: `Gói vay hỗ trợ lãi suất 0% (${loanMonths} tháng)`,
      clause: ['Dieu_3_Khoan_1', 'Điều 3, Khoản 1', 3, `Chủ đầu tư phối hợp Ngân hàng đối tác tài trợ gói vay hỗ trợ lãi suất 0% trong ${loanMonths} tháng đầu kể từ ngày giải ngân, ân hạn nợ gốc trong thời gian xây dựng, áp dụng cho khách hàng vay tối thiểu 70% giá trị căn hộ.`],
      interest_support_months: loanMonths,
      applicable_scenarios: ['PA-VAY'],
      relations: [conflict('EARLY_PAY_DISCOUNT', EARLY_VS_LOAN)],
      is_selectable: true,
    }),
    rule(doc, {
      rule_code: 'GOODWILL_SPECIAL',
      kind: 'DISCRETIONARY',
      title: 'Ưu đãi khách hàng đặc biệt theo quyết định riêng',
      clause: ['Dieu_9_Khoan_1', 'Điều 9, Khoản 1', 9, 'Ban Giám đốc có thể xem xét áp dụng thêm ưu đãi bổ sung cho một số trường hợp khách hàng thiện chí đặc biệt, tuỳ theo quyết định riêng của Ban Giám đốc trong từng thời điểm.'],
      applicable_scenarios: ALL,
      is_ambiguous: true,
      is_selectable: true,
    }),
  ]
}

const ZEN_V31: DocMeta = {
  policy_id: 'CSBH-ZEN-2026-V3.1',
  policy_version: 'v3.1',
  document_id: 'DOC-ZEN-2026-03',
  document_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  source_document: 'CSBH_TheZenPark_2026_Official_Stamped.pdf',
}

const ZEN_V4: DocMeta = {
  policy_id: 'CSBH-ZEN-2027-V4.0',
  policy_version: 'v4.0',
  document_id: 'DOC-ZEN-2027-01',
  document_hash: '9f2c1a7be04d3e55c1b8a0f6d2e47c93a51b6e08d7f4c2a9e3b1d5f7a8c6e402',
  source_document: 'CSBH_TheZenPark_Dot4_Draft.pdf',
}

// ─── VLandFuture Sapphire v1.0 ──────────────────────────────────────────────

const SAP_V1: DocMeta = {
  policy_id: 'CSBH-SAP-2026-V1.0',
  policy_version: 'v1.0',
  document_id: 'DOC-SAP-2026-01',
  document_hash: '4a7d1ed414474e4033ac29ccb8653d9b3f1c5e8a2b6d0f9e7c4a1b3d5e7f9a20',
  source_document: 'CSBH_Sapphire_2026_Official_Stamped.pdf',
}

const SAP_V1_RULES: PolicyRule[] = [
  rule(SAP_V1, {
    rule_code: 'RESIDENT_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu khách hàng thân thiết',
    clause: ['Dieu_2_Khoan_1', 'Điều 2, Khoản 1', 2, 'Khách hàng đã sở hữu sản phẩm của VLandFuture được hưởng chiết khấu 1.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.'],
    discount_rate: 0.01,
    applicable_scenarios: ALL,
    required_segments: ['EXISTING_RESIDENT'],
    is_selectable: false,
  }),
  rule(SAP_V1, {
    rule_code: 'EARLY_PAY_DISCOUNT',
    kind: 'PERCENT_DISCOUNT',
    title: 'Chiết khấu thanh toán sớm 95%',
    clause: ['Dieu_3_Khoan_1', 'Điều 3, Khoản 1', 3, 'Khách hàng thanh toán 95% giá trị trong vòng 15 ngày kể từ ngày ký HĐMB được hưởng chiết khấu 6.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.'],
    discount_rate: 0.06,
    applicable_scenarios: ['PA-NHANH'],
    relations: [conflict('BANK_LOAN_HTLS', EARLY_VS_LOAN)],
    is_selectable: true,
  }),
  rule(SAP_V1, {
    rule_code: 'BANK_LOAN_HTLS',
    kind: 'BANK_SUPPORT',
    title: 'Gói vay hỗ trợ lãi suất 0% (18 tháng)',
    clause: ['Dieu_4_Khoan_1', 'Điều 4, Khoản 1', 4, 'Ngân hàng đối tác hỗ trợ lãi suất 0% trong 18 tháng kể từ ngày giải ngân đầu tiên, ân hạn nợ gốc đến khi bàn giao, áp dụng cho khoản vay tối đa 70% giá trị căn hộ.'],
    interest_support_months: 18,
    applicable_scenarios: ['PA-VAY'],
    relations: [conflict('EARLY_PAY_DISCOUNT', EARLY_VS_LOAN)],
    is_selectable: true,
  }),
  rule(SAP_V1, {
    rule_code: 'MANAGEMENT_FEE_GIFT',
    kind: 'GIFT',
    title: 'Miễn phí quản lý 24 tháng',
    clause: ['Dieu_6_Khoan_1', 'Điều 6, Khoản 1', 6, 'Khách hàng ký HĐMB trong đợt mở bán được miễn phí quản lý vận hành 24 tháng đầu kể từ ngày bàn giao, trị giá quy đổi 45.000.000đ.'],
    cash_equivalent_vnd: 45_000_000,
    applicable_scenarios: ALL,
    is_selectable: true,
  }),
]

const doc = (meta: DocMeta, rest: Omit<PolicyDocument, keyof DocMeta | 'rules' | 'created_by' | 'published_by'> & { published: boolean }, rules: PolicyRule[]): PolicyDocument => {
  const { published, ...fields } = rest
  return { ...meta, ...fields, created_by: ADMIN, published_by: published ? ADMIN : null, rules }
}

export const POLICIES_FIXTURE: PolicyDocument[] = [
  doc(ZEN_V2, {
    title: 'Chính sách Bán hàng The Zen Park — Đợt mở bán đầu năm 2026',
    project_id: 'THE_ZEN_PARK',
    status: 'PUBLISHED',
    effective_from: '2026-01-01',
    effective_to: '2026-07-31',
    created_at: '2025-12-20T02:00:00.000Z',
    published_at: '2025-12-26T03:00:00.000Z',
    published: true,
  }, ZEN_V2_RULES),
  doc(ZEN_V31, {
    title: 'Chính sách Bán hàng The Zen Park — Đợt 3/2026',
    project_id: 'THE_ZEN_PARK',
    status: 'PUBLISHED',
    effective_from: '2026-08-01',
    effective_to: '2026-10-31',
    created_at: '2026-07-18T02:00:00.000Z',
    published_at: '2026-07-25T03:00:00.000Z',
    published: true,
  }, zenV3Rules(ZEN_V31, 0.085, 24)),
  doc(ZEN_V4, {
    title: 'Chính sách Bán hàng The Zen Park — Đợt 4 (Tết 2027)',
    project_id: 'THE_ZEN_PARK',
    status: 'DRAFT',
    effective_from: '2026-11-01',
    effective_to: '2027-02-28',
    created_at: '2026-09-20T04:00:00.000Z',
    published_at: null,
    published: false,
  }, zenV3Rules(ZEN_V4, 0.09, 24).map((r) => ({ ...r, validation_status: 'VALIDATION_REQUIRED' as const }))),
  doc(SAP_V1, {
    title: 'Chính sách Bán hàng VLandFuture Sapphire — Mở bán 2026',
    project_id: 'VLANDFUTURE_SAPPHIRE',
    status: 'PUBLISHED',
    effective_from: '2026-07-01',
    effective_to: '2026-12-31',
    created_at: '2026-06-10T02:00:00.000Z',
    published_at: '2026-06-20T03:00:00.000Z',
    published: true,
  }, SAP_V1_RULES),
]
