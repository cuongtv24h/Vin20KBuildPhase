import type {
  ApprovalRecord,
  PdfStatus,
  Quote,
  QuoteAccepted,
  QuoteWorkflowStatus,
  SseEventEnvelope,
  StaffUser,
  TransactionContext,
} from '@/api/contracts'
import { formatEventId, OPTIMIZATION_OBJECTIVES } from '@/api/contracts'
import { nextId, type MockDb, type PdfJob, type QuoteRecord, type StoredEvent } from '../db'
import { analyzeQuote, type AnalysisOutcome } from '../engine/analyze'
import { canonicalJsonStringify, sha256Hex } from '../engine/hash'
import { actorOf } from '../fixtures/users'
import { getFlags, scaled } from '../flags'
import { appendAudit, SYSTEM_ACTOR } from './audit'
import { invalid, MockError, notFound, transition } from './errors'

/** Trạng thái Sale được phép tạo phiên bản mới (sửa & phân tích lại). */
export const REVISABLE: QuoteWorkflowStatus[] = ['DRAFT', 'NEEDS_INPUT', 'NEEDS_REVISION', 'ABSTAINED', 'CALCULATION_FAILED']

const STEP_OFFSETS_MS = [1_000, 2_000, 3_000]
const READY_AFTER_LAST_STEP_MS = 1_200

export function findRecord(db: MockDb, quoteId: string): QuoteRecord {
  const record = db.quotes.find((q) => q.quote_id === quoteId)
  if (!record) throw notFound(`hồ sơ ${quoteId}`)
  return record
}

export const latest = (record: QuoteRecord): Quote => record.versions[record.versions.length - 1]

/** Bản trả về client: gắn danh sách phiên bản. */
export function view(record: QuoteRecord, version?: number): Quote {
  const q = version ? record.versions[version - 1] : latest(record)
  if (!q) throw notFound(`phiên bản ${version} của ${record.quote_id}`)
  return { ...q, versions: record.versions.map((v) => ({ quote_version: v.quote_version, status: v.status, created_at: v.created_at })) }
}

export function assertVisible(record: QuoteRecord, user: StaffUser) {
  if (user.role === 'SALE' && latest(record).created_by.user_id !== user.user_id) {
    throw new MockError(403, 'FORBIDDEN', 'Bạn không phụ trách hồ sơ này.')
  }
}

/** OCC — If-Match: "v<n>" phải khớp phiên bản mới nhất (TD-4.1 INV-RT-06). */
export function assertVersion(record: QuoteRecord, ifMatch: string | null) {
  const current = latest(record).quote_version
  const expected = ifMatch ? Number(/v?(\d+)/.exec(ifMatch)?.[1]) : NaN
  if (!Number.isFinite(expected)) throw new MockError(428, 'INPUT_VALIDATION_ERROR', 'Thiếu header If-Match.')
  if (expected !== current) {
    throw new MockError(409, 'STALE_QUOTE_VERSION', `Hồ sơ đã sang phiên bản ${current}, bạn đang thao tác trên phiên bản ${expected}.`)
  }
}

export function validateContext(db: MockDb, input: TransactionContext) {
  const unit = db.units.find((u) => u.unit_code === input.unit_code)
  if (!unit) throw notFound(`căn hộ ${input.unit_code}`)
  if (unit.status === 'SOLD') throw transition(`Căn ${unit.unit_code} đã bán.`)
  if (!input.customer_name?.trim()) throw invalid('Thiếu họ tên khách hàng.')
  if (!/^[0-9 +]{9,15}$/.test(input.customer_phone?.trim() ?? '')) throw invalid('Số điện thoại khách hàng không hợp lệ.')
  if (input.transaction_date !== null && !/^\d{4}-\d{2}-\d{2}$/.test(input.transaction_date)) throw invalid('Ngày giao dịch không hợp lệ.')
  if (!Number.isInteger(input.units_quantity) || input.units_quantity < 1) throw invalid('Số căn mua phải là số nguyên ≥ 1.')
  if (!OPTIMIZATION_OBJECTIVES.includes(input.objective)) throw invalid('Tiêu chí tối ưu không hợp lệ.')
  if (input.requested_policy_id) {
    const policy = db.policies.find((p) => p.policy_id === input.requested_policy_id && p.status === 'PUBLISHED')
    if (!policy) throw invalid('Văn bản chính sách viện dẫn không tồn tại hoặc chưa ban hành.')
    if (policy.project_id !== unit.project_id) throw invalid('Văn bản chính sách không thuộc dự án của căn hộ.')
  }
  return unit
}

function eventsFor(quoteId: string, version: number, outcome: AnalysisOutcome, start: number): StoredEvent[] {
  const correlation = `trace-${quoteId}-v${version}`
  const make = (seq: number, type: string, payload: unknown, at: number): StoredEvent => {
    const envelope: SseEventEnvelope = {
      event_id: formatEventId(quoteId, version, seq),
      event_seq: seq,
      event_type: type,
      session_id: null,
      quote_id: quoteId,
      quote_version: version,
      schema_version: 'sse-event.v1',
      correlation_id: correlation,
      occurred_at: new Date(at).toISOString(),
      payload,
    }
    return { envelope, emit_at: at }
  }
  const events = outcome.steps.map((node, i) => make(i + 1, 'step_update', { node, seq: i + 1 }, start + scaled(STEP_OFFSETS_MS[i], true)))
  const lastOffset = outcome.steps.length ? STEP_OFFSETS_MS[outcome.steps.length - 1] : 0
  const seq = events.length + 1
  events.push(make(seq, 'quote_ready', { quote_id: quoteId, status: outcome.status, seq }, start + scaled(lastOffset + READY_AFTER_LAST_STEP_MS, true)))
  return events
}

function analyzingVersion(quoteId: string, version: number, context: TransactionContext, actor: StaffUser, dossierId: string | null, unit: Quote['unit'], at: string): Quote {
  return {
    quote_id: quoteId,
    quote_version: version,
    status: 'ANALYZING',
    pdf_status: null,
    created_at: at,
    updated_at: at,
    created_by: actorOf(actor),
    submitted_at: null,
    source_dossier_id: dossierId,
    transaction_context: context,
    unit: { ...unit },
    policy_snapshot_ref: null,
    conflict_report: null,
    abstention: null,
    missing_fields: [],
    scenarios: [],
    calculation_validation: null,
    recommendation: null,
    risk_flag: { color: 'GREEN', label: 'Đang phân tích', reasons: [] },
    approval: null,
    artifact_hash: null,
    versions: [],
  }
}

async function startAnalysis(db: MockDb, record: QuoteRecord, version: number, context: TransactionContext, actor: StaffUser, dossierId: string | null, now: number) {
  const unit = validateContext(db, context)
  const outcome = await analyzeQuote({ unit, context, policies: db.policies })
  const at = new Date(now).toISOString()
  const base = analyzingVersion(record.quote_id, version, context, actor, dossierId, unit, at)
  const events = eventsFor(record.quote_id, version, outcome, now)
  const { claims, steps: _steps, ...fields } = outcome
  record.versions.push(base)
  record.events[version] = events
  record.pending = { version, ready_at: events[events.length - 1].emit_at, final: { ...base, ...fields }, claims }
}

export async function createQuote(db: MockDb, actor: StaffUser, context: TransactionContext, dossierId: string | null, now: number): Promise<QuoteAccepted> {
  const d = new Date(now)
  const quoteId = `QUO-${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(nextId(db, 'quote')).padStart(5, '0')}`
  const record: QuoteRecord = { quote_id: quoteId, versions: [], claims: {}, events: {}, pending: null, audit: [], pdf: null, sse_dropped: [] }
  await startAnalysis(db, record, 1, context, actor, dossierId, now)
  db.quotes.unshift(record)
  await appendAudit(db, record, { event_type: 'QUOTE_CREATED', quote_version: 1, actor: actorOf(actor), at: now, note: dossierId ? `Từ hồ sơ khách ${dossierId}` : null })
  return accepted(record)
}

export async function createVersion(db: MockDb, actor: StaffUser, record: QuoteRecord, context: TransactionContext, now: number): Promise<QuoteAccepted> {
  const current = latest(record)
  if (current.created_by.user_id !== actor.user_id) throw new MockError(403, 'FORBIDDEN', 'Bạn không phụ trách hồ sơ này.')
  if (!REVISABLE.includes(current.status)) throw transition(`Không thể sửa hồ sơ ở trạng thái ${current.status}.`)
  current.status = 'SUPERSEDED'
  current.updated_at = new Date(now).toISOString()
  const version = current.quote_version + 1
  await startAnalysis(db, record, version, context, actor, current.source_dossier_id, now)
  await appendAudit(db, record, { event_type: 'VERSION_CREATED', quote_version: version, actor: actorOf(actor), at: now, note: `Phiên bản ${current.quote_version} chuyển sang chỉ đọc.` })
  return accepted(record)
}

const accepted = (record: QuoteRecord): QuoteAccepted => {
  const q = latest(record)
  return { quote_id: q.quote_id, quote_version: q.quote_version, status: 'ANALYZING', stream_url: `/api/v1/quotes/${q.quote_id}/events` }
}

/** Áp kết quả phân tích & tiến trình PDF khi đến hạn — gọi ở đầu mỗi request. */
export async function settle(db: MockDb, now: number) {
  for (const record of db.quotes) {
    const p = record.pending
    if (p && now >= p.ready_at) {
      record.pending = null
      const at = new Date(p.ready_at).toISOString()
      record.versions[p.version - 1] = { ...p.final, updated_at: at }
      record.claims[p.version] = p.claims
      const status = p.final.status
      await appendAudit(db, record, {
        event_type: 'ANALYSIS_COMPLETED',
        quote_version: p.version,
        actor: SYSTEM_ACTOR,
        at: p.ready_at,
        note: p.final.abstention?.message ?? `${p.final.scenarios.length} phương án`,
      })
      if (status === 'ABSTAINED') {
        await appendAudit(db, record, { event_type: 'ESCALATED', quote_version: p.version, actor: SYSTEM_ACTOR, at: p.ready_at, note: 'Chuyển Quản lý thẩm định ngoại lệ.' })
      }
    }
    if (record.pdf) await settlePdf(db, record, now)
  }
}

function pdfPhase(job: PdfJob, now: number): PdfStatus {
  const t = now - job.requested_at
  if (job.retry && t < scaled(1_000)) return 'RETRYING'
  if (t < scaled(1_500)) return 'PENDING'
  if (t < scaled(3_500)) return 'GENERATING'
  return job.fail ? 'FAILED' : 'PDF_ISSUED'
}

async function settlePdf(db: MockDb, record: QuoteRecord, now: number) {
  const job = record.pdf
  if (!job) return
  const q = record.versions[job.version - 1]
  const status = pdfPhase(job, now)
  q.pdf_status = status
  if (status === 'PDF_ISSUED' && job.logged !== 'ISSUED') {
    job.logged = 'ISSUED'
    job.pdf_sha256 = await sha256Hex(`${q.quote_id}:v${q.quote_version}:${q.artifact_hash}`)
    await appendAudit(db, record, { event_type: 'PDF_ISSUED', quote_version: job.version, actor: SYSTEM_ACTOR, at: now, note: `pdf_sha256 ${job.pdf_sha256.slice(0, 16)}…` })
  }
  if (status === 'FAILED' && job.logged !== 'FAILED') {
    job.logged = 'FAILED'
    await appendAudit(db, record, { event_type: 'PDF_FAILED', quote_version: job.version, actor: SYSTEM_ACTOR, at: now, note: 'Worker xuất PDF lỗi, chờ thử lại.' })
  }
}

export async function submitQuote(db: MockDb, actor: StaffUser, record: QuoteRecord, now: number): Promise<Quote> {
  const q = latest(record)
  if (q.created_by.user_id !== actor.user_id) throw new MockError(403, 'FORBIDDEN', 'Bạn không phụ trách hồ sơ này.')
  if (q.status !== 'DRAFT') throw transition('Chỉ gửi duyệt được hồ sơ đã tính giá thành công.')
  const at = new Date(now).toISOString()
  q.status = 'READY_FOR_REVIEW'
  q.submitted_at = at
  q.updated_at = at
  await appendAudit(db, record, { event_type: 'SUBMITTED', quote_version: q.quote_version, actor: actorOf(actor), at: now })
  return view(record)
}

export async function decideQuote(
  db: MockDb,
  actor: StaffUser,
  record: QuoteRecord,
  decision: ApprovalRecord['decision'],
  reason: string,
  now: number,
): Promise<Quote> {
  const q = latest(record)
  const allowed: QuoteWorkflowStatus[] = decision === 'APPROVED' ? ['READY_FOR_REVIEW'] : ['READY_FOR_REVIEW', 'ABSTAINED']
  if (!allowed.includes(q.status)) throw transition(`Hồ sơ đang ở trạng thái ${q.status}, không thể thực hiện thao tác này.`)
  if (q.created_by.user_id === actor.user_id) throw new MockError(403, 'SOD_VIOLATION', 'Người lập hồ sơ không được tự phê duyệt (Separation of Duties).')
  if (decision !== 'APPROVED' && !reason.trim()) throw invalid('Bắt buộc nhập lý do.')

  const at = new Date(now).toISOString()
  let signature: ApprovalRecord['signature'] = null
  if (decision === 'APPROVED') {
    const { versions: _v, ...payload } = q
    q.artifact_hash = await sha256Hex(canonicalJsonStringify({ ...payload, approved_by: actor.user_id, approved_at: at }))
    const sig = (await sha256Hex(`ed25519:${q.artifact_hash}`)) + (await sha256Hex(`sig:${q.artifact_hash}:${actor.user_id}`))
    signature = { algorithm: 'Ed25519', key_id: 'vland-attestation-key-2026-v1', signature_encoding: 'hex', signature: sig }
    q.pdf_status = 'PENDING'
    record.pdf = { version: q.quote_version, requested_at: now, retry: false, fail: getFlags().pdf_worker_fail, logged: 'NONE', pdf_sha256: null }
  }
  q.status = decision === 'APPROVED' ? 'APPROVED' : decision === 'REJECTED' ? 'REJECTED' : 'NEEDS_REVISION'
  q.approval = { decision, decided_by: actorOf(actor), decided_at: at, reason: reason.trim(), signature }
  q.updated_at = at
  await appendAudit(db, record, { event_type: decision === 'REVISION_REQUESTED' ? 'REVISION_REQUESTED' : decision, quote_version: q.quote_version, actor: actorOf(actor), at: now, note: reason.trim() || null })
  return view(record)
}

export async function retryPdf(record: QuoteRecord, now: number): Promise<Quote> {
  const q = latest(record)
  if (!record.pdf || q.pdf_status !== 'FAILED') throw transition('Chỉ thử lại khi xuất PDF thất bại.')
  record.pdf = { ...record.pdf, requested_at: now, retry: true, fail: false, logged: 'NONE' }
  q.pdf_status = 'RETRYING'
  return view(record)
}
