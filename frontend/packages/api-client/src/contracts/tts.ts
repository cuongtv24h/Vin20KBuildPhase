/**
 * Hợp đồng đọc câu trả lời Copilot (Text-to-Speech).
 *
 * Nguyên tắc thiết kế: UI **không** tự bịa đơn giá hay danh sách giọng. Mọi thứ (nhà cung cấp, mã
 * giọng, giá, đã có khoá chưa) lấy từ server để màn hình cấu hình và màn hình đọc nói cùng một sự thật.
 */

export type TtsProviderMode = 'browser' | 'api'

export interface TtsVoiceOption {
  code: string
  label: string
  gender: 'male' | 'female' | 'neutral'
}

export interface TtsProviderInfo {
  provider: string
  label: string
  mode: TtsProviderMode
  default_model: string
  /** Đơn giá trên 1 triệu ký tự; 0 = miễn phí (đọc bằng trình duyệt). */
  price_per_1m_chars: number
  currency: string
  price_note: string
  /** Mốc kiểm chứng bảng giá — hiển thị để không ngộ nhận là giá hiện hành tuyệt đối. */
  verified_at: string
  supports_streaming: boolean
  voice_cloning: boolean
  note: string
  /** Đã có khoá API chưa (chỉ cờ boolean, không bao giờ là giá trị khoá). */
  api_key_configured: boolean
  /** Khoá đang lấy từ đâu: 'db' (nhập trên giao diện) | 'env' | 'llm' | 'browser' | 'none'. */
  key_source?: string
  /** Base URL hiệu lực (rỗng với nhà cung cấp dựng sẵn chưa cấu hình). */
  base_url?: string
  /** Tên biến ENV chứa khoá (đường lui DB → ENV). */
  env_key?: string
  /** Nhà cung cấp do Admin tự thêm trong màn hình quản trị (ngoài danh mục dựng sẵn). */
  custom?: boolean
  /** `provider_id` của bản ghi DB, nếu có. */
  provider_id?: string
  voices: TtsVoiceOption[]
}

export interface TtsSettings {
  enabled: boolean
  auto_speak: boolean
  provider: string
  model: string
  voice: string
  speed: number
  max_chars_per_turn: number
}

export interface TtsSettingsScope extends TtsSettings {
  updated_by?: string | null
  updated_at?: string | null
  /** Chỉ có ở nhánh `default`: người dùng đã chủ động đặt (khác với giá trị suy ra từ ENV). */
  is_explicit?: boolean
}

export interface TtsCostHint {
  provider: string
  mode: TtsProviderMode
  chars: number
  billable_chars: number
  price_per_1m_chars: number
  currency: string
  cost: number
  price_verified_at: string
}

export interface TtsFeedbackSummary {
  total: number
  up: number
  down: number
  satisfaction: number | null
}

export interface TtsSettingsResponse {
  catalog: TtsProviderInfo[]
  /** Mặc định toàn hệ thống (ADMIN/MANAGER đặt). */
  default: TtsSettingsScope
  /** Hồ sơ riêng của người đang hỏi, `null` nếu chưa đặt. */
  user_override: TtsSettingsScope | null
  /** Thiết lập thực sự sẽ dùng để đọc. */
  effective: TtsSettings
  /** Ước tính chi phí đọc trọn một câu trả lời dài tối đa. */
  cost_hint: TtsCostHint
  feedback_summary: TtsFeedbackSummary
}

export interface TtsSettingsPayload {
  /** 'user' = riêng tôi (mọi nhân viên); 'default' = toàn hệ thống (ADMIN/MANAGER). */
  scope?: 'user' | 'default'
  enabled?: boolean
  auto_speak?: boolean
  provider?: string
  model?: string
  voice?: string
  speed?: number
  max_chars_per_turn?: number
}

export interface TtsFeedbackPayload {
  /** 1 = nghe ổn, -1 = nghe chưa ổn. */
  rating: 1 | -1
  provider?: string
  voice?: string
  conversation_id?: string | null
  reason?: string
}

export interface TtsFeedbackResponse {
  feedback_id: string
  total: number
  up: number
  down: number
}

/** Yêu cầu đọc một đoạn văn bản qua nhà cung cấp TTS (backend gọi nhà cung cấp, không phải trình duyệt). */
export interface TtsSpeakRequest {
  text: string
  /** Bỏ trống = lấy thiết lập hiệu lực của người gọi. */
  provider?: string
  voice?: string
  model?: string
  speed?: number
  conversation_id?: string | null
  /** True = chỉ đọc phần đầu (chế độ rảnh tay). */
  summary_only?: boolean
}

export interface TtsQuota {
  /** 0 = không giới hạn. */
  daily_budget: number
  chars_today: number
  /** -1 khi không giới hạn. */
  remaining: number
}

export interface TtsSpeakAttempt {
  provider: string
  label: string
  ok: boolean
  status: string
  detail: string
  voice: string
  model: string
}

export interface TtsSpeakResponse {
  provider: string
  voice: string
  model: string
  mime: string
  audio_base64: string
  chars: number
  cached: boolean
  cost: number
  currency: string
  latency_ms: number
  quota: TtsQuota
  /** True khi nhà cung cấp đã đọc KHÔNG phải nhà cung cấp ưu tiên (đã tự chuyển tiếp). */
  fallback_used: boolean
  attempts: TtsSpeakAttempt[]
}
