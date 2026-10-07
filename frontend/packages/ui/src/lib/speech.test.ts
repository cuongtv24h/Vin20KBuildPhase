/**
 * Nhập liệu bằng giọng nói: cái khó không nằm ở việc gọi API trình duyệt, mà ở **cách xử lý khi trình
 * duyệt tự dừng hoặc từ chối micro**. Test dựng lớp `SpeechRecognition` giả để khoá lại:
 *
 * 1. Trình duyệt không hỗ trợ → nói thẳng cho người dùng, không im lặng.
 * 2. Chế độ rảnh tay → trình duyệt tự dừng sau quãng im lặng thì phải **tự nghe lại**.
 * 3. Người dùng bấm dừng → không được tự nghe lại.
 * 4. Lỗi quyền micro → câu tiếng Việt chỉ đúng cách mở quyền.
 *
 * Test chạy ở môi trường Node (không có DOM): `window` được giả lập tối thiểu — đúng phần mà
 * `speech.ts` thật sự chạm tới, nên không cần jsdom.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createSpeechToText,
  getSpeechRecognitionCtor,
  isSpeechToTextSupported,
  SPEECH_TO_TEXT_UNSUPPORTED_MESSAGE,
  type SpeechEventLike,
} from '@pricepolicy/ui/lib/speech'

/** Lớp nhận dạng giọng nói giả — đủ để lái các nhánh xử lý của `createSpeechToText`. */
class FakeRecognition {
  lang = ''
  continuous = false
  interimResults = false
  maxAlternatives = 1
  started = 0
  stopped = 0
  onresult: ((event: SpeechEventLike) => void) | null = null
  onerror: ((event: { error?: string; message?: string }) => void) | null = null
  onend: (() => void) | null = null
  onstart: (() => void) | null = null

  constructor() {
    instances.push(this)
  }

  start() {
    this.started += 1
    this.onstart?.()
  }

  stop() {
    this.stopped += 1
    this.onend?.()
  }

  abort() {}
}

/** Mọi lớp giả đã được khởi tạo — lái sự kiện "từ trình duyệt" qua phần tử cuối. */
const instances: FakeRecognition[] = []
const last = () => instances[instances.length - 1]

const install = (ctor: unknown) => {
  ;(globalThis as unknown as { window: unknown }).window = { webkitSpeechRecognition: ctor }
}

const uninstall = () => {
  delete (globalThis as unknown as { window?: unknown }).window
}

afterEach(() => {
  uninstall()
  instances.length = 0
  vi.useRealTimers()
})

describe('nhập liệu bằng giọng nói (rảnh tay)', () => {
  it('trình duyệt không hỗ trợ thì báo rõ phải dùng trình duyệt nào', () => {
    expect(getSpeechRecognitionCtor()).toBeNull()
    expect(isSpeechToTextSupported()).toBe(false)
    const errors: string[] = []
    const stt = createSpeechToText({ onError: (m) => errors.push(m) })
    expect(stt.supported).toBe(false)
    stt.start()
    expect(errors).toEqual([SPEECH_TO_TEXT_UNSUPPORTED_MESSAGE])
    expect(SPEECH_TO_TEXT_UNSUPPORTED_MESSAGE).toContain('Chrome')
  })

  it('chế độ rảnh tay: trình duyệt tự dừng thì tự nghe lại', () => {
    vi.useFakeTimers()
    install(FakeRecognition)
    const states: boolean[] = []
    const stt = createSpeechToText({ onStateChange: (v) => states.push(v), continuous: true })
    expect(stt.supported).toBe(true)

    stt.start()
    expect(stt.isListening()).toBe(true)
    expect(states).toEqual([true])

    // Chrome tự dừng sau quãng im lặng → phải hẹn nghe lại
    last().onend?.()
    expect(stt.isListening()).toBe(false)
    vi.advanceTimersByTime(300)
    expect(last().started).toBe(2) // đã nghe lại
  })

  it('người dùng bấm dừng thì KHÔNG nghe lại nữa', () => {
    vi.useFakeTimers()
    install(FakeRecognition)
    const stt = createSpeechToText({ continuous: true })
    stt.start()
    stt.stop()
    vi.advanceTimersByTime(1000)
    expect(last().started).toBe(1) // không tự bật lại
    expect(stt.isListening()).toBe(false)
  })

  it('lỗi quyền micro: câu tiếng Việt chỉ đúng cách mở quyền', () => {
    install(FakeRecognition)
    const errors: string[] = []
    const stt = createSpeechToText({ onError: (m) => errors.push(m) })
    stt.start()
    last().onerror?.({ error: 'not-allowed' })
    expect(errors[0]).toContain('Micro đang bị chặn')
    expect(stt.isListening()).toBe(false)
  })

  it('câu đã chốt và chữ tạm được đẩy ra đúng chỗ để hiển thị', () => {
    install(FakeRecognition)
    const partial: string[] = []
    const finals: string[] = []
    const stt = createSpeechToText({ onPartial: (t) => partial.push(t), onFinal: (t) => finals.push(t) })
    stt.start()
    const results = {
      length: 2,
      0: { isFinal: true, 0: { transcript: 'Chính sách thanh toán sớm' }, length: 1 },
      1: { isFinal: false, 0: { transcript: ' là bao nhiêu' }, length: 1 },
    }
    last().onresult?.({ resultIndex: 0, results } as unknown as SpeechEventLike)
    expect(finals).toEqual(['Chính sách thanh toán sớm'])
    expect(partial).toEqual(['là bao nhiêu'])  // hàm tự cắt khoảng trắng thừa
  })

  it('im lặng vài giây (no-speech) không làm phiền người dùng bằng thông báo lỗi', () => {
    install(FakeRecognition)
    const errors: string[] = []
    const stt = createSpeechToText({ onError: (m) => errors.push(m) })
    stt.start()
    last().onerror?.({ error: 'no-speech' })
    expect(errors).toEqual([])
  })
})
