/**
 * Test tầng ghi âm micro (`voiceRecorder.ts`) — chạy trong Node, không cần DOM thật.
 *
 * Điểm cần chốt:
 * 1. Chọn đúng kiểu MIME trình duyệt hỗ trợ (webm/opus trước, mp4 cho Safari) — sai kiểu là backend 415.
 * 2. Lỗi micro phải ra CÂU TIẾNG VIỆT làm theo được (bị chặn quyền, không có micro, app khác chiếm),
 *    không im lặng và không ném lỗi ra ngoài.
 * 3. Môi trường không có `MediaRecorder` (Node/Firefox cũ) → `supported = false`, `start()` chỉ báo lỗi.
 */

import { describe, expect, it, vi } from 'vitest'
import {
  AUDIO_MIME_CANDIDATES,
  MIN_CLIP_SECONDS,
  VOICE_RECORDER_UNSUPPORTED_MESSAGE,
  createVoiceRecorder,
  describeMediaError,
  isVoiceRecorderSupported,
  pickAudioMimeType,
} from './voiceRecorder'

describe('pickAudioMimeType — chọn kiểu audio trình duyệt hỗ trợ', () => {
  it('ưu tiên webm/opus (nhỏ, rõ cho giọng nói)', () => {
    const supported = (mime: string) => mime === 'audio/webm;codecs=opus' || mime === 'audio/mp4'
    expect(pickAudioMimeType(supported)).toBe('audio/webm;codecs=opus')
  })

  it('rơi xuống mp4 khi chỉ Safari hỗ trợ', () => {
    expect(pickAudioMimeType((mime) => mime === 'audio/mp4')).toBe('audio/mp4')
  })

  it('tôn trọng kiểu MIME do caller ép, nhưng chỉ khi trình duyệt hỗ trợ', () => {
    const supported = (mime: string) => mime === 'audio/ogg;codecs=opus'
    expect(pickAudioMimeType(supported, 'audio/ogg;codecs=opus')).toBe('audio/ogg;codecs=opus')
    expect(pickAudioMimeType(() => false, 'audio/ogg;codecs=opus')).toBeNull()
  })

  it('không hỗ trợ gì thì trả null (để caller báo lỗi rõ, không gửi kiểu lạ lên backend)', () => {
    expect(pickAudioMimeType(() => false)).toBeNull()
  })

  it('danh sách ưu tiên phải nằm trong các kiểu backend chấp nhận', () => {
    // Backend (`src/services/stt_providers.ACCEPTED_CONTENT_TYPES`) nhận audio/webm, ogg, mp4…
    for (const mime of AUDIO_MIME_CANDIDATES) {
      expect(mime.startsWith('audio/')).toBe(true)
    }
    expect(AUDIO_MIME_CANDIDATES[0]).toBe('audio/webm;codecs=opus')
  })
})

describe('describeMediaError — dịch lỗi micro sang tiếng Việt', () => {
  it('chặn quyền micro thì chỉ đúng chỗ phải bấm', () => {
    expect(describeMediaError('NotAllowedError')).toContain('ổ khóa')
    expect(describeMediaError('PermissionDeniedError')).toContain('ổ khóa')
  })

  it('không có micro / micro bị chiếm / trang không HTTPS đều có câu riêng', () => {
    expect(describeMediaError('NotFoundError')).toContain('Không tìm thấy micro')
    expect(describeMediaError('NotReadableError')).toContain('ứng dụng khác')
    expect(describeMediaError('SecurityError')).toContain('HTTPS')
  })

  it('lỗi lạ vẫn có câu giải thích kèm tên lỗi, không trả chuỗi rỗng', () => {
    const message = describeMediaError('WeirdError', 'boom')
    expect(message).toContain('WeirdError')
    expect(describeMediaError('', '')).toBeTruthy()
  })
})

describe('môi trường không có MediaRecorder (Node, Firefox cũ)', () => {
  it('báo không hỗ trợ thay vì ném lỗi', () => {
    expect(isVoiceRecorderSupported()).toBe(false)
    expect(MIN_CLIP_SECONDS).toBeGreaterThanOrEqual(1)
  })

  it('start() chỉ gọi onError với câu hướng dẫn dùng Chrome/Edge/Cốc Cốc', async () => {
    const onError = vi.fn()
    const onStop = vi.fn()
    const recorder = createVoiceRecorder({ onError, onStop })

    expect(recorder.supported).toBe(false)
    await expect(recorder.start()).resolves.toBeUndefined()
    expect(onError).toHaveBeenCalledWith(VOICE_RECORDER_UNSUPPORTED_MESSAGE)
    expect(onStop).not.toHaveBeenCalled()
    expect(recorder.isRecording()).toBe(false)
  })

  it('stop()/cancel() an toàn khi chưa từng ghi', () => {
    const onError = vi.fn()
    const recorder = createVoiceRecorder({ onError })
    expect(() => recorder.stop()).not.toThrow()
    expect(() => recorder.cancel()).not.toThrow()
    expect(onError).not.toHaveBeenCalled()
  })
})
