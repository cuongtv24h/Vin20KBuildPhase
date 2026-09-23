/**
 * Domain types cho PricePolicy AI Agent (VLandFuture).
 * Toàn bộ dữ liệu trong app này là MOCK — xem src/data/ để biết nguồn giả lập.
 * Khi nối API thật, chỉ cần thay lớp src/data/ bằng lớp gọi API cùng interface này.
 */

// ─── Trạng thái chuẩn (đặt tên đúng theo tài liệu nghiệp vụ) ───────────────

/** 6 trạng thái quyết định của một điều khoản/ưu đãi cho một giao dịch cụ thể. */
export type PolicyDecisionStatus =
  | 'ELIGIBLE'
  | 'NOT_ELIGIBLE'
  | 'CONFLICT'
  | 'AMBIGUOUS'
  | 'EXPIRED'
  | 'PENDING_APPROVAL'

/** Trạng thái vòng đời của một hồ sơ báo giá (Quote). */
export type WorkflowStatus =
  | 'DRAFT'
  | 'READY_FOR_REVIEW'
  | 'ABSTAINED'
  | 'APPROVED'
  | 'REJECTED'
  | 'NEEDS_REVISION'
  | 'CALCULATION_FAILED'

export type OptimizationObjective =
  | 'MIN_NET_PRICE'
  | 'MIN_INITIAL_OUTFLOW'
  | 'MIN_TOTAL_CASH_OUTFLOW'
  | 'MAX_BENEFIT_VALUE'

export type CustomerSegment = 'EXISTING_RESIDENT' | 'NEW_CUSTOMER'

export type PaymentPlanType = 'STANDARD_PROGRESS' | 'EARLY_PAYMENT_95' | 'BANK_LOAN_SUPPORT'

export type ConflictTier = 1 | 2 | 3

export type RiskFlagColor = 'RED' | 'YELLOW' | 'GREEN'

export type UserRole = 'SALES' | 'MANAGER' | 'ADMIN'

// ─── Căn hộ (Inventory reference — read-only) ──────────────────────────────

export interface ApartmentUnit {
  unitCode: string
  projectId: string
  projectName: string
  block: string
  floor: number
  bedrooms: number
  areaM2: number
  view: string
  listedPrice: number
  status: 'AVAILABLE' | 'RESERVED' | 'SOLD'
}

// ─── Chính sách (Policy Intelligence) ──────────────────────────────────────

export interface SourceCoordinate {
  documentId: string
  policyVersion: string
  clauseId: string
  clauseTitle: string
  page: number
  sourceDocument: string
  sourceFileHash: string
}

export interface PolicyRule {
  ruleCode: string
  policyId: string
  policyVersion: string
  kind: 'PERCENT_DISCOUNT' | 'GIFT' | 'BANK_SUPPORT' | 'AMBIGUOUS_CLAUSE'
  title: string
  evidenceText: string
  source: SourceCoordinate
  /** Áp dụng cho tỷ lệ % giảm trên giá niêm yết (kind = PERCENT_DISCOUNT). */
  discountRate?: number
  /** Giá trị quy đổi tiền mặt cho quà tặng hiện vật (kind = GIFT). */
  cashEquivalentVnd?: number
  /** Số tháng hỗ trợ lãi suất 0% (kind = BANK_SUPPORT). */
  interestSupportMonths?: number
  /** Phương án thanh toán mà điều khoản này có thể áp dụng. */
  applicablePlans: PaymentPlanType[]
  /** Nếu có, chỉ áp dụng cho các phân khúc khách hàng này. */
  requiredSegments?: CustomerSegment[]
  /** Nếu có, yêu cầu số lượng căn mua tối thiểu. */
  minUnitsPurchased?: number
  /** Cấp 1 — Loại trừ tường minh: danh sách ruleCode không được chọn cùng lúc. */
  mutualExclusion?: string[]
  /** Cấp 2 — Xung đột ràng buộc điều kiện ngầm. */
  conditionalConflict?: { ruleCode: string; reasonText: string }[]
  /** Cấp 3 — Điều khoản mơ hồ, không đủ căn cứ để agent tự quyết. */
  isAmbiguous?: boolean
  /** true nếu Sale phải tự chọn (checkbox); false = tự động áp dụng theo hồ sơ khách. */
  isSelectable: boolean
}

export interface PolicyVersion {
  policyId: string
  version: string
  title: string
  projectId: string
  effectiveFrom: string // ISO date
  effectiveTo: string // ISO date
  sourceDocument: string
  sourceFileHash: string
  rules: PolicyRule[]
}

// ─── Phương án thanh toán (Cashflow schedule config) ───────────────────────

export interface PaymentPlanConfig {
  plan: PaymentPlanType
  label: string
  description: string
  installmentsCount: number
  /** Tỷ lệ % netPrice phải trả ở đợt 1. */
  initialPaymentRatio: number
  /** Tỷ lệ % netPrice khách phải chi tiền mặt tính đến thời điểm bàn giao. */
  totalCashOutflowRatio: number
}

// ─── Kết quả tính toán (Deterministic Pricing Engine output) ──────────────

export interface RuleEvaluationResult {
  ruleCode: string
  title: string
  status: PolicyDecisionStatus
  amountVnd: number // số tiền chiết khấu hoặc giá trị quy đổi (0 nếu không áp dụng)
  reasonText: string
  source: SourceCoordinate
}

export interface CalculationResult {
  plan: PaymentPlanType
  planLabel: string
  basePrice: number
  totalDiscountRate: number
  discountAmount: number
  priceBeforeVAT: number
  vatAmount: number
  kpbtAmount: number
  netPrice: number
  initialPaymentVnd: number
  totalCashOutflowToHandoverVnd: number
  benefitValueVnd: number
  installmentsCount: number
  ruleBreakdown: RuleEvaluationResult[]
  validation: { valid: boolean; reasons: string[] }
}

export interface RecommendationRecord {
  objective: OptimizationObjective
  recommendedPlan: PaymentPlanType
  rationale: string
  comparisons: { plan: PaymentPlanType; deltaLabel: string; deltaVnd: number }[]
}

// ─── Preflight / Conflict Detection ────────────────────────────────────────

export interface ConflictFinding {
  /** Không áp dụng cho status = 'EXPIRED'. */
  tier?: ConflictTier
  ruleCodes: string[]
  status: 'CONFLICT' | 'AMBIGUOUS' | 'EXPIRED'
  message: string
  source?: SourceCoordinate
}

export interface PreflightResult {
  transactionDate: string
  activePolicy: PolicyVersion | null
  expired: boolean
  findings: ConflictFinding[]
  hasBlockingIssue: boolean
}

// ─── Transaction Context (input của Sales Copilot) ─────────────────────────

export interface TransactionContext {
  unitCode: string
  transactionDate: string
  customerSegment: CustomerSegment
  unitsQuantity: number
  selectedRuleCodes: string[]
  objective: OptimizationObjective
  customerName: string
  salesRepName: string
}

// ─── Quote (Hồ sơ báo giá — Commercial Quote) ──────────────────────────────

export interface RiskFlag {
  color: RiskFlagColor
  label: string
  reasons: string[]
}

export interface ApprovalRecord {
  approverId: string
  approverName: string
  decision: 'APPROVED' | 'REJECTED' | 'NEEDS_REVISION'
  notes: string
  timestamp: string
  signatureHex?: string
}

export interface PolicySnapshot {
  quoteId: string
  snapshotTimestamp: string
  snapshotHash: string
  unit: ApartmentUnit
  context: TransactionContext
  policyVersion: { policyId: string; version: string; effectiveFrom: string; effectiveTo: string; sourceFileHash: string }
  scenarios: CalculationResult[]
  recommendation: RecommendationRecord | null
  approval: ApprovalRecord | null
}

export interface Quote {
  quoteId: string
  version: number
  status: WorkflowStatus
  createdAt: string
  updatedAt: string
  context: TransactionContext
  unit: ApartmentUnit
  preflight: PreflightResult | null
  scenarios: CalculationResult[]
  recommendation: RecommendationRecord | null
  riskFlag: RiskFlag
  approval: ApprovalRecord | null
  snapshotHash: string | null
  demoScenarioTag?: string
}

// ─── Benchmark ──────────────────────────────────────────────────────────

export interface BenchmarkCase {
  id: string
  name: string
  basePrice: number
  eligibleDiscountRates: number[]
  expected: {
    discountAmount: number
    priceBeforeVAT: number
    vatAmount: number
    kpbtAmount: number
    netPrice: number
  }
}

export interface BenchmarkRunResult {
  case: BenchmarkCase
  actual: {
    discountAmount: number
    priceBeforeVAT: number
    vatAmount: number
    kpbtAmount: number
    netPrice: number
  }
  deltaVnd: number
  passed: boolean
}
