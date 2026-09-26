import { delay, http, HttpResponse } from 'msw'
import type {
  ComplianceCheckRequest,
  ConfirmConstraintsRequest,
  DraftMessageRequest,
  HandoffRequest,
  MessageSendResult,
  PolicyDocument,
  PreSalesMessageRequest,
  PreSalesSessionCreate,
  QuoteCreateRequest,
  SendMessageCommand,
} from '@/api/contracts'
import type { DemoAccount, MockFlags } from '@/api/devtools'
import { getDb, nextId, resetDb, commit } from '../db'
import { runBenchmark } from '../engine/benchmark'
import { checkMessage, draftMessage } from '../engine/compliance'
import { sha256Hex, sha256HexOfBuffer } from '../engine/hash'
import { testPolicyRules } from '../engine/rulesTest'
import { actorOf, MOCK_PASSWORD, STAFF_FIXTURE } from '../fixtures/users'
import { getFlags, scaled, setFlags } from '../flags'
import { appendAudit } from '../services/audit'
import { invalid, MockError, notFound, transition } from '../services/errors'
import { confirmConstraints, convertDossier, createSession, findSession, generatePlan, handoff, listDossiers, receiveMessage } from '../services/presales'
import { assertVisible, findRecord, latest } from '../services/quotes'
import { route } from './route'

const iso = (ms: number) => new Date(ms).toISOString()

export const leadHandlers = [
  route('leadList', ({ db, staff }) => ({ body: listDossiers(db, staff()) })),
  route(
    'leadConvert',
    async ({ db, staff, params, now, json }) => ({ status: 202, body: await convertDossier(db, staff(), params.dossier_id, await json<QuoteCreateRequest>(), now) }),
    { fixedDelayMs: 150 },
  ),
]

export const preSalesHandlers = [
  route('preSalesCreate', async ({ db, now, json }) => ({ status: 201, body: createSession(db, (await json<PreSalesSessionCreate>())?.preferred_unit_code ?? null, now) })),
  route('preSalesGet', ({ db, params, now }) => ({ body: findSession(db, params.session_id, now) })),
  route('preSalesMessage', async ({ db, params, now, json }) => ({ body: receiveMessage(db, findSession(db, params.session_id, now), (await json<PreSalesMessageRequest>())?.text ?? '', now) })),
  route('preSalesConfirm', async ({ db, params, now, json }) => {
    const body = await json<ConfirmConstraintsRequest>()
    if (!body?.constraints) throw invalid('Thiếu thông tin xác nhận.')
    return { body: confirmConstraints(db, findSession(db, params.session_id, now), body.constraints, now) }
  }),
  route('preSalesPlan', async ({ db, params, now }) => {
    // Kiểm tra chính sách + tính 3 phương án: thời gian xử lý thực tế ~1,5–2,5s.
    await delay(scaled(1_500 + Math.random() * 1_000, true))
    return { body: await generatePlan(db, findSession(db, params.session_id, now), Date.now()) }
  }),
  route('preSalesHandoff', async ({ db, params, now, json }) => ({ body: handoff(db, findSession(db, params.session_id, now), await json<HandoffRequest>(), now) })),
]

export const complianceHandlers = [
  route('complianceCheck', async ({ db, staff, json }) => {
    const body = await json<ComplianceCheckRequest>()
    const record = findRecord(db, body?.quote_id ?? '')
    assertVisible(record, staff())
    const quote = record.versions[(body.quote_version ?? 0) - 1]
    if (!quote) throw notFound('phiên bản báo giá')
    const policy = db.policies.find((p) => p.policy_id === quote.policy_snapshot_ref?.policy_id) ?? null
    const checkId = `CHK-${String(nextId(db, 'check')).padStart(6, '0')}`
    const result = await checkMessage({ text: body.message_text ?? '', mode: body.mode, quote, policy, checkId })
    db.checks[checkId] = { message_hash: result.message_hash, quote_id: quote.quote_id, quote_version: quote.quote_version }
    return { body: result }
  }),

  route('complianceDraft', async ({ db, staff, json }) => {
    const body = await json<DraftMessageRequest>()
    const record = findRecord(db, body?.quote_id ?? '')
    assertVisible(record, staff())
    const quote = record.versions[(body.quote_version ?? 0) - 1]
    if (!quote) throw notFound('phiên bản báo giá')
    const policy = db.policies.find((p) => p.policy_id === quote.policy_snapshot_ref?.policy_id) ?? null
    return { body: { message_text: draftMessage(quote, policy) } }
  }),

  /** Final send gate: tự băm & kiểm lại FINAL_SEND, không tin kết quả kiểm tra từ trình duyệt. */
  route('messageSend', async ({ db, staff, now, json }) => {
    const user = staff()
    const body = await json<SendMessageCommand>()
    const record = findRecord(db, body?.quote_id ?? '')
    assertVisible(record, user)
    const quote = latest(record)
    if (quote.quote_version !== body.quote_version) throw new MockError(409, 'STALE_QUOTE_VERSION', 'Báo giá đã có phiên bản mới, cần kiểm tra lại tin nhắn.')
    if (quote.status !== 'APPROVED') throw transition('Chỉ gửi khách báo giá đã được phê duyệt.')
    const hash = `sha256:${await sha256Hex(body.message_text ?? '')}`
    if (hash !== body.message_hash) throw invalid('Nội dung đã thay đổi sau lần kiểm tra — cần kiểm tra lại.')
    const policy = db.policies.find((p) => p.policy_id === quote.policy_snapshot_ref?.policy_id) ?? null
    const verdict = await checkMessage({ text: body.message_text, mode: 'FINAL_SEND', quote, policy, checkId: `CHK-${String(nextId(db, 'check')).padStart(6, '0')}` })
    const blocked = verdict.overall_status === 'PROHIBITED'
    await appendAudit(db, record, {
      event_type: blocked ? 'MESSAGE_BLOCKED' : 'MESSAGE_SENT',
      quote_version: quote.quote_version,
      actor: actorOf(user),
      at: now,
      note: `${body.channel} · ${verdict.overall_status} · ${hash.slice(0, 19)}…`,
    })
    if (blocked) {
      commit()
      throw new MockError(422, 'COMPLIANCE_BLOCKED', 'Tin nhắn chứa phát ngôn bị cấm và đã bị chặn ở cổng gửi.')
    }
    const result: MessageSendResult = { message_id: `MSGOUT-${String(nextId(db, 'outbound')).padStart(6, '0')}`, status: 'SENT', sent_at: iso(now), verdict }
    return { body: result }
  }),
]

export const adminHandlers = [
  /** F9 — nạp văn bản, "LLM" trích rule ứng viên (VALIDATION_REQUIRED) từ văn bản cùng dự án. */
  route('policyExtract', async ({ db, staff, request, now }) => {
    const user = staff()
    const form = await request.formData()
    const file = form.get('file')
    const field = (k: string) => String(form.get(k) ?? '').trim()
    if (!(file instanceof File) || file.size === 0) throw invalid('Cần tải lên văn bản chính sách (PDF/DOCX).')
    if (!/\.(pdf|docx?)$/i.test(file.name)) throw invalid('Chỉ nhận tệp PDF hoặc DOCX.')
    const projectId = field('project_id')
    const [from, to] = [field('effective_from'), field('effective_to')]
    if (!projectId || !field('title') || !field('policy_version') || !from || !to) throw invalid('Thiếu thông tin văn bản.')
    const template = db.policies.filter((p) => p.project_id === projectId).sort((a, b) => b.effective_from.localeCompare(a.effective_from))[0]
    if (!template) throw invalid('Dự án chưa có văn bản mẫu để đối chiếu.')
    const hash = await sha256HexOfBuffer(await file.arrayBuffer())
    const n = nextId(db, 'policy')
    const policyId = `CSBH-${projectId === 'THE_ZEN_PARK' ? 'ZEN' : 'SAP'}-${from.slice(0, 4)}-${field('policy_version').toUpperCase()}-${String(n).padStart(2, '0')}`
    const documentId = `DOC-UP-${String(n).padStart(4, '0')}`
    const version = field('policy_version')
    const policy: PolicyDocument = {
      policy_id: policyId,
      policy_version: version,
      title: field('title'),
      project_id: projectId,
      status: 'DRAFT',
      effective_from: from,
      effective_to: to,
      document_id: documentId,
      document_hash: hash,
      source_document: file.name,
      created_at: iso(now),
      created_by: actorOf(user),
      published_at: null,
      published_by: null,
      rules: template.rules.map((r) => ({
        ...r,
        validation_status: 'VALIDATION_REQUIRED',
        source: { ...r.source, document_id: documentId, document_version: version, document_hash: hash },
      })),
    }
    db.policies.push(policy)
    return { status: 201, body: policy }
  }),

  route('policyRulesTest', ({ db, params, now }) => {
    const policy = db.policies.find((p) => p.policy_id === params.policy_id)
    if (!policy) throw notFound(`chính sách ${params.policy_id}`)
    return { body: testPolicyRules(policy, db.policies, iso(now)) }
  }),

  /** Ban hành nguyên tử: chạy lại gate, rule chuyển APPROVED_FOR_USE cùng lúc. */
  route('policyPublish', ({ db, params, staff, now }) => {
    const user = staff()
    const policy = db.policies.find((p) => p.policy_id === params.policy_id)
    if (!policy) throw notFound(`chính sách ${params.policy_id}`)
    if (policy.status !== 'DRAFT') throw transition('Chỉ ban hành được bản nháp.')
    const report = testPolicyRules(policy, db.policies, iso(now))
    if (!report.can_publish) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Văn bản chưa vượt qua kiểm tra trước ban hành.')
    policy.status = 'PUBLISHED'
    policy.published_at = iso(now)
    policy.published_by = actorOf(user)
    policy.rules = policy.rules.map((r) => ({ ...r, validation_status: 'APPROVED_FOR_USE' }))
    return { body: policy }
  }),

  route('benchmarkRun', async ({ db, now }) => {
    await delay(scaled(600))
    return { status: 201, body: runBenchmark(`BR-${String(nextId(db, 'benchmark')).padStart(4, '0')}`, iso(now), iso(Date.now())) }
  }),
]

/** Điều khiển môi trường mock — chỉ gọi từ DevPanel. */
export const devtoolHandlers = [
  http.get('/__mock/flags', () => HttpResponse.json(getFlags())),
  http.patch('/__mock/flags', async ({ request }) => HttpResponse.json(setFlags((await request.json()) as Partial<MockFlags>))),
  http.post('/__mock/reset', async () => {
    await resetDb()
    return HttpResponse.json({ ok: true })
  }),
  http.get('/__mock/accounts', async () => {
    await getDb()
    const accounts: DemoAccount[] = STAFF_FIXTURE.map((u) => ({ email: u.email, password: MOCK_PASSWORD, full_name: u.full_name, role: u.role }))
    return HttpResponse.json(accounts)
  }),
]
