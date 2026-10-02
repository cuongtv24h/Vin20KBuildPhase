import type { TtsSettings, TtsSettingsScope } from '@pricepolicy/api-client/contracts'
import { onReset } from '../db'
import { MockError } from '../services/errors'
import { route } from './route'

/**
 * Thiết lập đọc câu trả lời (TTS) — bản mock song song với `src/api/endpoints/settings.py`.
 *
 * Cùng nguyên tắc với backend thật:
 * - `scope: 'default'` chỉ ADMIN/MANAGER đổi được (một Sale không đổi giọng cho cả công ty);
 * - `scope: 'user'` là hồ sơ riêng, thắng mặc định khi đọc;
 * - danh mục nhà cung cấp + đơn giá lấy từ bảng giá niêm yết, kèm cờ "đã có khoá" (mock: chưa cấu
 *   hình khoá nào nên mọi nhà cung cấp trả phí đều báo chưa có — UI nhờ vậy nói thật với người dùng);
 * - phản hồi giọng đọc được đếm để tính tỉ lệ hài lòng.
 */

interface CatalogEntry {
  provider: string
  label: string
  mode: 'browser' | 'api'
  default_model: string
  price_per_1m_chars: number
  currency: string
  price_note: string
  verified_at: string
  supports_streaming: boolean
  voice_cloning: boolean
  note: string
  voices: Array<{ code: string; label: string; gender: 'male' | 'female' | 'neutral' }>
}

/** Rút gọn danh mục so với backend (mock không cần đủ 7 nhà cung cấp, nhưng giữ đúng hình dạng). */
const CATALOG: CatalogEntry[] = [
  {
    provider: 'browser',
    label: 'Trình duyệt (Web Speech API)',
    mode: 'browser',
    default_model: '',
    price_per_1m_chars: 0,
    currency: 'USD',
    price_note: 'Miễn phí — dùng giọng có sẵn trên máy.',
    verified_at: '2026-10-02',
    supports_streaming: false,
    voice_cloning: false,
    note: 'Không cần khoá, chạy ngay trong demo; giọng tuỳ máy nên không đồng nhất giữa các nhân viên.',
    voices: [{ code: 'vi-VN', label: 'Giọng tiếng Việt của hệ điều hành', gender: 'neutral' }],
  },
  {
    provider: 'openai',
    label: 'OpenAI TTS',
    mode: 'api',
    default_model: 'tts-1',
    price_per_1m_chars: 15,
    currency: 'USD',
    price_note: 'tts-1: 15 USD/1M ký tự; tts-1-hd: 30 USD/1M; gpt-4o-mini-tts tính theo token audio.',
    verified_at: '2026-10-02',
    supports_streaming: true,
    voice_cloning: false,
    note: 'Dùng chung khoá với LLM; nên bật khi đã có nhà cung cấp LLM trong DB.',
    voices: [
      { code: 'alloy', label: 'Alloy — trung tính', gender: 'neutral' },
      { code: 'nova', label: 'Nova — nữ', gender: 'female' },
      { code: 'onyx', label: 'Onyx — nam', gender: 'male' },
    ],
  },
  {
    provider: 'google_cloud',
    label: 'Google Cloud TTS',
    mode: 'api',
    default_model: 'vi-VN-Wavenet-A',
    price_per_1m_chars: 4,
    currency: 'USD',
    price_note: 'Standard/WaveNet 4 USD/1M ký tự (miễn phí 4M/tháng); Neural2 16 USD/1M.',
    verified_at: '2026-10-02',
    supports_streaming: true,
    voice_cloning: false,
    note: 'Có giọng tiếng Việt chính thức và hạn mức miễn phí hằng tháng.',
    voices: [
      { code: 'vi-VN-Wavenet-A', label: 'vi-VN WaveNet A — nữ', gender: 'female' },
      { code: 'vi-VN-Wavenet-B', label: 'vi-VN WaveNet B — nam', gender: 'male' },
    ],
  },
  {
    provider: 'viettel',
    label: 'Viettel AI TTS',
    mode: 'api',
    default_model: 'viettel-tts',
    price_per_1m_chars: 320_000,
    currency: 'VND',
    price_note: 'Bảng giá công bố: 320.000 VNĐ/1M ký tự (không thuê bao).',
    verified_at: '2022-12-26',
    supports_streaming: false,
    voice_cloning: false,
    note: 'Nhà cung cấp trong nước, dữ liệu không ra ngoài; giá niêm yết cũ, cần xác nhận lại.',
    voices: [
      { code: 'hn_female_ngochuyen', label: 'Nữ Hà Nội', gender: 'female' },
      { code: 'hn_male_manhdung', label: 'Nam Hà Nội', gender: 'male' },
    ],
  },
]

const MAX_CHARS_MIN = 50
const MAX_CHARS_MAX = 5_000

const DEFAULT_SETTINGS: TtsSettings = {
  enabled: true,
  auto_speak: false,
  provider: 'browser',
  model: '',
  voice: 'vi-VN',
  speed: 1,
  max_chars_per_turn: 600,
}

let defaultScope: TtsSettingsScope | null = null
let userScopes: Record<string, TtsSettingsScope> = {}
let feedback: Array<{ user_id: string; provider: string; voice: string; rating: number; reason?: string | null; at: string }> = []

onReset(() => {
  defaultScope = null
  userScopes = {}
  feedback = []
})

const costOf = (settings: TtsSettings, chars: number) => {
  const entry = CATALOG.find((c) => c.provider === settings.provider) ?? CATALOG[0]
  const billable = Math.min(chars, settings.max_chars_per_turn)
  return {
    provider: entry.provider,
    mode: entry.mode,
    chars,
    billable_chars: billable,
    price_per_1m_chars: entry.price_per_1m_chars,
    currency: entry.currency,
    cost: Math.round((billable / 1_000_000) * entry.price_per_1m_chars * 1e6) / 1e6,
    price_verified_at: entry.verified_at,
  }
}

const feedbackSummary = (provider: string, voice: string) => {
  const mine = feedback.filter((f) => f.provider === provider && f.voice === voice)
  const up = mine.filter((f) => f.rating === 1).length
  const down = mine.filter((f) => f.rating === -1).length
  return { total: mine.length, up, down, satisfaction: mine.length ? Math.round((up / mine.length) * 1e4) / 1e4 : null }
}

function mergedSettings(userId: string): TtsSettings {
  const base: TtsSettings = { ...DEFAULT_SETTINGS }
  if (defaultScope) Object.assign(base, stripMeta(defaultScope))
  const mine = userScopes[userId]
  if (mine) Object.assign(base, stripMeta(mine))
  return base
}

const stripMeta = (scope: TtsSettingsScope): TtsSettings => {
  const { updated_by: _updatedBy, updated_at: _updatedAt, is_explicit: _isExplicit, ...rest } = scope
  return rest
}

function validate(payload: Partial<TtsSettings>): TtsSettings {
  const provider = CATALOG.find((c) => c.provider === payload.provider)
  if (payload.provider && !provider) {
    throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Nhà cung cấp TTS không hợp lệ.')
  }
  if (payload.voice !== undefined && !payload.voice?.trim()) {
    throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Thiếu mã giọng đọc (voice).')
  }
  if (payload.speed !== undefined && (payload.speed < 0.5 || payload.speed > 2)) {
    throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Tốc độ đọc phải trong khoảng 0.5–2.0.')
  }
  if (
    payload.max_chars_per_turn !== undefined &&
    (payload.max_chars_per_turn < MAX_CHARS_MIN || payload.max_chars_per_turn > MAX_CHARS_MAX)
  ) {
    throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Giới hạn ký tự mỗi lượt phải trong khoảng 50–5000.')
  }
  return { ...DEFAULT_SETTINGS, ...payload } as TtsSettings
}

const scopeOf = (payloadScope: string | undefined, userId: string) => {
  if (payloadScope === 'default') return { key: 'default', isDefault: true }
  return { key: `user:${userId}`, isDefault: false }
}

const payloadWithScope = async <T>(json: () => Promise<T>) => (await json()) as Partial<TtsSettings> & { scope?: string }

export const ttsHandlers = [
  route('ttsSettings', ({ staff }) => {
    const me = staff()
    const effective = mergedSettings(me.user_id)
    return {
      body: {
        catalog: CATALOG.map((c) => ({ ...c, api_key_configured: c.mode === 'browser', voices: c.voices })),
        default: {
          ...(defaultScope ?? { ...DEFAULT_SETTINGS }),
          is_explicit: defaultScope !== null,
        },
        user_override: userScopes[me.user_id] ?? null,
        effective,
        cost_hint: costOf(effective, effective.max_chars_per_turn),
        feedback_summary: feedbackSummary(effective.provider, effective.voice),
      },
    }
  }),

  route('ttsSettingsUpdate', async ({ staff, json, now }) => {
    const me = staff()
    const payload = await payloadWithScope<Partial<TtsSettings>>(json)
    const { scope: requestedScope, ...changes } = payload
    const { key, isDefault } = scopeOf(requestedScope, me.user_id)

    if (isDefault && !['ADMIN', 'MANAGER'].includes(me.role)) {
      throw new MockError(
        403,
        'FORBIDDEN',
        'Chỉ ADMIN/MANAGER được đổi giọng đọc dùng chung. Anh/chị có thể lưu lựa chọn riêng cho mình.',
      )
    }

    const current = isDefault ? (defaultScope ?? { ...DEFAULT_SETTINGS }) : (userScopes[me.user_id] ?? { ...DEFAULT_SETTINGS })
    const merged = validate({ ...stripMeta(current as TtsSettingsScope), ...changes })
    const saved: TtsSettingsScope = { ...merged, updated_by: me.user_id, updated_at: new Date(now).toISOString() }
    if (isDefault) defaultScope = saved
    else userScopes = { ...userScopes, [me.user_id]: saved }

    const effective = mergedSettings(me.user_id)
    return {
      body: {
        catalog: CATALOG.map((c) => ({ ...c, api_key_configured: c.mode === 'browser', voices: c.voices })),
        default: { ...(defaultScope ?? { ...DEFAULT_SETTINGS }), is_explicit: defaultScope !== null },
        user_override: userScopes[me.user_id] ?? null,
        effective,
        cost_hint: costOf(effective, effective.max_chars_per_turn),
        feedback_summary: feedbackSummary(effective.provider, effective.voice),
        scope_key: key,
      },
    }
  }),

  route('ttsFeedback', async ({ staff, json, now }) => {
    const me = staff()
    const body = await json<{ rating?: number; provider?: string; voice?: string; reason?: string }>()
    if (body?.rating !== 1 && body?.rating !== -1) {
      throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'rating chỉ nhận 1 hoặc -1.')
    }
    const effective = mergedSettings(me.user_id)
    const provider = (body.provider ?? effective.provider).trim().toLowerCase()
    const voice = (body.voice ?? effective.voice).trim()
    feedback = [
      ...feedback,
      {
        user_id: me.user_id,
        provider,
        voice,
        rating: body.rating,
        // Loại ký tự NUL bằng vòng lặp chuỗi (không dùng regex ký tự điều khiển).
        reason: (body.reason ?? '').split(String.fromCharCode(0)).join('').trim().slice(0, 300) || null,
        at: new Date(now).toISOString(),
      },
    ]
    const summary = feedbackSummary(provider, voice)
    return { status: 201, body: { feedback_id: `TTSFB-${feedback.length}`, ...summary } }
  }),
]
