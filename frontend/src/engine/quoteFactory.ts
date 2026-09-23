import { calculateNetPrice, computeScenarios, validatePricingResult } from '@/engine/calculator'
import { runPreflight } from '@/engine/conflictDetector'
import { recommendScenario } from '@/engine/recommend'
import { canonicalJsonStringify, sha256Hex } from '@/lib/hash'
import type {
  ApartmentUnit,
  ApprovalRecord,
  CalculationResult,
  PolicySnapshot,
  Quote,
  RiskFlag,
  TransactionContext,
  WorkflowStatus,
} from '@/types/domain'

let quoteSeq = 0

export function resetQuoteSequence() {
  quoteSeq = 0
}

export function nextQuoteId(date: Date = new Date()): string {
  quoteSeq += 1
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  return `QUO-${yyyy}-${mm}-${String(quoteSeq).padStart(5, '0')}`
}

const RISK_FLAG_THRESHOLD_RATE = 0.12

export function computeRiskFlag(status: WorkflowStatus, scenarios: CalculationResult[]): RiskFlag {
  if (status === 'ABSTAINED') {
    return {
      color: 'RED',
      label: 'Ngoại lệ — Dừng an toàn',
      reasons: ['Hệ thống phát hiện xung đột / mơ hồ / hết hiệu lực chính sách, cần Quản lý thẩm định trực tiếp.'],
    }
  }
  if (status === 'CALCULATION_FAILED') {
    return {
      color: 'RED',
      label: 'Lỗi tính toán',
      reasons: ['Kết quả tính toán không vượt qua Deterministic Financial Validation Gate.'],
    }
  }
  const maxRate = scenarios.reduce((m, s) => Math.max(m, s.totalDiscountRate), 0)
  if (maxRate >= RISK_FLAG_THRESHOLD_RATE) {
    return {
      color: 'YELLOW',
      label: 'Ưu đãi chạm trần',
      reasons: [
        `Tổng tỷ lệ ưu đãi đạt ${(maxRate * 100).toFixed(1)}%, chạm ngưỡng thẩm quyền phê duyệt tiêu chuẩn (12%).`,
      ],
    }
  }
  return { color: 'GREEN', label: 'Bình thường', reasons: [] }
}

/** Quy trình phân tích đầy đủ: Preflight → (nếu sạch) Compute 3 Scenarios → Recommend. */
export function buildQuoteFromContext(params: { unit: ApartmentUnit; context: TransactionContext }): Quote {
  const { unit, context } = params
  const now = new Date().toISOString()

  const preflight = runPreflight({
    unit,
    transactionDate: context.transactionDate,
    customerSegment: context.customerSegment,
    unitsQuantity: context.unitsQuantity,
    selectedRuleCodes: context.selectedRuleCodes,
  })

  if (preflight.hasBlockingIssue || !preflight.activePolicy) {
    return {
      quoteId: nextQuoteId(),
      version: 1,
      status: 'ABSTAINED',
      createdAt: now,
      updatedAt: now,
      context,
      unit,
      preflight,
      scenarios: [],
      recommendation: null,
      riskFlag: computeRiskFlag('ABSTAINED', []),
      approval: null,
      snapshotHash: null,
    }
  }

  const scenarios = computeScenarios({
    unit,
    policy: preflight.activePolicy,
    selectedRuleCodes: context.selectedRuleCodes,
    customerSegment: context.customerSegment,
    unitsQuantity: context.unitsQuantity,
  })

  const hasInvalidScenario = scenarios.some((s) => !s.validation.valid)
  if (hasInvalidScenario) {
    return {
      quoteId: nextQuoteId(),
      version: 1,
      status: 'CALCULATION_FAILED',
      createdAt: now,
      updatedAt: now,
      context,
      unit,
      preflight,
      scenarios,
      recommendation: null,
      riskFlag: computeRiskFlag('CALCULATION_FAILED', scenarios),
      approval: null,
      snapshotHash: null,
    }
  }

  const recommendation = recommendScenario(scenarios, context.objective)

  return {
    quoteId: nextQuoteId(),
    version: 1,
    status: 'DRAFT',
    createdAt: now,
    updatedAt: now,
    context,
    unit,
    preflight,
    scenarios,
    recommendation,
    riskFlag: computeRiskFlag('DRAFT', scenarios),
    approval: null,
    snapshotHash: null,
  }
}

/**
 * Kịch bản diễn tập FAIL-04 (Validation Failure): giả lập một cấu hình ưu đãi bị lỗi
 * (cộng dồn vượt 100%) để chứng minh Financial Validation Gate chặn đứng kết quả
 * trước khi nó có thể hiển thị cho khách hàng — KHÔNG bỏ qua validator thật.
 */
export function buildForcedCalculationFailureQuote(unit: ApartmentUnit, context: TransactionContext): Quote {
  const now = new Date().toISOString()
  const corrupted = calculateNetPrice({ basePrice: unit.listedPrice, eligibleDiscountRates: [0.6, 0.6] })
  const validation = validatePricingResult(corrupted)

  const scenario: CalculationResult = {
    plan: 'STANDARD_PROGRESS',
    planLabel: 'Tiến độ chuẩn (dữ liệu lỗi — mô phỏng)',
    basePrice: corrupted.basePrice,
    totalDiscountRate: corrupted.totalDiscountRate,
    discountAmount: corrupted.discountAmount,
    priceBeforeVAT: corrupted.priceBeforeVAT,
    vatAmount: corrupted.vatAmount,
    kpbtAmount: corrupted.kpbtAmount,
    netPrice: corrupted.netPrice,
    initialPaymentVnd: 0,
    totalCashOutflowToHandoverVnd: 0,
    benefitValueVnd: 0,
    installmentsCount: 0,
    ruleBreakdown: [
      {
        ruleCode: 'DEMO_BUG_DUPLICATE_DISCOUNT',
        title: '[MÔ PHỎNG LỖI] Cấu hình ưu đãi trùng lặp 60% + 60%',
        status: 'CONFLICT',
        amountVnd: corrupted.discountAmount,
        reasonText:
          'Dữ liệu ưu đãi bị cấu hình sai (ví dụ nhập trùng cùng một chương trình hai lần) khiến tổng tỷ lệ chiết khấu vượt 100% giá niêm yết.',
        source: {
          documentId: 'DEMO',
          policyVersion: 'demo',
          clauseId: 'N/A',
          clauseTitle: 'Kịch bản diễn tập',
          page: 0,
          sourceDocument: 'N/A',
          sourceFileHash: 'N/A',
        },
      },
    ],
    validation,
  }

  return {
    quoteId: nextQuoteId(),
    version: 1,
    status: 'CALCULATION_FAILED',
    createdAt: now,
    updatedAt: now,
    context,
    unit,
    preflight: null,
    scenarios: [scenario],
    recommendation: null,
    riskFlag: computeRiskFlag('CALCULATION_FAILED', [scenario]),
    approval: null,
    snapshotHash: null,
    demoScenarioTag: 'FAIL-04',
  }
}

export function buildSnapshot(quote: Quote): PolicySnapshot {
  return {
    quoteId: quote.quoteId,
    snapshotTimestamp: new Date().toISOString(),
    snapshotHash: '', // gán sau khi băm
    unit: quote.unit,
    context: quote.context,
    policyVersion: quote.preflight?.activePolicy
      ? {
          policyId: quote.preflight.activePolicy.policyId,
          version: quote.preflight.activePolicy.version,
          effectiveFrom: quote.preflight.activePolicy.effectiveFrom,
          effectiveTo: quote.preflight.activePolicy.effectiveTo,
          sourceFileHash: quote.preflight.activePolicy.sourceFileHash,
        }
      : { policyId: 'N/A', version: 'N/A', effectiveFrom: 'N/A', effectiveTo: 'N/A', sourceFileHash: 'N/A' },
    scenarios: quote.scenarios,
    recommendation: quote.recommendation,
    approval: quote.approval,
  }
}

/** Tính SHA-256 THẬT (Web Crypto) trên nội dung JSON Snapshot đã chuẩn hoá (key sắp xếp đệ quy). */
export async function hashSnapshot(snapshot: PolicySnapshot): Promise<string> {
  const canonical = canonicalJsonStringify(snapshot)
  return sha256Hex(canonical)
}

export function buildApprovalRecord(params: {
  approverName: string
  decision: ApprovalRecord['decision']
  notes: string
  signatureHex?: string
}): ApprovalRecord {
  return {
    approverId: `MGR-${params.approverName.toUpperCase().replace(/\s+/g, '-')}`,
    approverName: params.approverName,
    decision: params.decision,
    notes: params.notes,
    timestamp: new Date().toISOString(),
    signatureHex: params.signatureHex,
  }
}
