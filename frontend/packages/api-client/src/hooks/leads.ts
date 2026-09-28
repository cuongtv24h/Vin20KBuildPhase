import { useQuery } from '@tanstack/react-query'
import { api } from '../client'
import { queryKeys } from './core'

/** Hộp hồ sơ khách từ Pre-Sales — server tự lọc theo Sale đang đăng nhập. */
export const useLeads = () => useQuery({ queryKey: queryKeys.leads, queryFn: () => api.leads.list(), refetchInterval: 20_000 })

export function useLead(dossierId: string | null | undefined) {
  const leads = useLeads()
  return { ...leads, data: dossierId ? leads.data?.find((d) => d.dossier_id === dossierId) : undefined }
}
