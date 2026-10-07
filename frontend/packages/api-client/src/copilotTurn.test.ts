import { describe, expect, it } from 'vitest'
import type { CopilotStreamEvent } from './contracts'
import { decideTurnStep, INITIAL_TURN_PROGRESS, type CopilotTurnProgress } from './copilotTurn'

/**
 * Hợp đồng của một lượt chat Copilot khi đọc SSE — khoá lại lỗi "Trợ lý chưa phản hồi":
 * stream đóng êm mà thiếu `final` thì BẮT BUỘC rơi về bản gom, không được kết thúc lượt rỗng.
 */
const frame = (event: Partial<CopilotStreamEvent> & { type: string }): CopilotStreamEvent =>
  event as CopilotStreamEvent

function run(signals: Array<Parameters<typeof decideTurnStep>[1]>) {
  let progress: CopilotTurnProgress = INITIAL_TURN_PROGRESS
  const actions: string[] = []
  for (const signal of signals) {
    const step = decideTurnStep(progress, signal)
    progress = step.progress
    actions.push(step.action)
  }
  return { actions, progress }
}

describe('Lượt chat Copilot — luật kết thúc lượt', () => {
  it('thought/action/observation được ghi nối tiếp vào timeline, lượt chưa kết thúc', () => {
    const { actions, progress } = run([
      { kind: 'frame', event: frame({ type: 'thought' }) },
      { kind: 'frame', event: frame({ type: 'action' }) },
      { kind: 'frame', event: frame({ type: 'observation' }) },
    ])
    expect(actions).toEqual(['append-step', 'append-step', 'append-step'])
    expect(progress).toEqual({ settled: false, sawFrame: true })
  })

  it('final kết thúc lượt; tín hiệu đến sau đó bị bỏ qua', () => {
    const { actions, progress } = run([
      { kind: 'frame', event: frame({ type: 'final', reply: 'Dạ em gửi anh/chị bảng hàng.' }) },
      { kind: 'stream-close' },
    ])
    expect(actions).toEqual(['apply-final', 'none'])
    expect(progress.settled).toBe(true)
  })

  it('frame error kết thúc lượt và hiển thị lỗi của server', () => {
    const { actions } = run([{ kind: 'frame', event: frame({ type: 'error', message: 'Trợ lý gặp sự cố.' }) }])
    expect(actions).toEqual(['apply-error'])
  })

  it('final RỖNG (thiếu reply) vẫn tính là lượt rỗng → gọi bản gom', () => {
    const { actions } = run([
      { kind: 'frame', event: frame({ type: 'observation' }) },
      { kind: 'frame', event: frame({ type: 'final', reply: '   ' }) },
    ])
    expect(actions).toEqual(['append-step', 'fallback-json'])
  })

  it('stream đóng SAU observation mà thiếu final → gọi bản gom (không để lượt trả lời rỗng)', () => {
    const { actions, progress } = run([
      { kind: 'frame', event: frame({ type: 'action' }) },
      { kind: 'frame', event: frame({ type: 'observation' }) },
      { kind: 'stream-close' },
    ])
    expect(actions).toEqual(['append-step', 'append-step', 'fallback-json'])
    expect(progress.settled).toBe(true)
  })

  it('stream đóng ngay khi chưa có frame nào → cũng gọi bản gom', () => {
    expect(run([{ kind: 'stream-close' }]).actions).toEqual(['fallback-json'])
  })

  it('SSE lỗi trước frame đầu (proxy chặn) → bản gom; lỗi giữa chừng → báo đứt kết nối', () => {
    expect(run([{ kind: 'stream-error' }]).actions).toEqual(['fallback-json'])
    expect(
      run([
        { kind: 'frame', event: frame({ type: 'observation' }) },
        { kind: 'stream-error' },
      ]).actions,
    ).toEqual(['append-step', 'apply-error'])
  })

  it('lỗi rồi đóng thêm lần nữa không sinh lượt gọi thứ hai', () => {
    const { actions } = run([{ kind: 'stream-error' }, { kind: 'stream-close' }])
    expect(actions).toEqual(['fallback-json', 'none'])
  })
})
