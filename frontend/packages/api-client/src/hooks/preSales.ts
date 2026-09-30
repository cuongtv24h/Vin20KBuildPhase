import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../client'
import type { CustomerConstraints, HandoffRequest, PreSalesSession, PreSalesStreamEvent } from '../contracts'
import { subscribeSse, type SseConnectionState } from '../sse'
import { queryKeys, useCommand } from './core'

export const usePreSalesSession = (sessionId: string | null) =>
  useQuery({
    queryKey: queryKeys.preSales(sessionId ?? ''),
    queryFn: () => api.preSales.get(sessionId ?? ''),
    enabled: Boolean(sessionId),
    retry: false,
  })

function useSessionCommand<TVars>(run: (vars: TVars, key: string) => Promise<PreSalesSession>) {
  const qc = useQueryClient()
  return useCommand(run, { onSuccess: (session) => qc.setQueryData(queryKeys.preSales(session.session_id), session) })
}

export const useStartPreSales = () =>
  useSessionCommand((preferredUnitCode: string | null, key) => api.preSales.create({ preferred_unit_code: preferredUnitCode }, { idempotencyKey: key }))

export const useSendPreSalesMessage = () =>
  useSessionCommand(({ sessionId, text }: { sessionId: string; text: string }, key) =>
    api.preSales.sendMessage(sessionId, { text }, { idempotencyKey: key }),
  )

export const useConfirmConstraints = () =>
  useSessionCommand(({ sessionId, constraints }: { sessionId: string; constraints: CustomerConstraints }, key) =>
    api.preSales.confirmConstraints(sessionId, { constraints }, { idempotencyKey: key }),
  )

export const useGeneratePlan = () =>
  useSessionCommand((sessionId: string, key) => api.preSales.generatePlan(sessionId, { idempotencyKey: key }))

export const useHandoff = () =>
  useCommand(
    ({ sessionId, body }: { sessionId: string; body: HandoffRequest }, key) => api.preSales.handoff(sessionId, body, { idempotencyKey: key }),
    { invalidate: ({ sessionId }) => [queryKeys.preSales(sessionId)] },
  )

export interface PreSalesProgress {
  connection: SseConnectionState | 'idle'
  ready: boolean
  lastEventId: string | null
}

const IDLE: PreSalesProgress = { connection: 'idle', ready: false, lastEventId: null }

const READY: PreSalesProgress = { connection: 'idle', ready: true, lastEventId: null }

/** Refreshes the session when the API announces that its reference plan is ready. */
export function usePreSalesEvents(session: PreSalesSession | undefined): PreSalesProgress {
  const qc = useQueryClient()
  const finished = session?.status === 'PLAN_READY' || session?.status === 'HANDED_OFF'
  const active = Boolean(session?.stream_url) && !finished && session?.status !== 'EXPIRED'
  const sessionId = session?.session_id
  const streamUrl = session?.stream_url
  // Trạng thái gắn với đúng session đang theo dõi — đổi session thì tự về IDLE, không cần reset qua effect.
  const [tracked, setTracked] = useState<PreSalesProgress & { sessionId: string | undefined }>({ ...IDLE, sessionId })

  useEffect(() => {
    if (!active || !sessionId || !streamUrl) return
    const setState = (update: (s: PreSalesProgress) => PreSalesProgress) =>
      setTracked((t) => ({ ...update(t.sessionId === sessionId ? t : IDLE), sessionId }))

    const unsubscribe = subscribeSse({
      url: streamUrl,
      onState: (connection) => setState((s) => ({ ...s, connection })),
      onResync: () => qc.invalidateQueries({ queryKey: queryKeys.preSales(sessionId) }).then(() => undefined),
      isTerminal: (frame) => frame.event === 'PRE_SALES_PLAN_READY',
      onFrame: (frame) => {
        if (frame.event !== 'PRE_SALES_PLAN_READY') return
        try {
          const event = JSON.parse(frame.data) as PreSalesStreamEvent
          if (event.event_type !== 'PRE_SALES_PLAN_READY' || event.payload.session_id !== sessionId) return
          setState(() => ({ connection: 'open', ready: true, lastEventId: event.event_id }))
          void qc.invalidateQueries({ queryKey: queryKeys.preSales(sessionId) })
        } catch {
          setState((s) => ({ ...s, connection: 'open' }))
        }
      },
    })

    return () => unsubscribe()
  }, [active, sessionId, streamUrl, qc])

  if (finished) return READY
  if (!active || tracked.sessionId !== sessionId) return IDLE
  const { sessionId: _sessionId, ...progress } = tracked
  return progress
}
