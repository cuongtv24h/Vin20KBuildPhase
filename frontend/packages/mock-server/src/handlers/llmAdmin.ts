import type { LlmProvider, LlmUsageRecord, LlmUsageSummary } from '@pricepolicy/api-client/contracts'
import { onReset } from '../db'
import { MockError, notFound } from '../services/errors'
import { route } from './route'

/**
 * Quản trị nhà cung cấp LLM + đo chi phí/hiệu năng — bản mock song song với
 * `src/api/endpoints/llm_admin.py`.
 *
 * Nguyên tắc giống backend thật:
 * - API key **không** bao giờ trả về nguyên văn (chỉ `sk-…abcd`), lưu trữ mô phỏng bằng biến trong
 *   tiến trình mock.
 * - Có nhà cung cấp trong "DB" → dùng DB; trống → rơi về ENV (`source: 'env'`).
 * - Lượt gọi LLM được ghi log kèm chi phí quy từ đơn giá (token vào/ra × đơn giá/1M).
 *
 * Vì mock chạy offline (không gọi LLM thật), log usage được **giả lập tất định** mỗi khi Sale chat
 * Copilot để tab "Chi phí & hiệu năng" có số thật để tính, thay vì bảng rỗng.
 */

let providers: LlmProvider[] = []
let usage: LlmUsageRecord[] = []
/** Bộ đếm lệnh gọi — dùng để mô phỏng token/latency tất định thay vì random. */
let callCounter = 0
/** Bộ đếm id nhà cung cấp (mock không cần trùng id với backend thật). */
let providerSeq = 0

onReset(() => {
  providers = []
  usage = []
  callCounter = 0
  providerSeq = 0
})

const mask = (key: string) => (key.length <= 8 ? '•'.repeat(key.length) : `${key.slice(0, 4)}…${key.slice(-4)}`)

const cost = (record: Omit<LlmUsageRecord, 'cost'>) =>
  Math.round(
    ((record.input_tokens / 1_000_000) * (providers[0]?.input_price_per_1m ?? 0.15) +
      (record.output_tokens / 1_000_000) * (providers[0]?.output_price_per_1m ?? 0.6)) *
      1e6,
  ) / 1e6

/** Ghi một lượt gọi LLM (mock dùng khi Sale chat) — chi phí tính theo đơn giá provider đầu tiên. */
export function recordMockLlmCall(provider: string, model: string, inputTokens: number, outputTokens: number, latencyMs: number, ok = true) {
  callCounter += 1
  const base = {
    at: new Date().toISOString(),
    provider,
    model_name: model,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    latency_ms: Math.round(latencyMs * 100) / 100,
    ok,
    error: ok ? null : 'MOCK_TIMEOUT',
    is_fallback: callCounter % 7 === 0,
    currency: 'USD',
    conversation_id: null,
    user_id: null,
  }
  usage = [...usage, { ...base, cost: cost(base) }].slice(-500)
}

const percentile = (values: number[], pct: number) =>
  values.length ? [...values].sort((a, b) => a - b)[Math.min(Math.floor(values.length * pct), values.length - 1)] : 0

function summary(days: number): LlmUsageSummary {
  const cutoff = Date.now() - days * 86_400_000
  const records = usage.filter((r) => new Date(r.at).getTime() >= cutoff)
  const okLatencies = records.filter((r) => r.ok).map((r) => r.latency_ms)
  const totalIn = records.reduce((s, r) => s + r.input_tokens, 0)
  const totalOut = records.reduce((s, r) => s + r.output_tokens, 0)
  const totalCost = Math.round(records.reduce((s, r) => s + r.cost, 0) * 1e6) / 1e6
  const byProviderMap = new Map<string, LlmUsageSummary['by_provider'][number]>()
  for (const r of records) {
    const key = `${r.provider}::${r.model_name}`
    const bucket =
      byProviderMap.get(key) ??
      {
        provider: r.provider,
        model_name: r.model_name,
        calls: 0,
        failed_calls: 0,
        input_tokens: 0,
        output_tokens: 0,
        cost: 0,
        avg_latency_ms: 0,
        p95_latency_ms: 0,
        error_rate: 0,
      }
    bucket.calls += 1
    if (!r.ok) bucket.failed_calls += 1
    bucket.input_tokens += r.input_tokens
    bucket.output_tokens += r.output_tokens
    bucket.cost = Math.round((bucket.cost + r.cost) * 1e6) / 1e6
    byProviderMap.set(key, bucket)
  }
  for (const bucket of byProviderMap.values()) {
    const mine = records.filter((r) => r.provider === bucket.provider && r.model_name === bucket.model_name && r.ok).map((r) => r.latency_ms)
    bucket.avg_latency_ms = mine.length ? Math.round((mine.reduce((a, b) => a + b, 0) / mine.length) * 100) / 100 : 0
    bucket.p95_latency_ms = percentile(mine, 0.95)
    bucket.error_rate = bucket.calls ? Math.round((bucket.failed_calls / bucket.calls) * 1e4) / 1e4 : 0
  }
  const byDayMap = new Map<string, { day: string; calls: number; cost: number; tokens: number }>()
  for (const r of records) {
    const day = r.at.slice(0, 10)
    const slot = byDayMap.get(day) ?? { day, calls: 0, cost: 0, tokens: 0 }
    slot.calls += 1
    slot.cost = Math.round((slot.cost + r.cost) * 1e6) / 1e6
    slot.tokens += r.input_tokens + r.output_tokens
    byDayMap.set(day, slot)
  }
  return {
    window_days: days,
    total_calls: records.length,
    failed_calls: records.filter((r) => !r.ok).length,
    error_rate: records.length ? Math.round((records.filter((r) => !r.ok).length / records.length) * 1e4) / 1e4 : 0,
    total_input_tokens: totalIn,
    total_output_tokens: totalOut,
    total_tokens: totalIn + totalOut,
    total_cost: totalCost,
    currency: 'USD',
    p50_latency_ms: percentile(okLatencies, 0.5),
    p95_latency_ms: percentile(okLatencies, 0.95),
    avg_cost_per_call: records.length ? Math.round((totalCost / records.length) * 1e6) / 1e6 : 0,
    by_provider: [...byProviderMap.values()].sort((a, b) => b.cost - a.cost),
    by_day: [...byDayMap.values()].sort((a, b) => a.day.localeCompare(b.day)),
  }
}

/**
 * Hai nhà cung cấp “có sẵn từ biến môi trường” của mock — song song với `ENV · primary` /
 * `ENV · fallback 1` mà backend thật dựng từ `OPENAI_API_KEY` + `FALLBACK1_OPENAI_API_KEY`.
 * Chỉ để HIỂN THỊ (chỉ-đọc) và để “Test kết nối” chạy được, không sửa/xoá được từ giao diện.
 */
const ENV_PROVIDERS = [
  {
    provider_id: 'ENV-PRIMARY',
    name: 'ENV · primary',
    provider: 'openai',
    base_url: 'https://api.openai.com/v1',
    model_name: 'gpt-4o-mini',
    api_key_masked: 'sk-e…0001',
    has_api_key: true,
    priority: 0,
    is_fallback: false,
    source: 'env',
  },
  {
    provider_id: 'ENV-FALLBACK-1',
    name: 'ENV · fallback 1',
    provider: 'openai',
    base_url: 'https://api.deepseek.com/v1',
    model_name: 'deepseek-chat',
    api_key_masked: 'sk-e…0002',
    has_api_key: true,
    priority: 1,
    is_fallback: true,
    source: 'env',
  },
]

export const llmAdminHandlers = [
  route('llmProviders', () => ({
    body: {
      source: providers.length ? 'db' : 'env',
      total: providers.length,
      items: providers,
      // Nhà cung cấp ENV luôn hiện (chỉ-đọc) để màn hình nói đủ sự thật; khi đã khai báo trong DB thì
      // đánh dấu là đã bị bản ghi DB thay thế.
      env_items: ENV_PROVIDERS.map((item) => ({
        ...item,
        overridden_by_db: providers.some((p) => p.provider === item.provider),
      })),
    },
  })),

  route('llmProviderCreate', async ({ json, now }) => {
    const body = await json<Partial<LlmProvider> & { api_key?: string }>()
    if (!body?.name || !body?.model_name) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Thiếu tên hoặc model.')
    if (!body.api_key?.trim()) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Cần nhập API key.')
    const provider: LlmProvider = {
      provider_id: `LLM-${String((providerSeq += 1)).padStart(4, '0')}`,
      name: body.name.trim(),
      provider: (body.provider ?? 'openai').toLowerCase(),
      base_url: body.base_url?.trim() || null,
      model_name: body.model_name.trim(),
      api_key_masked: mask(body.api_key.trim()),
      has_api_key: true,
      input_price_per_1m: Number(body.input_price_per_1m ?? 0),
      output_price_per_1m: Number(body.output_price_per_1m ?? 0),
      currency: (body.currency ?? 'USD').toUpperCase(),
      temperature: Number(body.temperature ?? 0.2),
      priority: Number(body.priority ?? 10),
      is_active: body.is_active ?? true,
      last_test_status: null,
      last_test_latency_ms: null,
      last_tested_at: null,
      created_at: new Date(now).toISOString(),
      updated_at: new Date(now).toISOString(),
    }
    providers = [...providers, provider]
    return { status: 201, body: provider }
  }),

  route('llmProviderUpdate', async ({ params, json, now }) => {
    const body = await json<Partial<LlmProvider> & { api_key?: string | null }>()
    const existing = providers.find((p) => p.provider_id === params.provider_id)
    if (!existing) throw notFound(`nhà cung cấp ${params.provider_id}`)
    const updated: LlmProvider = {
      ...existing,
      name: body?.name?.trim() ?? existing.name,
      provider: (body?.provider ?? existing.provider).toLowerCase(),
      base_url: body?.base_url?.trim() || null,
      model_name: body?.model_name?.trim() ?? existing.model_name,
      api_key_masked: body?.api_key?.trim() ? mask(body.api_key.trim()) : existing.api_key_masked,
      has_api_key: body?.api_key?.trim() ? true : existing.has_api_key,
      input_price_per_1m: Number(body?.input_price_per_1m ?? existing.input_price_per_1m),
      output_price_per_1m: Number(body?.output_price_per_1m ?? existing.output_price_per_1m),
      currency: (body?.currency ?? existing.currency).toUpperCase(),
      temperature: Number(body?.temperature ?? existing.temperature),
      priority: Number(body?.priority ?? existing.priority),
      is_active: body?.is_active ?? existing.is_active,
      updated_at: new Date(now).toISOString(),
    }
    providers = providers.map((p) => (p.provider_id === existing.provider_id ? updated : p))
    return { body: updated }
  }),

  route('llmProviderDelete', ({ params }) => {
    if (!providers.some((p) => p.provider_id === params.provider_id)) throw notFound(`nhà cung cấp ${params.provider_id}`)
    providers = providers.filter((p) => p.provider_id !== params.provider_id)
    return { body: { ok: true, provider_id: params.provider_id } }
  }),

  route('llmProviderTest', ({ params }) => {
    // Nhà cung cấp đọc từ ENV cũng kiểm tra được (backend thật cũng vậy) — chỉ không ghi lịch sử.
    const envProvider = ENV_PROVIDERS.find((p) => p.provider_id === params.provider_id)
    if (envProvider) {
      return {
        body: {
          provider_id: envProvider.provider_id,
          ok: true,
          latency_ms: 140,
          status: 'OK',
          detail: 'Kết nối thành công với nhà cung cấp từ biến môi trường (mock — không gọi mạng thật).',
        },
      }
    }
    const provider = providers.find((p) => p.provider_id === params.provider_id)
    if (!provider) throw notFound(`nhà cung cấp ${params.provider_id}`)
    // Mock chạy offline: mô phỏng kết quả kiểm tra kết nối tất định (không gọi mạng thật).
    const ok = provider.has_api_key
    const latency = 120 + (provider.priority % 5) * 40
    provider.last_test_status = ok ? 'OK' : 'NOT_CONFIGURED'
    provider.last_test_latency_ms = latency
    provider.last_tested_at = new Date().toISOString()
    return {
      body: {
        provider_id: provider.provider_id,
        ok,
        latency_ms: latency,
        status: provider.last_test_status,
        detail: ok ? 'Kết nối thành công (mock — không gọi mạng thật).' : 'Chưa có API key.',
      },
    }
  }),

  route('llmUsageSummary', ({ query }) => {
    const days = Number(query.get('days') ?? 14)
    return { body: summary(Number.isFinite(days) && days > 0 ? days : 14) }
  }),

  route('llmUsageRecords', ({ query }) => {
    const limit = Number(query.get('limit') ?? 50)
    const items = [...usage].reverse().slice(0, Number.isFinite(limit) && limit > 0 ? limit : 50)
    return { body: { total: items.length, items } }
  }),
]
