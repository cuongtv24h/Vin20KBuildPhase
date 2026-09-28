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
export const useRunBenchmark = () => useCommand((_run: number, key) => api.evaluation.runBenchmark({ idempotencyKey: key }))
