import type { ApiClient } from '@/api/contracts'
import { createHttpClient } from '@/api/http/httpClient'
import { createMockClient } from '@/api/mock/mockClient'
import { getAccessToken } from '@/auth/sessionStore'

/** `mock` (mặc định) — backend giả lập trong trình duyệt; `http` — gọi REST backend thật. */
export const API_MODE: 'mock' | 'http' = import.meta.env.VITE_API_MODE === 'http' ? 'http' : 'mock'

export const api: ApiClient =
  API_MODE === 'http'
    ? createHttpClient(import.meta.env.VITE_API_BASE_URL ?? '/api/v1', getAccessToken)
    : createMockClient(getAccessToken)
