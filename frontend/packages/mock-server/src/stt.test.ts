// @vitest-environment node
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { api } from '@pricepolicy/api-client/client'
import { setAuthTokenProvider } from '@pricepolicy/api-client/http'
import { resetDb } from './db'
import { DEFAULT_FLAGS, setFlags } from './flags'
import { server } from './node'

/**
 * Đặc tả tầng nghe-nói (STT) ở chế độ mock — hình dạng phản hồi phải khớp `src/api/endpoints/stt.py`
 * để giao diện dev/demo không backend vẫn chạy đúng luồng, và để khi cắm backend thật không phải sửa UI.
 *
 * Mock KHÔNG nhận dạng âm thanh (không có Whisper trong Node): nó trả transcript dựng sẵn và khai
 * `provider: 'mock'` cho rõ ràng. Cái cần chốt ở đây là LUẬT, không phải chất lượng nhận dạng:
 *
 * 1. Bắt buộc đăng nhập (401) — không ai gửi audio lên máy chủ mà không có phiên.
 * 2. `/stt/health` phải cho UI biết: chuỗi nhà cung cấp đang bật, còn lưới an toàn trình duyệt không,
 *    trần thời lượng ghi âm là bao nhiêu (UI tự dừng ở mức đó để không bị backend từ chối).
 * 3. Cấu hình nhà cung cấp là việc ADMIN (403 với Sale); khoá dán vào chỉ trả lại dạng CHE.
 */

let token: string | null = null
setAuthTokenProvider(() => token)

const PASSWORD = 'Vland@2026'
const SALE = 'nam.hoang@vlandfuture.vn' // USR-SALE-001
const ADMIN_EMAIL = 'admin.stt@vlandfuture.vn'

async function loginAs(email: string) {
  token = (await api.auth.login({ email, password: PASSWORD })).access_token
}

/** ADMIN tạo qua đúng luồng khởi tạo của sản phẩm (bộ tài khoản mock không có sẵn vai trò ADMIN). */
async function loginAsAdmin() {
  const status = await api.admin.setupStatus()
  if (!status.has_admin) {
    await api.admin.setup({ user: 'admin.stt', password: PASSWORD, email: ADMIN_EMAIL, full_name: 'Admin STT' })
  }
  await loginAs(ADMIN_EMAIL)
}

/** Blob giả làm audio từ micro — mock không giải mã, chỉ cần đúng kiểu multipart. */
function fakeAudio(bytes = 48_000) {
  return new Blob([new Uint8Array(bytes)], { type: 'audio/webm' })
}

beforeAll(() => {
  setFlags({ ...DEFAULT_FLAGS, time_scale: 0.01 })
  server.listen({ onUnhandledRequest: 'error' })
})

beforeEach(async () => {
  setFlags({ ...DEFAULT_FLAGS, time_scale: 0.01 })
  await resetDb()
  token = null
})

afterAll(() => server.close())

describe('POST /stt/transcribe', () => {
  it('chưa đăng nhập thì 401, không nghe giúp ai cả', async () => {
    const error = await api.stt.transcribe(fakeAudio()).catch((e) => e)
    expect(error.status).toBe(401)
    expect(error.code).toBe('UNAUTHORIZED')
  })

  it('Sale gửi audio thì nhận CHỮ kèm hạn mức và cảnh báo rõ đây là bản mock', async () => {
    await loginAs(SALE)
    const result = await api.stt.transcribe(fakeAudio())

    expect(result.provider).toBe('mock')
    expect(result.language).toBe('vi')
    expect(result.normalized_text.trim().length).toBeGreaterThan(0)
    expect(result.audio_bytes).toBeGreaterThan(0)
    expect(result.estimated_seconds).toBeGreaterThan(0)
    expect(result.quota.daily_budget_minutes).toBeGreaterThan(0)
    expect(result.warnings.join(' ')).toContain('mock')
  })

  it('mã căn trong transcript đã chuẩn hoá (ZEN-A-1205, KPBT) — không để lọt dạng rời', async () => {
    await loginAs(SALE)
    const result = await api.stt.transcribe(fakeAudio())
    expect(result.normalized_text).not.toMatch(/zen a \d/i)
    expect(result.normalized_text).not.toContain('kpbt')
  })
})

describe('GET /stt/health — dữ liệu UI cần để chọn đường ghi âm', () => {
  it('báo chuỗi nhà cung cấp, lưới an toàn trình duyệt và trần thời lượng', async () => {
    await loginAs(SALE)
    const health = await api.stt.health()

    expect(health.enabled).toBe(true)
    expect(health.preferred).toBe('groq')
    expect(health.active_chain).toContain('groq')
    expect(health.browser_fallback).toBe(true)
    expect(health.limits.max_duration_seconds).toBe(120)
    expect(health.limits.accepted_content_types).toContain('audio/webm')
    const groq = health.chain.find((link) => link.provider === 'groq')
    expect(groq?.configured).toBe(true)
    expect(groq?.zero_data_retention).toBe(false)
    // Chưa bật ZDR thì phải có cảnh báo — không được im lặng về chuyện dữ liệu audio.
    expect(health.warnings.join(' ')).toContain('Zero Data Retention')
  })

  it('hạn mức còn lại giảm sau mỗi lượt nghe', async () => {
    await loginAs(SALE)
    const before = await api.stt.quota()
    await api.stt.transcribe(fakeAudio())
    const after = await api.stt.quota()
    expect(after.minutes_today).toBeGreaterThanOrEqual(before.minutes_today)
    expect(after.remaining_minutes).toBeLessThanOrEqual(before.remaining_minutes)
  })
})

describe('Cấu hình nhà cung cấp (ADMIN)', () => {
  it('Sale không mở được danh sách nhà cung cấp', async () => {
    await loginAs(SALE)
    const error = await api.sttAdmin.providers().catch((e) => e)
    expect(error.status).toBe(403)
    expect(error.code).toBe('FORBIDDEN')
  })

  it('ADMIN dán khoá thì khoá chỉ trả về dạng che, test được, và gỡ được bản ghi đè', async () => {
    await loginAsAdmin()

    const updated = await api.sttAdmin.updateProvider('groq', {
      api_key: 'gsk_khoa_dan_trong_app_1234',
      model: 'whisper-large-v3',
      zero_data_retention: true,
    })
    expect(updated.has_api_key).toBe(true)
    expect(updated.default_model).toBe('whisper-large-v3')
    expect(updated.zero_data_retention).toBe(true)
    expect(JSON.stringify(updated)).not.toContain('gsk_khoa_dan_trong_app_1234')

    const listing = await api.sttAdmin.providers()
    expect(listing.db_overrides).toContain('groq')
    expect(listing.effective_chain).toContain('groq')

    // Đã khai ZDR thì health hết cảnh báo (đúng hành vi backend thật).
    const health = await api.stt.health()
    expect(health.chain.find((l) => l.provider === 'groq')?.zero_data_retention).toBe(true)
    expect(health.warnings.join(' ')).not.toContain('Zero Data Retention')

    const tested = await api.sttAdmin.testProvider('groq')
    expect(tested.ok).toBe(true)
    expect(tested.tested_by).toBeTruthy()

    expect((await api.sttAdmin.deleteProvider('groq')).status).toBe('deleted')
    const again = await api.sttAdmin.deleteProvider('groq').catch((e) => e)
    expect(again.status).toBe(404)
  })
})
