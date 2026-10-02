import { api } from '../client'
import type { ExtractRulesFields } from '../contracts'
import { queryKeys, useCommand } from './core'

export const useExtractRules = () =>
  useCommand(({ fields, file }: { fields: ExtractRulesFields; file: File }, key) => api.policies.extractRules(fields, file, { idempotencyKey: key }), {
    fingerprint: ({ fields, file }) => JSON.stringify({ fields, name: file.name, size: file.size, modified: file.lastModified }),
    invalidate: () => [['policies']],
  })

export const useTestRules = () => useCommand((policyId: string, key) => api.policies.testRules(policyId, { idempotencyKey: key }))

export const usePublishPolicy = () =>
  useCommand((policyId: string, key) => api.policies.publish(policyId, { idempotencyKey: key }), {
    invalidate: (policyId) => [queryKeys.policy(policyId), ['policies'], queryKeys.projects],
  })

/** Chạy Formula Regression Benchmark — mỗi lần bấm là một lần chạy mới. */
export const useRunBenchmark = () =>
  useCommand((_run: number, key) => api.evaluation.runBenchmark({}, { idempotencyKey: key }))

// ─── Admin CP Hooks ──────────────────────────────────────────────────────────

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { CreateUserPayload, InitAdminPayload, UpdateUserPayload } from '../contracts'

export const useAdminSetupStatus = () =>
  useQuery({
    queryKey: ['admin', 'setup-status'],
    queryFn: () => api.admin.setupStatus(),
    refetchInterval: false,
  })

export const useAdminSetup = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: InitAdminPayload) => api.admin.setup(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'setup-status'] })
    },
  })
}

export const useAdminUsers = (params: { role?: string; search?: string } = {}) =>
  useQuery({
    queryKey: ['admin', 'users', params],
    queryFn: () => api.admin.users(params),
  })

export const useCreateUser = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateUserPayload) => api.admin.createUser(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
      qc.invalidateQueries({ queryKey: ['admin', 'setup-status'] })
    },
  })
}

export const useUpdateUser = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, body }: { userId: string; body: UpdateUserPayload }) =>
      api.admin.updateUser(userId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export const useDeleteUser = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => api.admin.deleteUser(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
      qc.invalidateQueries({ queryKey: ['admin', 'setup-status'] })
    },
  })
}

