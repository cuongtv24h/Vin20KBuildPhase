import type {
  AgentStep,
  ClaimSupportStatus,
  ClaimType,
  ComplianceStatus,
  CustomerConstraints,
  CustomerSegment,
  LeadDossierStatus,
  LeadTemperature,
  MessageChannel,
  OptimizationObjective,
  PdfStatus,
  PolicyDecisionStatus,
  PolicyStatus,
  QuoteAuditEvent,
  QuoteWorkflowStatus,
  ScenarioCode,
  UserRole,
} from '@/api/contracts'

export const ROLE_LABEL: Record<UserRole, string> = {
  SALE: 'Chuyên viên kinh doanh',
  MANAGER: 'Quản lý kinh doanh',
  POLICY_ADMIN: 'Quản trị chính sách',
}

export const QUOTE_STATUS_LABEL: Record<QuoteWorkflowStatus, string> = {
  DRAFT: 'Chờ gửi duyệt',
  ANALYZING: 'Đang phân tích',
  NEEDS_INPUT: 'Thiếu thông tin',
  READY_FOR_REVIEW: 'Chờ duyệt',
  NEEDS_REVISION: 'Cần chỉnh sửa',
  APPROVED: 'Đã phê duyệt',
  REJECTED: 'Đã từ chối',
  ABSTAINED: 'Dừng an toàn',
  BLOCKED: 'Bị chặn',
  CALCULATION_FAILED: 'Lỗi tính toán',
  SUPERSEDED: 'Đã thay thế',
  CLOSED: 'Đã đóng',
  REVOKED: 'Đã thu hồi',
}

export const PDF_STATUS_LABEL: Record<PdfStatus, string> = {
  PENDING: 'Chờ xuất PDF',
  GENERATING: 'Đang xuất PDF',
  PDF_ISSUED: 'Đã phát hành PDF',
  FAILED: 'Xuất PDF lỗi',
  RETRYING: 'Đang thử lại',
  MANUAL_INTERVENTION: 'Cần xử lý thủ công',
}

export const DECISION_STATUS_LABEL: Record<PolicyDecisionStatus, string> = {
  ELIGIBLE: 'Áp dụng',
  NOT_ELIGIBLE: 'Không đủ điều kiện',
  CONFLICT: 'Xung đột',
  AMBIGUOUS: 'Chưa đủ căn cứ',
  EXPIRED: 'Hết hiệu lực',
  PENDING_APPROVAL: 'Chờ duyệt ngoại lệ',
}

export const POLICY_STATUS_LABEL: Record<PolicyStatus, string> = {
  DRAFT: 'Bản nháp',
  PUBLISHED: 'Đã ban hành',
  ARCHIVED: 'Ngừng áp dụng',
}

export const SEGMENT_LABEL: Record<CustomerSegment, string> = {
  EXISTING_RESIDENT: 'Khách hàng hiện hữu',
  NEW_CUSTOMER: 'Khách hàng mới',
}

export const OBJECTIVE_LABEL: Record<OptimizationObjective, string> = {
  MIN_NET_PRICE: 'Giá mua thấp nhất',
  MIN_INITIAL_OUTFLOW: 'Trả trước ít nhất',
  MIN_TOTAL_CASH_OUTFLOW: 'Dòng tiền đến bàn giao thấp nhất',
  MAX_BENEFIT_VALUE: 'Giá trị ưu đãi lớn nhất',
}

export const SCENARIO_LABEL: Record<ScenarioCode, string> = {
  'PA-CHUDONG': 'Tiến độ chuẩn',
  'PA-NHANH': 'Thanh toán sớm 95%',
  'PA-VAY': 'Vay ngân hàng HTLS 0%',
}

export const AGENT_STEP_LABEL: Record<AgentStep, string> = {
  POLICY_LOOKUP: 'Tra cứu chính sách theo ngày giao dịch',
  VECTOR_RETRIEVAL: 'Đối chiếu điều khoản & kiểm tra xung đột',
  DETERMINISTIC_CALCULATION: 'Tính 3 phương án thanh toán',
}

export const COMPLIANCE_LABEL: Record<ComplianceStatus, string> = {
  SUPPORTED: 'Có căn cứ',
  CONDITIONAL: 'Cần nêu điều kiện',
  UNSUPPORTED: 'Không có căn cứ',
  PROHIBITED: 'Phát ngôn bị cấm',
}

export const SUPPORT_LABEL: Record<ClaimSupportStatus, string> = {
  SUPPORTED: 'Có chứng cứ',
  PARTIALLY_SUPPORTED: 'Chỉ đúng một phần',
  UNSUPPORTED: 'Chưa có chứng cứ',
  CONTRADICTED: 'Mâu thuẫn chứng cứ',
}

export const CLAIM_TYPE_LABEL: Record<ClaimType, string> = {
  POLICY_REASON: 'Điều khoản',
  CALCULATION_RESULT: 'Số liệu tính toán',
  DERIVED_RECOMMENDATION: 'Đề xuất',
  USER_PROVIDED: 'Khách khai',
}

export const TEMPERATURE_LABEL: Record<LeadTemperature, string> = { HOT: 'Nóng', WARM: 'Ấm', COLD: 'Lạnh' }

export const DOSSIER_STATUS_LABEL: Record<LeadDossierStatus, string> = {
  NEW: 'Mới',
  ASSIGNED: 'Chờ xử lý',
  CONVERTED_TO_QUOTE: 'Đã lập báo giá',
  EXPIRED: 'Hết hạn',
}

export const CHANNEL_LABEL: Record<MessageChannel, string> = { ZALO: 'Zalo', SMS: 'SMS', EMAIL: 'Email' }

export const AUDIT_EVENT_LABEL: Record<QuoteAuditEvent['event_type'], string> = {
  QUOTE_CREATED: 'Lập hồ sơ báo giá',
  ANALYSIS_COMPLETED: 'Hoàn tất phân tích',
  ESCALATED: 'Chuyển thẩm định ngoại lệ',
  SUBMITTED: 'Gửi Quản lý duyệt',
  APPROVED: 'Phê duyệt & ký số',
  REJECTED: 'Từ chối',
  REVISION_REQUESTED: 'Yêu cầu chỉnh sửa',
  VERSION_CREATED: 'Tạo phiên bản mới',
  PDF_ISSUED: 'Phát hành PDF',
  PDF_FAILED: 'Xuất PDF lỗi',
  MESSAGE_SENT: 'Gửi tin cho khách',
  MESSAGE_BLOCKED: 'Chặn tin gửi khách',
}

export const CONSTRAINT_LABEL: Record<keyof CustomerConstraints, string> = {
  own_funds_vnd: 'Vốn tự có',
  monthly_capacity_vnd: 'Trả góp hằng tháng',
  bedrooms: 'Số phòng ngủ',
  project_id: 'Dự án',
  preferred_unit_code: 'Căn quan tâm',
  objective: 'Ưu tiên',
  customer_segment: 'Khách hàng',
}

export const PROJECT_LABEL: Record<string, string> = {
  THE_ZEN_PARK: 'The Zen Park',
  VLANDFUTURE_SAPPHIRE: 'VLandFuture Sapphire',
}

export const MISSING_FIELD_LABEL: Record<string, string> = {
  transaction_date: 'Ngày giao dịch',
}
