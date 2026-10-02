/** Hợp đồng quản trị nhà cung cấp LLM & đo chi phí/hiệu năng (ADMIN). */

/** Nhà cung cấp Admin khai báo — `api_key` không bao giờ trả về nguyên văn. */
export interface LlmProvider {
  provider_id: string
  name: string
  provider: string
  base_url?: string | null
  model_name: string
  api_key_masked: string
  has_api_key: boolean
  /** Đơn giá token vào trên 1 triệu token (đơn vị `currency`). */
  input_price_per_1m: number
  /** Đơn giá token ra trên 1 triệu token. */
  output_price_per_1m: number
  currency: string
  temperature: number
  /** Số nhỏ chạy trước — provider có priority nhỏ nhất là primary. */
  priority: number
  is_active: boolean
  last_test_status?: string | null
  last_test_latency_ms?: number | null
  last_tested_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface LlmProviderListResponse {
  /** 'db' = đang dùng khai báo trong DB; 'env' = chưa khai báo gì nên rơi về biến môi trường. */
  source: 'db' | 'env' | 'none'
  total: number
  items: LlmProvider[]
}

export interface LlmProviderPayload {
  name: string
  provider: string
  base_url?: string | null
  model_name: string
  /** Bỏ trống khi sửa để giữ nguyên khoá cũ. */
  api_key?: string | null
  input_price_per_1m: number
  output_price_per_1m: number
  currency: string
  temperature: number
  priority: number
  is_active: boolean
}

export interface LlmProviderTestResult {
  provider_id: string
  ok: boolean
  latency_ms: number
  status: string
  detail: string
}

/** Một dòng trong bảng chi phí theo nhà cung cấp. */
export interface LlmUsageByProvider {
  provider: string
  model_name: string
  calls: number
  failed_calls: number
  input_tokens: number
  output_tokens: number
  cost: number
  avg_latency_ms: number
  p95_latency_ms: number
  error_rate: number
}

export interface LlmUsageByDay {
  day: string
  calls: number
  cost: number
  tokens: number
}

export interface LlmUsageSummary {
  window_days: number
  total_calls: number
  failed_calls: number
  error_rate: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  total_cost: number
  currency: string
  p50_latency_ms: number
  p95_latency_ms: number
  avg_cost_per_call: number
  by_provider: LlmUsageByProvider[]
  by_day: LlmUsageByDay[]
}

export interface LlmUsageRecord {
  at: string
  provider: string
  model_name: string
  input_tokens: number
  output_tokens: number
  latency_ms: number
  ok: boolean
  error?: string | null
  is_fallback: boolean
  cost: number
  currency: string
  conversation_id?: string | null
  user_id?: string | null
}

export interface LlmUsageRecordsResponse {
  total: number
  items: LlmUsageRecord[]
}
