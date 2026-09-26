import type { PublishCheck, PublishCheckReport } from '@/api/contracts'
import { runBenchmarkSuite, summarizeBenchmark } from '@/engine/benchmark'
import { formatDate } from '@/lib/format'
import type { PolicyVersion } from '@/types/domain'

/** Trần thẩm quyền: tổng mọi chiết khấu % có thể cộng dồn không vượt quá mức này. */
export const MAX_STACKED_DISCOUNT_RATE = 0.2

/** Bộ kiểm tra bắt buộc trước khi Admin Sale ban hành một phiên bản chính sách. */
export function runPublishChecks(policy: PolicyVersion, allPolicies: PolicyVersion[], now: string): PublishCheckReport {
  const checks: PublishCheck[] = []

  const validRange = policy.effectiveFrom <= policy.effectiveTo
  checks.push({
    code: 'DATE_RANGE',
    label: 'Dải hiệu lực hợp lệ',
    status: validRange ? 'PASS' : 'FAIL',
    detail: validRange
      ? `Từ ${formatDate(policy.effectiveFrom)} đến ${formatDate(policy.effectiveTo)}.`
      : 'Ngày bắt đầu hiệu lực đang sau ngày kết thúc.',
  })

  const overlaps = allPolicies.filter(
    (p) =>
      p.policyId !== policy.policyId &&
      p.projectId === policy.projectId &&
      p.status === 'PUBLISHED' &&
      p.effectiveFrom <= policy.effectiveTo &&
      policy.effectiveFrom <= p.effectiveTo,
  )
  checks.push({
    code: 'OVERLAP',
    label: 'Không chồng lấn phiên bản đang ban hành',
    status: overlaps.length === 0 ? 'PASS' : 'FAIL',
    detail:
      overlaps.length === 0
        ? 'Không trùng dải hiệu lực với phiên bản nào của dự án.'
        : `Trùng dải hiệu lực với ${overlaps.map((p) => `${p.version} (${formatDate(p.effectiveFrom)}–${formatDate(p.effectiveTo)})`).join(', ')}.`,
  })

  const badValues = policy.rules.filter((r) => {
    if (r.kind === 'PERCENT_DISCOUNT') return !(r.discountRate && r.discountRate > 0 && r.discountRate <= 0.6)
    if (r.kind === 'GIFT') return !(r.cashEquivalentVnd && r.cashEquivalentVnd > 0)
    if (r.kind === 'BANK_SUPPORT') return !(r.interestSupportMonths && r.interestSupportMonths > 0)
    return false
  })
  checks.push({
    code: 'RULE_VALUES',
    label: 'Giá trị ưu đãi hợp lệ',
    status: badValues.length === 0 ? 'PASS' : 'FAIL',
    detail:
      badValues.length === 0
        ? `${policy.rules.length} điều khoản đều có giá trị hợp lệ.`
        : `Giá trị không hợp lệ tại: ${badValues.map((r) => r.source.clauseTitle).join(', ')}.`,
  })

  const stacked = policy.rules
    .filter((r) => r.kind === 'PERCENT_DISCOUNT')
    .reduce((sum, r) => sum + (r.discountRate ?? 0), 0)
  checks.push({
    code: 'MAX_STACKED_DISCOUNT',
    label: 'Tổng chiết khấu tối đa trong trần thẩm quyền',
    status: stacked <= MAX_STACKED_DISCOUNT_RATE ? 'PASS' : 'WARN',
    detail: `Cộng dồn tối đa ${(stacked * 100).toFixed(1)}% (trần ${(MAX_STACKED_DISCOUNT_RATE * 100).toFixed(0)}%).`,
  })

  const codes = new Set(policy.rules.map((r) => r.ruleCode))
  const danglingRefs = policy.rules.flatMap((r) => [
    ...(r.mutualExclusion ?? []).filter((c) => !codes.has(c)),
    ...(r.conditionalConflict ?? []).map((c) => c.ruleCode).filter((c) => !codes.has(c)),
  ])
  checks.push({
    code: 'EXCLUSION_REFS',
    label: 'Tham chiếu loại trừ nhất quán',
    status: danglingRefs.length === 0 ? 'PASS' : 'FAIL',
    detail: danglingRefs.length === 0 ? 'Mọi điều khoản loại trừ đều trỏ tới điều khoản tồn tại.' : `Tham chiếu không tồn tại: ${danglingRefs.join(', ')}.`,
  })

  const hasSource = Boolean(policy.sourceDocument && /^[0-9a-f]{64}$/.test(policy.sourceFileHash))
  checks.push({
    code: 'SOURCE_DOCUMENT',
    label: 'Văn bản gốc đã đóng dấu',
    status: hasSource ? 'PASS' : 'FAIL',
    detail: hasSource ? `${policy.sourceDocument} · SHA-256 ${policy.sourceFileHash.slice(0, 12)}…` : 'Chưa tải lên văn bản chính sách gốc.',
  })

  const summary = summarizeBenchmark(runBenchmarkSuite())
  checks.push({
    code: 'FORMULA_REGRESSION',
    label: 'Kiểm thử hồi quy công thức',
    status: summary.exactMatchRate === 1 ? 'PASS' : 'FAIL',
    detail: `${summary.passedCount}/${summary.total} ca kiểm thử khớp tuyệt đối.`,
  })

  return {
    policyId: policy.policyId,
    checkedAt: now,
    checks,
    canPublish: policy.status === 'DRAFT' && checks.every((c) => c.status !== 'FAIL'),
  }
}
