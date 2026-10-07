import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { useRef } from 'react'
import { newRequestId } from '../http'

export const queryKeys = {
  projects: ['catalog', 'projects'] as const,
  units: (projectId?: string) => ['catalog', 'units', projectId ?? 'all'] as const,
  policies: (filter: Record<string, string | undefined> = {}) => ['policies', 'list', filter] as const,
  policy: (policyId: string) => ['policies', 'detail', policyId] as const,
  activePolicy: (projectId: string, date: string) => ['policies', 'active', projectId, date] as const,
  quotes: (filter: Record<string, unknown> = {}) => ['quotes', 'list', filter] as const,
  quote: (quoteId: string, version?: number) => ['quotes', 'detail', quoteId, version ?? 'latest'] as const,
  quoteRoot: (quoteId: string) => ['quotes', 'detail', quoteId] as const,
  evidence: (quoteId: string, version: number) => ['quotes', 'evidence', quoteId, version] as const,
  audit: (quoteId: string) => ['quotes', 'audit', quoteId] as const,
  pdf: (quoteId: string) => ['quotes', 'pdf', quoteId] as const,
  leads: ['leads'] as const,
  preSales: (sessionId: string) => ['pre-sales', sessionId] as const,
  copilotConversations: ['copilot', 'conversations'] as const,
  copilotConversation: (conversationId: string) => ['copilot', 'conversation', conversationId] as const,
  llmProviders: ['admin', 'llm', 'providers'] as const,
  llmUsage: ['admin', 'llm', 'usage'] as const,
  ttsSettings: ['settings', 'tts'] as const,
  ttsProviders: ['admin', 'tts', 'providers'] as const,
}

/**
 * Mutation có Idempotency-Key ổn định: cùng payload thử lại (sau timeout/lỗi mạng) dùng lại
 * đúng khoá cũ → server trả lại kết quả đã xử lý thay vì thực thi lần hai (TD-4.1 INV-RT-03/07).
 * Payload khác → khoá mới. Thành công → xoá khoá.
 */
export function useCommand<TVars, TResult>(
  run: (vars: TVars, idempotencyKey: string) => Promise<TResult>,
  options: {
    invalidate?: (vars: TVars, result: TResult) => QueryKey[]
    onSuccess?: (result: TResult, vars: TVars) => void
    fingerprint?: (vars: TVars) => string
  } = {},
) {
  const qc = useQueryClient()
  const pending = useRef<{ fingerprint: string; key: string } | null>(null)
  return useMutation({
    mutationFn: (vars: TVars) => {
      const fingerprint = options.fingerprint?.(vars) ?? JSON.stringify(vars)
      if (!pending.current || pending.current.fingerprint !== fingerprint) {
        pending.current = { fingerprint, key: newRequestId() }
      }
      return run(vars, pending.current.key)
    },
    onSuccess: async (result, vars) => {
      pending.current = null
      options.onSuccess?.(result, vars)
      await Promise.all((options.invalidate?.(vars, result) ?? []).map((queryKey) => qc.invalidateQueries({ queryKey })))
    },
  })
}
