/**
 * Hợp đồng cho luồng Sale NÓI → CHỮ (Speech-to-Text, Whisper qua Groq/OpenAI).
 *
 * Ranh giới: backend chỉ trả về CHỮ. Chữ đó được dán vào ô hỏi và đi qua đúng `POST /copilot/chat`
 * như khi Sale gõ — nên grounding/kiểm chứng/compliance/lịch sử hội thoại không đổi.
 * Backend KHÔNG lưu audio ở bất kỳ đâu; chỉ ghi sổ số giây + nhà cung cấp + độ trễ.
 */

/** Hạn mức nghe-nói theo ngày (tính bằng PHÚT audio; `daily_budget_minutes = 0` nghĩa là không giới hạn). */
export interface SttQuota {
  daily_budget_minutes: number
  minutes_today: number
  seconds_today: number
  remaining_minutes: number
}

/** Kết quả một lượt nghe. */
export interface SttTranscription {
  /** Transcript thô từ nhà cung cấp. */
  text: string
  /** Đã chuẩn hoá thuật ngữ (mã căn ZEN-A-1205, KPBT, "3 phẩy 864 tỷ" → "3,864 tỷ") — nên dùng bản này. */
  normalized_text: string
  language: string
  provider: string
  model: string
  latency_ms: number
  audio_bytes: number
  estimated_seconds: number
  quota: SttQuota
  /** `true` = nhà cung cấp ưu tiên lỗi, đã rơi xuống mắt xích kế. */
  fallback_used: boolean
  warnings: string[]
}

/** Một mắt xích trong chuỗi nhà cung cấp (báo cáo bởi `/stt/health`). */
export interface SttChainLink {
  provider: string
  label: string
  model: string
  configured: boolean
  active: boolean
  /** `db` = khoá ADMIN dán trong app; `env` = khoá trong `.env`; `none` = chưa có khoá. */
  key_source: 'db' | 'env' | 'none' | string
  api_key_masked: string
  /** Cam kết vận hành: đã bật Zero Data Retention phía nhà cung cấp (Groq: Console → Data Controls). */
  zero_data_retention: boolean
  price_per_hour_audio: number
  currency: string
}

export interface SttHealth {
  enabled: boolean
  preferred: string
  language: string
  chain: SttChainLink[]
  /** Chuỗi backend sẽ thử (không gồm `browser` — mắt xích đó chạy ngay trên trình duyệt). */
  active_chain: string[]
  /** Trình duyệt còn dùng được Web Speech API làm lưới an toàn không. */
  browser_fallback: boolean
  quota: SttQuota
  limits: {
    max_bytes: number
    max_duration_seconds: number
    accepted_content_types: string[]
  }
  warnings: string[]
}

/** Bản ghi nhà cung cấp STT (trả ra từ API quản trị — khoá luôn ở dạng che). */
export interface SttProviderView {
  provider_id: string
  provider: string
  label: string
  mode: 'api' | 'browser' | string
  base_url: string
  default_model: string
  language: string
  priority: number
  is_active: boolean
  zero_data_retention: boolean
  api_key_masked: string
  has_api_key: boolean
  source: string
  price_per_hour_audio?: number
  currency?: string
  note?: string
  env_key?: string
  prompt_bias?: string
  configured?: boolean
  key_source?: string
}

/** Payload ADMIN khai báo/đè cấu hình nhà cung cấp trong DB (DB được ưu tiên hơn `.env`). */
export interface SttProviderUpsert {
  label?: string
  /** Chuỗi rỗng = XOÁ khoá trong DB (quay về dùng `.env`). */
  api_key?: string
  base_url?: string
  model?: string
  language?: string
  priority?: number
  is_active?: boolean
  zero_data_retention?: boolean
  prompt_bias?: string
  env_key?: string
  price_per_hour_audio?: number
  currency?: string
  note?: string
}

export interface SttProviderListResponse {
  catalog: SttProviderView[]
  db_rows: SttProviderView[]
  effective_chain: string[]
  db_overrides: string[]
}

export interface SttProviderTestResult {
  provider: string
  ok: boolean
  detail?: string
  latency_ms?: number
  model?: string
  language?: string
  text?: string
  tested_by?: string
}
