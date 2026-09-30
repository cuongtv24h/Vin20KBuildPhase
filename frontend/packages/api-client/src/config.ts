/**
 * Cấu hình tầng API. Đổi mock ↔ backend thật chỉ bằng biến môi trường, không sửa màn hình:
 *   NEXT_PUBLIC_API_MODE=mock   → NEXT_PUBLIC_API_BASE_URL trỏ tới packages/mock-server (mặc định)
 *   NEXT_PUBLIC_API_MODE=real   → NEXT_PUBLIC_API_BASE_URL trỏ tới FastAPI thật
 * Cả hai app (Khách hàng :5173, Nội bộ :5174) gọi thẳng qua network tới cùng một origin API —
 * không đi qua proxy của Vite dev server nữa, vì đây là hai origin độc lập theo đúng cấu trúc
 * "2 UI riêng biệt, chỉ trao đổi qua API" (không phải app+API cùng origin như bản gộp trước đây).
 * Tiền tố NEXT_PUBLIC_ được bật trong vite.config.ts (envPrefix) để giữ nguyên tên biến theo
 * TD-4.1 (Next.js) — nếu sau này chuyển sang Next.js thì không phải đổi .env.
 *
 * Gói này được cả hai app (Vite, có `import.meta.env`) lẫn packages/mock-server (Node thuần, không
 * có `import.meta.env`) import — `?? {}` để tránh vỡ khi chạy ngoài Vite.
 */
const env = import.meta.env ?? {}

export type ApiMode = 'real'

/** Chế độ kết nối: Luôn luôn kết nối Backend & CSDL PostgreSQL thật (không mock). */
export const API_MODE: ApiMode = 'real'

function resolveApiBaseUrl(): string {
  const explicit = env.NEXT_PUBLIC_API_BASE_URL || env.NEXT_PUBLIC_API_URL

  // 1. Chạy trên môi trường Local / Dev (Vite port 5173, 5174 hoặc localhost / 127.0.0.1)
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    const port = window.location.port
    const isLocal = host === 'localhost' || host === '127.0.0.1' || port === '5173' || port === '5174'
    if (isLocal) {
      // Nếu có URL tuyệt đối được cấu hình (VD: http://192.168.1.10:8000), dùng URL đó
      if (explicit && explicit.startsWith('http')) {
        const trimmed = explicit.replace(/\/$/, '')
        return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`
      }
      // Ngược lại (dù env root để /api/v1 hay trống), trên local luôn gọi thẳng port 8000 của FastAPI
      return `http://${host || 'localhost'}:8000/api/v1`
    }
  }

  // 2. Chạy trên VPS Production (domain demoday.work.gd) -> ưu tiên explicit hoặc /api/v1 (Nginx proxy)
  if (explicit) {
    const trimmed = explicit.replace(/\/$/, '')
    return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`
  }
  return '/api/v1'
}

export const API_BASE_URL = resolveApiBaseUrl()

/** TD-4.1 §3.1 — Timeout-path deadline 10s: UI dừng an toàn, không treo spinner. */
export const REQUEST_TIMEOUT_MS = 10_000
export const ANALYSIS_DEADLINE_MS = 10_000

/** TD-4.1 §3.1 — server heartbeat 15s; quá 20s không nhận byte nào coi như mất kết nối. */
export const SSE_IDLE_TIMEOUT_MS = 20_000
export const SSE_BACKOFF_MS = [500, 1_000, 2_000, 4_000, 8_000]

/** Debounce kiểm tra tuân thủ khi Sale gõ — Implement plan D1-5 / D3-3. */
export const COMPLIANCE_DEBOUNCE_MS = 500

export const IS_DEV_TOOLS_ENABLED = false
