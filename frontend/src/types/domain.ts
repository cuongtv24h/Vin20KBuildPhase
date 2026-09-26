/**
 * Domain model dùng chung giữa UI và lớp API (src/api).
 * Tên trường và giá trị enum là hợp đồng dữ liệu với backend — đổi ở đây phải đổi cả
 * backend (xem frontend/docs/INTEGRATION.md).
 */

// ─── Enum trạng thái ────────────────────────────────────────────────────────

/** Trạng thái quyết định của một điều khoản/ưu đãi đối với một giao dịch cụ thể. */
export type PolicyDecisionStatus =
  | 'ELIGIBLE'
  | 'NOT_ELIGIBLE'
  | 'CONFLICT'
  | 'AMBIGUOUS'
  | 'EXPIRED'
  | 'PENDING_APPROVAL'

/** Vòng đời hồ sơ báo giá. Chuyển trạng thái hợp lệ: xem src/engine/workflow.ts. */
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

/** Vai trò nhân viên nội bộ. Khách hàng không đăng nhập — truy cập qua cổng công khai. */
export type UserRole = 'SALE' | 'SALE_ADMIN' | 'MANAGER'

export type PolicyStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'

export type UnitStatus = 'AVAILABLE' | 'RESERVED' | 'SOLD'

export type LeadStatus = 'NEW' | 'IN_PROGRESS' | 'QUOTE_SENT' | 'CUSTOMER_ACCEPTED' | 'CLOSED'

export type ShareChannel = 'ZALO' | 'SMS' | 'EMAIL'

export type CustomerDecision = 'ACCEPTED' | 'NEED_CONSULTATION'

// ─── Người dùng nội bộ ──────────────────────────────────────────────────────

export interface StaffUser {
  userId: string
  fullName: string
  email: string
  phone: string
  role: UserRole
  title: string
}

// ─── Dự án & căn hộ ─────────────────────────────────────────────────────────

export interface Project {
  projectId: string
  name: string
  location: string
  description: string
  handoverTime: string
  totalUnits: number
}

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
  status: UnitStatus
}

// ─── Chính sách bán hàng ───────────────────────────────────────────────────

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
  /** Tỷ lệ giảm trên giá niêm yết (kind = PERCENT_DISCOUNT). */
  discountRate?: number
  /** Giá trị quy đổi tiền mặt của quà tặng (kind = GIFT). */
  cashEquivalentVnd?: number
  /** Số tháng hỗ trợ lãi suất 0% (kind = BANK_SUPPORT). */
  interestSupportMonths?: number
  applicablePlans: PaymentPlanType[]
  requiredSegments?: CustomerSegment[]
  minUnitsPurchased?: number
  /** Xung đột Cấp 1 — loại trừ tường minh. */
  mutualExclusion?: string[]
  /** Xung đột Cấp 2 — mâu thuẫn điều kiện thực thi ngầm. */
  conditionalConflict?: { ruleCode: string; reasonText: string }[]
  /** Xung đột Cấp 3 — điều khoản mơ hồ, cần Quản lý thẩm định. */
  isAmbiguous?: boolean
  /** true = Sale chọn thủ công; false = tự động áp dụng theo hồ sơ khách. */
  isSelectable: boolean
}

export interface PolicyVersion {
  policyId: string
  version: string
  title: string
  projectId: string
  status: PolicyStatus
  effectiveFrom: string // YYYY-MM-DD
  effectiveTo: string // YYYY-MM-DD
  sourceDocument: string
  sourceFileHash: string
  createdAt: string
  createdBy: string
  publishedAt: string | null
  publishedBy: string | null
  rules: PolicyRule[]
}

// ─── Phương án thanh toán ──────────────────────────────────────────────────

export interface PaymentMilestone {
  label: string
  milestone: string
  /** Tỷ lệ trên Net Price. */
  ratio: number
  payer: 'CUSTOMER' | 'BANK'
}

export interface PaymentPlanConfig {
  plan: PaymentPlanType
  label: string
  description: string
  installmentsCount: number
  initialPaymentRatio: number
  totalCashOutflowRatio: number
  schedule: PaymentMilestone[]
}

// ─── Kết quả tính toán ─────────────────────────────────────────────────────

export interface RuleEvaluationResult {
  ruleCode: string
  title: string
  status: PolicyDecisionStatus
  amountVnd: number
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

// ─── Preflight ─────────────────────────────────────────────────────────────

export interface ConflictFinding {
  tier?: ConflictTier
  ruleCodes: string[]
  status: 'CONFLICT' | 'AMBIGUOUS' | 'EXPIRED'
  message: string
  source?: SourceCoordinate
}

export interface PolicyVersionRef {
  policyId: string
  version: string
  title: string
  effectiveFrom: string
  effectiveTo: string
  sourceFileHash: string
}

export interface PreflightResult {
  transactionDate: string
  activePolicy: PolicyVersionRef | null
  expired: boolean
  findings: ConflictFinding[]
  hasBlockingIssue: boolean
}

// ─── Đầu vào phân tích báo giá ─────────────────────────────────────────────

export interface TransactionContext {
  unitCode: string
  transactionDate: string
  customerSegment: CustomerSegment
  unitsQuantity: number
  selectedRuleCodes: string[]
  objective: OptimizationObjective
  customerName: string
  customerPhone: string
}

// ─── Khách hàng tiềm năng (Pre-sale) ───────────────────────────────────────

export interface Lead {
  leadId: string
  createdAt: string
  updatedAt: string
  fullName: string
  phone: string
  email: string
  unitCode: string
  customerSegment: CustomerSegment
  objective: OptimizationObjective
  note: string
  status: LeadStatus
  assignedSaleId: string | null
  assignedSaleName: string | null
}

// ─── Hồ sơ báo giá ─────────────────────────────────────────────────────────

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

export type QuoteEventType =
  | 'CREATED'
  | 'REVISED'
  | 'SUBMITTED'
  | 'ESCALATED'
  | 'APPROVED'
  | 'REJECTED'
  | 'REVISION_REQUESTED'
  | 'SHARED'
  | 'CUSTOMER_VIEWED'
  | 'CUSTOMER_RESPONDED'

export interface QuoteEvent {
  eventId: string
  type: QuoteEventType
  at: string
  version: number
  actorName: string
  actorRole: UserRole | 'CUSTOMER' | 'SYSTEM'
  note?: string
}

export interface CustomerResponse {
  decision: CustomerDecision
  note: string
  preferredAppointment: string | null
  at: string
}

export interface QuoteDistribution {
  shareToken: string
  channel: ShareChannel
  sharedAt: string
  sharedBy: string
  expiresAt: string
  viewedAt: string | null
  customerResponse: CustomerResponse | null
}

export interface PolicySnapshot {
  quoteId: string
  version: number
  snapshotTimestamp: string
  unit: ApartmentUnit
  context: TransactionContext
  policyVersion: PolicyVersionRef | null
  scenarios: CalculationResult[]
  recommendation: RecommendationRecord | null
  approval: Omit<ApprovalRecord, 'signatureHex'>
}

export interface Quote {
  quoteId: string
  version: number
  status: WorkflowStatus
  createdAt: string
  updatedAt: string
  ownerId: string
  ownerName: string
  leadId: string | null
  context: TransactionContext
  unit: ApartmentUnit
  preflight: PreflightResult | null
  scenarios: CalculationResult[]
  recommendation: RecommendationRecord | null
  riskFlag: RiskFlag
  approval: ApprovalRecord | null
  snapshot: PolicySnapshot | null
  snapshotHash: string | null
  distribution: QuoteDistribution | null
  history: QuoteEvent[]
}

// ─── Kiểm thử công thức ────────────────────────────────────────────────────

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
