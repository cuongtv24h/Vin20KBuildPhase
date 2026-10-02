// @vitest-environment node
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { api } from '@pricepolicy/api-client/client'
import { setAuthTokenProvider } from '@pricepolicy/api-client/http'
import { isSpeechSupported, speakText, toSpeakableText } from '@pricepolicy/ui/lib/speech'
import { resetDb } from './db'
import { server } from './node'

/**
 * Đọc câu trả lời thành tiếng (TTS):
 *  - hợp đồng API thiết lập giọng đọc (mặc định hệ thống vs hồ sơ riêng, quyền đổi mặc định);
 *  - hàm dọn văn bản trước khi đọc (không đọc cả markdown/citation);
 *  - hành vi khi môi trường **không** có Web Speech API (Node) — phải nói rõ lý do, không im lặng.
 */

let token: string | null = null
setAuthTokenProvider(() => token)

const PASSWORD = 'Vland@2026'
const SALE = 'nam.hoang@vlandfuture.vn'
const MANAGER = 'ha.nguyen@vlandfuture.vn'

async function loginAs(email: string) {
  token = (await api.auth.login({ email, password: PASSWORD })).access_token
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterAll(() => server.close())
beforeEach(async () => {
  await resetDb()
  token = null
})

describe('Thiết lập giọng đọc (TTS)', () => {
  it('mặc định là giọng trình duyệt, 0 đồng, và danh mục có nhà cung cấp tiếng Việt', async () => {
    await loginAs(SALE)
    const res = await api.tts.settings()
    expect(res.effective.provider).toBe('browser')
    expect(res.cost_hint.cost).toBe(0)
    expect(res.user_override).toBeNull()
    expect(res.default.is_explicit).toBe(false)
    const providers = res.catalog.map((c) => c.provider)
    expect(providers).toContain('google_cloud')
    expect(providers).toContain('viettel')
    // Chưa khai báo khoá thì phải nói thật là chưa có, để UI không hứa hão.
    expect(res.catalog.find((c) => c.provider === 'openai')?.api_key_configured).toBe(false)
    expect(res.catalog.find((c) => c.provider === 'browser')?.api_key_configured).toBe(true)
    // Đơn giá đi kèm mốc kiểm chứng, không phải con số vô chủ.
    expect(res.catalog.find((c) => c.provider === 'viettel')?.price_per_1m_chars).toBe(320_000)
  })

  it('hồ sơ riêng thắng mặc định, Sale không đổi được mặc định, MANAGER thì được', async () => {
    await loginAs(SALE)
    const saved = await api.tts.updateSettings({ scope: 'user', provider: 'google_cloud', voice: 'vi-VN-Wavenet-A', speed: 1.2 })
    expect(saved.effective.voice).toBe('vi-VN-Wavenet-A')
    expect(saved.cost_hint.provider).toBe('google_cloud')
    expect(saved.cost_hint.cost).toBeGreaterThan(0)

    await expect(api.tts.updateSettings({ scope: 'default', provider: 'viettel' })).rejects.toMatchObject({ status: 403 })

    await loginAs(MANAGER)
    const asDefault = await api.tts.updateSettings({ scope: 'default', provider: 'viettel', voice: 'hn_female_ngochuyen' })
    expect(asDefault.default.is_explicit).toBe(true)
    expect(asDefault.effective.provider).toBe('viettel')
    // Mặc định dùng chung không ghi đè hồ sơ riêng của Sale.
    await loginAs(SALE)
    expect((await api.tts.settings()).effective.provider).toBe('google_cloud')
  })

  it('từ chối cấu hình sai và ghi nhận phản hồi giọng đọc', async () => {
    await loginAs(SALE)
    await expect(api.tts.updateSettings({ provider: 'khong-co-that' })).rejects.toMatchObject({ status: 422 })
    await expect(api.tts.updateSettings({ speed: 5 })).rejects.toMatchObject({ status: 422 })

    await api.tts.feedback({ rating: 1, reason: 'Nghe rõ' })
    await api.tts.feedback({ rating: -1, reason: 'Hơi nhanh' })
    const res = await api.tts.settings()
    expect(res.feedback_summary).toMatchObject({ total: 2, up: 1, down: 1, satisfaction: 0.5 })
  })
})

describe('Dọn văn bản trước khi đọc', () => {
  it('bỏ markdown, citation và emoji — giữ nội dung nghiệp vụ', () => {
    const raw = '**Dạ**, căn ZEN-A-1205 còn hàng (Điều 4, Khoản 2b) · xem [chính sách](https://x.vn) ✅'
    const clean = toSpeakableText(raw)
    expect(clean).toBe('Dạ, căn ZEN-A-1205 còn hàng , · xem chính sách')
    expect(clean).not.toContain('*')
    expect(clean).not.toContain('http')
  })

  it('không có Web Speech API (Node) → trả lý do rõ ràng thay vì im lặng', () => {
    expect(isSpeechSupported()).toBe(false)
    const errors: string[] = []
    const result = speakText('Xin chào', { onError: (r) => errors.push(r) })
    expect(result.ok).toBe(false)
    expect(errors[0]).toContain('không hỗ trợ đọc thành tiếng')
    // Câu rỗng cũng phải báo lý do, không treo.
    const empty = speakText('   ')
    expect(empty.ok).toBe(false)
  })
})
