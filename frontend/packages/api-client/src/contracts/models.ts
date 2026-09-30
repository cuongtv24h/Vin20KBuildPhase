/**
 * DTO hợp đồng (wire format, snake_case). Nguồn từng nhóm ghi ở comment; field ngoài tài liệu
 * được đánh dấu [ĐỀ XUẤT] và liệt kê trong API_INTEGRATION.md §4.
 * Tiền: số nguyên VNĐ, hậu tố `_vnd`. Tỷ lệ: thập phân (0.085). Ngày nghiệp vụ: YYYY-MM-DD.
 * Thời điểm: ISO 8601 UTC.
 */
import type {
  ApprovalDecision,
  ClaimSupportStatus,
  ClaimType,
  ComplianceCheckMode,
  ComplianceRequiredAction,
  ComplianceStatus,
  ConflictTier,
  CustomerSegment,
  LeadDossierStatus,
  LeadTemperature,
  MessageChannel,
  OptimizationObjective,
  PdfStatus,
  PolicyDecisionStatus,
  PolicyStatus,
  PreSalesSessionStatus,
  QuoteWorkflowStatus,
  RiskFlagColor,
  RuleRelationType,
  RuleValidationStatus,
  ScenarioCode,
  UnitStatus,
  UserRole,
} from './enums'
import type { ErrorCode } from './errors'

// ─── Danh tính ─────────────────────────────────────────────────────────────

export interface ActorRef {
  user_id: string
  full_name: string
  role: UserRole
}

export interface StaffUser extends ActorRef {
  email: string
  phone: string
  title: string
}

/** [ĐỀ XUẤT] POST /auth/login. */
export interface LoginRequest {
  email: string
  password: string
}

export interface AuthSession {
  access_token: string
  expires_at: string
  user: StaffUser
}

/** TD-4.1 §3.2 — re-auth trước khi ký duyệt. Endpoint [ĐỀ XUẤT] POST /auth/reauth. */
export interface ReauthRequest {
  password: string
}

export interface ReauthGrant {
  reauth_token: string
  expires_at: string
}

// ─── Admin Control Panel (admin_cp) ──────────────────────────────────────────

export interface AdminSetupStatus {
  initialized: boolean
  total_users: number
  has_admin: boolean
  message: string
}

export interface InitAdminPayload {
  user: string
  password: string
  email: string
  phone?: string
  full_name?: string
}

export interface AdminUser {
  user: string
  password?: string
  email: string
  phone: string | null
  role: UserRole
  user_id?: string
  full_name?: string
  title?: string | null
  is_active?: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface CreateUserPayload {
  user: string
  password: string
  email: string
  phone?: string
  role: UserRole
  full_name?: string
}

export interface UpdateUserPayload {
  password?: string
  email?: string
  phone?: string
  role?: UserRole
  full_name?: string
  title?: string
  is_active?: boolean
}


// ─── Dự án & căn hộ (read-only snapshot từ CRM — AP-09) ──────────────────────

export interface Project {
  project_id: string
  name: string
  location: string
  description: string
  handover_time: string
}

export interface UnitSnapshot {
  unit_code: string
  project_id: string
  project_name: string
  block: string
  floor: number
  bedrooms: number
  area_m2: number
  view: string
  listed_price_before_tax_vnd: number
  status: UnitStatus
}

/** [ĐỀ XUẤT] GET /public/projects — trang chủ khách hàng. */
export interface ProjectOverview {
  project: Project
  active_policy: PolicySnapshotRef | null
  promotions: { title: string; section: string }[]
  available_units: number
  price_from_vnd: number | null
}

// ─── Chính sách & chứng cứ (C-02/C-03/C-04) ────────────────────────────────

/** Implement plan §10.2 + CodeBaseIndex coordinate_parser (`quote` = trích dẫn nguyên văn). */
export interface SourceCoordinate {
  document_id: string
  document_version: string
  document_hash: string
  page: number
  section: string
  clause_id: string
  quote: string
}

export interface RuleRelation {
  type: RuleRelationType
  rule_code: string
  reason: string | null
}

export interface PolicyRule {
  rule_code: string
  title: string
  kind: 'PERCENT_DISCOUNT' | 'GIFT' | 'BANK_SUPPORT' | 'DISCRETIONARY'
  discount_rate: number | null
  cash_equivalent_vnd: number | null
  interest_support_months: number | null
  applicable_scenarios: ScenarioCode[]
  required_segments: CustomerSegment[] | null
  min_units_purchased: number | null
  relations: RuleRelation[]
  is_ambiguous: boolean
  /** false = tự động áp dụng theo hồ sơ khách; true = Sale chọn đề nghị xét. */
  is_selectable: boolean
  validation_status: RuleValidationStatus
  source: SourceCoordinate
}

export interface PolicyDocument {
  policy_id: string
  policy_version: string
  title: string
  project_id: string
  status: PolicyStatus
  effective_from: string
  effective_to: string
  document_id: string
  document_hash: string
  source_document: string
  created_at: string
  created_by: ActorRef
  published_at: string | null
  published_by: ActorRef | null
  rules: PolicyRule[]
}

/** Implement plan §10.1 `policy_snapshot_ref` (+ title/effective range để hiển thị). */
export interface PolicySnapshotRef {
  policy_id: string
  policy_version: string
  snapshot_hash: string
  title: string
  effective_from: string
  effective_to: string
}

export interface ConflictFinding {
  tier: ConflictTier | null
  status: Extract<PolicyDecisionStatus, 'CONFLICT' | 'AMBIGUOUS' | 'EXPIRED'>
  rule_codes: string[]
  message: string
  source: SourceCoordinate | null
}

/** TD-4.3 N-07 ConflictReport. */
export interface ConflictReport {
  findings: ConflictFinding[]
}

/** Implement plan §10.2 — EvidenceBackedClaim. `direction` [ĐỀ XUẤT] để tách Why / Why-not. */
export interface EvidenceBackedClaim {
  claim_id: string
  claim_type: ClaimType
  direction: 'WHY' | 'WHY_NOT'
  text: string
  support_status: ClaimSupportStatus
  source_coordinates: SourceCoordinate[]
  calculation_refs: string[]
  /** Phần câu không có chứng cứ khi PARTIALLY_SUPPORTED (D1-4). */
  unsupported_fragment: string | null
  rule_code: string | null
  decision_status: PolicyDecisionStatus | null
}

/** GET /quotes/{id}/evidence. */
export interface QuoteEvidence {
  quote_id: string
  quote_version: number
  claims: EvidenceBackedClaim[]
}

// ─── Tính toán (C-06, FCS v2.6) ────────────────────────────────────────────

export interface Installment {
  seq: number
  label: string
  milestone: string
  ratio: number
  amount_vnd: number
  payer: 'CUSTOMER' | 'BANK'
}

export interface RuleEvaluation {
  rule_code: string
  title: string
  status: PolicyDecisionStatus
  /** [ĐỀ XUẤT] PRICE_REDUCTION trừ vào giá; IN_KIND quà hiện vật "không trừ vào giá" (PRD §7); FINANCING hỗ trợ vay. */
  effect: 'PRICE_REDUCTION' | 'IN_KIND' | 'FINANCING'
  amount_vnd: number
  reason: string
  source: SourceCoordinate
}

/** Implement plan D2-2 — field `_vnd` chuẩn. */
export interface Scenario {
  scenario_code: ScenarioCode
  label: string
  listed_price_before_tax_vnd: number
  total_discount_rate: number
  discount_vnd: number
  net_price_before_tax_vnd: number
  vat_vnd: number
  kpbt_vnd: number
  /** Giá bán sau ưu đãi (đã gồm VAT + KPBT) — PRD §1.3.1 "Net Selling Price". */
  total_contract_price_vnd: number
  /** Dòng tiền ban đầu khách tự chi. */
  initial_payment_vnd: number
  /** Tổng dòng tiền khách tự chi đến bàn giao (Issue A-03). */
  total_cash_outflow_vnd: number
  benefit_value_vnd: number
  installments_count: number
  payment_schedule: Installment[]
  rule_evaluations: RuleEvaluation[]
  feasible: boolean
  calculation_hash: string
}

/** Implement plan D2-3 — field-level error. */
export interface CalculationValidation {
  valid: boolean
  errors: {
    code: string
    field: string
    message: string
    expected_vnd: number | null
    actual_vnd: number | null
  }[]
}

/** Implement plan D2-4 — ranking tất định. Câu giải trình hiển thị do UI dựng từ số liệu. */
export interface Recommendation {
  objective: OptimizationObjective
  recommended_scenario: ScenarioCode
  tie_break_rule_id: string
  comparisons: { scenario_code: ScenarioCode; metric_vnd: number; delta_vnd: number }[]
}

export interface RiskFlag {
  color: RiskFlagColor
  label: string
  reasons: string[]
}

// ─── Quote (C-01) ──────────────────────────────────────────────────────────

/** Architecture C-01 (ma_can, ngay_giao_dich, muc_tieu) + PRD §8. */
export interface TransactionContext {
  unit_code: string
  /** null → backend trả NEEDS_INPUT (FC-01), không tự suy ra ngày hôm nay. */
  transaction_date: string | null
  customer_segment: CustomerSegment
  units_quantity: number
  selected_rule_codes: string[]
  objective: OptimizationObjective
  customer_name: string
  customer_phone: string
  /** [ĐỀ XUẤT] Văn bản chính sách Sale viện dẫn; null = tra cứu theo ngày giao dịch (FAIL-02). */
  requested_policy_id: string | null
}

export type QuoteCreateRequest = TransactionContext

/** TD-4.1 §3.1 — 202 Accepted. */
export interface QuoteAccepted {
  quote_id: string
  quote_version: number
  status: Extract<QuoteWorkflowStatus, 'ANALYZING'>
  stream_url: string
}

/**
 * Body thật của POST /api/v1/quotes (FastAPI `CreateQuoteRequest`, src/api/endpoints/quotes.py).
 * KHÔNG dùng chung shape với `TransactionContext` (đề xuất cũ, chưa khớp backend hiện có).
 */
export type BackendObjective = 'MIN_NET_PRICE' | 'MIN_INITIAL_CASH' | 'MIN_MONTHLY_BURDEN' | 'MIN_TOTAL_CASH_OUTFLOW' | 'MAX_BENEFIT_VALUE' | 'EARLY_HANDOVER'

export interface QuoteCreatePayload {
  project_id: string
  unit_code: string
  listed_price_before_tax_vnd: number
  deposit_amount_vnd?: number
  own_funds_vnd?: number
  monthly_capacity_vnd?: number
  objective?: BackendObjective
  tenant_id?: string
}

/** Response thật của POST/GET /api/v1/quotes (đồng bộ, 201) — không có scenarios/stream_url. */
export interface QuoteCreateResult {
  quote_id: string
  tenant_id: string
  quote_version: number
  status: string
  approval_status: string
  pdf_status: string | null
  unit_code: string
  total_contract_price_vnd: number | null
  signature: string | null
  snapshot_hash: string | null
  pdf_url: string | null
  created_by: string
  approved_by: string | null
  created_at: string | null
  updated_at: string | null
  snapshot_payload: Record<string, unknown> | null
}

/** TD-4.1 §3.1 abstention (FC-02/07/09, AC-RT-02). */
export interface Abstention {
  reason_code: ErrorCode
  message: string
}

/** TD-4.1 §5.2 SignatureEnvelope. */
export interface SignatureEnvelope {
  algorithm: 'Ed25519'
  key_id: string
  signature_encoding: 'hex'
  signature: string
}

export interface ApprovalRecord {
  decision: ApprovalDecision
  decided_by: ActorRef
  decided_at: string
  reason: string
  signature: SignatureEnvelope | null
}

export interface QuoteVersionSummary {
  quote_version: number
  status: QuoteWorkflowStatus
  created_at: string
}

export interface Quote {
  quote_id: string
  quote_version: number
  status: QuoteWorkflowStatus
  pdf_status: PdfStatus | null
  created_at: string
  updated_at: string
  created_by: ActorRef
  submitted_at: string | null
  source_dossier_id: string | null
  transaction_context: TransactionContext
  unit: UnitSnapshot
  policy_snapshot_ref: PolicySnapshotRef | null
  conflict_report: ConflictReport | null
  abstention: Abstention | null
  /** NEEDS_INPUT — tên field còn thiếu. */
  missing_fields: string[]
  scenarios: Scenario[]
  calculation_validation: CalculationValidation | null
  recommendation: Recommendation | null
  risk_flag: RiskFlag
  approval: ApprovalRecord | null
  /** SHA-256 snapshot đã ký (N-19A). */
  artifact_hash: string | null
  /** [ĐỀ XUẤT] danh sách phiên bản để xem lại bản cũ (chỉ đọc). */
  versions: QuoteVersionSummary[]
}

export interface QuoteListParams {
  status?: QuoteWorkflowStatus[]
  source_dossier_id?: string
}

/** POST /quotes/{id}/reject | /revision. */
export interface DecisionReasonRequest {
  reason: string
}

export interface ApproveRequest {
  note: string
}

/** C-07 hash chain — GET /quotes/{id}/audit. */
export interface QuoteAuditEvent {
  event_id: string
  event_type:
    | 'QUOTE_CREATED'
    | 'ANALYSIS_COMPLETED'
    | 'ESCALATED'
    | 'SUBMITTED'
    | 'APPROVED'
    | 'REJECTED'
    | 'REVISION_REQUESTED'
    | 'VERSION_CREATED'
    | 'PDF_ISSUED'
    | 'PDF_FAILED'
    | 'MESSAGE_SENT'
    | 'MESSAGE_BLOCKED'
  quote_version: number
  occurred_at: string
  actor: { user_id: string | null; full_name: string; role: UserRole | 'SYSTEM' }
  note: string | null
  prev_hash: string
  event_hash: string
}

export interface QuoteAudit {
  quote_id: string
  events: QuoteAuditEvent[]
  chain_valid: boolean
}

/** GET /quotes/{id}/pdf — 409 PDF_NOT_READY khi chưa phát hành. */
export interface QuotePdf {
  quote_id: string
  quote_version: number
  pdf_status: PdfStatus
  download_url: string
  pdf_sha256: string
  issued_at: string
}

// ─── Pre-Sales (C-09) & Lead Dossier (C-10) ────────────────────────────────

/** Implement plan §10.1 `customer_constraints` + F2. */
export interface CustomerConstraints {
  own_funds_vnd: number | null
  monthly_capacity_vnd: number | null
  bedrooms: number | null
  project_id: string | null
  preferred_unit_code: string | null
  objective: OptimizationObjective | null
  customer_segment: CustomerSegment | null
}

export interface ReferenceScenario {
  scenario_code: ScenarioCode
  label: string
  unit_code: string
  total_contract_price_vnd: number
  initial_payment_vnd: number
  total_cash_outflow_vnd: number
  benefit_value_vnd: number
  feasible: boolean
  infeasible_reason: string | null
  claims: EvidenceBackedClaim[]
}

/** INV-RT-09 — phương án tham khảo, luôn mang watermark, không phải báo giá. */
export interface ReferencePlan {
  plan_id: string
  generated_at: string
  expires_at: string
  watermark: 'PRE-SALES ESTIMATE — NOT AN OFFICIAL QUOTE'
  policy_snapshot_ref: PolicySnapshotRef | null
  objective: OptimizationObjective
  recommended_scenario: ScenarioCode | null
  scenarios: ReferenceScenario[]
  assumptions: string[]
  disclaimer: string
}

export interface ChatMessage {
  message_id: string
  role: 'CUSTOMER' | 'ASSISTANT'
  text: string
  created_at: string
  /** [ĐỀ XUẤT] gợi ý trả lời nhanh cho câu hỏi dẫn dắt (D3-1). */
  suggestions: string[]
}

export interface PreSalesSession {
  session_id: string
  /** Optional SSE URL returned by the API for this session. */
  stream_url?: string
  status: PreSalesSessionStatus
  created_at: string
  expires_at: string
  messages: ChatMessage[]
  constraints: CustomerConstraints
  missing_constraints: (keyof CustomerConstraints)[]
  constraints_confirmed_at: string | null
  plan: ReferencePlan | null
  dossier_id: string | null
}

export interface PreSalesSessionCreate {
  preferred_unit_code: string | null
}

export interface PreSalesMessageRequest {
  text: string
}

export interface ConfirmConstraintsRequest {
  constraints: CustomerConstraints
}

/** F6/F7 — handoff cần consent rõ ràng. */
export interface HandoffRequest {
  full_name: string
  phone: string
  consent: true
  consent_text_version: string
}

export interface HandoffReceipt {
  dossier_id: string
  handed_off_at: string
}

export interface LeadCreatePayload {
  customer_name: string
  customer_phone: string
  customer_segment?: CustomerSegment
  project_id?: string
  preferred_unit_code?: string | null
  bedrooms?: number | null
  own_funds_vnd?: number | null
  monthly_capacity_vnd?: number | null
  objective?: OptimizationObjective | null
  temperature?: LeadTemperature
  needs_summary?: string
}

export interface LeadDossier {
  dossier_id: string
  status: LeadDossierStatus
  temperature: LeadTemperature
  created_at: string
  sla_due_at: string
  assigned_sale: ActorRef | null
  source_session_id: string
  customer: { full_name: string; phone: string }
  consent: { granted_at: string; consent_text_version: string }
  needs_summary: string
  constraints: CustomerConstraints
  reference_plan: ReferencePlan | null
  converted_quote_id: string | null
}

// ─── Compliance (C-11 / F8) ────────────────────────────────────────────────

export interface ComplianceCheckRequest {
  message_text: string
  mode: ComplianceCheckMode
  quote_id: string
  quote_version: number
}

export interface ComplianceClaim {
  claim_id: string
  text: string
  span_start: number
  span_end: number
  status: ComplianceStatus
  reason: string
  source_coordinates: SourceCoordinate[]
  suggested_rewrite: string | null
}

/** Implement plan §10.4. */
export interface ComplianceCheckResponse {
  check_id: string
  message_hash: string
  mode: ComplianceCheckMode
  overall_status: ComplianceStatus
  quote_id: string
  quote_version: number
  policy_version_refs: string[]
  claims: ComplianceClaim[]
  required_action: ComplianceRequiredAction
}

/** CodeBaseIndex `SendMessageCommand` — POST /messages/send (cổng phát hành duy nhất). */
export interface SendMessageCommand {
  message_text: string
  message_hash: string
  check_id: string
  quote_id: string
  quote_version: number
  channel: MessageChannel
}

export interface MessageSendResult {
  message_id: string
  status: 'SENT' | 'BLOCKED'
  sent_at: string | null
  verdict: ComplianceCheckResponse
}

/** [ĐỀ XUẤT] POST /compliance/draft-message — tin do Agent soạn (vẫn phải qua check). */
export interface DraftMessageRequest {
  quote_id: string
  quote_version: number
}

export interface DraftMessage {
  message_text: string
}

// ─── Policy Admin (C-03 / F9) ──────────────────────────────────────────────

/** Trường multipart của POST /policies/extract-rules (kèm `file`). */
export interface ExtractRulesFields {
  project_id: string
  title: string
  policy_version: string
  effective_from: string
  effective_to: string
}

export interface RulesTestCheck {
  code: string
  label: string
  status: 'PASS' | 'WARN' | 'FAIL'
  detail: string
}

/** POST /policies/{id}/rules/test — pre-publish gate. */
export interface RulesTestReport {
  policy_id: string
  checked_at: string
  checks: RulesTestCheck[]
  conflict_findings: ConflictFinding[]
  regression: { passed: number; total: number }
  can_publish: boolean
}

// ─── Evaluation ────────────────────────────────────────────────────────────

export interface BenchmarkAmounts {
  discount_vnd: number
  net_price_before_tax_vnd: number
  vat_vnd: number
  kpbt_vnd: number
  total_contract_price_vnd: number
}

export interface BenchmarkCaseResult {
  case_id: string
  name: string
  listed_price_before_tax_vnd: number
  discount_rates: number[]
  expected: BenchmarkAmounts
  actual: BenchmarkAmounts
  delta_vnd: number
  passed: boolean
}

/** POST /evaluation/benchmark-runs. */
export interface BenchmarkRun {
  run_id: string
  started_at: string
  finished_at: string
  total: number
  passed: number
  exact_match_rate: number
  cases: BenchmarkCaseResult[]
}
