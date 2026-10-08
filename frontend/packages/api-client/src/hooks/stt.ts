import { useQuery } from '@tanstack/react-query'
import { api } from '../client'
import { queryKeys } from './core'

/**
 * Trạng thái tầng nghe-nói: chuỗi nhà cung cấp đang bật, hạn mức phút/ngày, trần thời lượng ghi âm.
 *
 * Nút micro trong SalesWorkspacePage đọc hook này để quyết định đi đường nào:
 * có nhà cung cấp API (Whisper) → ghi âm rồi gửi backend; chưa có → rơi về Web Speech API của trình duyệt.
 * `retry: false` để backend chưa bật STT thì UI biết ngay mà dùng lưới an toàn, không bắt Sale chờ.
 */
export const useSttHealth = (options: { enabled?: boolean } = {}) =>
  useQuery({
    queryKey: queryKeys.sttHealth,
    queryFn: ({ signal }) => api.stt.health(signal),
    staleTime: 60_000,
    retry: false,
    ...options,
  })

/** Hạn mức nghe-nói còn lại trong ngày (để hiện cảnh báo trước khi Sale hết lượt). */
export const useSttQuota = (options: { enabled?: boolean } = {}) =>
  useQuery({
    queryKey: queryKeys.sttQuota,
    queryFn: ({ signal }) => api.stt.quota(signal),
    staleTime: 30_000,
    retry: false,
    ...options,
  })

/** Danh mục nhà cung cấp STT cho màn hình quản trị (ADMIN). */
export const useSttProviders = (options: { enabled?: boolean } = {}) =>
  useQuery({
    queryKey: queryKeys.sttProviders,
    queryFn: ({ signal }) => api.sttAdmin.providers(signal),
    staleTime: 30_000,
    ...options,
  })
