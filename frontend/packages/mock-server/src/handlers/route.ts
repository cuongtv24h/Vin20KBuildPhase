import { delay, http, HttpResponse, type HttpHandler } from 'msw'
import type { StaffUser } from '@pricepolicy/api-client/contracts'
import { ENDPOINTS, type EndpointName } from '@pricepolicy/api-client/endpoints'
import { commit, getDb, type MockDb } from '../db'
import { sha256Hex } from '../engine/hash'
import { staffById } from '../fixtures/users'
import { getFlags, networkDelay } from '../flags'
import { MockError } from '../services/errors'
import { settlePreSales } from '../services/presales'
import { settle } from '../services/quotes'

/**
 * Tiền tố route cố định của chính mock-server — KHÔNG suy ra từ `api-client/config`'s
 * `API_BASE_URL` (giá trị đó chỉ tồn tại phía trình duyệt qua `import.meta.env`, không có trong
 * tiến trình Node của server.ts). Mọi path trong `ENDPOINTS` đã tương đối (không có `/api/v1`) —
 * `/api/v1` là quy ước cố định của server này, độc lập với client cấu hình gì cho base URL.
 * Wildcard `*` khớp mọi origin: '/api/v1' + '/quotes/{quote_id}' → '*\/api/v1/quotes/:quote_id'.
 */
export const API_PATH_PREFIX = '*/api/v1'
export const toMswPath = (path: string) => API_PATH_PREFIX + path.replace(/\{(\w+)\}/g, ':$1')

export interface Ctx {
  request: Request
  params: Record<string, string>
  query: URLSearchParams
  db: MockDb
  now: number
  user: StaffUser | null
  /** Người dùng đã xác thực — ném 401 nếu route public mà vẫn cần. */
  staff: () => StaffUser
  json: <T>() => Promise<T>
}

export interface Result {
  status?: number
  body?: unknown
  headers?: Record<string, string>
}

export const errorResponse = (e: MockError) =>
  HttpResponse.json({ code: e.code, message: e.message }, { status: e.status, headers: e.headers })

export function authenticate(request: Request, db: MockDb, now: number): StaffUser | null {
  const token = /^Bearer (.+)$/.exec(request.headers.get('Authorization') ?? '')?.[1]
  const session = token ? db.auth[token] : undefined
  if (!session || session.expires_at < now) return null
  return staffById(session.user_id) ?? null
}

interface RouteOptions {
  /** Độ trễ cố định (ms) thay cho độ trễ ngẫu nhiên — POST /quotes trả 202 ~150ms theo TD-4.1. */
  fixedDelayMs?: number
}

/**
 * Handler MSW cho một endpoint trong danh bạ: độ trễ + lỗi 500 giả lập, settle trạng thái theo
 * thời gian, xác thực/phân quyền theo `auth` của endpoint, Idempotency-Key cho mọi POST.
 */
export function route(name: EndpointName, handler: (ctx: Ctx) => Promise<Result> | Result, options: RouteOptions = {}): HttpHandler {
  const def = ENDPOINTS[name]
  const method = def.method.toLowerCase() as 'get' | 'post' | 'patch' | 'put' | 'delete'
  return http[method](toMswPath(def.path), async ({ request, params }) => {
    const flags = getFlags()
    const wait = options.fixedDelayMs !== undefined && flags.latency === 'normal' ? options.fixedDelayMs * Math.min(1, flags.time_scale) : networkDelay()
    if (wait > 0) await delay(wait)
    if (flags.fail_rate > 0 && Math.random() < flags.fail_rate) {
      return HttpResponse.json({ code: 'INTERNAL_ERROR', message: 'Máy chủ gặp sự cố (giả lập).' }, { status: 500 })
    }

    const db = await getDb()
    const now = Date.now()
    await settle(db, now)
    await settlePreSales(db, now)
    const user = authenticate(request, db, now)
    try {
      if (def.auth !== 'public') {
        if (!user) throw new MockError(401, 'UNAUTHORIZED', 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
        if (Array.isArray(def.auth) && !def.auth.includes(user.role)) throw new MockError(403, 'FORBIDDEN', 'Tài khoản không có quyền thực hiện thao tác này.')
      }

      let raw: string | null = null
      const readBody = async () => (raw ??= await request.clone().text())
      let idemKey: string | null = null
      let fingerprint = ''
      if (def.method === 'POST') {
        idemKey = request.headers.get('Idempotency-Key')
        if (!idemKey) throw new MockError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Thiếu header Idempotency-Key.')
        const contentType = request.headers.get('Content-Type') ?? ''
        const bodyPart = contentType.startsWith('multipart/') ? `multipart:${request.headers.get('Content-Length') ?? ''}` : await readBody()
        // TD-4.1 INV-RT-07: fingerprint = SHA256(method:endpoint:actor:payload)
        fingerprint = await sha256Hex(`POST:${new URL(request.url).pathname}:${user?.user_id ?? 'public'}:${request.headers.get('If-Match') ?? ''}:${bodyPart}`)
        const stored = db.idempotency[idemKey]
        if (stored) {
          if (stored.fingerprint !== fingerprint) {
            throw new MockError(409, 'IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH', 'Idempotency-Key đã dùng cho một yêu cầu khác.')
          }
          return HttpResponse.json(stored.body as Record<string, unknown>, { status: stored.status, headers: { 'Idempotent-Replayed': 'true' } })
        }
      }

      const ctx: Ctx = {
        request,
        params: params as Record<string, string>,
        query: new URL(request.url).searchParams,
        db,
        now,
        user,
        staff: () => {
          if (!user) throw new MockError(401, 'UNAUTHORIZED', 'Cần đăng nhập.')
          return user
        },
        json: async <T,>() => {
          try {
            return JSON.parse((await readBody()) || 'null') as T
          } catch {
            throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Body không phải JSON hợp lệ.')
          }
        },
      }
      const result = await handler(ctx)
      const status = result.status ?? 200
      if (idemKey) db.idempotency[idemKey] = { fingerprint, status, body: result.body ?? null }
      commit()
      return status === 204 ? new HttpResponse(null, { status }) : HttpResponse.json(result.body as Record<string, unknown>, { status, headers: result.headers })
    } catch (e) {
      commit()
      if (e instanceof MockError) return errorResponse(e)
      console.error('[mock]', e)
      return HttpResponse.json({ code: 'INTERNAL_ERROR', message: 'Lỗi không xác định ở backend giả lập.' }, { status: 500 })
    }
  })
}
