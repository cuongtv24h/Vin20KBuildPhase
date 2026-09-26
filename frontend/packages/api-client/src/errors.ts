import type { ErrorCode } from './contracts'

/** Lỗi chuẩn hoá từ mọi response ≠ 2xx, timeout và lỗi mạng. */
export class ApiError extends Error {
  readonly status: number
  readonly code: ErrorCode
  readonly details?: Record<string, unknown>

  constructor(status: number, code: ErrorCode, message: string, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

const FALLBACK_MESSAGE: Partial<Record<ErrorCode, string>> = {
  TIMEOUT: 'Máy chủ phản hồi quá 10 giây. Thao tác đã được dừng an toàn, vui lòng thử lại.',
  NETWORK_ERROR: 'Không kết nối được máy chủ. Kiểm tra mạng và thử lại.',
  INTERNAL_ERROR: 'Máy chủ gặp sự cố. Vui lòng thử lại sau ít phút.',
  UNAUTHORIZED: 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
  FORBIDDEN: 'Tài khoản không có quyền thực hiện thao tác này.',
  SOD_VIOLATION: 'Người lập hồ sơ không được tự phê duyệt hồ sơ của mình.',
  STALE_QUOTE_VERSION: 'Hồ sơ vừa được cập nhật sang phiên bản mới. Dữ liệu đã được tải lại.',
  IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH: 'Yêu cầu trùng mã với một thao tác khác. Vui lòng thử lại.',
  IDEMPOTENCY_PROCESSING: 'Thao tác trước đó vẫn đang được xử lý.',
  PDF_NOT_READY: 'Bản PDF chưa được phát hành.',
  COMPLIANCE_BLOCKED: 'Tin nhắn chứa phát ngôn bị cấm và đã bị chặn.',
  REAUTH_REQUIRED: 'Cần xác thực lại trước khi ký duyệt.',
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message || FALLBACK_MESSAGE[error.code] || 'Đã có lỗi xảy ra.'
  if (error instanceof Error) return error.message
  return 'Đã có lỗi xảy ra. Vui lòng thử lại.'
}

export function isApiError(error: unknown, ...codes: ErrorCode[]): error is ApiError {
  return error instanceof ApiError && (codes.length === 0 || codes.includes(error.code))
}

/** 409 STALE_QUOTE_VERSION (TD-4.1 INV-RT-06) hoặc 412 Precondition Failed (If-Match). */
export function isStaleVersion(error: unknown): boolean {
  return error instanceof ApiError && (error.code === 'STALE_QUOTE_VERSION' || error.status === 412)
}

export function fallbackMessage(code: ErrorCode): string {
  return FALLBACK_MESSAGE[code] ?? 'Đã có lỗi xảy ra.'
}
