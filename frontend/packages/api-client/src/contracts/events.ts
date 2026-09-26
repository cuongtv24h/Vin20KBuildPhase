import type { AgentStep, QuoteWorkflowStatus } from './enums'

/**
 * SSE envelope — Implement plan §10.3; event_id theo TD-4.1 INV-RT-08:
 *   "{quote_id}:v{quote_version}:{event_seq:06d}"
 * Khung wire:  id: <event_id>\nevent: <event_type>\ndata: <envelope JSON>\n\n
 * Heartbeat:   ": ping\n\n" mỗi 15s — không phải business event.
 */
export interface SseEventEnvelope<TType extends string = string, TPayload = unknown> {
  event_id: string
  event_seq: number
  event_type: TType
  session_id: string | null
  quote_id: string | null
  quote_version: number | null
  schema_version: 'sse-event.v1'
  correlation_id: string
  occurred_at: string
  payload: TPayload
}

/** TD-4.1 §3.1: data: {"node": "POLICY_LOOKUP", "seq": 1} */
export interface StepUpdatePayload {
  node: AgentStep
  seq: number
}

/** TD-4.1 §3.1: data: {"quote_id": "...", "status": "READY_FOR_REVIEW", "seq": 4} — sự kiện kết thúc. */
export interface QuoteReadyPayload {
  quote_id: string
  status: QuoteWorkflowStatus
  seq: number
}

export type QuoteStreamEvent =
  | SseEventEnvelope<'step_update', StepUpdatePayload>
  | SseEventEnvelope<'quote_ready', QuoteReadyPayload>

/** Pre-Sales stream — server-provided `stream_url`, scoped to one session. */
export interface PreSalesPlanReadyPayload {
  session_id: string
  status: 'PLAN_READY'
}

export type PreSalesStreamEvent = SseEventEnvelope<'PRE_SALES_PLAN_READY', PreSalesPlanReadyPayload>

export function formatEventId(quoteId: string, version: number, seq: number): string {
  return `${quoteId}:v${version}:${String(seq).padStart(6, '0')}`
}

export function parseEventId(eventId: string): { quoteId: string; version: number; seq: number } | null {
  const m = /^(.+):v(\d+):(\d{6,})$/.exec(eventId)
  return m ? { quoteId: m[1], version: Number(m[2]), seq: Number(m[3]) } : null
}
