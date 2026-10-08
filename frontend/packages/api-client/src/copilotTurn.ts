import type { CopilotStreamEvent } from './contracts'

/**
 * Luật chuyển trạng thái của MỘT lượt chat Copilot khi đọc SSE.
 *
 * Vì sao tách riêng khỏi hook: đây là chỗ từng sinh lỗi thật — stream đóng êm sau `observation` mà
 * không có `final` (proxy/gateway cắt kết nối, hoặc nhánh nào đó của backend không phát final) ⇒ UI
 * đứng ở "Trợ lý đang suy luận…" rồi thành một lượt trả lời RỖNG ("Trợ lý chưa phản hồi"). Luật "đóng
 * mà thiếu final thì phải gọi bản gom" nằm ở đây để kiểm được bằng unit test thuần (ghi chú 2 bug).
 */
export type CopilotTurnSignal =
  | { kind: 'frame'; event: CopilotStreamEvent }
  | { kind: 'stream-error' }
  | { kind: 'stream-close' }

export type CopilotTurnAction =
  /** Ghi thêm một bước suy luận vào timeline. */
  | 'append-step'
  /** Lượt kết thúc bằng câu trả lời cuối. */
  | 'apply-final'
  /** Lượt kết thúc bằng lỗi do server báo (hoặc mất kết nối giữa chừng). */
  | 'apply-error'
  /** Phải gọi `POST /copilot/chat` (bản gom) để Sale vẫn nhận được câu trả lời. */
  | 'fallback-json'
  /** Lượt đã kết thúc — bỏ qua tín hiệu đến muộn. */
  | 'none'

export interface CopilotTurnProgress {
  /** Đã có `final` (hoặc đã báo lỗi) ⇒ lượt kết thúc. */
  settled: boolean
  /** Đã nhận ít nhất một frame — phân biệt "stream chết trước khi chạy" với "chết giữa chừng". */
  sawFrame: boolean
}

export const INITIAL_TURN_PROGRESS: CopilotTurnProgress = { settled: false, sawFrame: false }

export function decideTurnStep(
  progress: CopilotTurnProgress,
  signal: CopilotTurnSignal,
): { action: CopilotTurnAction; progress: CopilotTurnProgress } {
  if (signal.kind === 'frame') {
    if (progress.settled) return { action: 'none', progress }
    if (signal.event.type === 'final') {
      // `final` mà KHÔNG có nội dung trả lời (thiếu trường `reply`) cũng là lượt rỗng với Sale — coi như
      // chưa kết thúc và gọi bản gom, thay vì ghim một bong bóng trả lời trống lên màn hình.
      const reply = String((signal.event as { reply?: string }).reply ?? '').trim()
      if (!reply) return { action: 'fallback-json', progress: { settled: true, sawFrame: true } }
      return { action: 'apply-final', progress: { settled: true, sawFrame: true } }
    }
    if (signal.event.type === 'error') return { action: 'apply-error', progress: { settled: true, sawFrame: true } }
    return { action: 'append-step', progress: { settled: false, sawFrame: true } }
  }

  if (progress.settled) return { action: 'none', progress }

  if (signal.kind === 'stream-error') {
    // SSE không chạy được từ đầu (proxy chặn stream, mạng chập) ⇒ dùng bản gom.
    // Đã nhận frame rồi mới đứt ⇒ giữ nguyên hành vi cũ: báo "kết nối bị ngắt giữa chừng" để Sale thử lại.
    return {
      action: progress.sawFrame ? 'apply-error' : 'fallback-json',
      progress: { settled: true, sawFrame: progress.sawFrame },
    }
  }

  // `stream-close`: server đóng response mà KHÔNG có `final` ⇒ lượt trả lời sẽ rỗng nếu để nguyên.
  return { action: 'fallback-json', progress: { settled: true, sawFrame: progress.sawFrame } }
}
