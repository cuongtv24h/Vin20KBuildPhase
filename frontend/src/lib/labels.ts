import type { AnalysisStage } from '@/api/contracts'
import type {
  CustomerSegment,
  LeadStatus,
  OptimizationObjective,
  PolicyStatus,
  QuoteEventType,
  ShareChannel,
  UnitStatus,
  UserRole,
  WorkflowStatus,
} from '@/types/domain'

export const ROLE_LABEL: Record<UserRole, string> = {
  SALE: 'Chuyên viên kinh doanh',
  MANAGER: 'Quản lý kinh doanh',
  SALE_ADMIN: 'Admin Sale',
}

export const WORKFLOW_STATUS_LABEL: Record<WorkflowStatus, string> = {
  DRAFT: 'Bản nháp',
  READY_FOR_REVIEW: 'Chờ duyệt',
  ABSTAINED: 'Thẩm định ngoại lệ',
  APPROVED: 'Đã phê duyệt',
  REJECTED: 'Đã từ chối',
  NEEDS_REVISION: 'Cần chỉnh sửa',
  CALCULATION_FAILED: 'Lỗi tính toán',
}

export const LEAD_STATUS_LABEL: Record<LeadStatus, string> = {
  NEW: 'Mới',
  IN_PROGRESS: 'Đang tư vấn',
  QUOTE_SENT: 'Đã gửi báo giá',
  CUSTOMER_ACCEPTED: 'Khách đồng ý',
  CLOSED: 'Đã đóng',
}

export const POLICY_STATUS_LABEL: Record<PolicyStatus, string> = {
  DRAFT: 'Bản nháp',
  PUBLISHED: 'Đã ban hành',
  ARCHIVED: 'Ngừng áp dụng',
}

export const UNIT_STATUS_LABEL: Record<UnitStatus, string> = {
  AVAILABLE: 'Đang mở bán',
  RESERVED: 'Đã giữ chỗ',
  SOLD: 'Đã bán',
}

export const SEGMENT_LABEL: Record<CustomerSegment, string> = {
  EXISTING_RESIDENT: 'Khách hàng hiện hữu',
  NEW_CUSTOMER: 'Khách hàng mới',
}

export const OBJECTIVE_OPTIONS: { value: OptimizationObjective; label: string; hint: string }[] = [
  { value: 'MIN_NET_PRICE', label: 'Giá mua thấp nhất', hint: 'Ưu tiên tổng giá trị căn hộ sau ưu đãi thấp nhất.' },
  { value: 'MIN_INITIAL_OUTFLOW', label: 'Trả trước ít nhất', hint: 'Ưu tiên số tiền thanh toán đợt đầu thấp nhất.' },
  { value: 'MIN_TOTAL_CASH_OUTFLOW', label: 'Dòng tiền đến bàn giao thấp nhất', hint: 'Ưu tiên tiền mặt phải chi đến khi nhận nhà.' },
  { value: 'MAX_BENEFIT_VALUE', label: 'Nhiều quà tặng nhất', hint: 'Ưu tiên tổng giá trị quà tặng, voucher quy đổi.' },
]

export const OBJECTIVE_SHORT_LABEL: Record<OptimizationObjective, string> = Object.fromEntries(
  OBJECTIVE_OPTIONS.map((o) => [o.value, o.label]),
) as Record<OptimizationObjective, string>

export const CHANNEL_LABEL: Record<ShareChannel, string> = {
  ZALO: 'Zalo',
  SMS: 'SMS',
  EMAIL: 'Email',
}

export const QUOTE_EVENT_LABEL: Record<QuoteEventType, string> = {
  CREATED: 'Lập hồ sơ báo giá',
  REVISED: 'Phân tích lại phiên bản mới',
  SUBMITTED: 'Gửi Quản lý duyệt',
  ESCALATED: 'Chuyển thẩm định ngoại lệ',
  APPROVED: 'Phê duyệt & ký số',
  REJECTED: 'Từ chối',
  REVISION_REQUESTED: 'Yêu cầu chỉnh sửa',
  SHARED: 'Gửi báo giá cho khách',
  CUSTOMER_VIEWED: 'Khách mở xem báo giá',
  CUSTOMER_RESPONDED: 'Khách phản hồi',
}

export const ANALYSIS_STAGE_LABEL: Record<AnalysisStage, string> = {
  POLICY_LOOKUP: 'Tra cứu chính sách theo ngày giao dịch',
  PREFLIGHT: 'Kiểm tra điều kiện & xung đột ưu đãi',
  PRICING: 'Tính giá 3 phương án thanh toán',
  RANKING: 'Xếp hạng theo mục tiêu của khách',
}
