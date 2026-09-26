import { describe, expect, it } from 'vitest'
import { PAYMENT_PLANS_FIXTURE } from '@/api/mock/fixtures/plans'
import { buildPaymentSchedule } from '@/engine/schedule'
import { canPerform } from '@/engine/workflow'

describe('canPerform', () => {
  it('chỉ Sale được gửi duyệt bản nháp', () => {
    expect(canPerform('SUBMIT', 'DRAFT', 'SALE')).toBe(true)
    expect(canPerform('SUBMIT', 'DRAFT', 'MANAGER')).toBe(false)
    expect(canPerform('SUBMIT', 'READY_FOR_REVIEW', 'SALE')).toBe(false)
  })

  it('không cho phê duyệt hồ sơ dừng an toàn, chỉ trả lại hoặc từ chối', () => {
    expect(canPerform('APPROVE', 'ABSTAINED', 'MANAGER')).toBe(false)
    expect(canPerform('REQUEST_REVISION', 'ABSTAINED', 'MANAGER')).toBe(true)
    expect(canPerform('REJECT', 'ABSTAINED', 'MANAGER')).toBe(true)
  })

  it('Admin Sale không tham gia duyệt giá', () => {
    for (const action of ['APPROVE', 'REJECT', 'REQUEST_REVISION', 'SUBMIT', 'SHARE'] as const) {
      expect(canPerform(action, 'READY_FOR_REVIEW', 'SALE_ADMIN')).toBe(false)
    }
  })
})

describe('buildPaymentSchedule', () => {
  it('tổng các đợt luôn đúng bằng Net Price kể cả khi số lẻ', () => {
    for (const plan of PAYMENT_PLANS_FIXTURE) {
      const schedule = buildPaymentSchedule(3_416_000_003, plan)
      expect(schedule).toHaveLength(plan.installmentsCount)
      expect(schedule.reduce((s, r) => s + r.amountVnd, 0)).toBe(3_416_000_003)
    }
  })

  it('tỷ lệ các đợt của mỗi phương án cộng đủ 100%', () => {
    for (const plan of PAYMENT_PLANS_FIXTURE) {
      expect(Math.round(plan.schedule.reduce((s, m) => s + m.ratio, 0) * 1000)).toBe(1000)
    }
  })
})
