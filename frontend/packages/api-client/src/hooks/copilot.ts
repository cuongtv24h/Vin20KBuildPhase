import { useQuery } from '@tanstack/react-query'
import { useCallback, useRef, useState } from 'react'
import { api } from '../client'
import type {
  CopilotChatHistoryItem,
  CopilotChatRequest,
  CopilotFeedbackRecentParams,
  CopilotFinalPayload,
  CopilotReasoningStep,
  CopilotStreamEvent,
} from '../contracts'

export interface CopilotContext {
  currentUnit?: string | null
  leadDossierId?: string | null
  transactionDate?: string | null
  projectId?: string | null
}

export interface CopilotTurnState {
  steps: CopilotReasoningStep[]
  final: CopilotFinalPayload | null
  streaming: boolean
  error: string | null
  /** Đã rơi về chế độ suy luận tất định (LLM không khả dụng). */
  degraded: boolean
  /** Câu hỏi đang chạy — phục vụ nút "Thử lại". */
  lastMessage: string | null
  lastContext: CopilotContext | null
}

const initialState: CopilotTurnState = {
  steps: [],
  final: null,
  streaming: false,
  error: null,
  degraded: false,
  lastMessage: null,
  lastContext: null,
}

/**
 * Vòng đời một lượt chat Copilot có stream tiến trình ReAct.
 *
 * - `send()` mở SSE POST tới `/copilot/chat/stream`, cập nhật `steps` theo từng frame
 *   (thought → action → observation → final) để UI vẽ timeline thật.
 * - SSE lỗi giữa chừng → tự fallback sang `POST /copilot/chat` (không stream).
 * - `cancel()` huỷ khi Sale gửi câu mới hoặc unmount.
 */
export function useCopilotTurn(history: CopilotChatHistoryItem[] = []) {
  const [state, setState] = useState<CopilotTurnState>(initialState)
  const cancelRef = useRef<(() => void) | null>(null)

  const cancel = useCallback(() => {
    cancelRef.current?.()
    cancelRef.current = null
    setState((s) => (s.streaming ? { ...s, streaming: false } : s))
  }, [])

  const fallbackToJson = useCallback(
    async (message: string, context: CopilotContext) => {
      try {
        const response = await api.copilot.chat({
          message,
          history,
          current_unit: context.currentUnit ?? null,
          lead_dossier_id: context.leadDossierId ?? null,
          transaction_date: context.transactionDate ?? null,
          project_id: context.projectId ?? null,
        })
        setState((s) => ({
          ...s,
          streaming: false,
          degraded: response.mode === 'offline_react',
          steps: response.reasoning?.length ? response.reasoning : s.steps,
          final: response,
        }))
      } catch (error) {
        setState((s) => ({
          ...s,
          streaming: false,
          error: error instanceof Error ? error.message : 'Không kết nối được trợ lý.',
        }))
      }
    },
    [history],
  )

  const send = useCallback(
    (message: string, context: CopilotContext = {}) => {
      const text = message.trim()
      if (!text) return
      cancelRef.current?.()
      setState({
        ...initialState,
        streaming: true,
        lastMessage: text,
        lastContext: context,
      })

      const request: CopilotChatRequest = {
        message: text,
        history,
        current_unit: context.currentUnit ?? null,
        lead_dossier_id: context.leadDossierId ?? null,
        transaction_date: context.transactionDate ?? null,
        project_id: context.projectId ?? null,
      }

      let sawStreamingFrame = false
      cancelRef.current = api.copilot.stream(request, {
        onEvent: (event: CopilotStreamEvent) => {
          sawStreamingFrame = true
          if (event.type === 'final') {
            setState((s) => ({
              ...s,
              streaming: false,
              final: event,
              degraded: (event as CopilotFinalPayload & { mode?: string }).mode === 'offline_react',
            }))
            return
          }
          if (event.type === 'error') {
            setState((s) => ({ ...s, streaming: false, error: event.message }))
            return
          }
          setState((s) => ({ ...s, steps: [...s.steps, event as CopilotReasoningStep] }))
        },
        onError: () => {
          // SSE không chạy được (proxy cắt stream, mạng chập) → dùng bản gom.
          if (!sawStreamingFrame) void fallbackToJson(text, context)
          else setState((s) => ({ ...s, streaming: false, error: 'Kết nối bị ngắt giữa chừng.' }))
        },
      })
    },
    [cancel, fallbackToJson, history],
  )

  const retry = useCallback(() => {
    if (!state.lastMessage) return
    send(state.lastMessage, state.lastContext ?? {})
  }, [send, state.lastContext, state.lastMessage])

  const reset = useCallback(() => {
    cancelRef.current?.()
    cancelRef.current = null
    setState(initialState)
  }, [])

  return { ...state, send, cancel, retry, reset }
}


// ─── Trang quản trị chất lượng Copilot (ADMIN / POLICY_ADMIN) ────────────────

export const copilotQualityKeys = {
  summary: ['copilot', 'feedback', 'summary'] as const,
  recent: (params: CopilotFeedbackRecentParams) => ['copilot', 'feedback', 'recent', params] as const,
}

/** Thống kê tích luỹ: tỉ lệ hài lòng, xu hướng 14 ngày, tool hay bị chê. */
export const useCopilotFeedbackSummary = () =>
  useQuery({
    queryKey: copilotQualityKeys.summary,
    queryFn: () => api.copilot.feedbackSummary(),
    refetchInterval: 60_000,
  })

/** Danh sách phản hồi chi tiết (server đã che PII). */
export const useCopilotFeedbackRecent = (params: CopilotFeedbackRecentParams = {}) =>
  useQuery({
    queryKey: copilotQualityKeys.recent(params),
    queryFn: () => api.copilot.feedbackRecent(params),
    refetchInterval: 60_000,
  })
