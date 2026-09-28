import { http, HttpResponse } from 'msw'
import type { ApproveRequest, DecisionReasonRequest, QuoteAudit, QuoteCreateRequest, QuoteEvidence, QuotePdf, QuoteWorkflowStatus } from '@pricepolicy/api-client/contracts'
import { parseEventId } from '@pricepolicy/api-client/contracts'
import { ENDPOINTS } from '@pricepolicy/api-client/endpoints'
import { commit, getDb } from '../db'
import { getFlags } from '../flags'
import { verifyChain } from '../services/audit'
import { MockError } from '../services/errors'
import { assertVersion, assertVisible, createQuote, createVersion, decideQuote, findRecord, latest, retryPdf, settle, submitQuote, view } from '../services/quotes'
import { authenticate, errorResponse, route, toMswPath } from './route'

const HEARTBEAT_MS = 15_000
const encoder = new TextEncoder()

export const quoteHandlers = [
  route('quoteList', ({ db, staff, query }) => {
    const user = staff()
    const statuses = query.get('status')?.split(',').filter(Boolean) as QuoteWorkflowStatus[] | undefined
    const dossier = query.get('source_dossier_id')
    const list = db.quotes
      .filter((r) => user.role !== 'SALE' || latest(r).created_by.user_id === user.user_id)
      .map((r) => view(r))
      .filter((q) => (!statuses?.length || statuses.includes(q.status)) && (!dossier || q.source_dossier_id === dossier))
    return { body: list }
  }),

  route('quoteDetail', ({ db, staff, params, query }) => {
    const record = findRecord(db, params.quote_id)
    assertVisible(record, staff())
    const version = query.get('version')
    return { body: view(record, version ? Number(version) : undefined) }
  }),

  route('quoteCreate', async ({ db, staff, now, json }) => ({ status: 202, body: await createQuote(db, staff(), await json<QuoteCreateRequest>(), null, now) }), {
    fixedDelayMs: 150,
  }),

  route(
    'quoteNewVersion',
    async ({ db, staff, now, params, request, json }) => {
      const record = findRecord(db, params.quote_id)
      assertVersion(record, request.headers.get('If-Match'))
      return { status: 202, body: await createVersion(db, staff(), record, await json<QuoteCreateRequest>(), now) }
    },
    { fixedDelayMs: 150 },
  ),

  route('quoteSubmit', async ({ db, staff, now, params, request }) => {
    const record = findRecord(db, params.quote_id)
    assertVersion(record, request.headers.get('If-Match'))
    return { body: await submitQuote(db, staff(), record, now) }
  }),

  route('quoteApprove', async ({ db, staff, now, params, request, json }) => {
    const user = staff()
    const record = findRecord(db, params.quote_id)
    assertVersion(record, request.headers.get('If-Match'))
    const reauthToken = request.headers.get('X-Reauth-Token') ?? ''
    const grant = db.reauth[reauthToken]
    if (!grant || grant.user_id !== user.user_id || grant.expires_at < now) {
      throw new MockError(403, 'REAUTH_REQUIRED', 'Phiên xác thực lại đã hết hạn. Vui lòng nhập lại mật khẩu.')
    }
    const body = await json<ApproveRequest>()
    const quote = await decideQuote(db, user, record, 'APPROVED', body?.note ?? '', now)
    delete db.reauth[reauthToken]
    return { body: quote }
  }),

  route('quoteReject', async ({ db, staff, now, params, request, json }) => {
    const record = findRecord(db, params.quote_id)
    assertVersion(record, request.headers.get('If-Match'))
    return { body: await decideQuote(db, staff(), record, 'REJECTED', (await json<DecisionReasonRequest>())?.reason ?? '', now) }
  }),

  route('quoteRevision', async ({ db, staff, now, params, request, json }) => {
    const record = findRecord(db, params.quote_id)
    assertVersion(record, request.headers.get('If-Match'))
    return { body: await decideQuote(db, staff(), record, 'REVISION_REQUESTED', (await json<DecisionReasonRequest>())?.reason ?? '', now) }
  }),

  route('quotePdfRetry', async ({ db, params, now }) => ({ body: await retryPdf(findRecord(db, params.quote_id), now) })),

  route('quoteEvidence', ({ db, staff, params, query }) => {
    const record = findRecord(db, params.quote_id)
    assertVisible(record, staff())
    const version = Number(query.get('version')) || latest(record).quote_version
    const body: QuoteEvidence = { quote_id: record.quote_id, quote_version: version, claims: record.claims[version] ?? [] }
    return { body }
  }),

  route('quoteAudit', async ({ db, staff, params }) => {
    const record = findRecord(db, params.quote_id)
    assertVisible(record, staff())
    const body: QuoteAudit = { quote_id: record.quote_id, events: record.audit, chain_valid: await verifyChain(record.audit) }
    return { body }
  }),

  route('quotePdf', ({ db, staff, params }) => {
    const record = findRecord(db, params.quote_id)
    assertVisible(record, staff())
    const q = latest(record)
    if (q.pdf_status !== 'PDF_ISSUED' || !record.pdf?.pdf_sha256) throw new MockError(409, 'PDF_NOT_READY', 'Bản PDF chưa được phát hành.')
    const body: QuotePdf = {
      quote_id: q.quote_id,
      quote_version: q.quote_version,
      pdf_status: q.pdf_status,
      download_url: `/files/quotes/${q.quote_id}/v${q.quote_version}/quote_${q.quote_id}_v${q.quote_version}.pdf`,
      pdf_sha256: record.pdf.pdf_sha256,
      issued_at: q.updated_at,
    }
    return { body }
  }),

  /**
   * SSE — TD-4.1 §3.1. Phát lại sự kiện có event_seq > Last-Event-ID theo đúng mốc thời gian đã lập
   * lịch khi tạo quote; `: ping` mỗi 15s; 410 + X-Action: RESYNC_FULL_STATE khi không thể replay.
   */
  http.get(toMswPath(ENDPOINTS.quoteEvents.path), async ({ request, params }) => {
    const db = await getDb()
    const now = Date.now()
    await settle(db, now)
    const user = authenticate(request, db, now)
    if (!user) return errorResponse(new MockError(401, 'UNAUTHORIZED', 'Cần đăng nhập.'))
    let record
    try {
      record = findRecord(db, String(params.quote_id))
      assertVisible(record, user)
    } catch (e) {
      return errorResponse(e as MockError)
    }
    const version = latest(record).quote_version
    const events = record.events[version] ?? []
    const lastEventId = request.headers.get('Last-Event-ID')
    const last = lastEventId ? parseEventId(lastEventId) : null
    const flags = getFlags()
    if (lastEventId && (!last || last.version !== version || last.quoteId !== record.quote_id || flags.expire_replay)) {
      return HttpResponse.json(
        { code: 'RESYNC_FULL_STATE', message: 'Không thể phát lại sự kiện, cần đồng bộ lại trạng thái.' },
        { status: 410, headers: { 'X-Action': 'RESYNC_FULL_STATE' } },
      )
    }
    const shouldDrop = flags.drop_sse_once && !record.sse_dropped.includes(version)
    if (shouldDrop) {
      record.sse_dropped.push(version)
      commit()
    }

    const timers: ReturnType<typeof setTimeout>[] = []
    let closed = false
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
          timers.push(setTimeout(beat, HEARTBEAT_MS))
        }
        timers.push(setTimeout(beat, HEARTBEAT_MS))
        for (const { envelope, emit_at } of events) {
          if (last && envelope.event_seq <= last.seq) continue
          timers.push(
            setTimeout(
              () => {
                send(`id: ${envelope.event_id}\nevent: ${envelope.event_type}\ndata: ${JSON.stringify(envelope)}\n\n`)
                if (envelope.event_type === 'quote_ready' || (shouldDrop && envelope.event_seq === 2)) close()
              },
              Math.max(0, emit_at - Date.now()),
            ),
          )
        }
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

  /** File PDF giả lập (object storage) — chỉ tồn tại sau khi worker phát hành. */
  http.get('*/files/quotes/:quote_id/:version/:file', async ({ params }) => {
    const db = await getDb()
    const record = db.quotes.find((q) => q.quote_id === params.quote_id)
    if (!record || latest(record).pdf_status !== 'PDF_ISSUED') return new HttpResponse(null, { status: 404 })
    return new HttpResponse(minimalPdf(`${record.quote_id} ${String(params.version)} - VLandFuture`), { headers: { 'Content-Type': 'application/pdf' } })
  }),
]

/** PDF 1 trang hợp lệ tối thiểu (ASCII) — đủ để trình duyệt mở được. */
function minimalPdf(title: string): Uint8Array {
  const text = title.replace(/[^\x20-\x7E]/g, '')
  const content = `BT /F1 18 Tf 72 760 Td (${text}) Tj ET`
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ]
  let pdf = '%PDF-1.4\n'
  const offsets: number[] = []
  objects.forEach((obj, i) => {
    offsets.push(pdf.length)
    pdf += `${i + 1} 0 obj\n${obj}\nendobj\n`
  })
  const xref = pdf.length
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.map((o) => `${String(o).padStart(10, '0')} 00000 n \n`).join('')}`
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`
  return encoder.encode(pdf)
}
