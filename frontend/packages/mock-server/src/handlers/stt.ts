import { MockError } from '../services/errors'
import { route } from './route'

/**
 * Nghe-nói (STT) — bản mock song song với `src/api/endpoints/stt.py`.
 *
 * Mock KHÔNG nhận dạng âm thanh thật (không có Whisper trong Node): nó trả transcript dựng sẵn để
 * frontend chạy được trọn luồng "bấm micro → nói → chữ hiện trong ô hỏi → gửi Copilot" khi dev/demo
 * không có backend. Vì vậy:
 * - `sttHealth` báo Groq **đã cấu hình** (mô phỏng) để UI đi đường ghi âm → upload, thay vì rơi về
 *   Web Speech API ngay và không bao giờ chạy thử được đường mới;
 * - `provider: 'mock'` ghi rõ trong phản hồi để không ai tưởng đây là kết quả Whisper thật;
 * - hạn mức đếm bằng biến module: `resetDb()` KHÔNG xoá nó (trạng thái nằm ngoài db) — chấp nhận được
 *   vì mock chỉ phục vụ UI, số liệu này không dùng để suy ra hành vi backend thật.
 */

/** Số phút audio "đã dùng" trong ngày — chỉ để UI hiển thị hạn mức, không liên quan dữ liệu seed. */
let minutesUsedToday = 0

const DAILY_BUDGET_MINUTES = 60

/** Transcript dựng sẵn: đúng loại câu Sale hỏi Copilot, có mã căn để thấy lớp chuẩn hoá hoạt động. */
const CANNED_TRANSCRIPTS = [
  { text: 'Khách hỏi căn zen a 1205 còn không, kpbt bao nhiêu', normalized_text: 'Khách hỏi căn ZEN-A-1205 còn không, KPBT bao nhiêu' },
  { text: 'Soạn hồ sơ đề xuất cho căn zen a 0803, vốn tự có 1 chấm 5 tỷ', normalized_text: 'Soạn hồ sơ đề xuất cho căn ZEN-A-0803, vốn tự có 1,5 tỷ' },
  { text: 'Chính sách chiết khấu thanh toán sớm hiện tại là bao nhiêu phần trăm', normalized_text: 'Chính sách chiết khấu thanh toán sớm hiện tại là bao nhiêu phần trăm' },
]

let callCount = 0

/** Cấu hình nhà cung cấp do "ADMIN" dán trong mock — nằm ngoài db nên không bị `resetDb()` xoá. */
const providerRows = new Map<string, Record<string, unknown>>()

function quota() {
  return {
    daily_budget_minutes: DAILY_BUDGET_MINUTES,
    minutes_today: minutesUsedToday,
    seconds_today: minutesUsedToday * 60,
    remaining_minutes: Math.max(0, DAILY_BUDGET_MINUTES - minutesUsedToday),
  }
}

function health() {
  const groqRow = providerRows.get('groq') ?? {}
  // Mock mặc định coi như ADMIN đã dán khoá (để UI chạy được đường ghi âm → upload); chỉ tắt khi bản ghi DB nói `has_api_key: false`.
  const groqConfigured = groqRow.has_api_key !== false
  return {
    enabled: true,
    preferred: 'groq',
    language: 'vi',
    chain: [
      {
        provider: 'groq',
        label: 'Groq Whisper (LPU) — MÔ PHỎNG',
        model: String(groqRow.default_model ?? 'whisper-large-v3-turbo'),
        configured: groqConfigured,
        active: groqRow.is_active !== false,
        key_source: groqRow.has_api_key === true ? 'db' : 'env',
        api_key_masked: String(groqRow.api_key_masked ?? 'gsk…mock'),
        zero_data_retention: Boolean(groqRow.zero_data_retention ?? false),
        price_per_hour_audio: 0.04,
        currency: 'USD',
      },
      {
        provider: 'browser',
        label: 'Trình duyệt (Web Speech API)',
        model: '',
        configured: true,
        active: true,
        key_source: 'none',
        api_key_masked: '',
        zero_data_retention: false,
        price_per_hour_audio: 0,
        currency: 'USD',
      },
    ],
    active_chain: groqRow.is_active !== false ? ['groq'] : [],
    browser_fallback: true,
    quota: quota(),
    limits: {
      max_bytes: 10_000_000,
      max_duration_seconds: 120,
      accepted_content_types: ['audio/webm', 'audio/ogg', 'audio/wav', 'audio/mp4', 'audio/mpeg', 'audio/flac'],
    },
    warnings: groqRow.zero_data_retention
      ? []
      : [
          'Bản mock: Groq chưa khai báo Zero Data Retention. Bản thật bật ở Console → Data Controls rồi đặt STT_ZERO_DATA_RETENTION=true.',
        ],
  }
}

export const sttHandlers = [
  /** Gửi audio micro lên, nhận CHỮ (mock: transcript dựng sẵn, không nhận dạng thật). */
  route('sttTranscribe', async ({ staff }) => {
    if (!staff()) throw new MockError(401, 'UNAUTHORIZED', 'Cần đăng nhập để dùng nghe-nói.')
    if (minutesUsedToday >= DAILY_BUDGET_MINUTES) {
      throw new MockError(429, 'STT_QUOTA_EXCEEDED', 'Đã hết hạn mức nghe-nói trong ngày (mock).')
    }
    const canned = CANNED_TRANSCRIPTS[callCount % CANNED_TRANSCRIPTS.length]
    callCount += 1
    minutesUsedToday = Math.min(DAILY_BUDGET_MINUTES, minutesUsedToday + 1)
    return {
      body: {
        text: canned.text,
        normalized_text: canned.normalized_text,
        language: 'vi',
        provider: 'mock',
        model: 'mock-whisper',
        latency_ms: 380,
        audio_bytes: 48_000,
        estimated_seconds: 12,
        quota: quota(),
        fallback_used: false,
        warnings: ['Bản mock trả transcript dựng sẵn — không có nhận dạng âm thanh thật.'],
      },
    }
  }),

  route('sttHealth', async () => ({ body: health() })),

  route('sttQuota', async () => ({ body: quota() })),
]

export const sttAdminHandlers = [
  route('sttProviders', async ({ staff }) => {
    if (staff()?.role !== 'ADMIN') throw new MockError(403, 'FORBIDDEN', 'Chỉ quản trị viên cấu hình được nhà cung cấp nghe-nói.')
    return {
      body: {
        catalog: health().chain.map((link) => ({ ...link, provider_id: `STT-${link.provider}`, has_api_key: true, source: 'env' })),
        db_rows: [...providerRows.entries()].map(([provider, row]) => ({ provider_id: `STT-${provider}`, provider, source: 'db', ...row })),
        effective_chain: health().active_chain,
        db_overrides: [...providerRows.keys()],
      },
    }
  }),

  route('sttProviderUpdate', async ({ staff, params, json }) => {
    if (staff()?.role !== 'ADMIN') throw new MockError(403, 'FORBIDDEN', 'Chỉ quản trị viên cấu hình được nhà cung cấp nghe-nói.')
    const provider = String(params.provider ?? '').trim().toLowerCase()
    if (!provider) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Mã nhà cung cấp không được để trống.')
    const body = (await json<Record<string, unknown>>()) ?? {}
    const existing = providerRows.get(provider) ?? {}
    const apiKey = typeof body.api_key === 'string' ? body.api_key.trim() : undefined
    const next: Record<string, unknown> = {
      ...existing,
      provider,
      label: String(body.label ?? existing.label ?? provider),
      mode: 'api',
      base_url: String(body.base_url ?? existing.base_url ?? ''),
      default_model: String(body.model ?? existing.default_model ?? 'whisper-large-v3-turbo'),
      language: String(body.language ?? existing.language ?? 'vi'),
      priority: Number(body.priority ?? existing.priority ?? 10),
      is_active: body.is_active === undefined ? existing.is_active !== false : Boolean(body.is_active),
      zero_data_retention: body.zero_data_retention === undefined ? Boolean(existing.zero_data_retention) : Boolean(body.zero_data_retention),
      prompt_bias: String(body.prompt_bias ?? existing.prompt_bias ?? ''),
      has_api_key: apiKey === undefined ? Boolean(existing.has_api_key) : apiKey.length > 0,
      api_key_masked: apiKey ? `${apiKey.slice(0, 3)}…${apiKey.slice(-4)}` : String(existing.api_key_masked ?? ''),
      source: 'db',
    }
    providerRows.set(provider, next)
    return { body: { provider_id: `STT-${provider}`, ...next } }
  }),

  route('sttProviderDelete', async ({ staff, params }) => {
    if (staff()?.role !== 'ADMIN') throw new MockError(403, 'FORBIDDEN', 'Chỉ quản trị viên cấu hình được nhà cung cấp nghe-nói.')
    const provider = String(params.provider ?? '').trim().toLowerCase()
    if (!providerRows.has(provider)) {
      throw new MockError(404, 'NOT_FOUND', `Không có bản ghi DB nào cho nhà cung cấp '${provider}'.`)
    }
    providerRows.delete(provider)
    return { body: { status: 'deleted', provider } }
  }),

  route('sttProviderTest', async ({ staff, params }) => {
    if (staff()?.role !== 'ADMIN') throw new MockError(403, 'FORBIDDEN', 'Chỉ quản trị viên cấu hình được nhà cung cấp nghe-nói.')
    const provider = String(params.provider ?? '').trim().toLowerCase()
    return {
      body: {
        provider,
        ok: true,
        model: provider === 'browser' ? '' : 'whisper-large-v3-turbo',
        latency_ms: 295,
        detail: 'Bản mock: không gọi nhà cung cấp thật. Bản thật gửi 1 giây im lặng để kiểm tra khoá/URL/model.',
        tested_by: staff()?.user_id ?? '',
      },
    }
  }),
]
