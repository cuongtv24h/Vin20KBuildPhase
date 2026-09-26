import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AnalysisProgressEvent, ApiClient } from '@/api/contracts'
import { ApiError } from '@/api/errors'
import { resetDb } from '@/api/mock/db'
import { MOCK_PASSWORD } from '@/api/mock/fixtures/users'
import { createMockClient } from '@/api/mock/mockClient'
import { SEED_SHARE_TOKEN } from '@/api/mock/seed'

let token: string | null = null
const api: ApiClient = createMockClient(() => token, { simulateLatency: false })

async function loginAs(email: string) {
  token = null
  token = (await api.auth.login({ email, password: MOCK_PASSWORD })).accessToken
}

async function expectApiError(promise: Promise<unknown>, status: number) {
  await expect(promise).rejects.toBeInstanceOf(ApiError)
  await promise.catch((e: ApiError) => expect(e.status).toBe(status))
}

beforeAll(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-09-25T09:00:00+07:00'))
})

afterAll(() => {
  vi.useRealTimers()
})

beforeEach(async () => {
  token = null
  await resetDb()
})

describe('Dữ liệu vận hành mẫu', () => {
  it('có hồ sơ ở đủ các trạng thái để mỗi vai trò có việc xử lý', async () => {
    await loginAs('ha.nguyen@vlandfuture.vn')
    const quotes = await api.quotes.list()
    const statuses = new Set(quotes.map((q) => q.status))
    for (const s of ['DRAFT', 'READY_FOR_REVIEW', 'ABSTAINED', 'APPROVED', 'REJECTED', 'NEEDS_REVISION'] as const) {
      expect(statuses.has(s), s).toBe(true)
    }
    expect(quotes.some((q) => q.status === 'READY_FOR_REVIEW' && q.riskFlag.color === 'YELLOW')).toBe(true)
  })

  it('báo giá mẫu đã gửi khách mở được bằng token cố định và khớp mã băm', async () => {
    const view = await api.public.getSharedQuote(SEED_SHARE_TOKEN)
    expect(view.customerName).toBe('Phạm Quốc Huy')
    const verification = await api.public.verifySharedQuote(SEED_SHARE_TOKEN)
    expect(verification.valid).toBe(true)
  })

  it('Sale chỉ thấy hồ sơ của chính mình', async () => {
    await loginAs('nam.hoang@vlandfuture.vn')
    const quotes = await api.quotes.list()
    expect(quotes.length).toBeGreaterThan(0)
    expect(quotes.every((q) => q.ownerId === 'USR-SALE-001')).toBe(true)
  })
})

describe('Luồng đầy đủ: Khách → Sale → Quản lý → Khách', () => {
  it('đi hết vòng đời báo giá và cập nhật trạng thái cho mọi vai trò', async () => {
    // Khách hàng (pre-sale) gửi yêu cầu từ trang căn hộ
    const estimate = await api.public.estimate({ unitCode: 'ZEN-A-1205', customerSegment: 'EXISTING_RESIDENT' })
    expect(estimate.policy?.version).toBe('v3.1')
    expect(estimate.plans.find((p) => p.plan === 'EARLY_PAYMENT_95')?.netPrice).toBe(4_233_600_000)

    const receipt = await api.public.submitLead({
      fullName: 'Trịnh Minh Khoa',
      phone: '0901 234 567',
      email: 'khoa@example.com',
      unitCode: 'ZEN-A-1205',
      customerSegment: 'EXISTING_RESIDENT',
      objective: 'MIN_NET_PRICE',
      note: '',
    })

    // Sale tiếp nhận yêu cầu
    await loginAs('nam.hoang@vlandfuture.vn')
    const pool = await api.leads.list({ scope: 'UNASSIGNED' })
    expect(pool.map((l) => l.leadId)).toContain(receipt.leadId)
    await api.leads.claim(receipt.leadId)

    const input = {
      leadId: receipt.leadId,
      unitCode: 'ZEN-A-1205',
      transactionDate: '2026-09-25',
      customerSegment: 'EXISTING_RESIDENT' as const,
      unitsQuantity: 1,
      selectedRuleCodes: ['EARLY_PAY_DISCOUNT', 'FURNITURE_GIFT'],
      objective: 'MIN_NET_PRICE' as const,
      customerName: 'Trịnh Minh Khoa',
      customerPhone: '0901 234 567',
    }

    // Kiểm tra xung đột tức thời trước khi phân tích
    const preflight = await api.quotes.preflight(input)
    expect(preflight.findings.map((f) => f.tier)).toContain(1)

    // Phân tích với tập ưu đãi xung đột → dừng an toàn, tự vào hàng đợi ngoại lệ
    const abstained = await api.quotes.create(input)
    expect(abstained.status).toBe('ABSTAINED')
    expect(abstained.history.map((e) => e.type)).toEqual(['CREATED', 'ESCALATED'])

    // Sale điều chỉnh → phiên bản 2 hợp lệ
    const progress: AnalysisProgressEvent[] = []
    const draft = await api.quotes.revise(
      abstained.quoteId,
      { ...input, selectedRuleCodes: ['EARLY_PAY_DISCOUNT', 'SMARTHOME_GIFT'] },
      { onProgress: (e) => progress.push(e) },
    )
    expect(draft.version).toBe(2)
    expect(draft.status).toBe('DRAFT')
    expect(draft.recommendation?.recommendedPlan).toBe('EARLY_PAYMENT_95')
    expect(progress.filter((e) => e.state === 'DONE').map((e) => e.stage)).toEqual(['POLICY_LOOKUP', 'PREFLIGHT', 'PRICING', 'RANKING'])

    await expectApiError(api.quotes.decide(draft.quoteId, { decision: 'APPROVED', notes: '' }), 403)
    const submitted = await api.quotes.submit(draft.quoteId)
    expect(submitted.status).toBe('READY_FOR_REVIEW')
    await expectApiError(api.quotes.submit(draft.quoteId), 409)

    // Quản lý duyệt
    await loginAs('ha.nguyen@vlandfuture.vn')
    await expectApiError(api.quotes.decide(draft.quoteId, { decision: 'REJECTED', notes: '  ' }), 422)
    const approved = await api.quotes.decide(draft.quoteId, { decision: 'APPROVED', notes: '' })
    expect(approved.status).toBe('APPROVED')
    expect(approved.snapshotHash).toMatch(/^[0-9a-f]{64}$/)
    expect((await api.quotes.verify(draft.quoteId)).valid).toBe(true)

    // Sale gửi khách
    await loginAs('nam.hoang@vlandfuture.vn')
    const shared = await api.quotes.share(draft.quoteId, { channel: 'ZALO' })
    const shareToken = shared.distribution?.shareToken ?? ''
    expect(shareToken).not.toBe('')
    expect((await api.leads.get(receipt.leadId)).status).toBe('QUOTE_SENT')

    // Khách mở báo giá & đồng ý
    const view = await api.public.getSharedQuote(shareToken)
    const early = view.scenarios.find((s) => s.plan === 'EARLY_PAYMENT_95')
    expect(early?.netPrice).toBe(4_233_600_000)
    expect(early?.schedule.reduce((sum, r) => sum + r.amountVnd, 0)).toBe(early?.netPrice)
    expect(view).not.toHaveProperty('riskFlag')

    await api.public.respondToQuote(shareToken, { decision: 'ACCEPTED', note: 'Hẹn cuối tuần', preferredAppointment: null })
    const finalQuote = await api.quotes.get(draft.quoteId)
    expect(finalQuote.distribution?.viewedAt).not.toBeNull()
    expect(finalQuote.history.map((e) => e.type)).toContain('CUSTOMER_RESPONDED')
    expect((await api.leads.get(receipt.leadId)).status).toBe('CUSTOMER_ACCEPTED')
  })
})

describe('Admin Sale — ban hành chính sách', () => {
  it('ban hành bản nháp hợp lệ và Time-Travel chọn đúng phiên bản mới', async () => {
    await loginAs('minh.tuan@vlandfuture.vn')
    expect(await api.catalog.getActivePolicy('THE_ZEN_PARK', '2026-11-15')).toBeNull()

    const report = await api.policies.runPublishChecks('CSBH-ZEN-2026-V4.0')
    expect(report.canPublish).toBe(true)
    await api.policies.publish('CSBH-ZEN-2026-V4.0')

    expect((await api.catalog.getActivePolicy('THE_ZEN_PARK', '2026-11-15'))?.version).toBe('v4.0')
    expect((await api.catalog.getActivePolicy('THE_ZEN_PARK', '2026-09-25'))?.version).toBe('v3.1')
  })

  it('chặn ban hành bản nháp chưa có văn bản gốc', async () => {
    await loginAs('minh.tuan@vlandfuture.vn')
    const draft = await api.policies.createDraft({ fromPolicyId: 'CSBH-SAP-2026-V1.0' })
    const report = await api.policies.runPublishChecks(draft.policyId)
    expect(report.checks.find((c) => c.code === 'SOURCE_DOCUMENT')?.status).toBe('FAIL')
    await expectApiError(api.policies.publish(draft.policyId), 422)
  })

  it('chỉ Admin Sale được sửa bảng hàng', async () => {
    await loginAs('nam.hoang@vlandfuture.vn')
    await expectApiError(api.inventory.updateUnit('ZEN-A-0803', { status: 'RESERVED' }), 403)
    await loginAs('minh.tuan@vlandfuture.vn')
    expect((await api.inventory.updateUnit('ZEN-A-0803', { status: 'RESERVED' })).status).toBe('RESERVED')
  })
})
