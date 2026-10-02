import { getResponse } from 'msw'
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http'
import { getDb } from './db'
import { handlers } from './handlers'

/**
 * Backend giả lập chạy như một tiến trình Node thật (không phải MSW trong trình duyệt), lắng
 * nghe một cổng TCP thật. Lý do: hai UI (Khách hàng, Nội bộ) là hai app/origin tách biệt —
 * mục 0 của brief yêu cầu chúng "không có link hay menu chuyển giữa 2 UI; chỉ trao đổi qua API"
 * và "state phải liên thông: khách handoff xong thì dossier hiện ngay trong inbox Sale". MSW chạy
 * trong từng tab sẽ có state tách biệt theo origin; một server thật dùng chung một MockDb thì
 * không thể tách rời được.
 *
 * Toàn bộ logic nghiệp vụ (route resolver, db, engine, services, handler MSW) giữ nguyên không đổi
 * so với bản chạy trong trình duyệt trước đây — file này chỉ là cầu nối IncomingMessage/
 * ServerResponse ⇄ Request/Response (Web Fetch API, có sẵn trong Node) rồi giao cho `msw`'s
 * `getResponse()` chạy đúng handler đã đăng ký, kể cả SSE streaming (ReadableStream) và abort khi
 * client ngắt kết nối giữa chừng.
 */

const PORT = Number(process.env.PORT ?? 8787)
const HOST_FALLBACK = `localhost:${PORT}`

/** TL-3: CORS cho 2 origin riêng biệt (Khách hàng :5173, Nội bộ :5174). Backend thật phải cấu hình
 * tương đương — xem API_INTEGRATION.md §"Hai UI riêng biệt". */
const ALLOWED_ORIGINS = (process.env.MOCK_SERVER_CORS_ORIGINS ?? 'http://localhost:5173,http://localhost:5174')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean)

const ALLOWED_HEADERS = ['Content-Type', 'Authorization', 'Idempotency-Key', 'If-Match', 'X-Correlation-ID', 'X-Reauth-Token', 'Last-Event-ID', 'Cache-Control']
const EXPOSED_HEADERS = ['Idempotent-Replayed', 'X-Action']

/** Trả true nếu đã tự xử lý xong request (preflight OPTIONS) — caller không cần làm gì thêm. */
function applyCors(req: IncomingMessage, res: ServerResponse): boolean {
  const origin = req.headers.origin
  if (origin && ALLOWED_ORIGINS.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin)
    res.setHeader('Vary', 'Origin')
  }
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, PUT, DELETE, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', ALLOWED_HEADERS.join(', '))
  res.setHeader('Access-Control-Expose-Headers', EXPOSED_HEADERS.join(', '))
  res.setHeader('Access-Control-Max-Age', '600')
  if (req.method === 'OPTIONS') {
    res.writeHead(204).end()
    return true
  }
  return false
}

async function readBody(req: IncomingMessage): Promise<Buffer | undefined> {
  if (req.method === 'GET' || req.method === 'HEAD') return undefined
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  return chunks.length ? Buffer.concat(chunks) : undefined
}

function toRequest(req: IncomingMessage, body: Buffer | undefined, signal: AbortSignal): Request {
  const headers: Record<string, string> = {}
  for (const [key, value] of Object.entries(req.headers)) {
    if (value !== undefined) headers[key] = Array.isArray(value) ? value.join(', ') : value
  }
  // Buffer là Uint8Array, nhưng lib DOM của TypeScript không nhận `Uint8Array<ArrayBufferLike>`
  // trong union BodyInit (dù undici chấp nhận khi chạy). Ép kiểu tường minh, không đổi hành vi.
  const payload = (body ? new Uint8Array(body) : undefined) as BodyInit | undefined
  return new Request(`http://${req.headers.host ?? HOST_FALLBACK}${req.url}`, { method: req.method, headers, body: payload, signal })
}

async function writeResponse(response: Response, res: ServerResponse) {
  const headers: Record<string, string> = {}
  response.headers.forEach((value, key) => {
    headers[key] = value
  })
  res.writeHead(response.status, headers)
  if (!response.body) {
    res.end()
    return
  }
  const reader = response.body.getReader()
  res.on('close', () => reader.cancel().catch(() => undefined))
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    // Xả buffer ngay để SSE chảy theo thời gian thực thay vì bị Node gộp lại.
    const flushed = res.write(Buffer.from(value))
    if (!flushed) await new Promise((resolve) => res.once('drain', resolve))
  }
  res.end()
}

const server = createServer((req, res) => {
  void (async () => {
    if (applyCors(req, res)) return
    const controller = new AbortController()
    req.on('close', () => controller.abort())
    try {
      const body = await readBody(req)
      const request = toRequest(req, body, controller.signal)
      const response = await getResponse(handlers, request)
      if (!response) {
        res.writeHead(404, { 'Content-Type': 'application/json' }).end(JSON.stringify({ code: 'NOT_FOUND', message: `Không có route cho ${req.method} ${req.url}` }))
        return
      }
      await writeResponse(response, res)
    } catch (error) {
      if (controller.signal.aborted) return
      console.error('[mock-server]', error)
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' }).end(JSON.stringify({ code: 'INTERNAL_ERROR', message: 'Lỗi không xác định ở backend giả lập.' }))
      }
    }
  })()
})

server.listen(PORT, async () => {
  await getDb()
  console.log(`[mock-server] http://localhost:${PORT}  (CORS: ${ALLOWED_ORIGINS.join(', ')})`)
  console.log('[mock-server] Tài khoản demo (mật khẩu Vland@2026): nam.hoang@ · trang.le@ · ha.nguyen@ · minh.tuan@vlandfuture.vn')
})
