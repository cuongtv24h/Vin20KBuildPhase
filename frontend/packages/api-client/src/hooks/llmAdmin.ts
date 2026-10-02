import { useQuery } from '@tanstack/react-query'
import { api } from '../client'
import type { LlmProviderPayload } from '../contracts'
import { queryKeys, useCommand } from './core'

/** Danh sách nhà cung cấp LLM Admin đã khai báo (DB trước, ENV sau). */
export const useLlmProviders = () =>
  useQuery({
    queryKey: queryKeys.llmProviders,
    queryFn: ({ signal }) => api.llmAdmin.providers(signal),
  })

export const useCreateLlmProvider = () =>
  useCommand((payload: LlmProviderPayload, key) => api.llmAdmin.createProvider(payload, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.llmProviders, queryKeys.llmUsage],
  })

export const useUpdateLlmProvider = () =>
  useCommand(
    ({ providerId, payload }: { providerId: string; payload: LlmProviderPayload }, key) =>
      api.llmAdmin.updateProvider(providerId, payload, { idempotencyKey: key }),
    { invalidate: () => [queryKeys.llmProviders, queryKeys.llmUsage] },
  )

export const useDeleteLlmProvider = () =>
  useCommand((providerId: string, key) => api.llmAdmin.deleteProvider(providerId, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.llmProviders, queryKeys.llmUsage],
  })

/** Kiểm tra kết nối thật tới nhà cung cấp (gọi /models) — không cần invalidate toàn bộ. */
export const useTestLlmProvider = () =>
  useCommand((providerId: string, key) => api.llmAdmin.testProvider(providerId, { idempotencyKey: key }), {
    invalidate: () => [queryKeys.llmProviders],
  })

/** Tab "Chi phí & hiệu năng": tổng hợp token/chi phí/độ trễ trong `days` ngày. */
export const useLlmUsageSummary = (days = 14) =>
  useQuery({
    queryKey: [...queryKeys.llmUsage, 'summary', days],
    queryFn: ({ signal }) => api.llmAdmin.usageSummary(days, signal),
  })

/** Log các lượt gọi gần nhất để đối chiếu chi phí thực tế. */
export const useLlmUsageRecords = (limit = 50) =>
  useQuery({
    queryKey: [...queryKeys.llmUsage, 'records', limit],
    queryFn: ({ signal }) => api.llmAdmin.usageRecords(limit, signal),
  })
