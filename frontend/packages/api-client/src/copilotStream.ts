import type { CopilotChatRequest, CopilotStreamEvent } from './contracts'
import { ENDPOINTS } from './endpoints'
import { buildHeaders, getAuthToken, toUrl } from './http'
import { parseSseChunk } from './sse'

/**
 * Đọc SSE của Sales Copilot qua `fetch` + `ReadableStream`.
 *
 * Vì sao không dùng `EventSource`: endpoint là POST (mang theo message + ngữ cảnh phiên),
 * `EventSource` chỉ hỗ trợ GET và không gửi được Authorization.
 *
 * Trả về hàm huỷ — gọi khi component unmount hoặc Sale gửi câu mới.
 */
export function streamCopilotChat(
  body: CopilotChatRequest,
  handlers: {
    onEvent: (event: CopilotStreamEvent) => void
    onError?: (error: unknown) => void
    onClose?: () => void
  },
  signal?: AbortSignal,
): () => void {
  const life = new AbortController()
  const abortAll = () => life.abort()
  signal?.addEventListener('abort', abortAll)

  void (async () => {
    try {
      const headers: Record<string, string> = {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        ...buildHeaders({ method: 'POST' }),
      }
      // Một số gateway yêu cầu Idempotency-Key cho mọi POST; SSE không replay nên khoá là duy nhất.
      headers['Idempotency-Key'] = `copilot-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
      const res = await fetch(toUrl(ENDPOINTS.copilotChatStream.path), {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: life.signal,
      })
      if (!res.ok || !res.body) {
        throw new Error(`Copilot stream HTTP ${res.status}`)
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parsed = parseSseChunk(buffer)
        buffer = parsed.rest
        for (const frame of parsed.frames) {
          if (frame === 'heartbeat') continue
          try {
            handlers.onEvent(JSON.parse(frame.data) as CopilotStreamEvent)
          } catch {
            // frame hỏng không được làm chết cả phiên chat
          }
        }
      }
      handlers.onClose?.()
    } catch (error) {
      if (!life.signal.aborted) handlers.onError?.(error)
    } finally {
      signal?.removeEventListener('abort', abortAll)
    }
  })()

  return () => life.abort()
}

/** Token hiện tại — dùng cho công cụ dev kiểm tra nhanh kết nối SSE. */
export const copilotAuthToken = () => getAuthToken()
