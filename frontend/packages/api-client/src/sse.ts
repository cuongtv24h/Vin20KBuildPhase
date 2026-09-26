import { SSE_BACKOFF_MS, SSE_IDLE_TIMEOUT_MS } from './config'
import { getAuthToken, toUrl } from './http'

/**
 * SSE client theo TD-4.1 §3.1 (quy tắc reconnect 1–5):
 * - Đọc stream bằng fetch (không dùng EventSource) để gửi được Authorization + Last-Event-ID.
 * - Heartbeat `: ping` chỉ cập nhật đồng hồ idle, không phải business event.
 * - Loại trùng theo event_id; reconnect backoff lũy tiến + jitter, gửi lại Last-Event-ID.
 * - 410 Gone (X-Action: RESYNC_FULL_STATE) → gọi onResync (REST GET) rồi nối lại từ đầu.
 * - 401/403 → đóng hẳn, không thử lại.
 */

export type SseConnectionState = 'connecting' | 'open' | 'reconnecting' | 'resyncing' | 'closed' | 'unauthorized'

export interface SseFrame {
  id: string | null
  event: string
  data: string
}

export interface SseSubscription {
  url: string
  lastEventId?: string | null
  onFrame: (frame: SseFrame) => void
  onState?: (state: SseConnectionState) => void
  onHeartbeat?: () => void
  /** Được gọi khi server trả 410 — caller tải lại trạng thái đầy đủ qua REST. */
  onResync?: () => Promise<void> | void
  /** true → dừng stream sau frame này (vd. `quote_ready`). */
  isTerminal?: (frame: SseFrame) => boolean
}

/** Tách buffer thành các frame SSE hoàn chỉnh; phần dư giữ lại cho lần đọc sau. */
export function parseSseChunk(buffer: string): { frames: (SseFrame | 'heartbeat')[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const rest = blocks.pop() ?? ''
  const frames: (SseFrame | 'heartbeat')[] = []
  for (const block of blocks) {
    if (!block.trim()) continue
    let id: string | null = null
    let event = 'message'
    const data: string[] = []
    let onlyComments = true
    for (const line of block.split('\n')) {
      if (line.startsWith(':')) continue
      onlyComments = false
      const idx = line.indexOf(':')
      const field = idx === -1 ? line : line.slice(0, idx)
      const value = idx === -1 ? '' : line.slice(idx + 1).replace(/^ /, '')
      if (field === 'id') id = value
      else if (field === 'event') event = value
      else if (field === 'data') data.push(value)
    }
    frames.push(onlyComments ? 'heartbeat' : { id, event, data: data.join('\n') })
  }
  return { frames, rest }
}

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const t = setTimeout(resolve, ms)
    signal.addEventListener('abort', () => {
      clearTimeout(t)
      resolve()
    })
  })

export function subscribeSse(sub: SseSubscription): () => void {
  const life = new AbortController()
  const seen = new Set<string>()
  let lastEventId = sub.lastEventId ?? null
  let finalState: SseConnectionState = 'closed'
  const setState = (s: SseConnectionState) => sub.onState?.(s)

  async function connectOnce(attempt: number): Promise<'done' | 'retry' | 'resync'> {
    const conn = new AbortController()
    const abortConn = () => conn.abort()
    life.signal.addEventListener('abort', abortConn)
    let idle: ReturnType<typeof setTimeout> | undefined
    const kick = () => {
      clearTimeout(idle)
      idle = setTimeout(() => conn.abort(), SSE_IDLE_TIMEOUT_MS)
    }
    try {
      setState(attempt === 0 ? 'connecting' : 'reconnecting')
      const headers: Record<string, string> = { Accept: 'text/event-stream', 'Cache-Control': 'no-cache' }
      const token = getAuthToken()
      if (token) headers.Authorization = `Bearer ${token}`
      if (lastEventId) headers['Last-Event-ID'] = lastEventId
      kick()
      const res = await fetch(toUrl(sub.url), { headers, signal: conn.signal })
      if (res.status === 410) return lastEventId ? 'resync' : 'done'
      if (res.status === 401 || res.status === 403) {
        finalState = 'unauthorized'
        return 'done'
      }
      if (!res.ok || !res.body) return 'retry'
      setState('open')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) return 'retry'
        kick()
        buffer += decoder.decode(value, { stream: true })
        const parsed = parseSseChunk(buffer)
        buffer = parsed.rest
        for (const frame of parsed.frames) {
          if (frame === 'heartbeat') {
            sub.onHeartbeat?.()
            continue
          }
          if (frame.id) {
            if (seen.has(frame.id)) continue
            seen.add(frame.id)
            lastEventId = frame.id
          }
          sub.onFrame(frame)
          if (sub.isTerminal?.(frame)) {
            reader.cancel().catch(() => undefined)
            return 'done'
          }
        }
      }
    } catch {
      return life.signal.aborted ? 'done' : 'retry'
    } finally {
      clearTimeout(idle)
      life.signal.removeEventListener('abort', abortConn)
      conn.abort()
    }
  }

  void (async () => {
    let attempt = 0
    while (!life.signal.aborted) {
      const outcome = await connectOnce(attempt)
      if (life.signal.aborted) break
      if (outcome === 'done') break
      if (outcome === 'resync') {
        setState('resyncing')
        lastEventId = null
        seen.clear()
        await sub.onResync?.()
        attempt = 0
        continue
      }
      const base = SSE_BACKOFF_MS[Math.min(attempt, SSE_BACKOFF_MS.length - 1)]
      attempt += 1
      setState('reconnecting')
      await sleep(base + Math.round(Math.random() * base * 0.2), life.signal)
    }
    setState(finalState)
  })()

  return () => life.abort()
}
