import type { OptimizationObjective, Quote, QuoteWorkflowStatus, Recommendation, UserRole } from '@/api/contracts'
import { formatVnd } from './format'
import { OBJECTIVE_LABEL } from './labels'

/**
 * Luật hiển thị hành động trên UI. Backend vẫn là nơi quyết định (trả 409/403) — bảng này chỉ để
 * không hiện nút mà server chắc chắn từ chối.
 */
export const MANAGER_QUEUE: QuoteWorkflowStatus[] = ['READY_FOR_REVIEW', 'ABSTAINED']
export const REVISABLE: QuoteWorkflowStatus[] = ['DRAFT', 'NEEDS_INPUT', 'NEEDS_REVISION', 'ABSTAINED', 'CALCULATION_FAILED']

export const isLatest = (q: Quote) => q.versions.length === 0 || q.quote_version === Math.max(...q.versions.map((v) => v.quote_version))

export function saleActions(q: Quote, role: UserRole) {
  const own = role === 'SALE' && isLatest(q)
  return {
    submit: own && q.status === 'DRAFT',
    revise: own && REVISABLE.includes(q.status),
    compose: own && q.status === 'APPROVED',
  }
}

export function managerActions(q: Quote, role: UserRole, userId: string) {
  const manager = role === 'MANAGER' && isLatest(q)
  const sodViolation = q.created_by.user_id === userId
  return {
    sodViolation,
    approve: manager && !sodViolation && q.status === 'READY_FOR_REVIEW',
    reject: manager && !sodViolation && MANAGER_QUEUE.includes(q.status),
    revise: manager && !sodViolation && MANAGER_QUEUE.includes(q.status),
  }
}

export type StopKind = 'CONFLICT' | 'AMBIGUOUS' | 'EXPIRED' | 'NOT_FOUND' | 'NEEDS_INPUT' | 'CALCULATION_FAILED'

/** Loại dừng an toàn để hiển thị đúng màu & nội dung (brief §3f). */
export function stopKindOf(q: Pick<Quote, 'status' | 'abstention'>): StopKind | null {
  if (q.status === 'NEEDS_INPUT') return 'NEEDS_INPUT'
  if (q.status === 'CALCULATION_FAILED') return 'CALCULATION_FAILED'
  if (q.status !== 'ABSTAINED') return null
  switch (q.abstention?.reason_code) {
    case 'POLICY_AMBIGUOUS':
      return 'AMBIGUOUS'
    case 'POLICY_EXPIRED':
      return 'EXPIRED'
    case 'POLICY_NOT_FOUND':
      return 'NOT_FOUND'
    default:
      return 'CONFLICT'
  }
}

const METRIC_PHRASE: Record<OptimizationObjective, string> = {
  MIN_NET_PRICE: 'giảm giá bán sau ưu đãi',
  MIN_INITIAL_OUTFLOW: 'giảm tiền thanh toán đợt đầu',
  MIN_TOTAL_CASH_OUTFLOW: 'giảm tổng dòng tiền đến bàn giao',
  MAX_BENEFIT_VALUE: 'tăng giá trị ưu đãi quy đổi',
}

/**
 * "Theo tiêu chí X, phương án Y giảm … so với …" — dựng từ số liệu ranking tất định, không dùng
 * nhận định chủ quan kiểu "phương án tốt nhất" (PRD §1.3.2).
 */
export function recommendationSentence(rec: Recommendation, labelOf: (code: string) => string): string {
  const others = rec.comparisons.filter((c) => c.scenario_code !== rec.recommended_scenario && c.delta_vnd > 0)
  const winner = labelOf(rec.recommended_scenario)
  if (others.length === 0) {
    return `Theo tiêu chí ${OBJECTIVE_LABEL[rec.objective]}, các phương án ngang nhau; ${winner} được chọn theo quy tắc ${rec.tie_break_rule_id}.`
  }
  const parts = others.map((c) => `${formatVnd(c.delta_vnd)} so với ${labelOf(c.scenario_code)}`)
  return `Theo tiêu chí ${OBJECTIVE_LABEL[rec.objective]}, phương án ${winner} ${METRIC_PHRASE[rec.objective]} ${parts.join(' và ')}.`
}
