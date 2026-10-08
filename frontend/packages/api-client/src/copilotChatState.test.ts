/**
 * Phiên chat Copilot phải sống ngoài vòng đời component.
 *
 * Đây là các lỗi thật đã xảy ra trên hệ thống: đang chat mà sang trang Báo giá rồi quay lại thì mất
 * sạch hội thoại; bấm một cuộc trong lịch sử không mở ra; F5 thì mới thấy nội dung cũ. Test khoá lại
 * đúng các hành vi đó ở tầng trạng thái (không cần trình duyệt):
 *
 * 1. Đổi trang  = component unmount/mount lại nhưng store vẫn giữ nội dung.
 * 2. F5         = tiến trình mới, đọc lại từ `sessionStorage`.
 * 3. Bấm lịch sử = mở cuộc đó ra ngay (cache) rồi `hydrate()` bằng bản mới nhất từ server.
 * 4. Phiên mới  = khung chat trống, không lẫn nội dung cuộc trước.
 * 5. Lượt ghi cũ trả về muộn không được "cướp" khung chat của cuộc vừa mở.
 */

import { describe, expect, it } from 'vitest'

import {
  ACTIVE_CONVERSATION_STORAGE_KEY,
  CHAT_SESSION_STORAGE_KEY,
  createCopilotChatStore,
  memoryStorage,
  type CopilotChatItem,
} from '@pricepolicy/api-client/copilotChatState'

const item = (id: string, text: string): CopilotChatItem => ({ id, type: 'user', time: '09:00', text })

const makeStore = (seed: Record<string, string> = {}, initialConversationId?: string | null) => {
  const storage = memoryStorage(seed)
  return { storage, store: createCopilotChatStore({ storage, initialConversationId }) }
}

describe('phiên chat Copilot — giữ qua đổi trang/F5 và mở lại lịch sử', () => {
  it('giữ nguyên hội thoại khi component unmount rồi mount lại (đổi trang)', () => {
    const { store } = makeStore()
    store.setConversationId(null)
    store.setItems([item('u-1', 'Chính sách thanh toán sớm?'), item('a-1', 'Dạ 8.0%')])
    store.assignConversationId('CNV-000001')

    // Component unmount → mount lại: chính là store mới đọc từ sessionStorage của cùng tab.
    const snapshot = store.getSnapshot()
    expect(snapshot.conversationId).toBe('CNV-000001')
    expect(snapshot.items.map((i) => i.id)).toEqual(['u-1', 'a-1'])
  })

  it('F5: đọc lại được phiên đã lưu trong sessionStorage', () => {
    const { storage, store } = makeStore()
    store.setConversationId(null)
    store.setItems([item('u-1', 'Còn căn 2 phòng ngủ?')])
    store.assignConversationId('CNV-000009')

    // "F5" = tiến trình mới, chỉ còn dữ liệu trong storage.
    const reloaded = createCopilotChatStore({ storage })
    expect(reloaded.getSnapshot().conversationId).toBe('CNV-000009')
    expect(reloaded.getSnapshot().items.map((i) => i.id)).toEqual(['u-1'])
  })

  it('bấm một cuộc trong lịch sử: mở ra ngay bằng cache, rồi hydrate bằng bản mới nhất từ server', () => {
    const { store } = makeStore()
    // Cuộc A đang mở
    store.setConversationId(null)
    store.setItems([item('a-1', 'câu hỏi A')])
    store.assignConversationId('CNV-A')
    // Cuộc B đã từng đọc → có cache
    store.setConversationId('CNV-B', { items: [item('b-1', 'câu hỏi B')] })
    // Quay lại A
    store.setConversationId('CNV-A')
    expect(store.getSnapshot().items.map((i) => i.id)).toEqual(['a-1'])

    // Server trả bản đầy đủ hơn cho A → phải thay bằng nội dung mới
    store.hydrate('CNV-A', [item('a-1', 'câu hỏi A'), item('a-2', 'trả lời A')])
    expect(store.getSnapshot().items.map((i) => i.id)).toEqual(['a-1', 'a-2'])
  })

  it('hydrate một cuộc KHÁC không được đè lên khung chat đang mở', () => {
    const { store } = makeStore()
    store.setConversationId('CNV-A', { items: [item('a-1', 'đang mở A')] })
    store.hydrate('CNV-B', [item('b-1', 'nội dung B')])
    expect(store.getSnapshot().items.map((i) => i.id)).toEqual(['a-1'])
    // Nhưng cache của B đã sẵn sàng cho lần mở sau
    expect(store.cachedItems('CNV-B')?.map((i) => i.id)).toEqual(['b-1'])
  })

  it('phiên chat mới: khung trống, không lẫn nội dung cuộc trước', () => {
    const { store } = makeStore()
    store.setConversationId('CNV-A', { items: [item('a-1', 'nội dung cũ')] })
    store.setConversationId(null)
    expect(store.getSnapshot().items).toEqual([])
    expect(store.getSnapshot().conversationId).toBeNull()
  })

  it('lượt ghi của cuộc cũ trả về muộn không cướp khung chat của cuộc vừa mở', () => {
    const { store } = makeStore()
    // Đang ở phiên mới (chưa có id), người dùng đã hỏi một câu
    store.setConversationId(null)
    store.setItems([item('new-1', 'câu hỏi phiên mới')])
    // Người dùng mở ngay một cuộc cũ trước khi lượt ghi trả về
    store.setConversationId('CNV-CU', { items: [item('old-1', 'nội dung cuộc cũ')] })
    // Phản hồi của lượt ghi về muộn, kèm id của phiên mới
    store.assignConversationId('CNV-MOI')
    // Khung chat vẫn là cuộc người dùng đang mở…
    expect(store.getSnapshot().conversationId).toBe('CNV-CU')
    expect(store.getSnapshot().items.map((i) => i.id)).toEqual(['old-1'])
    // …nhưng nội dung phiên mới vẫn được cache để quay lại xem
    expect(store.cachedItems('CNV-MOI')?.map((i) => i.id)).toEqual(['new-1'])
  })

  it('server cấp id cho phiên mới: khung chat GIỮ NGUYÊN nội dung và cất vào cache theo id mới', () => {
    // Đây là hợp đồng của trang Trợ lý sau khi ghi lượt đầu tiên: server trả về id cho CHÍNH phiên đang
    // mở ⇒ phải gọi `assignConversationId`. Bản trước gọi `setConversationId(id)` nên store hiểu là
    // "đổi sang cuộc khác" và xoá trắng khung chat ngay sau câu trả lời đầu tiên — Sale thấy đoạn hội
    // thoại mới "biến mất", bấm nút phiên mới cũng không thấy gì đổi.
    const { storage, store } = makeStore()
    store.setConversationId(null)
    store.setItems([item('u-1', 'câu hỏi đầu'), item('a-1', 'câu trả lời đầu')])

    store.assignConversationId('CNV-MOI')

    expect(store.getSnapshot().conversationId).toBe('CNV-MOI')
    expect(store.getSnapshot().items.map((i) => i.id)).toEqual(['u-1', 'a-1'])
    expect(store.cachedItems('CNV-MOI')?.map((i) => i.id)).toEqual(['u-1', 'a-1'])
    expect(storage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBe('CNV-MOI')
  })

  it('đổi sang cuộc KHÁC thì khung chat đổi theo (adopt ≠ chuyển cuộc)', () => {
    const { store } = makeStore()
    store.setConversationId(null)
    store.setItems([item('u-1', 'phiên chưa lưu')])
    store.hydrate('CNV-CU', [item('old-1', 'nội dung cũ')])

    store.setConversationId('CNV-CU')

    expect(store.getSnapshot().items.map((i) => i.id)).toEqual(['old-1'])
    expect(store.cachedItems('CNV-CU')?.map((i) => i.id)).toEqual(['old-1'])
  })

  it('ghi nhớ cuộc đang mở qua localStorage để F5 mở đúng cuộc', () => {
    const { storage, store } = makeStore()
    store.setConversationId('CNV-000042')
    expect(storage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBe('CNV-000042')
    store.setConversationId(null)
    expect(storage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)).toBeNull()
  })

  it('dữ liệu lưu bị hỏng thì bắt đầu sạch thay vì trắng trang', () => {
    const { store } = makeStore({ [CHAT_SESSION_STORAGE_KEY]: '{không-phải-json' })
    expect(store.getSnapshot()).toEqual({ conversationId: null, items: [] })
  })

  it('xoá cuộc thì quên luôn cache để không mở lại nhầm nội dung đã xoá', () => {
    const { store } = makeStore()
    store.setConversationId('CNV-X', { items: [item('x-1', 'nội dung X')] })
    store.forget('CNV-X')
    expect(store.cachedItems('CNV-X')).toBeUndefined()
    expect(store.getSnapshot().conversationId).toBeNull()
  })

  it('notify listener để React vẽ lại khi store đổi', () => {
    const { store } = makeStore()
    let calls = 0
    const unsubscribe = store.subscribe(() => (calls += 1))
    store.setConversationId('CNV-1')
    store.setItems([item('i-1', 'x')])
    unsubscribe()
    store.setItems([item('i-2', 'y')])
    expect(calls).toBe(2)
  })
})
