/**
 * Hợp đồng API giữa frontend và backend.
 *
 * - Mọi màn hình chỉ gọi dữ liệu qua `ApiClient` (thông qua hooks trong src/api/hooks.ts).
 * - Có 2 bản cài đặt: `mock` (src/api/mock) và `http` (src/api/http) — chọn bằng VITE_API_MODE.
 * - Comment `@endpoint` trên mỗi method là route REST mà httpClient gọi; backend hiện thực
 *   đúng route + DTO bên dưới là frontend chạy được ngay, không cần sửa UI.
 */
import type {
  ApartmentUnit,
  BenchmarkRunResult,
  CalculationResult,
  CustomerDecision,
  CustomerSegment,
  Lead,
  LeadStatus,
  OptimizationObjective,
  PaymentMilestone,
  PaymentPlanConfig,
  PaymentPlanType,
  PolicyRule,
  PolicyVersion,
  PolicyVersionRef,
  PreflightResult,
  Project,
  Quote,
  ShareChannel,
  StaffUser,
  TransactionContext,
  UnitStatus,
  WorkflowStatus,
} from '@/types/domain'

// ─── Auth ──────────────────────────────────────────────────────────────────

export interface LoginRequest {
  email: string
  password: string
}

export interface AuthSession {
  accessToken: string
  expiresAt: string
  user: StaffUser
}

// ─── Catalog ───────────────────────────────────────────────────────────────

export interface UnitFilter {
  projectId?: string
  status?: UnitStatus
  bedrooms?: number
}

// ─── Public (khách hàng — không cần đăng nhập) ─────────────────────────────

export interface PublicPromotion {
  ruleCode: string
  title: string
  summary: string
  clauseTitle: string
}

export interface ProjectOverview {
  project: Project
  activePolicy: PolicyVersionRef | null
  promotions: PublicPromotion[]
  availableUnits: number
  priceFrom: number | null
}

export interface EstimateRequest {
  unitCode: string
  customerSegment: CustomerSegment
}

export interface PlanEstimate {
  plan: PaymentPlanType
  planLabel: string
  description: string
  totalDiscountRate: number
  netPrice: number
  initialPaymentVnd: number
  installmentsCount: number
  appliedIncentives: string[]
}

export interface PriceEstimate {
  unit: ApartmentUnit
  policy: PolicyVersionRef | null
  estimatedAt: string
  plans: PlanEstimate[]
  gifts: { title: string; cashEquivalentVnd: number }[]
}

export interface CreateLeadRequest {
  fullName: string
  phone: string
  email: string
  unitCode: string
  customerSegment: CustomerSegment
  objective: OptimizationObjective
  note: string
}

export interface LeadReceipt {
  leadId: string
  createdAt: string
  unitCode: string
}

export interface ScheduledPayment extends PaymentMilestone {
  amountVnd: number
}

export interface CustomerScenario extends CalculationResult {
  schedule: ScheduledPayment[]
}

/** Báo giá chính thức theo góc nhìn khách hàng — không chứa cờ rủi ro / ghi chú nội bộ. */
export interface CustomerQuoteView {
  quoteId: string
  version: number
  issuedAt: string
  validUntil: string
  customerName: string
  unit: ApartmentUnit
  projectName: string
  policy: PolicyVersionRef | null
  objective: OptimizationObjective
  recommendedPlan: PaymentPlanType | null
  rationale: string | null
  scenarios: CustomerScenario[]
  salesRep: { fullName: string; phone: string; email: string }
  approvedBy: string
  snapshotHash: string
  customerResponse: {
    decision: CustomerDecision
    note: string
    preferredAppointment: string | null
    at: string
  } | null
}

export interface CustomerResponseRequest {
  decision: CustomerDecision
  note: string
  preferredAppointment: string | null
}

export interface QuoteVerification {
  quoteId: string
  storedHash: string
  recomputedHash: string
  valid: boolean
  verifiedAt: string
}

// ─── Leads (Sale) ──────────────────────────────────────────────────────────

export interface LeadListParams {
  scope: 'MINE' | 'UNASSIGNED' | 'ALL'
}

export interface UpdateLeadStatusRequest {
  status: LeadStatus
}

// ─── Quotes ────────────────────────────────────────────────────────────────

export interface QuoteListParams {
  /** Mặc định server lọc theo quyền: SALE chỉ thấy hồ sơ của mình. */
  status?: WorkflowStatus[]
  leadId?: string
}

export type CreateQuoteRequest = TransactionContext & { leadId: string | null }

export type PreflightRequest = Pick<
  TransactionContext,
  'unitCode' | 'transactionDate' | 'customerSegment' | 'unitsQuantity' | 'selectedRuleCodes'
>

/** Các bước agent xử lý — backend đẩy qua SSE `GET /quotes/{id}/events`. */
export type AnalysisStage = 'POLICY_LOOKUP' | 'PREFLIGHT' | 'PRICING' | 'RANKING'

export interface AnalysisProgressEvent {
  stage: AnalysisStage
  state: 'RUNNING' | 'DONE' | 'BLOCKED' | 'SKIPPED'
  message?: string
}

export interface AnalysisOptions {
  onProgress?: (event: AnalysisProgressEvent) => void
}

export interface ApprovalDecisionRequest {
  decision: 'APPROVED' | 'REJECTED' | 'NEEDS_REVISION'
  notes: string
}

export interface ShareQuoteRequest {
  channel: ShareChannel
}

// ─── Policies (Admin Sale) ─────────────────────────────────────────────────

export interface CreatePolicyDraftRequest {
  fromPolicyId: string
}

export type PolicyRulePatch = Pick<PolicyRule, 'ruleCode'> &
  Partial<Pick<PolicyRule, 'discountRate' | 'cashEquivalentVnd' | 'interestSupportMonths' | 'evidenceText'>>

export interface UpdatePolicyDraftRequest {
  title?: string
  version?: string
  effectiveFrom?: string
  effectiveTo?: string
  sourceDocument?: string
  sourceFileHash?: string
  rules?: PolicyRulePatch[]
}

export type PublishCheckStatus = 'PASS' | 'WARN' | 'FAIL'

export interface PublishCheck {
  code: 'DATE_RANGE' | 'OVERLAP' | 'RULE_VALUES' | 'MAX_STACKED_DISCOUNT' | 'EXCLUSION_REFS' | 'SOURCE_DOCUMENT' | 'FORMULA_REGRESSION'
  label: string
  status: PublishCheckStatus
  detail: string
}

export interface PublishCheckReport {
  policyId: string
  checkedAt: string
  checks: PublishCheck[]
  canPublish: boolean
}

// ─── Inventory (Admin Sale) ────────────────────────────────────────────────

export interface UpdateUnitRequest {
  status?: UnitStatus
  listedPrice?: number
}

// ─── Client interface ──────────────────────────────────────────────────────

export interface ApiClient {
  auth: {
    /** @endpoint POST /auth/login */
    login(input: LoginRequest): Promise<AuthSession>
    /** @endpoint POST /auth/logout */
    logout(): Promise<void>
  }

  catalog: {
    /** @endpoint GET /projects */
    listProjects(): Promise<Project[]>
    /** @endpoint GET /units?projectId=&status=&bedrooms= */
    listUnits(filter?: UnitFilter): Promise<ApartmentUnit[]>
    /** @endpoint GET /units/{unitCode} */
    getUnit(unitCode: string): Promise<ApartmentUnit>
    /** @endpoint GET /payment-plans */
    listPaymentPlans(): Promise<PaymentPlanConfig[]>
    /** @endpoint GET /policies/active?projectId=&date=  (Time-Travel lookup, chỉ PUBLISHED) */
    getActivePolicy(projectId: string, date: string): Promise<PolicyVersion | null>
  }

  public: {
    /** @endpoint GET /public/projects */
    listProjectOverviews(): Promise<ProjectOverview[]>
    /** @endpoint POST /public/estimates */
    estimate(input: EstimateRequest): Promise<PriceEstimate>
    /** @endpoint POST /public/leads */
    submitLead(input: CreateLeadRequest): Promise<LeadReceipt>
    /** @endpoint GET /public/quotes/{shareToken}  (đánh dấu viewedAt ở lần mở đầu) */
    getSharedQuote(shareToken: string): Promise<CustomerQuoteView>
    /** @endpoint POST /public/quotes/{shareToken}/response */
    respondToQuote(shareToken: string, input: CustomerResponseRequest): Promise<CustomerQuoteView>
    /** @endpoint GET /public/quotes/{shareToken}/verify */
    verifySharedQuote(shareToken: string): Promise<QuoteVerification>
  }

  leads: {
    /** @endpoint GET /leads?scope=MINE|UNASSIGNED|ALL */
    list(params: LeadListParams): Promise<Lead[]>
    /** @endpoint GET /leads/{leadId} */
    get(leadId: string): Promise<Lead>
    /** @endpoint POST /leads/{leadId}/claim */
    claim(leadId: string): Promise<Lead>
    /** @endpoint PATCH /leads/{leadId} */
    updateStatus(leadId: string, input: UpdateLeadStatusRequest): Promise<Lead>
  }

  quotes: {
    /** @endpoint GET /quotes?status=A,B&leadId= */
    list(params?: QuoteListParams): Promise<Quote[]>
    /** @endpoint GET /quotes/{quoteId} */
    get(quoteId: string): Promise<Quote>
    /** @endpoint POST /quotes/preflight  (kiểm tra xung đột tức thời, không lưu) */
    preflight(input: PreflightRequest): Promise<PreflightResult>
    /** @endpoint POST /quotes → 202 {quoteId}; tiến trình qua SSE GET /quotes/{id}/events */
    create(input: CreateQuoteRequest, options?: AnalysisOptions): Promise<Quote>
    /** @endpoint POST /quotes/{quoteId}/revisions → 202; SSE như create */
    revise(quoteId: string, input: CreateQuoteRequest, options?: AnalysisOptions): Promise<Quote>
    /** @endpoint POST /quotes/{quoteId}/submit */
    submit(quoteId: string): Promise<Quote>
    /** @endpoint POST /quotes/{quoteId}/decision  (MANAGER) */
    decide(quoteId: string, input: ApprovalDecisionRequest): Promise<Quote>
    /** @endpoint POST /quotes/{quoteId}/share */
    share(quoteId: string, input: ShareQuoteRequest): Promise<Quote>
    /** @endpoint GET /quotes/{quoteId}/verify */
    verify(quoteId: string): Promise<QuoteVerification>
  }

  policies: {
    /** @endpoint GET /policies */
    list(): Promise<PolicyVersion[]>
    /** @endpoint GET /policies/{policyId} */
    get(policyId: string): Promise<PolicyVersion>
    /** @endpoint POST /policies  (nhân bản thành bản nháp) */
    createDraft(input: CreatePolicyDraftRequest): Promise<PolicyVersion>
    /** @endpoint PATCH /policies/{policyId}  (chỉ DRAFT) */
    updateDraft(policyId: string, input: UpdatePolicyDraftRequest): Promise<PolicyVersion>
    /** @endpoint POST /policies/{policyId}/checks */
    runPublishChecks(policyId: string): Promise<PublishCheckReport>
    /** @endpoint POST /policies/{policyId}/publish */
    publish(policyId: string): Promise<PolicyVersion>
    /** @endpoint POST /policies/{policyId}/archive */
    archive(policyId: string): Promise<PolicyVersion>
  }

  inventory: {
    /** @endpoint PATCH /units/{unitCode}  (SALE_ADMIN) */
    updateUnit(unitCode: string, input: UpdateUnitRequest): Promise<ApartmentUnit>
  }

  qa: {
    /** @endpoint POST /qa/formula-regression */
    runFormulaRegression(): Promise<BenchmarkRunResult[]>
  }
}
