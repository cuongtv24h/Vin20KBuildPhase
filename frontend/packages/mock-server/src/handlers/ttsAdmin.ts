import type { TtsProviderAdmin, TtsProviderPayload } from '@pricepolicy/api-client/contracts'
import { recordMockTtsCall } from './llmAdmin'
import { MockError } from '../services/errors'
import { route } from './route'
import {
  BUILTIN_ENV_KEYS,
  type CatalogEntry,
  type TtsProviderRow,
  effectiveCatalog,
  getProviderRows,
  scopesUsingProvider,
  nextProviderId,
  setProviderRows,
} from './tts'

/**
 * Quản trị nhà cung cấp TTS — bản mock song song với `src/api/endpoints/tts_admin.py`.
 *
 * Cùng nguyên tắc với backend thật:
 * - khoá API **không** bao giờ trả nguyên văn (chỉ `sk-…abcd`), mock giữ khoá trong tiến trình;
 * - ưu tiên **DB → ENV**; mock không cấu hình khoá ENV nào nên các nhà cung cấp trả phí báo "chưa có"
 *   cho tới khi quản trị viên nhập khoá trong màn hình quản trị (nói thật, không hứa hão);
 * - một bản ghi có thể là **bản ghi đè** nhà cung cấp dựng sẵn (theo mã) hoặc **nhà cung cấp mới**;
 * - "Test kết nối" phải nói đúng sự thật: thiếu khoá ⇒ chưa cấu hình; nhà cung cấp không mở endpoint
 *   kiểm tra ⇒ nói rõ không kiểm tra tự động được (mock ghi chú rõ đây là mô phỏng, không gọi mạng).
 */

const mask = (key: string) => (key.length <= 8 ? '•'.repeat(key.length) : `${key.slice(0, 4)}…${key.slice(-4)}`)

const BUILTIN = new Set(['browser', 'openai', 'google_cloud', 'viettel'])
/** Nhà cung cấp dùng giao thức OpenAI-compatible (có `/models`) — giống backend. */
const OPENAI_COMPATIBLE = new Set(['openai', 'openai_compatible', 'groq', 'openrouter', 'deepseek'])

const rowOr404 = (providerId: string): TtsProviderRow => {
  const row = getProviderRows().find((r) => r.provider_id === providerId)
  if (!row) throw new MockError(404, 'NOT_FOUND', `Không có bản ghi nhà cung cấp TTS '${providerId}'.`)
  return row
}

/** Bản ghi DB → view cho UI (kèm cờ suy ra: custom, has_db_row, nguồn khoá). */
const toView = (row: TtsProviderRow): TtsProviderAdmin => ({
  provider: row.provider,
  provider_id: row.provider_id,
  label: row.label,
  mode: row.mode,
  base_url: row.base_url,
  default_model: row.default_model,
  env_key: row.env_key,
  price_per_1m_chars: row.price_per_1m_chars,
  currency: row.currency,
  price_note: row.price_note,
  verified_at: row.verified_at,
  note: row.note,
  voices: row.voices,
  supports_streaming: row.supports_streaming,
  voice_cloning: row.voice_cloning,
  priority: row.priority,
  is_active: row.is_active,
  custom: !BUILTIN.has(row.provider),
  has_db_row: true,
  api_key_configured: row.mode === 'browser' || row.key_source !== 'none',
  api_key_masked: row.api_key_masked,
  key_source: row.key_source,
  key_source_label:
    row.key_source === 'db'
      ? 'DB (nhập trên giao diện)'
      : row.key_source === 'env'
        ? 'ENV máy chủ'
        : row.key_source === 'browser'
          ? 'không cần khoá (đọc tại trình duyệt)'
          : 'chưa có khoá',
  last_test_status: row.last_test_status,
  last_test_latency_ms: row.last_test_latency_ms,
  last_tested_at: row.last_tested_at,
  created_at: null,
  updated_at: null,
})

/** Nhà cung cấp dựng sẵn chưa có bản ghi DB → view chỉ-để-đọc cho danh sách quản trị. */
const builtinView = (entry: CatalogEntry): TtsProviderAdmin => ({
  provider: entry.provider,
  provider_id: entry.provider_id ?? '',
  label: entry.label,
  mode: entry.mode,
  base_url: entry.base_url ?? '',
  default_model: entry.default_model,
  env_key: entry.env_key ?? BUILTIN_ENV_KEYS[entry.provider] ?? '',
  price_per_1m_chars: entry.price_per_1m_chars,
  currency: entry.currency,
  price_note: entry.price_note,
  verified_at: entry.verified_at,
  note: entry.note,
  voices: entry.voices,
  supports_streaming: entry.supports_streaming,
  voice_cloning: entry.voice_cloning,
  priority: entry.priority ?? 50,
  is_active: true,
  custom: false,
  has_db_row: false,
  api_key_configured: entry.mode === 'browser' || (entry.key_source ?? 'none') !== 'none',
  api_key_masked: '',
  key_source: entry.key_source ?? (entry.mode === 'browser' ? 'browser' : 'none'),
  key_source_label:
    (entry.key_source ?? 'none') === 'env'
      ? 'ENV máy chủ'
      : entry.mode === 'browser'
        ? 'không cần khoá (đọc tại trình duyệt)'
        : 'chưa có khoá',
  last_test_status: entry.last_test_status ?? null,
  last_test_latency_ms: entry.last_test_latency_ms ?? null,
  last_tested_at: entry.last_tested_at ?? null,
  created_at: null,
  updated_at: null,
})

const parseVoices = (text: string) =>
  text
    .split('\n')
    .map((line) => line.split('|').map((part) => part.trim()))
    .filter((parts) => parts[0])
    .map((parts) => ({
      code: parts[0],
      label: parts[1] || parts[0],
      gender: (parts[2] as 'male' | 'female' | 'neutral') || 'neutral',
    }))

export const ttsAdminHandlers = [
  route('ttsProviders', () => {
    const catalog = effectiveCatalog()
    const rows = new Map(getProviderRows().map((r) => [r.provider, r]))
    const items = catalog.map((entry) => {
      const row = rows.get(entry.provider)
      return row ? toView(row) : builtinView(entry)
    })
    return { body: { source: getProviderRows().length ? 'db' : 'builtin', total: items.length, items } }
  }),

  route('ttsProviderCreate', async ({ json }) => {
    const body = await json<TtsProviderPayload>()
    const slug = (body?.provider ?? '').trim().toLowerCase()
    if (!slug || !body?.label?.trim()) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Thiếu mã hoặc tên nhà cung cấp.')
    if (getProviderRows().some((r) => r.provider === slug)) {
      throw new MockError(409, 'CONFLICT', `Nhà cung cấp '${slug}' đã có bản ghi — dùng nút Sửa để cập nhật.`)
    }
    const mode = body.mode ?? 'api'
    if (mode === 'api' && !body.api_key?.trim()) {
      throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Cần nhập API key cho nhà cung cấp mới.')
    }
    const base = effectiveCatalog().find((c) => c.provider === slug)
    const row: TtsProviderRow = {
      provider_id: nextProviderId(),
      provider: slug,
      label: body.label.trim(),
      mode,
      base_url: body.base_url?.trim() || base?.base_url || '',
      default_model: body.default_model?.trim() || base?.default_model || '',
      env_key: (body.env_key ?? '').trim().toUpperCase() || BUILTIN_ENV_KEYS[slug] || '',
      price_per_1m_chars: Number(body.price_per_1m_chars ?? 0),
      currency: (body.currency ?? 'USD').toUpperCase(),
      price_note: body.price_note?.trim() ?? '',
      verified_at: body.verified_at?.trim() || new Date().toISOString().slice(0, 10),
      note: body.note?.trim() ?? '',
      voices: body.voices_text?.trim() ? parseVoices(body.voices_text) : (base?.voices ?? []),
      supports_streaming: body.supports_streaming ?? false,
      voice_cloning: body.voice_cloning ?? false,
      api_key_masked: body.api_key?.trim() ? mask(body.api_key.trim()) : '',
      has_key: Boolean(body.api_key?.trim()),
      key_source: mode === 'browser' ? 'browser' : 'db',
      priority: Number(body.priority ?? 50),
      is_active: body.is_active ?? true,
      last_test_status: null,
      last_test_latency_ms: null,
      last_tested_at: null,
    }
    setProviderRows([...getProviderRows(), row])
    return { status: 201, body: toView(row) }
  }),

  route('ttsProviderUpdate', async ({ params, json }) => {
    const row = rowOr404(params.provider_id)
    const body = await json<TtsProviderPayload>()
    const slug = (body?.provider ?? row.provider).trim().toLowerCase()
    if (slug !== row.provider && getProviderRows().some((r) => r.provider === slug && r.provider_id !== row.provider_id)) {
      throw new MockError(409, 'CONFLICT', `Nhà cung cấp '${slug}' đã có bản ghi khác.`)
    }
    const updated: TtsProviderRow = {
      ...row,
      provider: slug,
      label: body.label?.trim() || row.label,
      mode: body.mode ?? row.mode,
      base_url: body.base_url?.trim() ?? row.base_url,
      default_model: body.default_model?.trim() ?? row.default_model,
      env_key: (body.env_key ?? row.env_key).trim().toUpperCase(),
      price_per_1m_chars: Number(body.price_per_1m_chars ?? row.price_per_1m_chars),
      currency: (body.currency ?? row.currency).toUpperCase(),
      price_note: body.price_note ?? row.price_note,
      verified_at: body.verified_at ?? row.verified_at,
      note: body.note ?? row.note,
      voices: body.voices_text?.trim() ? parseVoices(body.voices_text) : row.voices,
      supports_streaming: body.supports_streaming ?? row.supports_streaming,
      voice_cloning: body.voice_cloning ?? row.voice_cloning,
      // Bỏ trống khoá khi sửa = giữ khoá cũ (đúng hành vi backend).
      api_key_masked: body.api_key?.trim() ? mask(body.api_key.trim()) : row.api_key_masked,
      has_key: body.api_key?.trim() ? true : row.has_key,
      key_source: (body.mode ?? row.mode) === 'browser' ? 'browser' : row.has_key || body.api_key?.trim() ? 'db' : row.key_source,
      priority: Number(body.priority ?? row.priority),
      is_active: body.is_active ?? row.is_active,
    }
    setProviderRows(getProviderRows().map((r) => (r.provider_id === row.provider_id ? updated : r)))
    return { body: toView(updated) }
  }),

  route('ttsProviderDelete', ({ params }) => {
    const row = rowOr404(params.provider_id)
    const usedByScopes = scopesUsingProvider(row.provider)
    setProviderRows(getProviderRows().filter((r) => r.provider_id !== row.provider_id))
    return {
      body: {
        ok: true,
        provider_id: row.provider_id,
        provider: row.provider,
        still_available: BUILTIN.has(row.provider),
        used_by_scopes: usedByScopes,
      },
    }
  }),

  route('ttsProviderTest', ({ params, now }) => {
    const ref = (params.provider_id ?? '').trim().toLowerCase()
    const row = getProviderRows().find((r) => r.provider_id === params.provider_id)
    const entry = effectiveCatalog().find((c) => c.provider === (row?.provider ?? ref))
    const provider = row?.provider ?? ref

    const record = (status: string, latency: number) => {
      if (!row) return
      setProviderRows(
        getProviderRows().map((r) =>
          r.provider_id === row.provider_id
            ? { ...r, last_test_status: status, last_test_latency_ms: latency, last_tested_at: new Date(now).toISOString() }
            : r,
        ),
      )
    }

    if (!entry) throw new MockError(404, 'NOT_FOUND', `Không tìm thấy nhà cung cấp TTS '${params.provider_id}' để kiểm tra.`)
    const mode = row ? row.mode : entry.mode
    const hasKey = row ? row.key_source !== 'none' && row.mode !== 'browser' : (entry.key_source ?? 'none') !== 'none' && entry.mode !== 'browser'

    if (mode === 'browser') {
      record('NO_KEY_NEEDED', 0)
      return {
        body: {
          provider,
          ok: true,
          latency_ms: 0,
          status: 'NO_KEY_NEEDED',
          detail: 'Đọc tại trình duyệt (Web Speech API) — không cần khoá, không phát sinh chi phí.',
          method: null,
          url: null,
        },
      }
    }
    if (!hasKey) {
      record('NOT_CONFIGURED', 0)
      return {
        body: {
          provider,
          ok: false,
          latency_ms: 0,
          status: 'NOT_CONFIGURED',
          detail: `Chưa có khoá để kiểm tra${row?.env_key ? ` (đặt khoá trong DB hoặc biến ENV ${row.env_key})` : ''}.`,
          method: null,
          url: null,
        },
      }
    }
    const baseUrl = (row?.base_url ?? entry.base_url ?? '').trim()
    if (!baseUrl) {
      record('NOT_CONFIGURED', 0)
      return {
        body: {
          provider,
          ok: false,
          latency_ms: 0,
          status: 'NOT_CONFIGURED',
          detail: 'Chưa khai Base URL cho nhà cung cấp này nên không kiểm tra được.',
          method: null,
          url: null,
        },
      }
    }
    // Mock không gọi mạng: mô phỏng kết quả tất định, ghi rõ trong phần diễn giải để không ngộ nhận.
    if (OPENAI_COMPATIBLE.has(provider)) {
      const latency = 40 + (provider.length % 7) * 3
      record('OK', latency)
      return {
        body: {
          provider,
          ok: true,
          latency_ms: latency,
          status: 'OK',
          detail: 'Kết nối thành công qua GET /models (mô phỏng trong mock — backend thật sẽ gọi nhà cung cấp).',
          method: 'GET /models',
          url: `${baseUrl.replace(/\/$/, '')}/models`,
        },
      }
    }
    record('UNSUPPORTED', 12)
    return {
      body: {
        provider,
        ok: false,
        latency_ms: 12,
        status: 'UNSUPPORTED',
        detail:
          'Không kiểm tra tự động được với nhà cung cấp này (endpoint kiểm tra không mở). Cách kiểm bằng tay: bấm nút “Đọc” một câu trả lời ngắn trong workspace Sale. (mô phỏng trong mock)',
        method: null,
        url: baseUrl,
      },
    }
  }),
]

/**
 * Đường **đọc thành tiếng qua nhà cung cấp** — bản mock song song với `src/api/endpoints/tts_speak.py`.
 *
 * Mock chạy offline nên trả một đoạn WAV ngắn cố định (không gọi mạng), nhưng giữ đúng hành vi quan
 * trọng của backend thật: trình duyệt thì KHÔNG đi đường này; thiếu khoá/chưa nối adapter thì nói thật;
 * chi phí quy theo ký tự và ghi vào nhật ký để tab “Chi phí & hiệu năng” cộng đúng.
 */
const MOCK_AUDIO_BASE64 =
  'UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAABErAAABAAgAZGF0YQAAAAA='  // WAV im lặng, đủ để trình phát chạy

const UNWIRED = new Set(['google_cloud', 'azure', 'viettel', 'vbee', 'fpt'])

export const ttsSpeakHandlers = [
  route('ttsQuota', () => {
    const used = getProviderRows().length ? 0 : 0  // mock không giới hạn; số liệu thật nằm ở backend
    return { body: { daily_budget: 300_000, chars_today: used, remaining: 300_000 } }
  }),

  route('ttsSpeak', async ({ json }) => {
    const body = await json<{ text?: string; provider?: string; voice?: string; summary_only?: boolean }>()
    const text = (body?.text ?? '').trim()
    if (!text) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Không có nội dung để đọc.')

    const catalog = effectiveCatalog()
    const wanted = (body?.provider ?? 'browser').trim().toLowerCase()
    const entry = catalog.find((c) => c.provider === wanted)
    if (!entry) throw new MockError(422, 'INPUT_VALIDATION_ERROR', `Nhà cung cấp TTS '${wanted}' không có trong danh mục.`)
    if (entry.mode === 'browser') {
      throw new MockError(
        409,
        'BROWSER_PROVIDER',
        'Nhà cung cấp đang chọn là giọng trình duyệt — giao diện đọc trực tiếp tại máy, không gửi qua backend.',
      )
    }
    // Khoá lấy từ DB trước, rồi tới ENV; mock không cấu hình ENV nào ⇒ nhà cung cấp dựng sẵn chưa nhập khoá
    // thì phải nói thật là thiếu khoá (đúng như backend thật).
    const hasKey = (entry.key_source ?? 'none') !== 'none'
    if (!hasKey) {
      throw new MockError(
        503,
        'MISSING_KEY',
        `Chưa có khoá cho ${entry.label}. Nhập khoá trong Quản trị CP → Giọng đọc → Nhà cung cấp TTS.`,
      )
    }
    if (!entry.custom && UNWIRED.has(entry.provider)) {
      throw new MockError(
        501,
        'ADAPTER_NOT_WIRED',
        `Chưa nối adapter tổng hợp audio cho ${entry.label} (${entry.provider}). Hiện chạy được: OpenAI và máy chủ/gateway theo giao thức OpenAI-compatible.`,
      )
    }

    // Cắt theo hạn mức ký tự như backend (mock lấy mặc định 600) — đủ để UI thấy số ký tự thật.
    const spoken = body?.summary_only ? text.slice(0, 240) : text.slice(0, 600)
    const chars = spoken.length
    const cost = Math.round((chars / 1_000_000) * entry.price_per_1m_chars * 1e6) / 1e6
    const latency = 320 + (chars % 30) * 4
    recordMockTtsCall(entry.provider, body?.voice ?? entry.voices[0]?.code ?? '', chars, cost, latency)
    return {
      body: {
        provider: entry.provider,
        voice: body?.voice ?? entry.voices[0]?.code ?? '',
        model: entry.default_model,
        mime: 'audio/wav',
        audio_base64: MOCK_AUDIO_BASE64,
        chars,
        cached: false,
        cost,
        currency: entry.currency,
        latency_ms: latency,
        quota: { daily_budget: 300_000, chars_today: chars, remaining: 300_000 - chars },
      },
    }
  }),
]
