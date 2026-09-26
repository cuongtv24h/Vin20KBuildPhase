import type {
  EvidenceBackedClaim,
  LeadDossier,
  PolicyDocument,
  PreSalesSession,
  Quote,
  QuoteAuditEvent,
  SseEventEnvelope,
  UnitSnapshot,
} from '@/api/contracts'

/**
 * "Database" của backend giả lập. Lưu localStorage (trình duyệt) để giữ trạng thái trong phiên demo,
 * đồng bộ giữa các tab (Sale một tab, Quản lý tab khác); bộ nhớ thuần khi chạy test Node.
 */

export interface StoredEvent {
  envelope: SseEventEnvelope
  emit_at: number
}

export interface PendingAnalysis {
  version: number
  ready_at: number
  final: Quote
  claims: EvidenceBackedClaim[]
}

export interface PdfJob {
  version: number
  requested_at: number
  retry: boolean
  fail: boolean
  logged: 'NONE' | 'ISSUED' | 'FAILED'
  pdf_sha256: string | null
}

export interface QuoteRecord {
  quote_id: string
  /** versions[i] = phiên bản i+1; bản cũ SUPERSEDED, bất biến. */
  versions: Quote[]
  claims: Record<number, EvidenceBackedClaim[]>
  events: Record<number, StoredEvent[]>
  pending: PendingAnalysis | null
  audit: QuoteAuditEvent[]
  pdf: PdfJob | null
  sse_dropped: number[]
}

export interface IdempotencyRecord {
  fingerprint: string
  status: number
  body: unknown
}

export interface MockDb {
  schema_version: number
  units: UnitSnapshot[]
  policies: PolicyDocument[]
  quotes: QuoteRecord[]
  dossiers: LeadDossier[]
  presales: PreSalesSession[]
  auth: Record<string, { user_id: string; expires_at: number }>
  reauth: Record<string, { user_id: string; expires_at: number }>
  idempotency: Record<string, IdempotencyRecord>
  checks: Record<string, { message_hash: string; quote_id: string; quote_version: number }>
  counters: Record<string, number>
}

const KEY = 'pricepolicy.mock-db'
export const SCHEMA_VERSION = 4

let state: MockDb | null = null
let seeder: (() => Promise<MockDb>) | null = null
const listeners = new Set<() => void>()

const storage = (): Storage | null => {
  try {
    return globalThis.localStorage ?? null
  } catch {
    return null
  }
}

export function registerSeeder(fn: () => Promise<MockDb>) {
  seeder = fn
}

export async function getDb(): Promise<MockDb> {
  if (state) return state
  try {
    const raw = storage()?.getItem(KEY)
    const parsed = raw ? (JSON.parse(raw) as MockDb) : null
    if (parsed?.schema_version === SCHEMA_VERSION) {
      state = parsed
      return state
    }
  } catch {
    // dữ liệu hỏng → seed lại
  }
  if (!seeder) throw new Error('Mock seeder chưa được đăng ký.')
  state = await seeder()
  commit()
  return state
}

export function commit() {
  if (!state) return
  try {
    storage()?.setItem(KEY, JSON.stringify(state))
  } catch {
    // quota / chế độ riêng tư — chỉ sống trong bộ nhớ
  }
}

export async function resetDb(): Promise<void> {
  try {
    storage()?.removeItem(KEY)
  } catch {
    // bỏ qua
  }
  state = null
  await getDb()
  listeners.forEach((l) => l())
}

export function nextId(db: MockDb, counter: string): number {
  db.counters[counter] = (db.counters[counter] ?? 0) + 1
  return db.counters[counter]
}

/** Tab khác ghi dữ liệu → nạp lại và báo cho ứng dụng làm mới cache. */
export function onExternalChange(listener: () => void): () => void {
  listeners.add(listener)
  const handler = (e: StorageEvent) => {
    if (e.key !== KEY) return
    state = null
    listener()
  }
  globalThis.addEventListener?.('storage', handler)
  return () => {
    listeners.delete(listener)
    globalThis.removeEventListener?.('storage', handler)
  }
}
