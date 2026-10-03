// @vitest-environment node
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { api } from '@pricepolicy/api-client/client'
import { setAuthTokenProvider } from '@pricepolicy/api-client/http'
import { resetDb } from './db'
import { server } from './node'

/**
 * Đợt 22 — người dùng chốt: “Dùng sẵn cơ chế cũ đã có, cho phép thêm mới nhà cung cấp ngoài các nhà
 * cung cấp sẵn.”
 *
 * Bộ test khoá lại luồng quản trị nhà cung cấp TTS trên mock (đặc tả cho backend FastAPI thật):
 *  - nhập khoá trên giao diện (chỉ trả dạng che), thêm được nhà cung cấp NGOÀI danh mục dựng sẵn;
 *  - bản ghi đè cho nhà cung cấp dựng sẵn (giữ vị trí, đổi đơn giá/khoá), xoá thì quay về danh mục gốc;
 *  - nhà cung cấp mới xuất hiện ngay ở màn hình chọn giọng đọc và chọn được để đọc;
 *  - “Test kết nối” nói đúng sự thật (trình duyệt không cần khoá, thiếu khoá thì báo thiếu, nhà cung cấp
 *    không mở endpoint kiểm tra thì hướng dẫn kiểm bằng tay);
 *  - nhân viên thường không có quyền (403).
 */

let token: string | null = null
setAuthTokenProvider(() => token)

const PASSWORD = 'Vland@2026'
const ADMIN_EMAIL = 'admin.mock@vlandfuture.vn'
const SALE = 'nam.hoang@vlandfuture.vn'

async function loginAs(email: string) {
  token = (await api.auth.login({ email, password: PASSWORD })).access_token
}

async function loginAsAdmin() {
  const status = await api.admin.setupStatus()
  if (!status.initialized) {
    await api.admin.setup({ user: 'mockadmin', password: PASSWORD, email: ADMIN_EMAIL, phone: '0900 000 000' })
  }
  await loginAs(ADMIN_EMAIL)
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterAll(() => server.close())
beforeEach(async () => {
  await resetDb()
  token = null
})

const CUSTOM = {
  provider: 'vieneu',
  label: 'VieNeu TTS (tự dựng)',
  mode: 'api' as const,
  base_url: 'http://10.0.0.5:8080',
  default_model: 'vieneu-v3',
  env_key: 'VIENEU_TTS_TOKEN',
  price_per_1m_chars: 0,
  currency: 'VND',
  price_note: 'Máy chủ nội bộ — chi phí cố định, không tính theo ký tự.',
  verified_at: '2026-10-03',
  note: 'Dữ liệu không ra ngoài.',
  voices_text: 'vi-female-01 | Nữ miền Bắc | female\nvi-male-01 | Nam miền Bắc | male',
  supports_streaming: true,
  voice_cloning: true,
  api_key: 'tok-vieneu-1234',
  priority: 20,
  is_active: true,
}

describe('Admin quản trị nhà cung cấp TTS', () => {
  it('danh mục dựng sẵn hiện đủ, chưa khai báo gì thì nguồn là danh mục', async () => {
    await loginAsAdmin()
    const res = await api.ttsAdmin.providers()
    expect(res.source).toBe('builtin')
    const byProvider = Object.fromEntries(res.items.map((i) => [i.provider, i]))
    expect(Object.keys(byProvider)).toEqual(expect.arrayContaining(['browser', 'openai', 'google_cloud', 'viettel']))
    expect(byProvider.browser.api_key_configured).toBe(true)
    expect(byProvider.browser.key_source).toBe('browser')
    expect(byProvider.browser.has_db_row).toBe(false)
    expect(byProvider.browser.custom).toBe(false)
    // Mock không cấu hình khoá ENV nào ⇒ phải nói thật là chưa có (không hứa hão).
    expect(byProvider.openai.key_source).toBe('none')
    // Tên biến ENV vẫn hiển thị để quản trị viên biết đường lui DB → ENV.
    expect(byProvider.openai.env_key).toBe('OPENAI_API_KEY')
    expect(byProvider.viettel.api_key_configured).toBe(false)
    expect(byProvider.viettel.key_source).toBe('none')
  })

  it('thêm nhà cung cấp MỚI ngoài danh mục, khoá chỉ trả dạng che, và dùng được ngay để đọc', async () => {
    await loginAsAdmin()
    const created = await api.ttsAdmin.createProvider(CUSTOM)
    expect(created.provider_id).toMatch(/^TTS-/)
    expect(created.custom).toBe(true)
    expect(created.has_db_row).toBe(true)
    expect(created.api_key_configured).toBe(true)
    expect(created.key_source).toBe('db')
    expect(created.api_key_masked).toBe('tok-…1234')
    expect(created.voices.map((v) => v.code)).toEqual(['vi-female-01', 'vi-male-01'])
    // Khoá thô không bao giờ được trả ra ngoài.
    expect(JSON.stringify(created)).not.toContain('tok-vieneu-1234')

    const listing = await api.ttsAdmin.providers()
    expect(listing.source).toBe('db')
    expect(listing.items.at(-1)?.provider).toBe('vieneu')

    // Nhà cung cấp mới phải xuất hiện ở màn hình chọn giọng đọc và chọn được.
    const settings = await api.tts.settings()
    const entry = settings.catalog.find((c) => c.provider === 'vieneu')
    expect(entry?.custom).toBe(true)
    expect(entry?.api_key_configured).toBe(true)
    expect(entry?.key_source).toBe('db')

    const saved = await api.tts.updateSettings({ scope: 'default', provider: 'vieneu', voice: 'vi-female-01' })
    expect(saved.effective.provider).toBe('vieneu')
  })

  it('bản ghi đè nhà cung cấp dựng sẵn: giữ vị trí, đổi đơn giá, bỏ trống khoá thì giữ khoá cũ', async () => {
    await loginAsAdmin()
    const before = await api.ttsAdmin.providers()
    const viettelIndex = before.items.findIndex((i) => i.provider === 'viettel')

    const created = await api.ttsAdmin.createProvider({
      ...CUSTOM,
      provider: 'viettel',
      label: 'Viettel AI TTS (đối chiếu 2026)',
      price_per_1m_chars: 350_000,
      api_key: 'viettel-token-9999',
    })
    expect(created.custom).toBe(false)
    expect(created.has_db_row).toBe(true)

    const after = await api.ttsAdmin.providers()
    expect(after.items.findIndex((i) => i.provider === 'viettel')).toBe(viettelIndex)
    expect(after.items[viettelIndex].price_per_1m_chars).toBe(350_000)

    const updated = await api.ttsAdmin.updateProvider(created.provider_id, {
      ...CUSTOM,
      provider: 'viettel',
      label: 'Viettel AI TTS (đổi tên)',
      price_per_1m_chars: 350_000,
      api_key: '',
    })
    expect(updated.label).toBe('Viettel AI TTS (đổi tên)')
    expect(updated.api_key_configured).toBe(true)
    expect(updated.api_key_masked).toBe(created.api_key_masked)

    // Xoá bản ghi đè: nhà cung cấp dựng sẵn vẫn còn, quay về đơn giá gốc.
    const deleted = await api.ttsAdmin.deleteProvider(created.provider_id)
    expect(deleted.still_available).toBe(true)
    const restored = (await api.ttsAdmin.providers()).items.find((i) => i.provider === 'viettel')
    expect(restored?.price_per_1m_chars).toBe(320_000)
    expect(restored?.has_db_row).toBe(false)

    // Xoá nhà cung cấp tự thêm thì biến mất hẳn.
    const custom = await api.ttsAdmin.createProvider(CUSTOM)
    expect((await api.ttsAdmin.deleteProvider(custom.provider_id)).still_available).toBe(false)
    expect((await api.ttsAdmin.providers()).items.some((i) => i.provider === 'vieneu')).toBe(false)
  })

  it('xoá nhà cung cấp đang được chọn ⇒ cảnh báo số thiết lập dính và tự rơi về giọng trình duyệt', async () => {
    await loginAsAdmin()
    const created = await api.ttsAdmin.createProvider(CUSTOM)
    await api.tts.updateSettings({ scope: 'default', provider: 'vieneu', voice: 'vi-female-01' })
    expect((await api.tts.settings()).effective.provider).toBe('vieneu')

    const deleted = await api.ttsAdmin.deleteProvider(created.provider_id)
    expect(deleted.used_by_scopes).toBe(1)

    // Trang giọng đọc vẫn chạy và tự nói thật là đang dùng giọng trình duyệt.
    const after = await api.tts.settings()
    expect(after.effective.provider).toBe('browser')
  })

  it('Test kết nối nói đúng sự thật cho từng loại nhà cung cấp', async () => {
    await loginAsAdmin()

    // 1) Trình duyệt: không cần khoá, luôn sẵn sàng.
    const browser = await api.ttsAdmin.testProvider('browser')
    expect(browser.ok).toBe(true)
    expect(browser.status).toBe('NO_KEY_NEEDED')

    // 2) Nhà cung cấp dựng sẵn chưa có khoá: phải nói rõ là chưa cấu hình kèm tên biến ENV.
    const viettel = await api.ttsAdmin.testProvider('viettel')
    expect(viettel.ok).toBe(false)
    expect(viettel.status).toBe('NOT_CONFIGURED')

    // 3) Nhà cung cấp tự thêm không mở endpoint kiểm tra: hướng dẫn kiểm bằng tay, không báo xanh giả.
    const created = await api.ttsAdmin.createProvider(CUSTOM)
    const unsupported = await api.ttsAdmin.testProvider(created.provider_id)
    expect(unsupported.ok).toBe(false)
    expect(unsupported.status).toBe('UNSUPPORTED')
    expect(unsupported.detail).toContain('Đọc')

    // 4) Gateway OpenAI-compatible: có khoá + Base URL thì kiểm tra được.
    const gateway = await api.ttsAdmin.createProvider({
      ...CUSTOM,
      provider: 'openai',
      label: 'OpenAI qua gateway nội bộ',
      base_url: 'https://gateway.noibo.vn/v1',
      price_per_1m_chars: 15,
      currency: 'USD',
      api_key: 'sk-gateway-0001',
    })
    const ok = await api.ttsAdmin.testProvider(gateway.provider_id)
    expect(ok.ok).toBe(true)
    expect(ok.status).toBe('OK')
    // Kết quả kiểm tra đọng lại trong danh sách để bảng không còn hiện “Chưa kiểm tra”.
    const row = (await api.ttsAdmin.providers()).items.find((i) => i.provider === 'openai')
    expect(row?.last_test_status).toBe('OK')
    expect(row?.last_tested_at).toBeTruthy()
  })

  it('thiếu khoá thì từ chối (422) và nhân viên thường không có quyền (403)', async () => {
    await loginAsAdmin()
    await expect(api.ttsAdmin.createProvider({ ...CUSTOM, provider: 'thieu-khoa', api_key: '' })).rejects.toMatchObject({
      status: 422,
    })

    await loginAs(SALE)
    await expect(api.ttsAdmin.providers()).rejects.toMatchObject({ status: 403 })
    await expect(api.ttsAdmin.testProvider('browser')).rejects.toMatchObject({ status: 403 })
  })
})
