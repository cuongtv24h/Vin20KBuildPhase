import type { ConflictFinding, PolicyDocument, RulesTestCheck, RulesTestReport } from '@pricepolicy/api-client/contracts'
import { runBenchmark } from './benchmark'
import { MAX_STACKED_DISCOUNT_RATE } from './sanity'

const fmt = (d: string) => d.split('-').reverse().join('/')

/** Quét xung đột nội tại của văn bản: mọi cặp loại trừ / mâu thuẫn điều kiện / điều khoản mơ hồ. */
export function scanPolicyConflicts(policy: PolicyDocument): ConflictFinding[] {
  const findings: ConflictFinding[] = []
  const seen = new Set<string>()
  for (const rule of policy.rules) {
    if (rule.is_ambiguous) {
      findings.push({ tier: 3, status: 'AMBIGUOUS', rule_codes: [rule.rule_code], message: `"${rule.title}" không quy định rõ mức áp dụng — sẽ luôn chuyển Quản lý thẩm định.`, source: rule.source })
    }
    for (const rel of rule.relations) {
      if (rel.type !== 'MUTUALLY_EXCLUSIVE' && rel.type !== 'CONDITIONAL_CONFLICT') continue
      const key = [rule.rule_code, rel.rule_code].sort().join('::')
      if (seen.has(key)) continue
      seen.add(key)
      const other = policy.rules.find((r) => r.rule_code === rel.rule_code)
      findings.push({
        tier: rel.type === 'MUTUALLY_EXCLUSIVE' ? 1 : 2,
        status: 'CONFLICT',
        rule_codes: [rule.rule_code, rel.rule_code],
        message: `"${rule.title}" ↔ "${other?.title ?? rel.rule_code}": ${rel.reason ?? ''}`,
        source: rule.source,
      })
    }
  }
  return findings
}

/** Pre-publish gate F9: chỉ ban hành khi không có FAIL (WARN cho phép, hiển thị để Admin cân nhắc). */
export function testPolicyRules(policy: PolicyDocument, all: PolicyDocument[], now: string, runId = 'inline'): RulesTestReport {
  const checks: RulesTestCheck[] = []
  const add = (code: string, label: string, ok: boolean | 'warn', detail: string) =>
    checks.push({ code, label, status: ok === 'warn' ? 'WARN' : ok ? 'PASS' : 'FAIL', detail })

  add('DATE_RANGE', 'Dải hiệu lực hợp lệ', policy.effective_from <= policy.effective_to, `${fmt(policy.effective_from)} – ${fmt(policy.effective_to)}`)

  const overlaps = all.filter(
    (p) => p.policy_id !== policy.policy_id && p.project_id === policy.project_id && p.status === 'PUBLISHED' && p.effective_from <= policy.effective_to && policy.effective_from <= p.effective_to,
  )
  add('OVERLAP', 'Không chồng lấn phiên bản đang ban hành', overlaps.length === 0, overlaps.length ? `Trùng hiệu lực với ${overlaps.map((p) => `${p.policy_version} (${fmt(p.effective_from)} – ${fmt(p.effective_to)})`).join(', ')}` : 'Không chồng lấn')

  const bad = policy.rules.filter((r) =>
    r.kind === 'PERCENT_DISCOUNT' ? !(r.discount_rate && r.discount_rate > 0 && r.discount_rate <= 0.6) : r.kind === 'GIFT' ? !(r.cash_equivalent_vnd && r.cash_equivalent_vnd > 0) : r.kind === 'BANK_SUPPORT' ? !(r.interest_support_months && r.interest_support_months > 0) : false,
  )
  add('RULE_VALUES', 'Giá trị ưu đãi hợp lệ', bad.length === 0, bad.length ? `Không hợp lệ: ${bad.map((r) => r.source.section).join(', ')}` : `${policy.rules.length} điều khoản`)

  const stacked = policy.rules.filter((r) => r.kind === 'PERCENT_DISCOUNT').reduce((s, r) => s + (r.discount_rate ?? 0), 0)
  add('MAX_STACKED_DISCOUNT', 'Tổng chiết khấu cộng dồn trong trần', stacked <= MAX_STACKED_DISCOUNT_RATE ? true : 'warn', `${(stacked * 100).toFixed(1)}% / trần ${MAX_STACKED_DISCOUNT_RATE * 100}%`)

  const codes = new Set(policy.rules.map((r) => r.rule_code))
  const dangling = policy.rules.flatMap((r) => r.relations.map((x) => x.rule_code)).filter((c) => !codes.has(c))
  add('RELATION_REFS', 'Tham chiếu loại trừ nhất quán', dangling.length === 0, dangling.length ? `Không tồn tại: ${dangling.join(', ')}` : 'Nhất quán')

  add('SOURCE_DOCUMENT', 'Văn bản gốc có mã băm', /^[0-9a-f]{64}$/.test(policy.document_hash) && Boolean(policy.source_document), `${policy.source_document} · ${policy.document_hash.slice(0, 12)}…`)

  const ambiguous = policy.rules.filter((r) => r.is_ambiguous)
  add('AMBIGUOUS_CLAUSES', 'Điều khoản mơ hồ', ambiguous.length ? 'warn' : true, ambiguous.length ? ambiguous.map((r) => r.source.section).join(', ') : 'Không có')

  const regression = runBenchmark(runId, now, now, { policy_id: policy.policy_id, policy_version: policy.policy_version })
  add('FORMULA_REGRESSION', 'Kiểm thử hồi quy công thức', regression.passed === regression.total, `${regression.passed}/${regression.total} ca khớp tuyệt đối`)
  add(
    'GOLDEN_ALIGNMENT',
    'Đối chiếu bản golden đang khoá',
    regression.policy_alignment === 'MATCH' ? true : 'warn',
    regression.policy_alignment === 'MATCH'
      ? `${policy.policy_version} khớp ${regression.golden_policy_ref}`
      : `${policy.policy_version} chưa có bộ ca vàng riêng — đang đối chiếu với ${regression.golden_policy_ref}`,
  )

  return {
    policy_id: policy.policy_id,
    checked_at: now,
    checks,
    conflict_findings: scanPolicyConflicts(policy),
    regression: { passed: regression.passed, total: regression.total },
    can_publish: policy.status === 'DRAFT' && checks.every((c) => c.status !== 'FAIL'),
    benchmark_run_id: regression.run_id,
    policy_alignment: regression.policy_alignment ?? 'PINNED',
  }
}
