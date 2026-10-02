/**
 * Phiên chat Copilot phía client — giữ hội thoại **qua các lần đổi trang** và khi tải lại trang.
 *
 * Vì sao cần: `messages` từng nằm trong `useState` của trang Trợ lý. Rời trang (sang Báo giá…) là
 * component unmount → mất sạch khung chat; quay lại chỉ còn màn hình trắng, dù server đã lưu hội
 * thoại. Bản này tách trạng thái ra khỏi vòng đời component:
 *
 * 1. **Trong bộ nhớ tiến trình (module)** — đổi trang rồi quay lại vẫn còn nguyên, không cần chờ mạng.
 * 2. **`sessionStorage`** — F5 vẫn còn (mỗi tab một phiên), nhưng không lưu vĩnh viễn vào máy dùng chung.
 * 3. **Cache theo từng cuộc** — bấm một cuộc trong lịch sử là thấy nội dung đã đọc ngay, sau đó
 *    `hydrate()` thay bằng bản mới nhất từ server (server vẫn là nguồn sự thật).
 *
 * Store cố ý **không phụ thuộc React/không đụng DOM trực tiếp**: mọi truy cập lưu trữ đi qua
 * `CopilotChatStorage`, nên test được bằng bộ nhớ giả và không cần trình duyệt.
 */

import { useCallback, useSyncExternalStore } from 'react'

/** Khoá trỏ tới cuộc đang mở — dùng chung với trang Trợ lý để F5/mở lại tab vẫn đúng cuộc. */
export const ACTIVE_CONVERSATION_STORAGE_KEY = 'copilot.activeConversationId'

/** Khoá lưu phiên chat (nội dung các cuộc đã đọc) trong `sessionStorage`. */
export const CHAT_SESSION_STORAGE_KEY = 'copilot.chatSession.v1'

/** Số cuộc giữ trong cache — đủ để qua lại vài cuộc gần nhất mà không phình bộ nhớ.
 *  Từng cuộc được khôi phục bằng truy vấn lịch sử; ở đây chỉ cần đủ gần. */
const MAX_CACHED_CONVERSATIONS = 3

/** Trần số mục mỗi cuộc khi **lưu tạm** — chỉ áp cho dữ liệu ghi vào `sessionStorage`, KHÔNG cắt
 *  khung chat đang xem (phiên chat dài phải xem được đủ trong lúc đang làm việc). */
const MAX_PERSISTED_ITEMS = 60

/** Mục tối thiểu của khung chat (trang Trợ lý dùng kiểu `StreamItem` giàu thông tin hơn). */
export interface CopilotChatItem {
  id: string
  type: string
  time: string
}

/** Lưu trữ tối thiểu — `sessionStorage` thật, hoặc bộ nhớ giả trong test. */
export interface CopilotChatStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export interface CopilotChatSnapshot<T extends CopilotChatItem = CopilotChatItem> {
  /** `null` = phiên mới chưa được server cấp id (lượt đầu chưa ghi xong). */
  conversationId: string | null
  /** Mục đang hiển thị của cuộc đang mở. */
  items: T[]
}

interface PersistedSession {
  conversationId: string | null
  /** Nội dung đang hiển thị của cuộc đang mở. */
  items: CopilotChatItem[]
  /**
   * Nội dung của **phiên mới chưa được server cấp id** (lượt đầu chưa ghi xong) nhưng người dùng đã
   * rời sang cuộc khác. Không có chỗ này thì lượt ghi trả về muộn sẽ mất trắng nội dung vừa hỏi.
   */
  pendingItems: CopilotChatItem[]
  /** Cache theo `conversation_id` — bấm lại cuộc cũ là thấy ngay. */
  cache: Record<string, CopilotChatItem[]>
}

const emptySession = (): PersistedSession => ({ conversationId: null, items: [], pendingItems: [], cache: {} })

/** `sessionStorage` của trình duyệt; môi trường không có (SSR/test Node) thì dùng bộ nhớ. */
function browserSessionStorage(): CopilotChatStorage {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) return window.sessionStorage
  } catch {
    /* chế độ riêng tư chặn truy cập — rơi về bộ nhớ */
  }
  return memoryStorage()
}

/** Bộ nhớ giả — dùng cho test và cho môi trường không có `sessionStorage`. */
export function memoryStorage(seed: Record<string, string> = {}): CopilotChatStorage {
  const map = new Map<string, string>(Object.entries(seed))
  return {
    getItem: (key) => (map.has(key) ? (map.get(key) as string) : null),
    setItem: (key, value) => void map.set(key, value),
    removeItem: (key) => void map.delete(key),
  }
}

/**
 * Đọc phiên đã lưu. Dữ liệu hỏng/không đúng dạng thì **bỏ qua và bắt đầu sạch** — không được để
 * một lần lưu lỗi làm trang Trợ lý trắng.
 */
function readPersisted(storage: CopilotChatStorage): PersistedSession {
  try {
    const raw = storage.getItem(CHAT_SESSION_STORAGE_KEY)
    if (!raw) return emptySession()
    const parsed = JSON.parse(raw) as Partial<PersistedSession>
    const items = Array.isArray(parsed.items) ? (parsed.items as CopilotChatItem[]) : []
    const cache: Record<string, CopilotChatItem[]> = {}
    if (parsed.cache && typeof parsed.cache === 'object') {
      for (const [key, value] of Object.entries(parsed.cache)) {
        if (Array.isArray(value)) cache[key] = value as CopilotChatItem[]
      }
    }
    const pendingItems = Array.isArray(parsed.pendingItems) ? (parsed.pendingItems as CopilotChatItem[]) : []
    return {
      conversationId: typeof parsed.conversationId === 'string' ? parsed.conversationId : null,
      items: items.filter((item) => item && typeof item.id === 'string'),
      pendingItems: pendingItems.filter((item) => item && typeof item.id === 'string'),
      cache,
    }
  } catch {
    return emptySession()
  }
}

export interface CopilotChatStore<T extends CopilotChatItem = CopilotChatItem> {
  subscribe: (listener: () => void) => () => void
  getSnapshot: () => CopilotChatSnapshot<T>
  /** Đổi cuộc đang mở. Không truyền `items` thì lấy từ cache (hoặc rỗng). */
  setConversationId: (conversationId: string | null, options?: { items?: T[] }) => void
  /** Thay nội dung cuộc đang mở (nhận giá trị hoặc hàm cập nhật như `useState`). */
  setItems: (next: T[] | ((prev: T[]) => T[])) => void
  /** Ghi nội dung mới nhất đọc từ server. Chỉ đổi khung đang hiển thị nếu đúng cuộc đang mở. */
  hydrate: (conversationId: string, items: T[]) => void
  /** Server vừa cấp id cho phiên mới: chuyển nội dung đang có sang khoá của cuộc mới. */
  assignConversationId: (conversationId: string) => void
  /** Quên một cuộc (đã xoá) — bỏ khỏi cache để không mở lại nhầm. */
  forget: (conversationId: string) => void
  /** Nội dung đã cache của một cuộc (nếu có). */
  cachedItems: (conversationId: string) => T[] | undefined
  /** Xoá sạch phiên (test). */
  reset: () => void
}

/**
 * Tạo store phiên chat. `initialConversationId` cho phép trang Trợ lý truyền id đang nhớ trong
 * `localStorage` khi khởi động — nhờ vậy F5 vẫn mở đúng cuộc.
 */
export function createCopilotChatStore<T extends CopilotChatItem = CopilotChatItem>(options: {
  storage?: CopilotChatStorage
  initialConversationId?: string | null
} = {}): CopilotChatStore<T> {
  const storage = options.storage ?? browserSessionStorage()
  const listeners = new Set<() => void>()

  const persisted = readPersisted(storage)
  let conversationId = options.initialConversationId ?? persisted.conversationId
  let items = conversationId && persisted.cache[conversationId] ? persisted.cache[conversationId] : persisted.items
  let pendingItems = persisted.pendingItems
  const cache = { ...persisted.cache }

  let snapshot: CopilotChatSnapshot<T> = { conversationId, items: items as T[] }

  const persist = () => {
    try {
      if (conversationId) storage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, conversationId)
      else storage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY)
    } catch {
      /* nơi lưu trữ hỏng: vẫn chạy bằng bộ nhớ trong phiên */
    }
    const key = conversationId
    if (key && items.length) cache[key] = items
    // Giới hạn số cuộc giữ lại: bỏ cuộc cũ nhất (theo thứ tự chèn của object).
    const keys = Object.keys(cache)
    for (const extra of keys.slice(0, Math.max(0, keys.length - MAX_CACHED_CONVERSATIONS))) delete cache[extra]
    try {
      storage.setItem(
        CHAT_SESSION_STORAGE_KEY,
        JSON.stringify({
          conversationId,
          items: trim(items),
          pendingItems: trim(pendingItems),
          cache: Object.fromEntries(Object.entries(cache).map(([id, list]) => [id, trim(list)])),
        } satisfies PersistedSession),
      )
    } catch {
      /* hết dung lượng: bỏ qua, phiên vẫn sống trong bộ nhớ */
    }
  }

  const emit = () => {
    snapshot = { conversationId, items: items as T[] }
    persist()
    for (const listener of listeners) listener()
  }

  /** Bản rút gọn để **lưu tạm** (không dùng cho khung chat đang xem). */
  const trim = (list: CopilotChatItem[]) => list.slice(-MAX_PERSISTED_ITEMS)

  return {
    subscribe: (listener) => {
      listeners.add(listener)
      return () => void listeners.delete(listener)
    },
    getSnapshot: () => snapshot,

    setConversationId: (next, opts = {}) => {
      if (next === conversationId && !opts.items) return
      // Rời khỏi phiên chưa có id: cất nội dung lại để lượt ghi trả về muộn không làm mất trắng.
      if (!conversationId && items.length) pendingItems = items as CopilotChatItem[]
      conversationId = next
      if (opts.items) items = opts.items
      else if (next && cache[next]) items = cache[next] as T[]
      else items = []
      emit()
    },

    setItems: (next) => {
      const resolved = typeof next === 'function' ? (next as (prev: T[]) => T[])(items as T[]) : next
      items = resolved
      emit()
    },

    hydrate: (id, nextItems) => {
      cache[id] = nextItems as CopilotChatItem[]
      if (id === conversationId) items = nextItems as T[]
      emit()
    },

    assignConversationId: (id) => {
      if (conversationId === id) return
      // Lượt ghi cũ trả về muộn khi người dùng đã mở cuộc khác: KHÔNG cướp khung chat, nhưng phải
      // cất nội dung phiên mới vào cache để mở lại từ lịch sử vẫn còn nguyên.
      if (conversationId) {
        if (pendingItems.length) {
          cache[id] = pendingItems
          pendingItems = []
        }
        emit()
        return
      }
      conversationId = id
      cache[id] = items
      pendingItems = []
      emit()
    },

    forget: (id) => {
      delete cache[id]
      if (conversationId === id) {
        conversationId = null
        items = []
      }
      pendingItems = pendingItems.filter((entry) => entry.id !== id)
      emit()
    },

    cachedItems: (id) => cache[id] as T[] | undefined,

    reset: () => {
      conversationId = null
      items = []
      pendingItems = []
      for (const key of Object.keys(cache)) delete cache[key]
      emit()
    },
  }
}

/** Store dùng chung cho ứng dụng (nội bộ mỗi tab một phiên). */
export const copilotChatStore = createCopilotChatStore()

/** Đọc trạng thái store trong React, có re-render khi store đổi. */
export function useCopilotChatSession<T extends CopilotChatItem = CopilotChatItem>(): CopilotChatSnapshot<T> {
  return useSyncExternalStore(
    copilotChatStore.subscribe,
    () => copilotChatStore.getSnapshot() as CopilotChatSnapshot<T>,
    () => ({ conversationId: null, items: [] as T[] }),
  )
}

/**
 * Trạng thái khung chat dùng như `useState` nhưng **sống ngoài component**: đổi trang quay lại vẫn
 * còn, F5 vẫn còn. Trả về `[items, setItems]` với `setItems` nhận cả giá trị lẫn hàm cập nhật.
 */
export function useCopilotChatMessages<T extends CopilotChatItem>(): [
  T[],
  (next: T[] | ((prev: T[]) => T[])) => void,
] {
  const session = useCopilotChatSession<T>()
  const setItems = useCallback((next: T[] | ((prev: T[]) => T[])) => {
    ;(copilotChatStore.setItems as (value: unknown) => void)(next)
  }, [])
  return [session.items, setItems]
}

/** Id cuộc đang mở (cùng store với `useCopilotChatMessages`). */
export function useCopilotChatConversationId(): [string | null, (id: string | null) => void] {
  const session = useCopilotChatSession()
  return [session.conversationId, copilotChatStore.setConversationId]
}
