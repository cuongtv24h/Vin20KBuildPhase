/**
 * Enum hợp đồng — dẫn xuất từ tài liệu thiết kế vì `src/contracts/enums.py` chưa có trong repo.
 * Mỗi enum ghi nguồn; giá trị đánh dấu [ĐỀ XUẤT] nằm trong API_INTEGRATION.md §4 chờ TechLead chốt.
 * Tên & giá trị giữ nguyên dạng wire (snake_case field, UPPER_CASE value) để khi có OpenAPI
 * thật chỉ cần thay file này bằng file sinh tự động.
 */

/** TD-4.1 §6 + PRD §11.1; SUPERSEDED theo N-17 (CodeBaseIndex). Tách biệt PdfStatus / ApprovalDecision. */
export const QUOTE_WORKFLOW_STATUSES = [
  'DRAFT',
  'ANALYZING',
  'NEEDS_INPUT',
  'READY_FOR_REVIEW',
  'NEEDS_REVISION',
  'APPROVED',
  'REJECTED',
  'ABSTAINED',
  'BLOCKED',
  'CALCULATION_FAILED',
  'SUPERSEDED',
  'CLOSED',
  'REVOKED',
] as const
export type QuoteWorkflowStatus = (typeof QUOTE_WORKFLOW_STATUSES)[number]

/** TD-4.1 §6 — PDF ASYNC STATUS. `null` khi quote chưa được duyệt. */
export type PdfStatus = 'PENDING' | 'GENERATING' | 'PDF_ISSUED' | 'FAILED' | 'RETRYING' | 'MANUAL_INTERVENTION'

/** TD-4.3 ApprovalStatus (tên giá trị [ĐỀ XUẤT]). */
export type ApprovalDecision = 'APPROVED' | 'REJECTED' | 'REVISION_REQUESTED'

/** PRD §6 — 6 trạng thái quyết định điều khoản. */
export const POLICY_DECISION_STATUSES = [
  'ELIGIBLE',
  'NOT_ELIGIBLE',
  'CONFLICT',
  'AMBIGUOUS',
  'EXPIRED',
  'PENDING_APPROVAL',
] as const
export type PolicyDecisionStatus = (typeof POLICY_DECISION_STATUSES)[number]

/**
 * PRD §1.3.2 — 4 tiêu chí. CodeBaseIndex nói TD-4.3 có 6 objectives nhưng tên 2 giá trị còn lại
 * không có trong tài liệu nào của repo → [CẦN TECHLEAD] (API_INTEGRATION.md §4).
 */
export const OPTIMIZATION_OBJECTIVES = [
  'MIN_NET_PRICE',
  'MIN_INITIAL_OUTFLOW',
  'MIN_TOTAL_CASH_OUTFLOW',
  'MAX_BENEFIT_VALUE',
] as const
export type OptimizationObjective = (typeof OPTIMIZATION_OBJECTIVES)[number]

/** PRD §8 (customer_segment). */
export type CustomerSegment = 'EXISTING_RESIDENT' | 'NEW_CUSTOMER'

/** CodeBaseIndex `contracts/pricing.py` — ScenarioCode (FCS v2.6). */
export const SCENARIO_CODES = ['PA-CHUDONG', 'PA-NHANH', 'PA-VAY'] as const
export type ScenarioCode = (typeof SCENARIO_CODES)[number]

/** PRD §1.3.4 — 3 cấp xung đột. */
export type ConflictTier = 1 | 2 | 3

export type RiskFlagColor = 'RED' | 'YELLOW' | 'GREEN'

/** PRD §2 — 3 persona nội bộ. Khách hàng pre-sale không đăng nhập. */
export type UserRole = 'SALE' | 'MANAGER' | 'POLICY_ADMIN'

export type PolicyStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'

/** Implement plan D1-3 — rule chỉ dùng cho Official Quote khi APPROVED_FOR_USE. */
export type RuleValidationStatus = 'VALIDATION_REQUIRED' | 'APPROVED_FOR_USE'

/** Implement plan D1-3 (STACKABLE/MUTUALLY_EXCLUSIVE/REPLACES) + CONDITIONAL_CONFLICT [ĐỀ XUẤT] cho xung đột cấp 2. */
export type RuleRelationType = 'MUTUALLY_EXCLUSIVE' | 'CONDITIONAL_CONFLICT' | 'REPLACES' | 'STACKABLE'

/** Implement plan D1-5 — 4 mức tuân thủ F8. */
export const COMPLIANCE_STATUSES = ['SUPPORTED', 'CONDITIONAL', 'UNSUPPORTED', 'PROHIBITED'] as const
export type ComplianceStatus = (typeof COMPLIANCE_STATUSES)[number]

/** Implement plan D1-5 — 3 checkpoint. */
export type ComplianceCheckMode = 'ON_DRAFT' | 'DEBOUNCE' | 'FINAL_SEND'

/** Implement plan §10.4. Giá trị ngoài KEEP_REQUIRED_CONDITION là [ĐỀ XUẤT]. */
export type ComplianceRequiredAction = 'NONE' | 'KEEP_REQUIRED_CONDITION' | 'REWRITE_UNSUPPORTED' | 'REMOVE_PROHIBITED'

/** Implement plan D1-4 — archetype claim F4. */
export type ClaimType = 'POLICY_REASON' | 'CALCULATION_RESULT' | 'DERIVED_RECOMMENDATION' | 'USER_PROVIDED'

/** Implement plan D1-4 / TD-4.1 INV-RT-10. */
export type ClaimSupportStatus = 'SUPPORTED' | 'PARTIALLY_SUPPORTED' | 'UNSUPPORTED' | 'CONTRADICTED'

/** CodeBaseIndex C-10: NEW → … → CONVERTED_TO_QUOTE (giá trị giữa là [ĐỀ XUẤT]). */
export type LeadDossierStatus = 'NEW' | 'ASSIGNED' | 'CONVERTED_TO_QUOTE' | 'EXPIRED'

/** Architecture design, tool `create_lead_dossier`. */
export type LeadTemperature = 'HOT' | 'WARM' | 'COLD'

/** TD-4.3 PreSalesSessionStatus (giá trị [ĐỀ XUẤT]). */
export type PreSalesSessionStatus = 'COLLECTING' | 'AWAITING_CONFIRMATION' | 'PLAN_READY' | 'HANDED_OFF' | 'EXPIRED'

/** Các node Agent phát qua SSE `step_update` — TD-4.1 §3.1. */
export const AGENT_STEPS = ['POLICY_LOOKUP', 'VECTOR_RETRIEVAL', 'DETERMINISTIC_CALCULATION'] as const
export type AgentStep = (typeof AGENT_STEPS)[number]

export type MessageChannel = 'ZALO' | 'SMS' | 'EMAIL'

export type UnitStatus = 'AVAILABLE' | 'RESERVED' | 'SOLD'
