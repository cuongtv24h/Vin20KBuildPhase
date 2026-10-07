import { useQuery } from '@tanstack/react-query'
import { api } from '../client'
import type { TtsFeedbackPayload, TtsSettingsPayload, TtsSpeakRequest } from '../contracts'
import { queryKeys, useCommand } from './core'

/** Thiết lập giọng đọc hiện hành (danh mục nhà cung cấp + mặc định + hồ sơ riêng). */
export const useTtsSettings = () =>
  useQuery({
    queryKey: queryKeys.ttsSettings,
    queryFn: ({ signal }) => api.tts.settings(signal),
    staleTime: 60_000,
  })

/** Lưu lựa chọn giọng đọc. `scope: 'user'` cho mọi nhân viên; `'default'` chỉ ADMIN/MANAGER. */
export const useUpdateTtsSettings = () =>
  useCommand((payload: TtsSettingsPayload, key) => api.tts.updateSettings(payload, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.ttsSettings],
  })

/** Phản hồi "nghe ổn / chưa ổn" cho giọng vừa đọc — dữ liệu chọn giọng theo thực tế. */
export const useTtsVoiceFeedback = () =>
  useCommand((payload: TtsFeedbackPayload, key) => api.tts.feedback(payload, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.ttsSettings],
  })

/**
 * Đọc một đoạn văn bản qua nhà cung cấp TTS. Không invalidate danh sách nào (audio không đổi dữ liệu
 * hiển thị), nhưng hạn mức ngày thì đổi ⇒ làm mới số liệu chi phí để tab “Chi phí & hiệu năng” đúng.
 */
export const useTtsSpeak = () =>
  useCommand((payload: TtsSpeakRequest, key) => api.tts.speak(payload, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.llmUsage],
  })
