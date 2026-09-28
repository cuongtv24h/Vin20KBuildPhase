import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../client'
import { ANALYSIS_DEADLINE_MS } from '../config'
import type { AgentStep, Quote, QuoteStreamEvent, QuoteWorkflowStatus } from '../contracts'
import { subscribeSse, type SseConnectionState } from '../sse'
import { queryKeys } from './core'

export interface AgentProgress {
  connection: SseConnectionState | 'idle'
  completedSteps: AgentStep[]
  finalStatus: QuoteWorkflowStatus | null
  lastEventId: string | null
  /** Quá 10s chưa có `quote_ready` → UI dừng an toàn (TD-4.1 Timeout-Path). */
  timedOut: boolean
  reconnects: number
}

const IDLE: AgentProgress = { connection: 'idle', completedSteps: [], finalStatus: null, lastEventId: null, timedOut: false, reconnects: 0 }

/**
 * Theo dõi tiến trình Agent của một phiên bản quote qua SSE. Chỉ mở kết nối khi quote đang
 * ANALYZING; kết nối mới luôn nhận lại toàn bộ sự kiện của phiên bản (replay), reconnect trong
 * phiên dùng Last-Event-ID. `quote_ready` → làm mới dữ liệu quote qua REST.
 */
export function useQuoteEvents(quote: Quote | undefined, streamUrl?: string): AgentProgress {
  const qc = useQueryClient()
  const active = quote?.status === 'ANALYZING'
  const quoteId = quote?.quote_id
  const version = quote?.quote_version
  const key = `${quoteId}:v${version}`
  // Trạng thái gắn với đúng phiên bản đang theo dõi — đổi phiên bản thì tự về IDLE, không cần reset.
  const [tracked, setTracked] = useState<AgentProgress & { key: string }>({ ...IDLE, key })

  useEffect(() => {
    if (!active || !quoteId) return
    const setState = (update: (s: AgentProgress) => AgentProgress) =>
      setTracked((t) => ({ ...update(t.key === key ? t : IDLE), key }))
    const refresh = () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.quoteRoot(quoteId) }),
        qc.invalidateQueries({ queryKey: ['quotes', 'list'] }),
        qc.invalidateQueries({ queryKey: queryKeys.audit(quoteId) }),
        qc.invalidateQueries({ queryKey: ['leads'] }),
      ]).then(() => undefined)

    const deadline = setTimeout(() => setState((s) => (s.finalStatus ? s : { ...s, timedOut: true })), ANALYSIS_DEADLINE_MS)

    const unsubscribe = subscribeSse({
      url: streamUrl ?? api.quotes.eventsPath(quoteId),
      onState: (connection) =>
        setState((s) => ({ ...s, connection, reconnects: s.reconnects + (connection === 'reconnecting' && s.connection !== 'reconnecting' ? 1 : 0) })),
      onResync: refresh,
      isTerminal: (frame) => frame.event === 'quote_ready',
      onFrame: (frame) => {
        let event: QuoteStreamEvent
        try {
          event = JSON.parse(frame.data) as QuoteStreamEvent
        } catch {
          return
        }
        if (event.quote_version !== version) return
        if (event.event_type === 'step_update') {
          const node = event.payload.node
          setState((s) => ({
            ...s,
            lastEventId: event.event_id,
            completedSteps: s.completedSteps.includes(node) ? s.completedSteps : [...s.completedSteps, node],
          }))
        } else if (event.event_type === 'quote_ready') {
          clearTimeout(deadline)
          setState((s) => ({ ...s, lastEventId: event.event_id, finalStatus: event.payload.status, timedOut: false }))
          void refresh()
        }
      },
    })

    return () => {
      clearTimeout(deadline)
      unsubscribe()
    }
  }, [active, quoteId, version, key, streamUrl, qc])

  if (!active || tracked.key !== key) return IDLE
  const { key: _key, ...progress } = tracked
  return progress
}
