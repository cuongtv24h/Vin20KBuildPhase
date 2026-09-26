import type { ConflictFinding, PolicyRule, PolicyVersion, PolicyVersionRef, PreflightResult } from '@/types/domain'

export interface PreflightParams {
  projectName: string
  transactionDate: string
  /** Phiên bản chính sách PUBLISHED có hiệu lực tại ngày giao dịch (null nếu không có). */
  activePolicy: PolicyVersion | null
  selectedRuleCodes: string[]
}

export function toPolicyRef(policy: PolicyVersion): PolicyVersionRef {
  return {
    policyId: policy.policyId,
    version: policy.version,
    title: policy.title,
    effectiveFrom: policy.effectiveFrom,
    effectiveTo: policy.effectiveTo,
    sourceFileHash: policy.sourceFileHash,
  }
}

/** Time-Travel: chọn phiên bản PUBLISHED có dải hiệu lực bao trùm ngày giao dịch. */
export function selectPolicyForDate(policies: PolicyVersion[], projectId: string, date: string): PolicyVersion | null {
  return (
    policies.find(
      (p) => p.status === 'PUBLISHED' && p.projectId === projectId && date >= p.effectiveFrom && date <= p.effectiveTo,
    ) ?? null
  )
}

/**
 * Conflict Gate — chạy TRƯỚC khi tính toán. Nếu phát hiện EXPIRED / CONFLICT (Cấp 1, 2) /
 * AMBIGUOUS (Cấp 3) trong tập ưu đãi đã chọn, luồng tính toán bị chặn (Safe Abstention).
 */
export function runPreflight(params: PreflightParams): PreflightResult {
  const { projectName, transactionDate, activePolicy, selectedRuleCodes } = params
  const findings: ConflictFinding[] = []

  if (!activePolicy) {
    return {
      transactionDate,
      activePolicy: null,
      expired: true,
      hasBlockingIssue: true,
      findings: [
        {
          status: 'EXPIRED',
          ruleCodes: [],
          message: `Không có văn bản chính sách nào của dự án "${projectName}" còn hiệu lực tại ngày giao dịch ${transactionDate}.`,
        },
      ],
    }
  }

  const rulesByCode = new Map<string, PolicyRule>(activePolicy.rules.map((r) => [r.ruleCode, r]))
  const selectedSet = new Set(selectedRuleCodes)

  // Cấp 3 — Mơ hồ / thiếu căn cứ
  for (const code of selectedRuleCodes) {
    const rule = rulesByCode.get(code)
    if (rule?.isAmbiguous) {
      findings.push({
        tier: 3,
        status: 'AMBIGUOUS',
        ruleCodes: [code],
        message: `Điều khoản "${rule.title}" (${rule.source.clauseTitle}) không quy định rõ mức và cách thức áp dụng — cần Quản lý thẩm định.`,
        source: rule.source,
      })
    }
  }

  // Cấp 1 — Loại trừ tường minh
  const seenTier1 = new Set<string>()
  for (const code of selectedRuleCodes) {
    const rule = rulesByCode.get(code)
    if (!rule?.mutualExclusion) continue
    for (const otherCode of rule.mutualExclusion) {
      if (!selectedSet.has(otherCode)) continue
      const pairKey = [code, otherCode].sort().join('::')
      if (seenTier1.has(pairKey)) continue
      seenTier1.add(pairKey)
      const other = rulesByCode.get(otherCode)
      findings.push({
        tier: 1,
        status: 'CONFLICT',
        ruleCodes: [code, otherCode],
        message: `"${rule.title}" và "${other?.title ?? otherCode}" bị loại trừ lẫn nhau theo ${rule.source.clauseTitle}, không được áp dụng đồng thời.`,
        source: rule.source,
      })
    }
  }

  // Cấp 2 — Mâu thuẫn điều kiện thực thi
  const seenTier2 = new Set<string>()
  for (const code of selectedRuleCodes) {
    const rule = rulesByCode.get(code)
    if (!rule?.conditionalConflict) continue
    for (const conflict of rule.conditionalConflict) {
      if (!selectedSet.has(conflict.ruleCode)) continue
      const pairKey = [code, conflict.ruleCode].sort().join('::')
      if (seenTier2.has(pairKey)) continue
      seenTier2.add(pairKey)
      const other = rulesByCode.get(conflict.ruleCode)
      findings.push({
        tier: 2,
        status: 'CONFLICT',
        ruleCodes: [code, conflict.ruleCode],
        message: `"${rule.title}" và "${other?.title ?? conflict.ruleCode}" mâu thuẫn điều kiện thực thi: ${conflict.reasonText}`,
        source: rule.source,
      })
    }
  }

  return {
    transactionDate,
    activePolicy: toPolicyRef(activePolicy),
    expired: false,
    findings,
    hasBlockingIssue: findings.length > 0,
  }
}
