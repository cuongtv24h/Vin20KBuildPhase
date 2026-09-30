import type { QuoteAuditEvent } from '@pricepolicy/api-client/contracts'
import { nextId, type MockDb, type QuoteRecord } from '../db'
import { canonicalJsonStringify, sha256Hex } from '../engine/hash'

export const GENESIS_HASH = '0'.repeat(64)

type AuditInput = Pick<QuoteAuditEvent, 'event_type' | 'quote_version' | 'actor'> & { note?: string | null; at: number }

/** C-07 append-only hash chain: event_hash = SHA256(prev_hash ‖ canonical(event)). */
export async function appendAudit(db: MockDb, record: QuoteRecord, input: AuditInput): Promise<QuoteAuditEvent> {
  const prev = record.audit.at(-1)?.event_hash ?? GENESIS_HASH
  const body = {
    event_id: `EVT-${String(nextId(db, 'event')).padStart(6, '0')}`,
    event_type: input.event_type,
    quote_version: input.quote_version,
    occurred_at: new Date(input.at).toISOString(),
    actor: input.actor,
    note: input.note ?? null,
  }
  const event: QuoteAuditEvent = { ...body, prev_hash: prev, event_hash: await sha256Hex(prev + canonicalJsonStringify(body)) }
  record.audit.push(event)
  return event
}

export async function verifyChain(events: QuoteAuditEvent[]): Promise<boolean> {
  let prev = GENESIS_HASH
  for (const e of events) {
    const { prev_hash, event_hash, ...body } = e
    if (prev_hash !== prev || event_hash !== (await sha256Hex(prev + canonicalJsonStringify(body)))) return false
    prev = event_hash
  }
  return true
}

export const SYSTEM_ACTOR = { user_id: null, full_name: 'PricePolicy Agent', role: 'SYSTEM' as const }
