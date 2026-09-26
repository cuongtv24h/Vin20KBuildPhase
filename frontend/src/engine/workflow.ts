import type { UserRole, WorkflowStatus } from '@/types/domain'

/**
 * Máy trạng thái hồ sơ báo giá — nguồn sự thật duy nhất cho việc bật/tắt hành động trên UI.
 * Backend phải áp cùng bảng chuyển trạng thái này (trả 409 nếu không hợp lệ).
 *
 *   (create/revise) ─▶ DRAFT | ABSTAINED | CALCULATION_FAILED
 *   DRAFT ── submit ──▶ READY_FOR_REVIEW
 *   READY_FOR_REVIEW ── decide ──▶ APPROVED | REJECTED | NEEDS_REVISION
 *   ABSTAINED (tự động vào hàng đợi ngoại lệ) ── decide ──▶ REJECTED | NEEDS_REVISION
 *   DRAFT | ABSTAINED | CALCULATION_FAILED | NEEDS_REVISION ── revise ──▶ (phân tích lại, version + 1)
 *   APPROVED ── share ──▶ APPROVED (+ distribution)
 */
export type QuoteAction = 'SUBMIT' | 'REVISE' | 'APPROVE' | 'REJECT' | 'REQUEST_REVISION' | 'SHARE'

const ALLOWED: Record<QuoteAction, { from: WorkflowStatus[]; roles: UserRole[] }> = {
  SUBMIT: { from: ['DRAFT'], roles: ['SALE'] },
  REVISE: { from: ['DRAFT', 'ABSTAINED', 'CALCULATION_FAILED', 'NEEDS_REVISION'], roles: ['SALE'] },
  APPROVE: { from: ['READY_FOR_REVIEW'], roles: ['MANAGER'] },
  REJECT: { from: ['READY_FOR_REVIEW', 'ABSTAINED'], roles: ['MANAGER'] },
  REQUEST_REVISION: { from: ['READY_FOR_REVIEW', 'ABSTAINED'], roles: ['MANAGER'] },
  SHARE: { from: ['APPROVED'], roles: ['SALE'] },
}

export function canPerform(action: QuoteAction, status: WorkflowStatus, role: UserRole): boolean {
  const rule = ALLOWED[action]
  return rule.from.includes(status) && rule.roles.includes(role)
}

/** Trạng thái đang chờ Quản lý xử lý. */
export const MANAGER_QUEUE_STATUSES: WorkflowStatus[] = ['READY_FOR_REVIEW', 'ABSTAINED']

/** Trạng thái Sale cần hành động tiếp. */
export const SALE_ACTION_STATUSES: WorkflowStatus[] = ['DRAFT', 'NEEDS_REVISION', 'CALCULATION_FAILED']
