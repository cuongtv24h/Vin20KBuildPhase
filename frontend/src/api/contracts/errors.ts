/**
 * Mã lỗi chuẩn. Nhóm 1 lấy nguyên từ Error Catalog TL-0.3 (Implement plan §5.1);
 * nhóm 2 từ TD-4.1 (INV-RT-06/07, §3.1, §5.1); nhóm 3 là mã hạ tầng phía client / [ĐỀ XUẤT].
 */
export type ErrorCode =
  // TL-0.3
  | 'INPUT_VALIDATION_ERROR'
  | 'MISSING_TRANSACTION_DATE'
  | 'POLICY_NOT_FOUND'
  | 'POLICY_EXPIRED'
  | 'POLICY_CONFLICT_UNRESOLVED'
  | 'FINANCIAL_SANITY_FAILED'
  | 'STALE_QUOTE_VERSION'
  | 'INVALID_STATE_TRANSITION'
  | 'IDEMPOTENCY_PROCESSING'
  | 'IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH'
  | 'EXPLANATION_VALIDATION_FAILED'
  | 'COMPLIANCE_BLOCKED'
  | 'PDF_NOT_READY'
  // TD-4.1
  | 'SOD_VIOLATION'
  | 'LLM_GATEWAY_TIMEOUT'
  | 'RESYNC_FULL_STATE'
  | 'TRANSACTION_FAILED_RETRYABLE'
  // Hạ tầng / [ĐỀ XUẤT]
  | 'POLICY_AMBIGUOUS'
  | 'IDEMPOTENCY_KEY_REQUIRED'
  | 'REAUTH_REQUIRED'
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'INTERNAL_ERROR'
  | 'TIMEOUT'
  | 'NETWORK_ERROR'
  | 'HTTP_ERROR'

/** Body lỗi mà client chấp nhận. Hỗ trợ cả `{ code, message }`, `{ error: {...} }` và FastAPI `{ detail }`. */
export interface ErrorEnvelope {
  code: ErrorCode
  message: string
  details?: Record<string, unknown>
}
