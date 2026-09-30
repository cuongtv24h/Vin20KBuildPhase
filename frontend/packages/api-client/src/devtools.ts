import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { API_BASE_URL } from './config'
import type { UserRole } from './contracts'

/**
 * Điều khiển backend giả lập (chỉ tồn tại khi NEXT_PUBLIC_API_MODE=mock và chạy dev).
 * Đi qua HTTP `/__mock/*` do mock-server phục vụ trên cùng origin với `/api/v1` — component không
 * import thẳng mã mock.
 */
const MOCK_ORIGIN = API_BASE_URL.replace(/\/api\/v1$/, '')
export interface MockFlags {
  /** Độ trễ mỗi request: normal 200–800ms, slow 2.5–6s. */
  latency: 'normal' | 'slow'
  /** Tỷ lệ request trả 500 INTERNAL_ERROR (0 → 1). */
  fail_rate: number
  /** Agent xử lý chậm ×3 → vượt deadline 10s. */
  slow_agent: boolean
  /** Ngắt SSE sau sự kiện thứ 2 (một lần mỗi phiên bản) để kiểm tra reconnect + Last-Event-ID. */
  drop_sse_once: boolean
  /** Reconnect có Last-Event-ID trả 410 → client phải resync qua REST. */
  expire_replay: boolean
  /** PDF worker thất bại → FAILED, chờ pdf-retry. */
  pdf_worker_fail: boolean
  /** Hệ số thời gian cho các mốc giả lập (test dùng 0.01). */
  time_scale: number
}

export interface DemoAccount {
  email: string
  password: string
  full_name: string
  role: UserRole
}

async function devFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${MOCK_ORIGIN}/__mock${path}`, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!res.ok) throw new Error(`Mock devtools ${path} → ${res.status}`)
  return (await res.json()) as T
}

export const useMockFlags = (enabled: boolean) =>
  useQuery({ queryKey: ['__mock', 'flags'], queryFn: () => devFetch<MockFlags>('/flags'), enabled })

export const useDemoAccounts = (enabled: boolean) =>
  useQuery({ queryKey: ['__mock', 'accounts'], queryFn: () => devFetch<DemoAccount[]>('/accounts'), enabled, staleTime: Infinity })

export function useUpdateMockFlags() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: Partial<MockFlags>) => devFetch<MockFlags>('/flags', { method: 'PATCH', body: JSON.stringify(patch) }),
    onSuccess: (flags) => qc.setQueryData(['__mock', 'flags'], flags),
  })
}

export function useResetDemo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => devFetch<{ ok: true }>('/reset', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries(),
  })
}
