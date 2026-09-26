/** Lỗi chuẩn hoá trả về từ mọi ApiClient. Backend nên trả body `{ code, message }`. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Đã có lỗi xảy ra. Vui lòng thử lại.'
}
