import type {
  Abstention,
  AgentStep,
  CalculationValidation,
  ConflictReport,
  EvidenceBackedClaim,
  PolicyDocument,
  PolicySnapshotRef,
  QuoteWorkflowStatus,
  Recommendation,
  RiskFlag,
  Scenario,
  TransactionContext,
  UnitSnapshot,
} from '@pricepolicy/api-client/contracts'
import { PAYMENT_PLANS_FIXTURE } from '../fixtures/plans'
import { computeScenarios } from './calculator'
import { buildQuoteClaims } from './claims'
import { detectConflicts, selectPolicyForDate } from './conflicts'
import { canonicalJsonStringify, sha256Hex } from './hash'
import { rankScenarios } from './recommend'
import { validateScenarios } from './sanity'

/** Ngưỡng tổng tỷ lệ ưu đãi cần Quản lý lưu ý (cờ vàng, PRD §5 Vùng 2). */
export const YELLOW_FLAG_RATE = 0.12

export interface AnalysisOutcome {
  status: Extract<QuoteWorkflowStatus, 'DRAFT' | 'NEEDS_INPUT' | 'ABSTAINED' | 'CALCULATION_FAILED'>
  /** Các node Agent đã chạy — quyết định chuỗi sự kiện SSE. */
  steps: AgentStep[]
  policy_snapshot_ref: PolicySnapshotRef | null
  conflict_report: ConflictReport | null
  abstention: Abstention | null
  missing_fields: string[]
  scenarios: Scenario[]
  calculation_validation: CalculationValidation | null
  recommendation: Recommendation | null
  risk_flag: RiskFlag
  claims: EvidenceBackedClaim[]
}

const fmtDate = (d: string) => d.split('-').reverse().join('/')

const empty = (partial: Partial<AnalysisOutcome> & Pick<AnalysisOutcome, 'status' | 'steps' | 'risk_flag'>): AnalysisOutcome => ({
  policy_snapshot_ref: null,
  conflict_report: null,
  abstention: null,
  missing_fields: [],
  scenarios: [],
  calculation_validation: null,
  recommendation: null,
  claims: [],
  ...partial,
})

export async function snapshotRefOf(policy: PolicyDocument): Promise<PolicySnapshotRef> {
  return {
    policy_id: policy.policy_id,
    policy_version: policy.policy_version,
    snapshot_hash: `sha256:${await sha256Hex(canonicalJsonStringify(policy))}`,
    title: policy.title,
    effective_from: policy.effective_from,
    effective_to: policy.effective_to,
  }
}

/**
 * Pipeline Official Quote rút gọn (N-01 → N-14B): input guard → time-travel policy → conflict gate
 * → tính 3 phương án → 6 sanity check → ranking → claim evidence. Mọi nhánh dừng đều không tính tiền.
 */
export async function analyzeQuote(params: { unit: UnitSnapshot; context: TransactionContext; policies: PolicyDocument[] }): Promise<AnalysisOutcome> {
  const { unit, context, policies } = params

  // N-01 — thiếu ngày giao dịch: không tự lấy ngày hôm nay (FC-01).
  if (!context.transaction_date) {
    return empty({
      status: 'NEEDS_INPUT',
      steps: [],
      missing_fields: ['transaction_date'],
      abstention: { reason_code: 'MISSING_TRANSACTION_DATE', message: 'Chưa có ngày giao dịch thực tế.' },
      risk_flag: { color: 'YELLOW', label: 'Thiếu dữ liệu', reasons: ['Thiếu ngày giao dịch.'] },
    })
  }
  const date = context.transaction_date

  // N-03/N-04 — Time-Travel Policy Lookup
  let policy: PolicyDocument | null
  if (context.requested_policy_id) {
    policy = policies.find((p) => p.policy_id === context.requested_policy_id && p.status === 'PUBLISHED') ?? null
    if (policy && (date < policy.effective_from || date > policy.effective_to)) {
      return empty({
        status: 'ABSTAINED',
        steps: ['POLICY_LOOKUP'],
        policy_snapshot_ref: await snapshotRefOf(policy),
        conflict_report: {
          findings: [
            {
              tier: null,
              status: 'EXPIRED',
              rule_codes: [],
              message: `${policy.title} (${policy.policy_version}) hiệu lực ${fmtDate(policy.effective_from)} – ${fmtDate(policy.effective_to)}; ngày giao dịch ${fmtDate(date)} nằm ngoài dải hiệu lực.`,
              source: null,
            },
          ],
        },
        abstention: { reason_code: 'POLICY_EXPIRED', message: 'Văn bản chính sách viện dẫn không có hiệu lực tại ngày giao dịch.' },
        risk_flag: { color: 'RED', label: 'Chính sách hết hiệu lực', reasons: ['Ngày giao dịch nằm ngoài hiệu lực văn bản chính sách.'] },
      })
    }
  } else {
    policy = selectPolicyForDate(policies, unit.project_id, date)
  }
  if (!policy) {
    return empty({
      status: 'ABSTAINED',
      steps: ['POLICY_LOOKUP'],
      conflict_report: {
        findings: [{ tier: null, status: 'EXPIRED', rule_codes: [], message: `Không có chính sách nào của ${unit.project_name} còn hiệu lực tại ngày ${fmtDate(date)}.`, source: null }],
      },
      abstention: { reason_code: 'POLICY_NOT_FOUND', message: 'Không tìm thấy chính sách có hiệu lực.' },
      risk_flag: { color: 'RED', label: 'Không có chính sách hiệu lực', reasons: ['Không tìm thấy chính sách có hiệu lực tại ngày giao dịch.'] },
    })
  }
  const policyRef = await snapshotRefOf(policy)
  const selectedCodes = context.selected_rule_codes.filter((c) => policy.rules.some((r) => r.rule_code === c))

  // N-06/N-07/N-08 — Conflict Gate & Safe Abstention
  const findings = detectConflicts(policy, selectedCodes)
  if (findings.length > 0) {
    const hasConflict = findings.some((f) => f.status === 'CONFLICT')
    return empty({
      status: 'ABSTAINED',
      steps: ['POLICY_LOOKUP', 'VECTOR_RETRIEVAL'],
      policy_snapshot_ref: policyRef,
      conflict_report: { findings },
      abstention: hasConflict
        ? { reason_code: 'POLICY_CONFLICT_UNRESOLVED', message: 'Tập ưu đãi đề nghị xét có xung đột chưa giải quyết.' }
        : { reason_code: 'POLICY_AMBIGUOUS', message: 'Điều khoản mơ hồ, không đủ căn cứ tự động áp dụng.' },
      risk_flag: hasConflict
        ? { color: 'RED', label: 'Xung đột chính sách', reasons: findings.map((f) => f.message) }
        : { color: 'YELLOW', label: 'Điều khoản cần thẩm định', reasons: findings.map((f) => f.message) },
    })
  }

  // N-09 → N-11 — Deterministic calculation + Financial Validation Gate
  const scenarios = await computeScenarios({
    unit,
    policy,
    plans: PAYMENT_PLANS_FIXTURE,
    selected_rule_codes: selectedCodes,
    customer_segment: context.customer_segment,
    units_quantity: context.units_quantity,
  })
  const validation = validateScenarios(unit, scenarios)
  const steps: AgentStep[] = ['POLICY_LOOKUP', 'VECTOR_RETRIEVAL', 'DETERMINISTIC_CALCULATION']
  if (!validation.valid) {
    return empty({
      status: 'CALCULATION_FAILED',
      steps,
      policy_snapshot_ref: policyRef,
      conflict_report: { findings: [] },
      scenarios,
      calculation_validation: validation,
      abstention: { reason_code: 'FINANCIAL_SANITY_FAILED', message: 'Kết quả tính không vượt qua cổng kiểm tra tài chính.' },
      risk_flag: { color: 'RED', label: 'Lỗi tính toán', reasons: [...new Set(validation.errors.map((e) => e.message))] },
    })
  }

  // N-12 → N-14B — ranking + evidence
  const recommendation = rankScenarios(scenarios, context.objective)
  const maxRate = Math.max(...scenarios.map((s) => s.total_discount_rate))
  return {
    status: 'DRAFT',
    steps,
    policy_snapshot_ref: policyRef,
    conflict_report: { findings: [] },
    abstention: null,
    missing_fields: [],
    scenarios,
    calculation_validation: validation,
    recommendation,
    risk_flag:
      maxRate >= YELLOW_FLAG_RATE
        ? { color: 'YELLOW', label: 'Ưu đãi chạm trần', reasons: [`Tổng tỷ lệ ưu đãi đạt ${(maxRate * 100).toFixed(1)}%, chạm ngưỡng thẩm quyền tiêu chuẩn 12%.`] }
        : { color: 'GREEN', label: 'Đúng chính sách', reasons: [] },
    claims: buildQuoteClaims(policy, context, scenarios, recommendation),
  }
}
