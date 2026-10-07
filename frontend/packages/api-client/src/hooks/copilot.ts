import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../client'
import { newRequestId } from '../http'
import type {
  CopilotAppendTurnRequest,
  CopilotChatHistoryItem,
  CopilotConversationDetail,
  CopilotChatRequest,
  CopilotFeedbackRecentParams,
  CopilotFinalPayload,
  CopilotReasoningStep,
  CopilotStreamEvent,
} from '../contracts'
import { queryKeys, useCommand } from './core'

export interface CopilotContext {
  currentUnit?: string | null
  leadDossierId?: string | null
  transactionDate?: string | null
  projectId?: string | null
}

/** Tuỳ chọn riêng cho một lượt gửi. */
export interface CopilotSendOptions {
  /**
   * Gọi đúng một lần khi lượt có câu trả lời cuối — **kể cả khi trang đã bị rời đi** (stream vẫn chạy
   * tiếp ở nền). Dùng để ghi câu trả lời vào lịch sử mà không phụ thuộc component còn sống hay không.
   */
  onFinal?: (final: CopilotFinalPayload) => void
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
 * - `cancel()` huỷ khi Sale gửi câu mới. Rời trang KHÔNG huỷ: lượt vẫn chạy tới khi có câu trả lời và
 *   `onFinal` ghi nó vào lịch sử.
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
    async (message: string, context: CopilotContext, options: CopilotSendOptions = {}) => {
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
        options.onFinal?.(response)
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
    (message: string, context: CopilotContext = {}, options: CopilotSendOptions = {}) => {
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
            options.onFinal?.(event)
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
          if (!sawStreamingFrame) void fallbackToJson(text, context, options)
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

// ─── Lịch sử hội thoại (giữ qua các trang, tra cứu lại được) ──────────────────

/** Danh sách cuộc hội thoại của chính nhân viên đang đăng nhập (mới nhất trước). */
export const useCopilotConversations = () =>
  useQuery({
    queryKey: queryKeys.copilotConversations,
    queryFn: ({ signal }) => api.copilot.conversations(signal),
  })

/** Nội dung đầy đủ của một cuộc hội thoại cũ (đọc lại sau khi đổi trang). */
export const useCopilotConversation = (conversationId: string | null) =>
  useQuery({
    queryKey: queryKeys.copilotConversation(conversationId ?? 'none'),
    queryFn: ({ signal }) => api.copilot.conversation(conversationId as string, signal),
    enabled: Boolean(conversationId),
  })

/** Ghi lượt hỏi–đáp vào lịch sử (tự tạo cuộc mới nếu chưa có). */
export const useAppendCopilotTurn = () =>
  useCommand((body: CopilotAppendTurnRequest, key) => api.copilot.appendTurn(body, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.copilotConversations],
  })

/** Mở cuộc hội thoại mới (nút "Cuộc trò chuyện mới"). */
export const useCreateCopilotConversation = () =>
  useCommand(
    (_: void, key) => api.copilot.conversationCreate({}, { idempotencyKey: key }),
    { invalidate: () => [queryKeys.copilotConversations] },
  )

export const useRenameCopilotConversation = () =>
  useCommand(
    ({ conversationId, title }: { conversationId: string; title: string }, key) =>
      api.copilot.conversationRename(conversationId, title, { idempotencyKey: key }),
    { invalidate: () => [queryKeys.copilotConversations] },
  )

/**
 * Ghi lượt hỏi–đáp vào lịch sử **không chặn UI** (fire-and-forget, có hàng đợi tuần tự).
 *
 * Vì sao không dùng `useCommand`: lượt chat là hiệu ứng phụ của câu trả lời đã hiển thị — nếu
 * mạng lỗi thì Sale vẫn thấy câu trả lời, chỉ mất bản ghi; không được để lỗi này nổi lên UI hay
 * chặn lượt chat kế tiếp. Hàng đợi giữ đúng thứ tự user → assistant khi bấm nhanh liên tiếp.
 */
export const useAppendCopilotTurnSync = () => {
  const qc = useQueryClient()
  const queue = useRef<Promise<CopilotConversationDetail | null>>(Promise.resolve(null))

  const append = useCallback(
    (body: CopilotAppendTurnRequest) => {
      const next = queue.current
        .then(() => api.copilot.appendTurn(body, { idempotencyKey: newRequestId() }))
        .then((detail) => {
          void qc.invalidateQueries({ queryKey: queryKeys.copilotConversations })
          return detail
        })
        .catch(() => {
          /* Lịch sử là phụ trợ: lỗi ghi không được làm gián đoạn hội thoại đang mở. */
          return null
        })
      queue.current = next
      return next
    },
    [qc],
  )

  // Đảm bảo lượt cuối cùng kịp gửi khi Sale rời trang (đổi route → component unmount).
  useEffect(() => () => void queue.current, [])

  return append
}

export const useDeleteCopilotConversation = () =>
  useCommand((conversationId: string, key) => api.copilot.conversationDelete(conversationId, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.copilotConversations],
  })
