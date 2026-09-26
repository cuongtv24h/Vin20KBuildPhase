/**
 * Cấu hình tầng API. Đổi mock ↔ backend thật chỉ bằng biến môi trường, không sửa màn hình:
 *   NEXT_PUBLIC_API_MODE=mock   → MSW chặn request trong trình duyệt (mặc định)
 *   NEXT_PUBLIC_API_MODE=real   → gọi thẳng FastAPI qua NEXT_PUBLIC_API_BASE_URL
 * Tiền tố NEXT_PUBLIC_ được bật trong vite.config.ts (envPrefix) để giữ nguyên tên biến theo
 * TD-4.1 (Next.js) — nếu sau này chuyển sang Next.js thì không phải đổi .env.
 */
const env = import.meta.env

export type ApiMode = 'mock' | 'real'

export const API_MODE: ApiMode = env.NEXT_PUBLIC_API_MODE === 'real' ? 'real' : 'mock'

export const API_BASE_URL = (env.NEXT_PUBLIC_API_BASE_URL || '/api/v1').replace(/\/$/, '')

/** TD-4.1 §3.1 — Timeout-path deadline 10s: UI dừng an toàn, không treo spinner. */
export const REQUEST_TIMEOUT_MS = 10_000
export const ANALYSIS_DEADLINE_MS = 10_000

/** TD-4.1 §3.1 — server heartbeat 15s; quá 20s không nhận byte nào coi như mất kết nối. */
export const SSE_IDLE_TIMEOUT_MS = 20_000
export const SSE_BACKOFF_MS = [500, 1_000, 2_000, 4_000, 8_000]

/** Debounce kiểm tra tuân thủ khi Sale gõ — Implement plan D1-5 / D3-3. */
export const COMPLIANCE_DEBOUNCE_MS = 500

export const IS_DEV_TOOLS_ENABLED = API_MODE === 'mock' && env.DEV
