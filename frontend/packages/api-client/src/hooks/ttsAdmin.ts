import { useQuery } from '@tanstack/react-query'
import { api } from '../client'
import type { TtsProviderPayload } from '../contracts'
import { queryKeys, useCommand } from './core'

/** Danh mục nhà cung cấp TTS hiệu lực (dựng sẵn + bản ghi Admin thêm/đè) — dùng cho tab quản trị. */
export const useTtsProviders = () =>
  useQuery({
    queryKey: queryKeys.ttsProviders,
    queryFn: ({ signal }) => api.ttsAdmin.providers(signal),
  })

/** Thêm nhà cung cấp mới hoặc tạo bản ghi đè cho nhà cung cấp dựng sẵn (theo mã `provider`). */
export const useCreateTtsProvider = () =>
  useCommand(
    (payload: TtsProviderPayload, key) => api.ttsAdmin.createProvider(payload, { idempotencyKey: key }),
    // Danh mục ở màn hình giọng đọc cũng đổi theo ⇒ làm mới cả hai.
    { invalidate: () => [queryKeys.ttsProviders, queryKeys.ttsSettings] },
  )

export const useUpdateTtsProvider = () =>
  useCommand(
    ({ providerId, payload }: { providerId: string; payload: TtsProviderPayload }, key) =>
      api.ttsAdmin.updateProvider(providerId, payload, { idempotencyKey: key }),
    { invalidate: () => [queryKeys.ttsProviders, queryKeys.ttsSettings] },
  )

export const useDeleteTtsProvider = () =>
  useCommand((providerId: string, key) => api.ttsAdmin.deleteProvider(providerId, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.ttsProviders, queryKeys.ttsSettings],
  })

/** Kiểm tra kết nối thật tới nhà cung cấp (không tổng hợp thử để tránh phát sinh tiền). */
export const useTestTtsProvider = () =>
  useCommand((providerRef: string, key) => api.ttsAdmin.testProvider(providerRef, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.ttsProviders],
  })
