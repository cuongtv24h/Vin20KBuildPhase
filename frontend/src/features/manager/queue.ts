import type { Quote, RiskFlagColor } from '@/types/domain'

const RISK_ORDER: Record<RiskFlagColor, number> = { RED: 0, YELLOW: 1, GREEN: 2 }

/** Thời điểm hồ sơ vào hàng đợi của phiên bản hiện tại (gửi duyệt hoặc tự động chuyển ngoại lệ). */
export function enteredQueueAt(q: Quote): string {
  const e = [...q.history].reverse().find((ev) => ev.version === q.version && (ev.type === 'SUBMITTED' || ev.type === 'ESCALATED'))
  return e?.at ?? q.updatedAt
}

/** Ưu tiên rủi ro cao trước, cùng mức thì hồ sơ chờ lâu hơn trước. */
export function sortQueue(quotes: Quote[]): Quote[] {
  return [...quotes].sort(
    (a, b) => RISK_ORDER[a.riskFlag.color] - RISK_ORDER[b.riskFlag.color] || enteredQueueAt(a).localeCompare(enteredQueueAt(b)),
  )
}

/** Thời gian trung bình (phút) từ lúc vào hàng đợi đến lúc Quản lý ra quyết định. */
export function averageDecisionMinutes(quotes: Quote[]): number | null {
  const durations: number[] = []
  for (const q of quotes) {
    let enteredAt: string | null = null
    for (const e of q.history) {
      if (e.type === 'SUBMITTED' || e.type === 'ESCALATED') enteredAt = e.at
      if ((e.type === 'APPROVED' || e.type === 'REJECTED' || e.type === 'REVISION_REQUESTED') && enteredAt) {
        durations.push((new Date(e.at).getTime() - new Date(enteredAt).getTime()) / 60_000)
        enteredAt = null
      }
    }
  }
  if (durations.length === 0) return null
  return Math.round(durations.reduce((s, d) => s + d, 0) / durations.length)
}
