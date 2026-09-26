import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import type { CustomerConstraints, HandoffRequest, PreSalesSession } from '../contracts'
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
