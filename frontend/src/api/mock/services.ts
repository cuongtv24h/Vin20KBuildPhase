/**
 * Nghiệp vụ phía "server" của backend giả lập. Mỗi hàm thao tác trực tiếp trên MockDbState
 * và áp đúng quy tắc mà backend thật phải áp (quyền, máy trạng thái, validate).
 */
import type {
  ApprovalDecisionRequest,
  CreateLeadRequest,
  CreateQuoteRequest,
  CustomerQuoteView,
  CustomerResponseRequest,
  QuoteVerification,
} from '@/api/contracts'
import { ApiError } from '@/api/errors'
import type { MockDbState } from '@/api/mock/db'
import { PAYMENT_PLANS_FIXTURE } from '@/api/mock/fixtures/plans'
import { STAFF_FIXTURE } from '@/api/mock/fixtures/users'
import { selectPolicyForDate } from '@/engine/conflictDetector'
import { analyzeQuote, buildSnapshot, hashSnapshot } from '@/engine/quoteFactory'
import { buildPaymentSchedule } from '@/engine/schedule'
import { canPerform, type QuoteAction } from '@/engine/workflow'
import { CHANNEL_LABEL } from '@/lib/labels'
import type {
  ApartmentUnit,
  ApprovalRecord,
  Lead,
  PolicyVersion,
  Quote,
  QuoteEvent,
  QuoteEventType,
  ShareChannel,
  StaffUser,
} from '@/types/domain'

export const QUOTE_VALIDITY_DAYS = 7

// ─── Tra cứu ───────────────────────────────────────────────────────────────

export function findUnit(db: MockDbState, unitCode: string): ApartmentUnit {
  const unit = db.units.find((u) => u.unitCode === unitCode)
  if (!unit) throw new ApiError(404, 'UNIT_NOT_FOUND', `Không tìm thấy căn hộ ${unitCode}.`)
  return unit
}

export function findQuote(db: MockDbState, quoteId: string): Quote {
  const quote = db.quotes.find((q) => q.quoteId === quoteId)
  if (!quote) throw new ApiError(404, 'QUOTE_NOT_FOUND', `Không tìm thấy hồ sơ ${quoteId}.`)
  return quote
}

export function findLead(db: MockDbState, leadId: string): Lead {
  const lead = db.leads.find((l) => l.leadId === leadId)
  if (!lead) throw new ApiError(404, 'LEAD_NOT_FOUND', `Không tìm thấy yêu cầu ${leadId}.`)
  return lead
}

export function findPolicy(db: MockDbState, policyId: string): PolicyVersion {
  const policy = db.policies.find((p) => p.policyId === policyId)
  if (!policy) throw new ApiError(404, 'POLICY_NOT_FOUND', `Không tìm thấy chính sách ${policyId}.`)
  return policy
}

export function findQuoteByToken(db: MockDbState, shareToken: string, now: string): Quote {
  const quote = db.quotes.find((q) => q.distribution?.shareToken === shareToken)
  if (!quote || quote.status !== 'APPROVED' || !quote.distribution) {
    throw new ApiError(404, 'SHARED_QUOTE_NOT_FOUND', 'Đường dẫn báo giá không tồn tại hoặc đã bị thu hồi.')
  }
  if (quote.distribution.expiresAt < now) {
    throw new ApiError(410, 'SHARED_QUOTE_EXPIRED', 'Báo giá đã hết thời hạn hiệu lực. Vui lòng liên hệ chuyên viên tư vấn để được cập nhật.')
  }
  return quote
}

export function activePolicyFor(db: MockDbState, projectId: string, date: string): PolicyVersion | null {
  return selectPolicyForDate(db.policies, projectId, date)
}

// ─── Tiện ích ──────────────────────────────────────────────────────────────

function pushEvent(db: MockDbState, quote: Quote, type: QuoteEventType, at: string, actor: { name: string; role: QuoteEvent['actorRole'] }, note?: string) {
  db.counters.event += 1
  quote.history.push({
    eventId: `EVT-${String(db.counters.event).padStart(6, '0')}`,
    type,
    at,
    version: quote.version,
    actorName: actor.name,
    actorRole: actor.role,
    ...(note ? { note } : {}),
  })
  quote.updatedAt = at
}

function assertTransition(action: QuoteAction, quote: Quote, actor: StaffUser) {
  if (!canPerform(action, quote.status, actor.role)) {
    throw new ApiError(409, 'INVALID_TRANSITION', `Không thể thực hiện thao tác này khi hồ sơ ở trạng thái ${quote.status}.`)
  }
}

function assertOwner(quote: Quote, actor: StaffUser) {
  if (quote.ownerId !== actor.userId) {
    throw new ApiError(403, 'FORBIDDEN', 'Bạn không phụ trách hồ sơ này.')
  }
}

function randomToken(length = 18): string {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
  const bytes = crypto.getRandomValues(new Uint8Array(length))
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join('')
}

function addDays(iso: string, days: number): string {
  return new Date(new Date(iso).getTime() + days * 86_400_000).toISOString()
}

function validateContext(input: CreateQuoteRequest) {
  if (!input.customerName.trim()) throw new ApiError(422, 'VALIDATION_ERROR', 'Thiếu tên khách hàng.')
  if (!/^[0-9 +]{9,15}$/.test(input.customerPhone.trim())) {
    throw new ApiError(422, 'VALIDATION_ERROR', 'Số điện thoại khách hàng không hợp lệ.')
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(input.transactionDate)) throw new ApiError(422, 'VALIDATION_ERROR', 'Ngày giao dịch không hợp lệ.')
  if (!Number.isInteger(input.unitsQuantity) || input.unitsQuantity < 1) {
    throw new ApiError(422, 'VALIDATION_ERROR', 'Số lượng căn phải là số nguyên ≥ 1.')
  }
}

function runAnalysis(db: MockDbState, input: CreateQuoteRequest) {
  const unit = findUnit(db, input.unitCode)
  if (unit.status === 'SOLD') throw new ApiError(409, 'UNIT_UNAVAILABLE', `Căn ${unit.unitCode} đã bán, không thể lập báo giá.`)
  const { leadId: _leadId, ...context } = input
  const activePolicy = activePolicyFor(db, unit.projectId, context.transactionDate)
  const analysis = analyzeQuote({ unit, context, activePolicy, plans: PAYMENT_PLANS_FIXTURE })
  return { unit, context, analysis }
}

const SYSTEM = { name: 'PricePolicy Agent', role: 'SYSTEM' as const }

// ─── Quotes ────────────────────────────────────────────────────────────────

export function createQuoteRecord(db: MockDbState, actor: StaffUser, input: CreateQuoteRequest, at: string): Quote {
  validateContext(input)
  const { unit, context, analysis } = runAnalysis(db, input)

  if (input.leadId) {
    const lead = findLead(db, input.leadId)
    if (lead.assignedSaleId && lead.assignedSaleId !== actor.userId) {
      throw new ApiError(403, 'FORBIDDEN', 'Yêu cầu này đang do chuyên viên khác phụ trách.')
    }
    lead.assignedSaleId = actor.userId
    lead.assignedSaleName = actor.fullName
    if (lead.status === 'NEW') lead.status = 'IN_PROGRESS'
    lead.updatedAt = at
  }

  db.counters.quote += 1
  const d = new Date(at)
  const quoteId = `QUO-${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(db.counters.quote).padStart(5, '0')}`

  const quote: Quote = {
    quoteId,
    version: 1,
    status: analysis.status,
    createdAt: at,
    updatedAt: at,
    ownerId: actor.userId,
    ownerName: actor.fullName,
    leadId: input.leadId,
    context,
    unit: { ...unit },
    preflight: analysis.preflight,
    scenarios: analysis.scenarios,
    recommendation: analysis.recommendation,
    riskFlag: analysis.riskFlag,
    approval: null,
    snapshot: null,
    snapshotHash: null,
    distribution: null,
    history: [],
  }
  pushEvent(db, quote, 'CREATED', at, { name: actor.fullName, role: actor.role })
  if (quote.status === 'ABSTAINED') {
    pushEvent(db, quote, 'ESCALATED', at, SYSTEM, 'Tự động chuyển Quản lý thẩm định ngoại lệ.')
  }
  db.quotes.unshift(quote)
  return quote
}

export function reviseQuoteRecord(db: MockDbState, actor: StaffUser, quoteId: string, input: CreateQuoteRequest, at: string): Quote {
  const quote = findQuote(db, quoteId)
  assertOwner(quote, actor)
  assertTransition('REVISE', quote, actor)
  validateContext(input)
  const { unit, context, analysis } = runAnalysis(db, { ...input, leadId: quote.leadId })

  quote.version += 1
  quote.status = analysis.status
  quote.context = context
  quote.unit = { ...unit }
  quote.preflight = analysis.preflight
  quote.scenarios = analysis.scenarios
  quote.recommendation = analysis.recommendation
  quote.riskFlag = analysis.riskFlag
  quote.approval = null
  pushEvent(db, quote, 'REVISED', at, { name: actor.fullName, role: actor.role })
  if (quote.status === 'ABSTAINED') {
    pushEvent(db, quote, 'ESCALATED', at, SYSTEM, 'Tự động chuyển Quản lý thẩm định ngoại lệ.')
  }
  return quote
}

export function submitQuoteRecord(db: MockDbState, actor: StaffUser, quoteId: string, at: string): Quote {
  const quote = findQuote(db, quoteId)
  assertOwner(quote, actor)
  assertTransition('SUBMIT', quote, actor)
  quote.status = 'READY_FOR_REVIEW'
  pushEvent(db, quote, 'SUBMITTED', at, { name: actor.fullName, role: actor.role })
  return quote
}

export async function decideQuoteRecord(
  db: MockDbState,
  actor: StaffUser,
  quoteId: string,
  input: ApprovalDecisionRequest,
  at: string,
): Promise<Quote> {
  const quote = findQuote(db, quoteId)
  const action: QuoteAction =
    input.decision === 'APPROVED' ? 'APPROVE' : input.decision === 'REJECTED' ? 'REJECT' : 'REQUEST_REVISION'
  assertTransition(action, quote, actor)
  const notes = input.notes.trim()
  if (input.decision !== 'APPROVED' && notes.length === 0) {
    throw new ApiError(422, 'VALIDATION_ERROR', 'Vui lòng nhập lý do cho Sale.')
  }

  const approval: Omit<ApprovalRecord, 'signatureHex'> = {
    approverId: actor.userId,
    approverName: actor.fullName,
    decision: input.decision,
    notes,
    timestamp: at,
  }

  if (input.decision === 'APPROVED') {
    const snapshot = buildSnapshot(quote, approval, at)
    const hash = await hashSnapshot(snapshot)
    quote.snapshot = snapshot
    quote.snapshotHash = hash
    quote.approval = { ...approval, signatureHex: hash }
    quote.status = 'APPROVED'
    pushEvent(db, quote, 'APPROVED', at, { name: actor.fullName, role: actor.role }, notes || undefined)
  } else {
    quote.approval = approval
    quote.status = input.decision
    pushEvent(db, quote, input.decision === 'REJECTED' ? 'REJECTED' : 'REVISION_REQUESTED', at, { name: actor.fullName, role: actor.role }, notes)
  }
  return quote
}

export function shareQuoteRecord(db: MockDbState, actor: StaffUser, quoteId: string, channel: ShareChannel, at: string): Quote {
  const quote = findQuote(db, quoteId)
  assertOwner(quote, actor)
  assertTransition('SHARE', quote, actor)
  quote.distribution = {
    shareToken: quote.distribution?.shareToken ?? randomToken(),
    channel,
    sharedAt: at,
    sharedBy: actor.fullName,
    expiresAt: addDays(at, QUOTE_VALIDITY_DAYS),
    viewedAt: quote.distribution?.viewedAt ?? null,
    customerResponse: quote.distribution?.customerResponse ?? null,
  }
  pushEvent(db, quote, 'SHARED', at, { name: actor.fullName, role: actor.role }, `Gửi qua ${CHANNEL_LABEL[channel]}`)
  if (quote.leadId) {
    const lead = findLead(db, quote.leadId)
    if (lead.status === 'NEW' || lead.status === 'IN_PROGRESS') lead.status = 'QUOTE_SENT'
    lead.updatedAt = at
  }
  return quote
}

export async function verifyQuoteIntegrity(quote: Quote, at: string): Promise<QuoteVerification> {
  if (!quote.snapshot || !quote.snapshotHash) {
    throw new ApiError(409, 'NOT_SIGNED', 'Hồ sơ chưa được ký duyệt nên chưa có mã xác thực.')
  }
  const recomputed = await hashSnapshot(quote.snapshot)
  return {
    quoteId: quote.quoteId,
    storedHash: quote.snapshotHash,
    recomputedHash: recomputed,
    valid: recomputed === quote.snapshotHash,
    verifiedAt: at,
  }
}

// ─── Khách hàng ────────────────────────────────────────────────────────────

export function markSharedQuoteViewed(db: MockDbState, quote: Quote, at: string) {
  if (!quote.distribution || quote.distribution.viewedAt) return
  quote.distribution.viewedAt = at
  pushEvent(db, quote, 'CUSTOMER_VIEWED', at, { name: quote.context.customerName, role: 'CUSTOMER' })
}

export function respondSharedQuote(db: MockDbState, quote: Quote, input: CustomerResponseRequest, at: string) {
  if (!quote.distribution) return
  quote.distribution.customerResponse = { ...input, note: input.note.trim(), at }
  const label = input.decision === 'ACCEPTED' ? 'Đồng ý báo giá, đăng ký lịch ký cọc' : 'Cần tư vấn thêm'
  pushEvent(db, quote, 'CUSTOMER_RESPONDED', at, { name: quote.context.customerName, role: 'CUSTOMER' }, [label, input.note.trim()].filter(Boolean).join(' — '))
  if (quote.leadId && input.decision === 'ACCEPTED') {
    const lead = findLead(db, quote.leadId)
    lead.status = 'CUSTOMER_ACCEPTED'
    lead.updatedAt = at
  }
}

export function toCustomerView(quote: Quote): CustomerQuoteView {
  if (!quote.approval || !quote.snapshotHash || !quote.distribution) {
    throw new ApiError(404, 'SHARED_QUOTE_NOT_FOUND', 'Báo giá chưa được phát hành.')
  }
  const rep = STAFF_FIXTURE.find((u) => u.userId === quote.ownerId)
  return {
    quoteId: quote.quoteId,
    version: quote.version,
    issuedAt: quote.approval.timestamp,
    validUntil: quote.distribution.expiresAt,
    customerName: quote.context.customerName,
    unit: quote.unit,
    projectName: quote.unit.projectName,
    policy: quote.preflight?.activePolicy ?? null,
    objective: quote.context.objective,
    recommendedPlan: quote.recommendation?.recommendedPlan ?? null,
    rationale: quote.recommendation?.rationale ?? null,
    scenarios: quote.scenarios.map((s) => {
      const plan = PAYMENT_PLANS_FIXTURE.find((p) => p.plan === s.plan)
      return { ...s, schedule: plan ? buildPaymentSchedule(s.netPrice, plan) : [] }
    }),
    salesRep: { fullName: quote.ownerName, phone: rep?.phone ?? '', email: rep?.email ?? '' },
    approvedBy: quote.approval.approverName,
    snapshotHash: quote.snapshotHash,
    customerResponse: quote.distribution.customerResponse,
  }
}

// ─── Leads ─────────────────────────────────────────────────────────────────

export function createLeadRecord(db: MockDbState, input: CreateLeadRequest, at: string): Lead {
  if (!input.fullName.trim()) throw new ApiError(422, 'VALIDATION_ERROR', 'Vui lòng nhập họ tên.')
  if (!/^[0-9 +]{9,15}$/.test(input.phone.trim())) throw new ApiError(422, 'VALIDATION_ERROR', 'Số điện thoại không hợp lệ.')
  if (input.email && !/^\S+@\S+\.\S+$/.test(input.email)) throw new ApiError(422, 'VALIDATION_ERROR', 'Email không hợp lệ.')
  findUnit(db, input.unitCode)

  db.counters.lead += 1
  const lead: Lead = {
    leadId: `LEAD-${new Date(at).getFullYear()}-${String(db.counters.lead).padStart(4, '0')}`,
    createdAt: at,
    updatedAt: at,
    fullName: input.fullName.trim(),
    phone: input.phone.trim(),
    email: input.email.trim(),
    unitCode: input.unitCode,
    customerSegment: input.customerSegment,
    objective: input.objective,
    note: input.note.trim(),
    status: 'NEW',
    assignedSaleId: null,
    assignedSaleName: null,
  }
  db.leads.unshift(lead)
  return lead
}

export function claimLeadRecord(db: MockDbState, actor: StaffUser, leadId: string, at: string): Lead {
  const lead = findLead(db, leadId)
  if (lead.assignedSaleId && lead.assignedSaleId !== actor.userId) {
    throw new ApiError(409, 'LEAD_ALREADY_ASSIGNED', `Yêu cầu đã được ${lead.assignedSaleName} tiếp nhận.`)
  }
  lead.assignedSaleId = actor.userId
  lead.assignedSaleName = actor.fullName
  if (lead.status === 'NEW') lead.status = 'IN_PROGRESS'
  lead.updatedAt = at
  return lead
}
