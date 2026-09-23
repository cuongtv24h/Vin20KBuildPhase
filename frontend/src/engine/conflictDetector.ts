import { getPolicyForDate } from '@/data/policies.mock'
import type {
  ApartmentUnit,
  ConflictFinding,
  CustomerSegment,
  PolicyRule,
  PreflightResult,
} from '@/types/domain'

export interface PreflightParams {
  unit: ApartmentUnit
  transactionDate: string
  customerSegment: CustomerSegment
  unitsQuantity: number
  selectedRuleCodes: string[]
}

/**
 * Cửa kiểm soát Xung đột (Conflict Gate) + Time-Travel Policy Selector.
 * Chạy TRƯỚC khi tính toán — nếu phát hiện EXPIRED / CONFLICT (Cấp 1, 2) / AMBIGUOUS
 * (Cấp 3) trong tập ưu đãi Sale đã chọn, toàn bộ luồng tính toán bị chặn (Safe
 * Abstention Gate — Vùng 3 theo Decision Boundary của PRD §5).
 */
export function runPreflight(params: PreflightParams): PreflightResult {
  const { unit, transactionDate, selectedRuleCodes } = params
  const activePolicy = getPolicyForDate(unit.projectId, transactionDate)
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
          message: `Không tìm thấy văn bản chính sách nào của dự án "${unit.projectName}" còn hiệu lực tại ngày giao dịch ${transactionDate}. Hệ thống từ chối tự suy đoán chính sách áp dụng.`,
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
        message: `Điều khoản "${rule.title}" (${rule.source.clauseTitle}) dùng từ ngữ mở, không quy định rõ ràng cách thức áp dụng. Agent từ chối tự suy diễn mức ưu đãi.`,
        source: rule.source,
      })
    }
  }

  // Cấp 1 — Loại trừ tường minh (Explicit Exclusion)
  const seenPairs = new Set<string>()
  for (const code of selectedRuleCodes) {
    const rule = rulesByCode.get(code)
    if (!rule?.mutualExclusion) continue
    for (const otherCode of rule.mutualExclusion) {
      if (!selectedSet.has(otherCode)) continue
      const pairKey = [code, otherCode].sort().join('::')
      if (seenPairs.has(pairKey)) continue
      seenPairs.add(pairKey)
      const other = rulesByCode.get(otherCode)
      findings.push({
        tier: 1,
        status: 'CONFLICT',
        ruleCodes: [code, otherCode],
        message: `"${rule.title}" và "${other?.title ?? otherCode}" bị loại trừ tường minh lẫn nhau theo ${rule.source.clauseTitle}. Không được phép cộng dồn đồng thời.`,
        source: rule.source,
      })
    }
  }

  // Cấp 2 — Xung đột ràng buộc điều kiện ngầm (Conditional Conflict)
  const seenPairsTier2 = new Set<string>()
  for (const code of selectedRuleCodes) {
    const rule = rulesByCode.get(code)
    if (!rule?.conditionalConflict) continue
    for (const conflict of rule.conditionalConflict) {
      if (!selectedSet.has(conflict.ruleCode)) continue
      const pairKey = [code, conflict.ruleCode].sort().join('::')
      if (seenPairsTier2.has(pairKey)) continue
      seenPairsTier2.add(pairKey)
      const other = rulesByCode.get(conflict.ruleCode)
      findings.push({
        tier: 2,
        status: 'CONFLICT',
        ruleCodes: [code, conflict.ruleCode],
        message: `"${rule.title}" và "${other?.title ?? conflict.ruleCode}" mâu thuẫn điều kiện thực thi ngầm: ${conflict.reasonText}`,
        source: rule.source,
      })
    }
  }

  return {
    transactionDate,
    activePolicy,
    expired: false,
    findings,
    hasBlockingIssue: findings.length > 0,
  }
}
