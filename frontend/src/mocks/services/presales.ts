import type {
  ChatMessage,
  CustomerConstraints,
  HandoffReceipt,
  HandoffRequest,
  LeadDossier,
  LeadTemperature,
  PreSalesSession,
  QuoteAccepted,
  StaffUser,
  TransactionContext,
} from '@/api/contracts'
import { nextId, type MockDb } from '../db'
import { buildReferencePlan, EMPTY_CONSTRAINTS, extractConstraints, missingOf, nextQuestion, summarizeNeeds } from '../engine/presales'
import { PROJECTS_FIXTURE } from '../fixtures/units'
import { actorOf, STAFF_FIXTURE } from '../fixtures/users'
import { invalid, MockError, notFound, transition } from './errors'
import { createQuote } from './quotes'

const SESSION_TTL_MS = 24 * 3_600_000
const SLA_HOURS: Record<LeadTemperature, number> = { HOT: 2, WARM: 8, COLD: 24 }
const INJECTION = /(bỏ qua (mọi |các )?(hướng dẫn|chỉ dẫn)|ignore (all |previous )?instructions|system prompt|bạn là admin|phê duyệt báo giá)/i

const iso = (ms: number) => new Date(ms).toISOString()

function message(db: MockDb, role: ChatMessage['role'], text: string, now: number, suggestions: string[] = []): ChatMessage {
  return { message_id: `MSG-${String(nextId(db, 'chat')).padStart(6, '0')}`, role, text, created_at: iso(now), suggestions }
}

export function findSession(db: MockDb, sessionId: string, now: number): PreSalesSession {
  const s = db.presales.find((x) => x.session_id === sessionId)
  if (!s) throw notFound('phiên tư vấn')
  if (s.status !== 'HANDED_OFF' && Date.parse(s.expires_at) < now) s.status = 'EXPIRED'
  return s
}

function assertActive(s: PreSalesSession) {
  if (s.status === 'EXPIRED') throw new MockError(410, 'INVALID_STATE_TRANSITION', 'Phiên tư vấn đã hết hạn. Vui lòng bắt đầu phiên mới.')
  if (s.status === 'HANDED_OFF') throw transition('Phiên tư vấn đã được chuyển cho chuyên viên.')
}

function askOrConfirm(db: MockDb, s: PreSalesSession, now: number) {
  s.missing_constraints = missingOf(s.constraints)
  const q = nextQuestion(s.constraints)
  if (q) {
    s.status = 'COLLECTING'
    s.messages.push(message(db, 'ASSISTANT', q.text, now, q.suggestions))
  } else {
    s.status = 'AWAITING_CONFIRMATION'
    s.messages.push(message(db, 'ASSISTANT', 'Em đã ghi nhận đủ thông tin. Anh/chị kiểm tra lại và bấm Xác nhận để em lập phương án tham khảo.', now))
  }
}

export function createSession(db: MockDb, preferredUnitCode: string | null, now: number): PreSalesSession {
  const unit = preferredUnitCode ? db.units.find((u) => u.unit_code === preferredUnitCode) : undefined
  const constraints: CustomerConstraints = unit
    ? { ...EMPTY_CONSTRAINTS, preferred_unit_code: unit.unit_code, project_id: unit.project_id, bedrooms: unit.bedrooms }
    : { ...EMPTY_CONSTRAINTS }
  const s: PreSalesSession = {
    session_id: `SES-${String(nextId(db, 'session')).padStart(5, '0')}`,
    status: 'COLLECTING',
    created_at: iso(now),
    expires_at: iso(now + SESSION_TTL_MS),
    messages: [],
    constraints,
    missing_constraints: [],
    constraints_confirmed_at: null,
    plan: null,
    dossier_id: null,
  }
  s.messages.push(
    message(
      db,
      'ASSISTANT',
      unit
        ? `Chào anh/chị! Em hỗ trợ lập phương án tài chính tham khảo cho căn ${unit.unit_code} (${unit.project_name}).`
        : 'Chào anh/chị! Em hỗ trợ lập phương án tài chính tham khảo theo chính sách bán hàng đang áp dụng.',
      now,
    ),
  )
  askOrConfirm(db, s, now)
  db.presales.unshift(s)
  return s
}

export function receiveMessage(db: MockDb, s: PreSalesSession, text: string, now: number): PreSalesSession {
  assertActive(s)
  const clean = text.trim().slice(0, 1_000)
  if (!clean) throw invalid('Tin nhắn trống.')
  s.messages.push(message(db, 'CUSTOMER', clean, now))
  // N-02 security guardrail input — không làm theo chỉ dẫn chèn vào hội thoại.
  if (INJECTION.test(clean)) {
    s.messages.push(message(db, 'ASSISTANT', 'Em chỉ hỗ trợ lập phương án tài chính tham khảo theo chính sách bán hàng hiện hành.', now + 1))
    return s
  }
  s.constraints = extractConstraints(clean, s.constraints, db.units)
  s.plan = null
  s.constraints_confirmed_at = null
  askOrConfirm(db, s, now + 1)
  return s
}

export function confirmConstraints(_db: MockDb, s: PreSalesSession, constraints: CustomerConstraints, now: number): PreSalesSession {
  assertActive(s)
  const missing = missingOf(constraints)
  if (missing.length) throw invalid('Còn thiếu thông tin bắt buộc.')
  if ((constraints.own_funds_vnd ?? 0) <= 0) throw invalid('Vốn tự có phải lớn hơn 0.')
  s.constraints = constraints
  s.missing_constraints = []
  s.constraints_confirmed_at = iso(now)
  s.status = 'AWAITING_CONFIRMATION'
  return s
}

const vnd = (n: number) => `${n.toLocaleString('vi-VN')} đ`

export async function generatePlan(db: MockDb, s: PreSalesSession, now: number): Promise<PreSalesSession> {
  assertActive(s)
  if (!s.constraints_confirmed_at) throw transition('Cần xác nhận thông tin trước khi lập phương án.')
  const today = iso(now).slice(0, 10)
  const { plan, reason } = await buildReferencePlan({
    constraints: s.constraints,
    units: db.units,
    policies: db.policies,
    today,
    now,
    planId: `PLAN-${String(nextId(db, 'plan')).padStart(5, '0')}`,
  })
  if (!plan) {
    s.messages.push(message(db, 'ASSISTANT', `${reason} Chuyên viên có thể tư vấn thêm khi anh/chị để lại thông tin.`, now))
    return s
  }
  s.plan = plan
  s.status = 'PLAN_READY'
  const rec = plan.scenarios.find((x) => x.scenario_code === plan.recommended_scenario)
  s.messages.push(
    message(
      db,
      'ASSISTANT',
      rec
        ? `Em đã lập 3 phương án tham khảo cho căn ${rec.unit_code}. Theo ưu tiên của anh/chị, phương án ${rec.label} có đợt đầu ${vnd(rec.initial_payment_vnd)}.`
        : 'Với vốn tự có hiện tại, chưa phương án nào đủ đợt thanh toán đầu. Chuyên viên có thể tư vấn căn phù hợp hơn.',
      now,
    ),
  )
  return s
}

function temperatureOf(s: PreSalesSession): LeadTemperature {
  const rec = s.plan?.scenarios.find((x) => x.scenario_code === s.plan?.recommended_scenario)
  if (rec && (s.constraints.own_funds_vnd ?? 0) >= rec.total_contract_price_vnd * 0.3) return 'HOT'
  return rec ? 'WARM' : 'COLD'
}

/** Sale nhận hồ sơ: chia đều cho Sale đang ít hồ sơ chờ nhất. */
function pickSale(db: MockDb): StaffUser {
  const sales = STAFF_FIXTURE.filter((u) => u.role === 'SALE')
  const load = (u: StaffUser) => db.dossiers.filter((d) => d.assigned_sale?.user_id === u.user_id && d.status !== 'CONVERTED_TO_QUOTE').length
  return [...sales].sort((a, b) => load(a) - load(b))[0]
}

export function createDossier(db: MockDb, s: PreSalesSession, body: HandoffRequest, now: number): LeadDossier {
  const temperature = temperatureOf(s)
  const sale = pickSale(db)
  const dossier: LeadDossier = {
    dossier_id: `LD-${new Date(now).getFullYear()}-${String(nextId(db, 'dossier')).padStart(4, '0')}`,
    status: 'ASSIGNED',
    temperature,
    created_at: iso(now),
    sla_due_at: iso(now + SLA_HOURS[temperature] * 3_600_000),
    assigned_sale: actorOf(sale),
    source_session_id: s.session_id,
    customer: { full_name: body.full_name.trim(), phone: body.phone.trim() },
    consent: { granted_at: iso(now), consent_text_version: body.consent_text_version },
    needs_summary: summarizeNeeds(s.constraints, s.plan?.scenarios[0]?.unit_code ?? s.constraints.preferred_unit_code),
    constraints: s.constraints,
    reference_plan: s.plan,
    converted_quote_id: null,
  }
  db.dossiers.unshift(dossier)
  return dossier
}

export function handoff(db: MockDb, s: PreSalesSession, body: HandoffRequest, now: number): HandoffReceipt {
  assertActive(s)
  if (s.status !== 'PLAN_READY' || !s.plan) throw transition('Cần có phương án tham khảo trước khi chuyển chuyên viên.')
  if (body.consent !== true) throw invalid('Cần đồng ý chia sẻ thông tin.')
  if (!body.full_name?.trim()) throw invalid('Vui lòng nhập họ tên.')
  if (!/^[0-9 +]{9,15}$/.test(body.phone?.trim() ?? '')) throw invalid('Số điện thoại không hợp lệ.')
  const dossier = createDossier(db, s, body, now)
  s.status = 'HANDED_OFF'
  s.dossier_id = dossier.dossier_id
  s.messages.push(
    message(db, 'ASSISTANT', `Chuyên viên ${dossier.assigned_sale?.full_name} sẽ liên hệ anh/chị trong vòng ${SLA_HOURS[dossier.temperature]} giờ để lập báo giá chính thức.`, now),
  )
  return { dossier_id: dossier.dossier_id, handed_off_at: iso(now) }
}

export function listDossiers(db: MockDb, user: StaffUser): LeadDossier[] {
  return db.dossiers.filter((d) => !d.assigned_sale || d.assigned_sale.user_id === user.user_id)
}

/** Official Quote từ dossier: tạo quote mới, tính lại từ đầu — không kế thừa số liệu pre-sales (ADR-020). */
export async function convertDossier(db: MockDb, user: StaffUser, dossierId: string, context: TransactionContext, now: number): Promise<QuoteAccepted> {
  const dossier = db.dossiers.find((d) => d.dossier_id === dossierId)
  if (!dossier) throw notFound(`hồ sơ khách ${dossierId}`)
  if (dossier.assigned_sale && dossier.assigned_sale.user_id !== user.user_id) throw new MockError(403, 'FORBIDDEN', 'Hồ sơ khách do chuyên viên khác phụ trách.')
  if (dossier.status === 'CONVERTED_TO_QUOTE') throw transition(`Hồ sơ đã được chuyển thành báo giá ${dossier.converted_quote_id}.`)
  const accepted = await createQuote(db, user, context, dossierId, now)
  dossier.status = 'CONVERTED_TO_QUOTE'
  dossier.assigned_sale = actorOf(user)
  dossier.converted_quote_id = accepted.quote_id
  return accepted
}

export const projectName = (id: string | null) => PROJECTS_FIXTURE.find((p) => p.project_id === id)?.name ?? ''
