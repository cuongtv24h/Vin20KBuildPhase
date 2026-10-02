import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import type { LeadCreatePayload, LeadUpdatePayload, LeadDossier } from '../contracts'
import { queryKeys } from './core'

/** Hộp hồ sơ khách từ Pre-Sales — server tự lọc theo Sale đang đăng nhập. */
export const useLeads = () => useQuery({ queryKey: queryKeys.leads, queryFn: () => api.leads.list(), refetchInterval: 20_000 })

export function useLead(dossierId: string | null | undefined) {
  const leads = useLeads()
  return { ...leads, data: dossierId ? leads.data?.find((d) => d.dossier_id === dossierId) : undefined }
}

/** Khởi tạo khách hàng mới trực tiếp bởi chuyên viên Sale / Copilot Tool */
export function useCreateLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: LeadCreatePayload) => api.leads.create(body),
    onSuccess: (newDossier) => {
      qc.setQueryData<LeadDossier[]>(queryKeys.leads, (old) => {
        if (!old) return [newDossier]
        return [newDossier, ...old.filter((d) => d.dossier_id !== newDossier.dossier_id)]
      })
      qc.invalidateQueries({ queryKey: queryKeys.leads })
    },
  })
}

/** Cập nhật thông tin khách hàng bởi Sale (CRM) */
export function useUpdateLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ dossierId, payload }: { dossierId: string; payload: LeadUpdatePayload }) =>
      api.leads.update(dossierId, payload),
    onSuccess: (updated) => {
      qc.setQueryData<LeadDossier[]>(queryKeys.leads, (old) => {
        if (!old) return [updated]
        return old.map((d) => (d.dossier_id === updated.dossier_id ? updated : d))
      })
      qc.invalidateQueries({ queryKey: queryKeys.leads })
    },
  })
}

/** Xóa hồ sơ khách hàng */
export function useDeleteLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (dossierId: string) => api.leads.delete(dossierId),
    onSuccess: (_, dossierId) => {
      qc.setQueryData<LeadDossier[]>(queryKeys.leads, (old) => {
        if (!old) return []
        return old.filter((d) => d.dossier_id !== dossierId)
      })
      qc.invalidateQueries({ queryKey: queryKeys.leads })
    },
  })
}
