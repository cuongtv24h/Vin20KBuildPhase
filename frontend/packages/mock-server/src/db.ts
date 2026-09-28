import type {
  EvidenceBackedClaim,
  LeadDossier,
  PolicyDocument,
  PreSalesSession,
  Quote,
  QuoteAuditEvent,
  SseEventEnvelope,
  UnitSnapshot,
} from '@pricepolicy/api-client/contracts'

/**
 * "Database" của backend giả lập — thuần bộ nhớ trong tiến trình Node của mock-server. Một tiến
 * trình duy nhất phục vụ cả hai app (Khách hàng, Nội bộ) qua HTTP nên state tự nhiên liên thông
 * giữa chúng (không cần đồng bộ qua localStorage/BroadcastChannel như khi chạy MSW riêng trong
 * từng tab trình duyệt). Dữ liệu mất khi tiến trình dừng — đúng bản chất một backend giả lập cho
 * dev/demo; seed lại từ đầu mỗi lần khởi động (`npm run dev:mock`) hoặc khi gọi `POST /__mock/reset`.
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
  /** Lập phương án tham khảo đang chờ tới hạn (settle() xử lý) — chìa khoá là session_id. */
  presales_pending: Record<string, { ready_at: number }>
  /** Nhật ký SSE của từng phiên Pre-Sales — tối đa 1 sự kiện PRE_SALES_PLAN_READY mỗi lượt lập plan. */
  presales_events: Record<string, StoredEvent[]>
  auth: Record<string, { user_id: string; expires_at: number }>
  reauth: Record<string, { user_id: string; expires_at: number }>
  idempotency: Record<string, IdempotencyRecord>
  checks: Record<string, { message_hash: string; quote_id: string; quote_version: number }>
  counters: Record<string, number>
}

export const SCHEMA_VERSION = 4

let state: MockDb | null = null
let loading: Promise<MockDb> | null = null
let seeder: (() => Promise<MockDb>) | null = null

export function registerSeeder(fn: () => Promise<MockDb>) {
  seeder = fn
}

export async function getDb(): Promise<MockDb> {
  if (state) return state
  if (!loading) {
    if (!seeder) throw new Error('Mock seeder chưa được đăng ký.')
    loading = seeder()
  }
  state = await loading
  return state
}

/** Không còn tác dụng thực (không có storage để ghi) — giữ lại vì `route.ts`/handler gọi sau mỗi request. */
export function commit() {
  // no-op: state đã là nguồn sự thật duy nhất trong bộ nhớ tiến trình.
}

export async function resetDb(): Promise<void> {
  state = null
  loading = null
  await getDb()
}

export function nextId(db: MockDb, counter: string): number {
  db.counters[counter] = (db.counters[counter] ?? 0) + 1
  return db.counters[counter]
}
