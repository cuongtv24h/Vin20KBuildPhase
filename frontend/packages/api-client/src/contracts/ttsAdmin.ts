/**
 * Hợp đồng quản trị nhà cung cấp TTS (ADMIN) — cùng hình dạng với `llmAdmin` (đợt 22).
 *
 * Người dùng chốt: “Dùng sẵn cơ chế cũ đã có, cho phép thêm mới nhà cung cấp ngoài các nhà cung cấp sẵn.”
 * Vì vậy màn hình quản trị giọng đọc cho phép: nhập khoá (mã hoá, chỉ trả dạng che), bấm “Test kết nối”,
 * và **thêm nhà cung cấp mới** ngoài danh mục dựng sẵn (self-host, gateway nội bộ, nhà cung cấp khác).
 */

/** Một nhà cung cấp TTS trong danh mục hiệu lực (dựng sẵn, bản ghi đè, hoặc do Admin tự thêm). */
export interface TtsProviderAdmin {
  provider: string
  /** `provider_id` của bản ghi DB; `''` khi chỉ có trong danh mục dựng sẵn. */
  provider_id: string
  label: string
  mode: 'browser' | 'api'
  base_url: string
  default_model: string
  env_key: string
  price_per_1m_chars: number
  currency: string
  price_note: string
  verified_at: string
  note: string
  voices: Array<{ code: string; label: string; gender: string }>
  supports_streaming: boolean
  voice_cloning: boolean
  priority: number
  is_active: boolean
  /** Không nằm trong danh mục dựng sẵn ⇒ do Admin tự thêm. */
  custom: boolean
  /** Đã có bản ghi DB (bản ghi đè hoặc nhà cung cấp mới). */
  has_db_row: boolean
  api_key_configured: boolean
  /** Khoá đã lưu, dạng che `sk-…abcd`; không bao giờ là khoá thật. */
  api_key_masked: string
  /** 'db' | 'env' | 'llm' | 'browser' | 'none' */
  key_source: string
  /** Câu chữ hiển thị của `key_source` (ví dụ “DB (nhập trên giao diện)”). */
  key_source_label: string
  last_test_status?: string | null
  last_test_latency_ms?: number | null
  last_tested_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface TtsProviderListResponse {
  /** 'db' = đã có khai báo trong DB; 'builtin' = chỉ có danh mục dựng sẵn. */
  source: 'db' | 'builtin'
  total: number
  items: TtsProviderAdmin[]
}

export interface TtsProviderPayload {
  provider: string
  label: string
  mode: 'browser' | 'api'
  base_url?: string | null
  default_model?: string
  env_key?: string
  price_per_1m_chars: number
  currency: string
  price_note?: string
  verified_at?: string
  note?: string
  /** Mỗi dòng một giọng: `mã | nhãn | giới tính`. Để trống khi sửa = giữ danh sách cũ. */
  voices_text?: string
  supports_streaming?: boolean
  voice_cloning?: boolean
  /** Bỏ trống khi sửa để giữ nguyên khoá cũ. */
  api_key?: string | null
  priority: number
  is_active: boolean
}

export interface TtsProviderTestResult {
  provider: string
  ok: boolean
  latency_ms: number
  /** OK | ERROR | UNREACHABLE | NOT_CONFIGURED | UNSUPPORTED | NO_KEY_NEEDED */
  status: string
  detail: string
  method?: string | null
  url?: string | null
}
