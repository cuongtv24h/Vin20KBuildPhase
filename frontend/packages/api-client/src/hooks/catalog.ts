import { useQuery } from '@tanstack/react-query'
import { api } from '../client'
import type { AuthSession, LoginRequest, ReauthRequest } from '../contracts'
import { queryKeys, useCommand } from './core'

export const useProjectOverviews = () => useQuery({ queryKey: queryKeys.projects, queryFn: () => api.catalog.projects() })

export const useUnits = (projectId?: string) =>
  useQuery({ queryKey: queryKeys.units(projectId), queryFn: () => api.catalog.units({ project_id: projectId }), staleTime: 60_000 })

export const usePolicies = (filter: { project_id?: string; status?: string } = {}, enabled = true) =>
  useQuery({ queryKey: queryKeys.policies(filter), queryFn: () => api.catalog.policies(filter), enabled })

export const usePolicy = (policyId: string | null | undefined) =>
  useQuery({ queryKey: queryKeys.policy(policyId ?? ''), queryFn: () => api.catalog.policy(policyId ?? ''), enabled: Boolean(policyId) })

/** Time-Travel lookup: phiên bản PUBLISHED có hiệu lực tại ngày giao dịch. */
export const useActivePolicy = (projectId: string | undefined, date: string | null) =>
  useQuery({
    queryKey: queryKeys.activePolicy(projectId ?? '', date ?? ''),
    queryFn: () => api.catalog.activePolicy({ project_id: projectId ?? '', date: date ?? '' }),
    enabled: Boolean(projectId && date),
  })

export const useLogin = () => useCommand((body: LoginRequest, key): Promise<AuthSession> => api.auth.login(body, { idempotencyKey: key }))

export const useReauth = () => useCommand((body: ReauthRequest, key) => api.auth.reauth(body, { idempotencyKey: key }))
