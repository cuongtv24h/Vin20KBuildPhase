// @vitest-environment node
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { api } from '@pricepolicy/api-client/client'
import { turnToAppendPayload } from '@pricepolicy/api-client/copilotHistory'
import { ApiError } from '@pricepolicy/api-client/errors'
import { setAuthTokenProvider } from '@pricepolicy/api-client/http'
import { resetDb } from './db'
import { translateSlash } from './handlers/copilot'
import { server } from './node'

/**
 * Vòng 5 — ba yêu cầu người dùng nêu trực tiếp:
 *  1. Hội thoại Copilot phải lưu lại và xem lại được (không mất khi đổi trang).
 *  2. Câu trả lời không được lọt lệnh gạch chéo (`/ch`, `/chinh-sach`…).
 *  3. Admin tự khai báo nhà cung cấp + API key trong giao diện (DB ưu tiên hơn ENV) kèm đơn giá,
 *     để tab "Chi phí & hiệu năng" tính được chi phí/độ trễ/token.
 *
 * Đây cũng là đặc tả cho backend FastAPI: đổi base URL sang backend thật, các kỳ vọng phải giữ nguyên.
 */

let token: string | null = null
setAuthTokenProvider(() => token)

const PASSWORD = 'Vland@2026'
const ADMIN_EMAIL = 'admin.mock@vlandfuture.vn'
const SALE = 'nam.hoang@vlandfuture.vn'
const OTHER_SALE = 'trang.le@vlandfuture.vn' // USR-SALE-002 — nhân viên khác để kiểm tra cô lập lịch sử

async function loginAs(email: string) {
  token = (await api.auth.login({ email, password: PASSWORD })).access_token
}

/**
 * Mock chưa seed sẵn tài khoản ADMIN (đúng luồng admin_cp: khởi tạo lần đầu rồi đăng nhập).
 * Tài khoản tạo ra nằm trong bộ nhớ tiến trình nên các lần sau chỉ cần đăng nhập lại.
 */
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

describe('Chuẩn hoá lệnh gạch chéo (không lọt vào câu trả lời)', () => {
  it('dịch lệnh đầy đủ thành câu lệnh tự nhiên', () => {
    expect(translateSlash('/chinh-sach')).toBe('Tra cứu chính sách đang hiệu lực')
    expect(translateSlash('/tim-khach Nguyễn Văn An')).toBe('Tìm khách hàng Nguyễn Văn An')
    expect(translateSlash('/gio-hang')).toBe('Xem giỏ hàng còn căn nào')
  })

  it('lệnh gõ tắt không lộ nguyên văn vào câu trả lời', () => {
    expect(translateSlash('/ch')).toBe('')
    expect(translateSlash('/baogi')).toBe('Baogi')
    // Văn bản thường (kể cả "km/h", "Anh/chị", "/api/v1") giữ nguyên.
    expect(translateSlash('Đi 60 km/h được không?')).toBe('Đi 60 km/h được không?')
    expect(translateSlash('Anh/chị gõ /chinh-sach để tra cứu nhé')).toBe('Anh/chị gõ /chinh-sach để tra cứu nhé')
  })

  it('chat bằng lệnh gạch chéo → trả lời đúng nghiệp vụ và không còn ký tự "/" của lệnh', async () => {
    await loginAs(SALE)
    const turn = await api.copilot.chat({ message: '/chinh-sach', history: [] })
    expect(turn.reply).not.toContain('/chinh-sach')
    expect(turn.reply).not.toMatch(/(^|\s)\/ch\b/)
    expect(turn.grounded).toBe(true)
  })
})

describe('Lịch sử hội thoại Copilot', () => {
  it('ghi lượt hỏi–đáp rồi đọc lại được sau khi "rời trang"', async () => {
    await loginAs(SALE)
    const first = await api.copilot.appendTurn({
      conversation_id: null,
      user_message: 'Tra cứu chính sách đang hiệu lực',
      assistant_message: 'Chính sách CSBH-ZEN-2026-V2.6 đang hiệu lực với mức chiết khấu 3%.',
      citations: [],
      action_type: null,
    })
    expect(first.conversation_id).toBeTruthy()
    expect(first.message_count).toBe(2)

    const second = await api.copilot.appendTurn({
      conversation_id: first.conversation_id,
      user_message: 'Căn ZEN-A-1205 còn hàng không?',
      assistant_message: 'Còn 3 căn loại tương tự.',
    })
    expect(second.conversation_id).toBe(first.conversation_id)
    expect(second.messages.map((m) => m.role)).toEqual(['user', 'assistant', 'user', 'assistant'])

    // Phiên mới (như đổi trang rồi quay lại): danh sách + nội dung vẫn còn.
    const list = await api.copilot.conversations()
    expect(list.total).toBe(1)
    expect(list.items[0].conversation_id).toBe(first.conversation_id)
    expect(list.items[0].title).toBe('Tra cứu chính sách đang hiệu lực')

    const detail = await api.copilot.conversation(first.conversation_id)
    expect(detail.messages).toHaveLength(4)
    expect(detail.messages[0].content).toBe('Tra cứu chính sách đang hiệu lực')
  })

  it('câu trả lời chế độ dự phòng (chưa đối chiếu dữ liệu) VẪN phải lưu vào lịch sử', async () => {
    // Đúng lỗi Sale báo: backend chưa cấu hình khoá LLM → mọi câu trả lời có mode=offline_react,
    // grounded=false. Bản cũ bỏ qua không lưu → lịch sử rỗng và đổi trang là mất hội thoại.
    await loginAs(SALE)
    const payload = turnToAppendPayload({
      conversationId: null,
      question: 'Căn này giá bao nhiêu?',
      final: {
        reply: 'Dạ em chưa đối chiếu được dữ liệu, anh kiểm tra lại giúp em.',
        citations: [],
        action_type: null,
      },
    })
    expect(payload.user_message).toBe('Căn này giá bao nhiêu?')
    expect(payload.assistant_message).toContain('chưa đối chiếu')
    expect(payload.citations).toEqual([])

    const saved = await api.copilot.appendTurn(payload)
    expect(saved.conversation_id).toBeTruthy()

    // "Đổi trang rồi quay lại": danh sách và nội dung cuộc vẫn còn nguyên.
    const list = await api.copilot.conversations()
    expect(list.items.map((c) => c.conversation_id)).toContain(saved.conversation_id)
    const detail = await api.copilot.conversation(saved.conversation_id)
    expect(detail.messages.map((m) => m.content)).toEqual([
      'Căn này giá bao nhiêu?',
      'Dạ em chưa đối chiếu được dữ liệu, anh kiểm tra lại giúp em.',
    ])
  })

  it('lịch sử tách theo nhân viên, đổi tên và xoá được', async () => {
    await loginAs(SALE)
    const mine = await api.copilot.appendTurn({
      user_message: 'Xem giỏ hàng còn căn nào',
      assistant_message: 'Còn 12 căn.',
    })

    // Nhân viên khác không đọc được hội thoại của đồng nghiệp (404, không phải 403).
    await loginAs(OTHER_SALE)
    await expect(api.copilot.conversation(mine.conversation_id)).rejects.toMatchObject({ status: 404 })

    await loginAs(SALE)
    const renamed = await api.copilot.conversationRename(mine.conversation_id, 'Kiểm tra giỏ hàng')
    expect(renamed.title).toBe('Kiểm tra giỏ hàng')
    await api.copilot.conversationDelete(mine.conversation_id)
    await expect(api.copilot.conversation(mine.conversation_id)).rejects.toBeInstanceOf(ApiError)
    expect((await api.copilot.conversations()).total).toBe(0)
  })
})

describe('Admin tự khai báo nhà cung cấp LLM', () => {
  it('danh sách trống → nguồn ENV; khai báo xong → nguồn DB, khoá luôn được che', async () => {
    await loginAsAdmin()
    const before = await api.llmAdmin.providers()
    expect(before.source).toBe('env')
    expect(before.total).toBe(0)

    const created = await api.llmAdmin.createProvider({
      name: 'OpenAI chính',
      provider: 'openai',
      base_url: 'https://api.openai.com/v1',
      model_name: 'gpt-4o-mini',
      api_key: 'sk-test-1234567890abcd',
      input_price_per_1m: 0.15,
      output_price_per_1m: 0.6,
      currency: 'USD',
      temperature: 0.2,
      priority: 0,
      is_active: true,
    })
    expect(created.provider_id).toMatch(/^LLM-/)
    expect(created.api_key_masked).toBe('sk-t…abcd')
    expect(created.has_api_key).toBe(true)
    expect(JSON.stringify(created)).not.toContain('1234567890')

    const after = await api.llmAdmin.providers()
    expect(after.source).toBe('db')
    expect(after.items[0].input_price_per_1m).toBe(0.15)

    // Sửa mà không nhập khoá mới → giữ nguyên khoá cũ.
    const updated = await api.llmAdmin.updateProvider(created.provider_id, {
      name: 'OpenAI chính (đổi tên)',
      provider: 'openai',
      base_url: 'https://api.openai.com/v1',
      model_name: 'gpt-4o-mini',
      api_key: null,
      input_price_per_1m: 0.2,
      output_price_per_1m: 0.8,
      currency: 'USD',
      temperature: 0.2,
      priority: 0,
      is_active: true,
    })
    expect(updated.name).toBe('OpenAI chính (đổi tên)')
    expect(updated.has_api_key).toBe(true)
    expect(updated.input_price_per_1m).toBe(0.2)

    // Kiểm tra kết nối (mock chạy offline, trả kết quả tất định) — đúng luồng “lưu rồi Test kết nối”
    // trong hộp thoại khai báo nhà cung cấp.
    const test = await api.llmAdmin.testProvider(created.provider_id)
    expect(test.ok).toBe(true)
    expect(test.status).toBe('OK')
    expect(test.provider_id).toBe(created.provider_id)
    expect(test.detail).toContain('thành công')
    expect(test.latency_ms).toBeGreaterThan(0)

    // Kết quả kiểm tra phải đọng lại trong danh sách — nếu không, bảng vẫn hiện “Chưa kiểm tra”
    // dù Admin vừa bấm Test.
    const tested = (await api.llmAdmin.providers()).items.find((p) => p.provider_id === created.provider_id)
    expect(tested?.last_test_status).toBe('OK')
    expect(tested?.last_test_latency_ms).toBeGreaterThan(0)
    expect(tested?.last_tested_at).toBeTruthy()

    await api.llmAdmin.deleteProvider(created.provider_id)
    expect((await api.llmAdmin.providers()).source).toBe('env')
  })

  it('thiếu API key bị từ chối (422) và nhân viên thường không có quyền (403)', async () => {
    await loginAsAdmin()
    await expect(
      api.llmAdmin.createProvider({
        name: 'Thiếu khoá',
        provider: 'openai',
        model_name: 'gpt-4o-mini',
        api_key: '',
        input_price_per_1m: 0,
        output_price_per_1m: 0,
        currency: 'USD',
        temperature: 0.2,
        priority: 1,
        is_active: true,
      }),
    ).rejects.toMatchObject({ status: 422 })

    await loginAs(SALE)
    await expect(api.llmAdmin.providers()).rejects.toMatchObject({ status: 403 })
  })
})

describe('Tab Chi phí & hiệu năng', () => {
  it('mỗi lượt chat có log token/độ trễ/chi phí và tổng hợp được theo nhà cung cấp', async () => {
    await loginAs(SALE)
    await api.copilot.chat({ message: 'Xem giỏ hàng còn căn nào', history: [] })
    await api.copilot.chat({ message: 'Tra cứu chính sách đang hiệu lực', history: [] })

    await loginAsAdmin()
    const summary = await api.llmAdmin.usageSummary(14)
    expect(summary.total_calls).toBeGreaterThanOrEqual(2)
    expect(summary.total_tokens).toBeGreaterThan(0)
    expect(summary.total_cost).toBeGreaterThan(0)
    expect(summary.avg_cost_per_call).toBeGreaterThan(0)
    expect(summary.p95_latency_ms).toBeGreaterThan(0)
    expect(summary.by_provider[0].calls).toBeGreaterThanOrEqual(2)
    // Chi phí = token vào/ra × đơn giá mặc định (0.15 / 0.60 USD mỗi 1M token).
    expect(summary.by_provider[0].cost).toBeCloseTo(
      (summary.total_input_tokens / 1_000_000) * 0.15 + (summary.total_output_tokens / 1_000_000) * 0.6,
      6,
    )

    const records = await api.llmAdmin.usageRecords(10)
    expect(records.items.length).toBeGreaterThanOrEqual(2)
    expect(new Date(records.items[0].at).getTime()).toBeGreaterThanOrEqual(
      new Date(records.items[1].at).getTime(),
    )
    expect(records.items[0].ok).toBe(true)
  })
})
