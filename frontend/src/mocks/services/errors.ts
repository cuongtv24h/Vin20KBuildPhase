import type { ErrorCode } from '@/api/contracts'

/** Lỗi nghiệp vụ phía server giả lập → HTTP `{ code, message }`. */
export class MockError extends Error {
  readonly status: number
  readonly code: ErrorCode
  readonly headers?: Record<string, string>

  constructor(status: number, code: ErrorCode, message: string, headers?: Record<string, string>) {
    super(message)
    this.status = status
    this.code = code
    this.headers = headers
  }
}

export const notFound = (what: string) => new MockError(404, 'NOT_FOUND', `Không tìm thấy ${what}.`)
export const invalid = (message: string) => new MockError(422, 'INPUT_VALIDATION_ERROR', message)
export const transition = (message: string) => new MockError(409, 'INVALID_STATE_TRANSITION', message)
