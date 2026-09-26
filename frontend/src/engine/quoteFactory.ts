import { computeScenarios } from '@/engine/calculator'
import { runPreflight } from '@/engine/conflictDetector'
import { recommendScenario } from '@/engine/recommend'
import { canonicalJsonStringify, sha256Hex } from '@/lib/hash'
import type {
  ApartmentUnit,
  ApprovalRecord,
  CalculationResult,
  PaymentPlanConfig,
  PolicySnapshot,
  PolicyVersion,
  PreflightResult,
  Quote,
  RecommendationRecord,
  RiskFlag,
  TransactionContext,
  WorkflowStatus,
} from '@/types/domain'

/** Ngưỡng tổng tỷ lệ ưu đãi cần Quản lý lưu ý (cờ vàng). */
export const RISK_FLAG_THRESHOLD_RATE = 0.12

export function computeRiskFlag(status: WorkflowStatus, scenarios: CalculationResult[]): RiskFlag {
  if (status === 'ABSTAINED') {
    return {
      color: 'RED',
      label: 'Ngoại lệ — Dừng an toàn',
      reasons: ['Phát hiện xung đột, điều khoản mơ hồ hoặc chính sách hết hiệu lực — cần Quản lý thẩm định trực tiếp.'],
    }
  }
  if (status === 'CALCULATION_FAILED') {
    return {
      color: 'RED',
      label: 'Lỗi tính toán',
      reasons: ['Kết quả tính toán không vượt qua bước kiểm tra an toàn tài chính.'],
    }
  }
  const maxRate = scenarios.reduce((m, s) => Math.max(m, s.totalDiscountRate), 0)
  if (maxRate >= RISK_FLAG_THRESHOLD_RATE) {
    return {
      color: 'YELLOW',
      label: 'Ưu đãi chạm trần',
      reasons: [`Tổng tỷ lệ ưu đãi đạt ${(maxRate * 100).toFixed(1)}%, chạm ngưỡng thẩm quyền tiêu chuẩn (12%).`],
    }
  }
  return { color: 'GREEN', label: 'Bình thường', reasons: [] }
}

export interface QuoteAnalysis {
  status: Extract<WorkflowStatus, 'DRAFT' | 'ABSTAINED' | 'CALCULATION_FAILED'>
  preflight: PreflightResult
  scenarios: CalculationResult[]
  recommendation: RecommendationRecord | null
  riskFlag: RiskFlag
}

/** Pipeline phân tích: Preflight → (nếu sạch) tính 3 phương án → xếp hạng đề xuất. */
export function analyzeQuote(params: {
  unit: ApartmentUnit
  context: TransactionContext
  activePolicy: PolicyVersion | null
  plans: PaymentPlanConfig[]
}): QuoteAnalysis {
  const { unit, context, activePolicy, plans } = params

  const preflight = runPreflight({
    projectName: unit.projectName,
    transactionDate: context.transactionDate,
    activePolicy,
    selectedRuleCodes: context.selectedRuleCodes,
  })

  if (preflight.hasBlockingIssue || !activePolicy) {
    return { status: 'ABSTAINED', preflight, scenarios: [], recommendation: null, riskFlag: computeRiskFlag('ABSTAINED', []) }
  }

  const scenarios = computeScenarios({
    unit,
    policy: activePolicy,
    plans,
    selectedRuleCodes: context.selectedRuleCodes,
    customerSegment: context.customerSegment,
    unitsQuantity: context.unitsQuantity,
  })

  if (scenarios.some((s) => !s.validation.valid)) {
    return {
      status: 'CALCULATION_FAILED',
      preflight,
      scenarios,
      recommendation: null,
      riskFlag: computeRiskFlag('CALCULATION_FAILED', scenarios),
    }
  }

  return {
    status: 'DRAFT',
    preflight,
    scenarios,
    recommendation: recommendScenario(scenarios, context.objective),
    riskFlag: computeRiskFlag('DRAFT', scenarios),
  }
}

export function buildSnapshot(quote: Quote, approval: Omit<ApprovalRecord, 'signatureHex'>, at: string): PolicySnapshot {
  return {
    quoteId: quote.quoteId,
    version: quote.version,
    snapshotTimestamp: at,
    unit: quote.unit,
    context: quote.context,
    policyVersion: quote.preflight?.activePolicy ?? null,
    scenarios: quote.scenarios,
    recommendation: quote.recommendation,
    approval,
  }
}

/** SHA-256 (Web Crypto) trên JSON Snapshot đã chuẩn hoá — key sắp xếp đệ quy. */
export async function hashSnapshot(snapshot: PolicySnapshot): Promise<string> {
  return sha256Hex(canonicalJsonStringify(snapshot))
}
