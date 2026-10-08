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
} from '@pricepolicy/api-client/contracts'
import type { DemoAccount, MockFlags } from '@pricepolicy/api-client/devtools'
import { ENDPOINTS } from '@pricepolicy/api-client/endpoints'
import { getDb, nextId, resetDb, commit } from '../db'
import { runBenchmark } from '../engine/benchmark'
import { checkMessage, draftMessage } from '../engine/compliance'
import { sha256Hex, sha256HexOfBuffer } from '../engine/hash'
import { testPolicyRules } from '../engine/rulesTest'
import { actorOf, MOCK_PASSWORD, STAFF_FIXTURE } from '../fixtures/users'
import { getFlags, scaled, setFlags } from '../flags'
import { appendAudit } from '../services/audit'
import { forbidden, invalid, MockError, notFound, transition } from '../services/errors'
import { confirmConstraints, convertDossier, createSession, findSession, handoff, listDossiers, presalesEvents, receiveMessage, settlePreSales, startGeneratePlan } from '../services/presales'
import { assertVisible, findRecord, latest } from '../services/quotes'
import { route, toMswPath } from './route'

const iso = (ms: number) => new Date(ms).toISOString()

export const leadHandlers = [
  route('leadList', ({ db, staff }) => ({ body: listDossiers(db, staff()) })),
  route(
    'leadCreate',
    async ({ db, staff, now, json }) => {
      const payload = (await json<any>()) ?? {}
      const user = staff()
      const dossierId = `DOS-${Date.now().toString().slice(-6)}`
      const newDossier = {
        dossier_id: dossierId,
        status: 'ASSIGNED' as const,
        temperature: payload.temperature ?? 'HOT',
        created_at: new Date(now).toISOString(),
        sla_due_at: new Date(now + 2 * 3600 * 1000).toISOString(),
        assigned_sale: user ? { user_id: user.user_id, full_name: user.full_name, role: user.role } : null,
        // Khớp máy chủ thật: hồ sơ Sale tạo thì ghi nhận người tạo (cơ sở của quyền xoá).
        created_by: user?.user_id ?? null,
        assigned_sales_id: user?.user_id ?? null,
        source_session_id: `SES-${Date.now()}`,
        customer: {
          full_name: payload.customer_name || 'Khách hàng mới',
          phone: payload.customer_phone || '0900000000',
        },
        consent: {
          granted_at: new Date(now).toISOString(),
          consent_text_version: 'v1.0',
        },
        needs_summary: payload.needs_summary || `Nhu cầu tìm căn hộ tại dự án ${payload.project_id || 'The Zen Park'}.`,
        constraints: {
          own_funds_vnd: payload.own_funds_vnd ?? 1_000_000_000,
          monthly_capacity_vnd: payload.monthly_capacity_vnd ?? 25_000_000,
          bedrooms: payload.bedrooms ?? 2,
          project_id: payload.project_id ?? 'THE_ZEN_PARK',
          preferred_unit_code: payload.preferred_unit_code ?? null,
          objective: payload.objective ?? 'MIN_NET_PRICE',
          customer_segment: payload.customer_segment ?? 'NEW_CUSTOMER',
        },
        reference_plan: null,
        converted_quote_id: null,
      }
      db.dossiers.unshift(newDossier)
      return { status: 201, body: newDossier }
    },
    { fixedDelayMs: 100 },
  ),
  route('leadGet', ({ db, params }) => {
    const dossier = db.dossiers.find((d) => d.dossier_id === params.dossier_id)
    if (!dossier) throw notFound(`hồ sơ ${params.dossier_id}`)
    return { body: dossier }
  }),

  /** PUT /leads/{id} — Sale cập nhật nhu cầu/ràng buộc; giữ nguyên các trường không gửi lên. */
  route('leadUpdate', async ({ db, params, json, now }) => {
    const index = db.dossiers.findIndex((d) => d.dossier_id === params.dossier_id)
    if (index < 0) throw notFound(`hồ sơ ${params.dossier_id}`)
    const body = (await json<Record<string, unknown>>()) ?? {}
    const current = db.dossiers[index]
    const constraints = { ...current.constraints }
    for (const key of ['customer_segment', 'project_id', 'preferred_unit_code', 'bedrooms', 'own_funds_vnd', 'monthly_capacity_vnd', 'objective'] as const) {
      if (body[key] !== undefined) (constraints as Record<string, unknown>)[key] = body[key]
    }
    const updated = {
      ...current,
      constraints,
      status: (body.status as typeof current.status) ?? current.status,
      temperature: (body.lead_temperature ?? body.temperature ?? current.temperature) as typeof current.temperature,
      needs_summary: typeof body.needs_summary === 'string' ? body.needs_summary : current.needs_summary,
      customer: {
        full_name: typeof body.customer_name === 'string' ? body.customer_name : current.customer.full_name,
        phone: typeof body.customer_phone === 'string' ? body.customer_phone : current.customer.phone,
      },
      updated_at: iso(now),
    }
    db.dossiers[index] = updated
    return { body: updated }
  }),

  /**
   * POST /leads/{id}/assign-sale — ADMIN gán Sale phụ trách.
   * Hồ sơ chưa có người tạo thì đóng dấu `created_by` = Sale được gán (cấp quyền xoá/sửa); hồ sơ đã có
   * chủ thì chỉ đổi người phụ trách, KHÔNG ghi đè người tạo.
   */
  route('leadAssignSale', async ({ db, staff, params, json }) => {
    const actor = staff()
    if (actor?.role !== 'ADMIN') throw forbidden('chỉ quản trị viên mới được gán Sale phụ trách')
    const index = db.dossiers.findIndex((d) => d.dossier_id === params.dossier_id)
    if (index < 0) throw notFound(`hồ sơ ${params.dossier_id}`)
    const body = (await json<{ sales_id?: string }>()) ?? {}
    const salesId = String(body.sales_id ?? '').trim()
    if (!salesId) throw invalid('cần chỉ định Sale phụ trách (sales_id không được để trống)')
    const target = STAFF_FIXTURE.find((u) => u.user_id === salesId)
    const current = db.dossiers[index]
    const updated = {
      ...current,
      assigned_sale: target ? actorOf(target) : { user_id: salesId, full_name: salesId, role: 'SALE' as const },
      assigned_sales_id: salesId,
      created_by: current.created_by || salesId,
    }
    db.dossiers[index] = updated
    return { body: updated }
  }),

  route('leadDelete', ({ db, staff, params }) => {
    const index = db.dossiers.findIndex((d) => d.dossier_id === params.dossier_id)
    if (index < 0) throw notFound(`hồ sơ ${params.dossier_id}`)
    // Khớp luật của máy chủ thật: Sale chỉ xoá khách DO MÌNH TẠO. Hồ sơ CHƯA có người tạo (dữ liệu cũ /
    // Pre-Sales bàn giao) thì chỉ ADMIN xoá được — ADMIN gán Sale phụ trách để cấp chủ sở hữu.
    const dossier = db.dossiers[index]
    const owner = dossier.created_by || dossier.assigned_sale?.user_id || ''
    const actor = staff()
    const isAdmin = actor?.role === 'ADMIN'
    if (!owner) {
      if (!isAdmin) {
        throw forbidden(`hồ sơ ${params.dossier_id} chưa ghi nhận người tạo — chỉ quản trị viên xoá được`)
      }
    } else if (actor && !isAdmin && owner !== actor.user_id) {
      throw forbidden(`chỉ ${owner} (người tạo) mới xoá được hồ sơ ${params.dossier_id}`)
    }
    if (db.dossiers[index].status === 'CONVERTED_TO_QUOTE') {
      throw transition('Hồ sơ đã chuyển thành báo giá — không thể xóa.')
    }
    db.dossiers.splice(index, 1)
    return { body: { deleted: true } }
  }),

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
  // 202 + SSE (PRE_SALES_PLAN_READY) — kiểm tra chính sách + tính 3 phương án ~1,5–2,5s, xem services/presales.ts.
  route('preSalesPlan', ({ db, params, now }) => ({ status: 202, body: startGeneratePlan(db, findSession(db, params.session_id, now), now) })),
  route('preSalesHandoff', async ({ db, params, now, json }) => ({ body: handoff(db, findSession(db, params.session_id, now), await json<HandoffRequest>(), now) })),

  /**
   * SSE — PRE_SALES_PLAN_READY (D3-1). Dùng chung `subscribeSse()`/heartbeat/reconnect với luồng
   * quote (xem handlers/quotes.ts); khác biệt: công khai (không auth) và event_id chỉ có
   * `{session_id}:{seq}` (không có "phiên bản" như quote — mỗi lượt lập phương án ghi đè lượt trước).
   */
  http.get(toMswPath(ENDPOINTS.preSalesEvents.path), async ({ request, params }) => {
    const db = await getDb()
    const now = Date.now()
    await settlePreSales(db, now)
    const sessionId = String(params.session_id)
    const events = presalesEvents(db, sessionId)
    const lastEventId = request.headers.get('Last-Event-ID')
    const lastSeq = lastEventId?.startsWith(`${sessionId}:`) ? Number(lastEventId.slice(sessionId.length + 1)) : null

    const timers: ReturnType<typeof setTimeout>[] = []
    let closed = false
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        const send = (text: string) => {
          if (closed) return
          try {
            controller.enqueue(encoder.encode(text))
          } catch {
            closed = true
          }
        }
        const close = () => {
          if (closed) return
          closed = true
          timers.forEach(clearTimeout)
          try {
            controller.close()
          } catch {
            // đã đóng
          }
        }
        send(': ping\n\n')
        const beat = () => {
          send(': ping\n\n')
          timers.push(setTimeout(beat, 15_000))
        }
        timers.push(setTimeout(beat, 15_000))
        for (const { envelope, emit_at } of events) {
          if (lastSeq !== null && envelope.event_seq <= lastSeq) continue
          timers.push(
            setTimeout(
              () => {
                send(`id: ${envelope.event_id}\nevent: ${envelope.event_type}\ndata: ${JSON.stringify(envelope)}\n\n`)
                close()
              },
              Math.max(0, emit_at - Date.now()),
            ),
          )
        }
        // Chưa từng có lượt lập phương án nào cho session này — không có gì để chờ, đóng ngay.
        if (events.length === 0) close()
        request.signal?.addEventListener('abort', close)
      },
      cancel() {
        closed = true
        timers.forEach(clearTimeout)
      },
    })
    return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' } })
  }),
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
    return { body: testPolicyRules(policy, db.policies, iso(now), `BR-${String(nextId(db, 'benchmark')).padStart(4, '0')}`) }
  }),

  /** Ban hành nguyên tử: chạy lại gate, rule chuyển APPROVED_FOR_USE cùng lúc. */
  route('policyPublish', ({ db, params, staff, now }) => {
    const user = staff()
    const policy = db.policies.find((p) => p.policy_id === params.policy_id)
    if (!policy) throw notFound(`chính sách ${params.policy_id}`)
    if (policy.status !== 'DRAFT') throw transition('Chỉ ban hành được bản nháp.')
    const report = testPolicyRules(policy, db.policies, iso(now), `BR-${String(nextId(db, 'benchmark')).padStart(4, '0')}`)
    if (!report.can_publish) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Văn bản chưa vượt qua kiểm tra trước ban hành.')
    policy.status = 'PUBLISHED'
    policy.published_at = iso(now)
    policy.published_by = actorOf(user)
    policy.rules = policy.rules.map((r) => ({ ...r, validation_status: 'APPROVED_FOR_USE' }))
    return { body: policy }
  }),

  route('benchmarkRun', async ({ db, now, json }) => {
    await delay(scaled(600))
    // Body tuỳ chọn: backend thật nhận `policy_id`/`policy_version` để ghi bằng chứng theo văn bản.
    const body = await json<{ policy_id?: string; policy_version?: string }>()
    const policy = body?.policy_id && body.policy_version ? { policy_id: body.policy_id, policy_version: body.policy_version } : undefined
    return { status: 201, body: runBenchmark(`BR-${String(nextId(db, 'benchmark')).padStart(4, '0')}`, iso(now), iso(Date.now()), policy) }
  }),
]

/** Điều khiển môi trường mock — chỉ gọi từ DevPanel. */
export const devtoolHandlers = [
  http.get('*/__mock/flags', () => HttpResponse.json(getFlags())),
  http.patch('*/__mock/flags', async ({ request }) => HttpResponse.json(setFlags((await request.json()) as Partial<MockFlags>))),
  http.post('*/__mock/reset', async () => {
    await resetDb()
    return HttpResponse.json({ ok: true })
  }),
  http.get('*/__mock/accounts', async () => {
    await getDb()
    const accounts: DemoAccount[] = STAFF_FIXTURE.map((u) => ({ email: u.email, password: MOCK_PASSWORD, full_name: u.full_name, role: u.role }))
    return HttpResponse.json(accounts)
  }),
]
