import { API_BASE_URL, REQUEST_TIMEOUT_MS } from './config'
import type { ErrorCode } from './contracts'
import { ApiError, fallbackMessage } from './errors'

/**
 * fetch wrapper dùng chung cho cả mock (MSW chặn ở tầng mạng) lẫn backend thật.
 * Header chuẩn:
 *   Authorization: Bearer <token>         — mọi route nội bộ
 *   Idempotency-Key: <uuid>               — MỌI POST (TD-4.1 INV-RT-07); tự sinh nếu caller không truyền
 *   If-Match: "v<quote_version>"          — lệnh đổi trạng thái quote (OCC, INV-RT-06)
 *   X-Correlation-ID: <uuid>              — truy vết (TL-3)
 */

let tokenProvider: () => string | null = () => null
let sessionInfoProvider: () => { userId?: string; role?: string } | null = () => null

export function setAuthTokenProvider(provider: () => string | null) {
  tokenProvider = provider
}

export function setSessionInfoProvider(provider: () => { userId?: string; role?: string } | null) {
  sessionInfoProvider = provider
}

export function getAuthToken(): string | null {
  return tokenProvider()
}

export function newRequestId(): string {
  return crypto.randomUUID()
}

export interface HttpRequest {
  method: string
  path: string
  query?: Record<string, string | number | boolean | undefined | null>
  json?: unknown
  form?: FormData
  idempotencyKey?: string
  ifMatchVersion?: number
  headers?: Record<string, string>
  signal?: AbortSignal
  timeoutMs?: number
}

export function toUrl(path: string, query?: HttpRequest['query']): string {
  const url = path.startsWith('http') || path.startsWith(API_BASE_URL) ? path : `${API_BASE_URL}${path}`
  if (!query) return url
  const search = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== '') search.set(k, String(v))
  const qs = search.toString()
  return qs ? `${url}?${qs}` : url
}

export function buildHeaders(req: Pick<HttpRequest, 'method' | 'idempotencyKey' | 'ifMatchVersion' | 'headers' | 'json'>) {
  const headers: Record<string, string> = { Accept: 'application/json', 'X-Correlation-ID': newRequestId(), ...req.headers }
  if (req.json !== undefined) headers['Content-Type'] = 'application/json'
  const token = tokenProvider()
  if (token) headers.Authorization = `Bearer ${token}`
  const info = sessionInfoProvider()
  if (info?.userId) headers['X-User-Id'] = info.userId
  if (info?.role) headers['X-User-Role'] = info.role
  if (req.method === 'POST') headers['Idempotency-Key'] = req.idempotencyKey ?? newRequestId()
  if (req.ifMatchVersion !== undefined) headers['If-Match'] = `"v${req.ifMatchVersion}"`
  return headers
}

/** Gộp signal ngoài + timeout. */
export function withTimeout(timeoutMs: number, external?: AbortSignal) {
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const onAbort = () => controller.abort()
  external?.addEventListener('abort', onAbort)
  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    dispose: () => {
      clearTimeout(timer)
      external?.removeEventListener('abort', onAbort)
    },
  }
}

export async function parseError(res: Response): Promise<ApiError> {
  let code: ErrorCode = res.status === 401 ? 'UNAUTHORIZED' : res.status === 403 ? 'FORBIDDEN' : res.status === 404 ? 'NOT_FOUND' : res.status >= 500 ? 'INTERNAL_ERROR' : 'HTTP_ERROR'
  let message = ''
  let details: Record<string, unknown> | undefined
  try {
    const body = (await res.json()) as {
      code?: ErrorCode
      message?: string
      details?: Record<string, unknown>
      error?: { code?: ErrorCode; message?: string; details?: Record<string, unknown> }
      detail?: string | { code?: ErrorCode; message?: string }
    }
    const inner = body.error ?? (typeof body.detail === 'object' ? body.detail : undefined) ?? body
    code = inner.code ?? code
    message = inner.message ?? (typeof body.detail === 'string' ? body.detail : '')
    // Envelope của backend đặt payload lỗi ngay trong `detail` (ví dụ checklist của QUOTE_NOT_READY)
    // — giữ lại nguyên cụm để UI hiển thị đúng việc cần làm thay vì chỉ một dòng message.
    details = body.error?.details ?? body.details ?? (typeof body.detail === 'object' ? body.detail : undefined)
  } catch {
    // body không phải JSON
  }
  return new ApiError(res.status, code, message || fallbackMessage(code), details)
}

export async function http<T>(req: HttpRequest): Promise<T> {
  const timeout = withTimeout(req.timeoutMs ?? REQUEST_TIMEOUT_MS, req.signal)
  let res: Response
  try {
    res = await fetch(toUrl(req.path, req.query), {
      method: req.method,
      headers: buildHeaders(req),
      body: req.form ?? (req.json !== undefined ? JSON.stringify(req.json) : undefined),
      signal: timeout.signal,
    })
  } catch (e) {
    if (timeout.timedOut()) throw new ApiError(0, 'TIMEOUT', fallbackMessage('TIMEOUT'))
    if (req.signal?.aborted) throw e
    throw new ApiError(0, 'NETWORK_ERROR', fallbackMessage('NETWORK_ERROR'))
  } finally {
    timeout.dispose()
  }
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
