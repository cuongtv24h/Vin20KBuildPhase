import type { ApartmentUnit, Lead, PolicyVersion, Quote } from '@/types/domain'

/**
 * "Database" của backend giả lập — lưu trong localStorage để dữ liệu giữ nguyên khi đổi
 * tài khoản, tải lại trang hoặc mở trang khách hàng ở tab khác.
 */
export interface MockDbState {
  schemaVersion: number
  units: ApartmentUnit[]
  policies: PolicyVersion[]
  leads: Lead[]
  quotes: Quote[]
  /** accessToken → userId */
  sessions: Record<string, string>
  counters: { quote: number; lead: number; event: number; policy: number }
}

const STORAGE_KEY = 'pricepolicy.mock-db'
export const SCHEMA_VERSION = 3

let state: MockDbState | null = null
let loading: Promise<MockDbState> | null = null
let seeder: (() => Promise<MockDbState>) | null = null
const listeners = new Set<() => void>()

export function registerSeeder(fn: () => Promise<MockDbState>) {
  seeder = fn
}

function readStorage(): MockDbState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as MockDbState
    return parsed.schemaVersion === SCHEMA_VERSION ? parsed : null
  } catch {
    return null
  }
}

function writeStorage(value: MockDbState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  } catch {
    // Trình duyệt chặn storage (chế độ riêng tư) — dữ liệu chỉ sống trong phiên hiện tại.
  }
}

export async function getDb(): Promise<MockDbState> {
  if (state) return state
  if (!loading) {
    loading = (async () => {
      const stored = readStorage()
      if (stored) return stored
      if (!seeder) throw new Error('Mock seeder chưa được đăng ký.')
      const seeded = await seeder()
      writeStorage(seeded)
      return seeded
    })()
  }
  state = await loading
  return state
}

export function commit() {
  if (state) writeStorage(state)
}

export async function resetDb(): Promise<void> {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // bỏ qua
  }
  state = null
  loading = null
  await getDb()
  listeners.forEach((l) => l())
}

/** Đồng bộ khi tab khác ghi dữ liệu (ví dụ khách phản hồi báo giá ở tab riêng). */
export function onExternalChange(listener: () => void): () => void {
  listeners.add(listener)
  const handler = (e: StorageEvent) => {
    if (e.key !== STORAGE_KEY) return
    state = readStorage()
    loading = null
    listener()
  }
  window.addEventListener('storage', handler)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('storage', handler)
  }
}
