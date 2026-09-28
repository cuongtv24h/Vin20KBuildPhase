import type { ConflictFinding, PolicyDocument } from '@pricepolicy/api-client/contracts'

/** Time-Travel: phiên bản PUBLISHED có dải hiệu lực bao trùm ngày giao dịch. */
export function selectPolicyForDate(policies: PolicyDocument[], projectId: string, date: string): PolicyDocument | null {
  return policies.find((p) => p.status === 'PUBLISHED' && p.project_id === projectId && date >= p.effective_from && date <= p.effective_to) ?? null
}

const pairKey = (a: string, b: string) => [a, b].sort().join('::')

const EXCLUSION_SENTENCE = /không (được )?áp dụng đồng thời/i

/**
 * Conflict Gate (N-07) — chạy TRƯỚC khi tính tiền (ADR-006).
 * Cấp 1 loại trừ tường minh, Cấp 2 mâu thuẫn điều kiện, Cấp 3 điều khoản mơ hồ.
 */
export function detectConflicts(policy: PolicyDocument, selectedRuleCodes: string[]): ConflictFinding[] {
  const byCode = new Map(policy.rules.map((r) => [r.rule_code, r]))
  const selected = new Set(selectedRuleCodes)
  const findings: ConflictFinding[] = []
  const seen = new Set<string>()

  for (const code of selectedRuleCodes) {
    const rule = byCode.get(code)
    if (!rule) continue
    if (rule.is_ambiguous) {
      findings.push({
        tier: 3,
        status: 'AMBIGUOUS',
        rule_codes: [code],
        message: `"${rule.title}" (${rule.source.section}) không quy định rõ mức và cách thức áp dụng. Hệ thống không tự suy đoán — cần Quản lý thẩm định.`,
        source: rule.source,
      })
    }
    for (const rel of rule.relations) {
      if (!selected.has(rel.rule_code) || (rel.type !== 'MUTUALLY_EXCLUSIVE' && rel.type !== 'CONDITIONAL_CONFLICT')) continue
      const key = pairKey(code, rel.rule_code)
      if (seen.has(key)) continue
      seen.add(key)
      const other = byCode.get(rel.rule_code)
      const tier = rel.type === 'MUTUALLY_EXCLUSIVE' ? 1 : 2
      // Trích đúng điều khoản chứa câu loại trừ (vd. Điều 6.2), không phải điều khoản bị loại.
      const exclusionSource = [rule, other].find((r) => r && EXCLUSION_SENTENCE.test(r.source.quote))?.source ?? rule.source
      findings.push({
        tier,
        status: 'CONFLICT',
        rule_codes: [code, rel.rule_code],
        message:
          tier === 1
            ? `"${rule.title}" và "${other?.title ?? rel.rule_code}" loại trừ lẫn nhau — ${rel.reason ?? 'không được áp dụng đồng thời'}`
            : `"${rule.title}" và "${other?.title ?? rel.rule_code}" mâu thuẫn điều kiện thực thi — ${rel.reason ?? ''}`,
        source: exclusionSource,
      })
    }
  }
  return findings
}
