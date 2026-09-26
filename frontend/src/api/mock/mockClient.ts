import type {
  AnalysisOptions,
  AnalysisProgressEvent,
  ApiClient,
  ProjectOverview,
  UpdatePolicyDraftRequest,
} from '@/api/contracts'
import { ApiError } from '@/api/errors'
import { commit, getDb, registerSeeder, type MockDbState } from '@/api/mock/db'
import { PAYMENT_PLANS_FIXTURE } from '@/api/mock/fixtures/plans'
import { PROJECTS_FIXTURE } from '@/api/mock/fixtures/units'
import { MOCK_PASSWORD, STAFF_FIXTURE } from '@/api/mock/fixtures/users'
import { buildSeedState } from '@/api/mock/seed'
import {
  activePolicyFor,
  claimLeadRecord,
  createLeadRecord,
  createQuoteRecord,
  decideQuoteRecord,
  findLead,
  findPolicy,
  findQuote,
  findQuoteByToken,
  findUnit,
  markSharedQuoteViewed,
  respondSharedQuote,
  reviseQuoteRecord,
  shareQuoteRecord,
  submitQuoteRecord,
  toCustomerView,
  verifyQuoteIntegrity,
} from '@/api/mock/services'
import { runBenchmarkSuite } from '@/engine/benchmark'
import { runPreflight, toPolicyRef } from '@/engine/conflictDetector'
import { estimatePlans, listPublicPromotions } from '@/engine/estimate'
import { runPublishChecks } from '@/engine/policyChecks'
import { todayIso } from '@/lib/format'
import type { PolicyVersion, Quote, StaffUser, UserRole } from '@/types/domain'

registerSeeder(buildSeedState)

const now = () => new Date().toISOString()
const clone = <T>(value: T): T => structuredClone(value)

function randomToken(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(24)), (b) => b.toString(16).padStart(2, '0')).join('')
}

export interface MockClientOptions {
  /** Giả lập độ trễ mạng và thời gian xử lý của agent (tắt trong unit test). */
  simulateLatency?: boolean
}

export function createMockClient(getAccessToken: () => string | null, options: MockClientOptions = {}): ApiClient {
  const simulate = options.simulateLatency ?? true
  const sleep = (ms: number) => (simulate ? new Promise((r) => setTimeout(r, ms)) : Promise.resolve())
  const latency = () => sleep(180 + Math.round(Math.random() * 220))

  async function db(): Promise<MockDbState> {
    await latency()
    return getDb()
  }

  function currentUser(state: MockDbState, roles?: UserRole[]): StaffUser {
    const token = getAccessToken()
    const userId = token ? state.sessions[token] : undefined
    const user = STAFF_FIXTURE.find((u) => u.userId === userId)
    if (!user) throw new ApiError(401, 'UNAUTHORIZED', 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
    if (roles && !roles.includes(user.role)) throw new ApiError(403, 'FORBIDDEN', 'Tài khoản không có quyền thực hiện thao tác này.')
    return user
  }

  function visibleQuote(state: MockDbState, user: StaffUser, quoteId: string): Quote {
    const quote = findQuote(state, quoteId)
    if (user.role === 'SALE' && quote.ownerId !== user.userId) {
      throw new ApiError(403, 'FORBIDDEN', 'Bạn không phụ trách hồ sơ này.')
    }
    return quote
  }

  async function replayProgress(quote: Quote, options?: AnalysisOptions) {
    const emit = (e: AnalysisProgressEvent) => options?.onProgress?.(e)
    const policy = quote.preflight?.activePolicy
    const blockedByPolicy = quote.preflight?.expired ?? false
    const findings = quote.preflight?.findings.length ?? 0

    emit({ stage: 'POLICY_LOOKUP', state: 'RUNNING' })
    await sleep(450)
    if (blockedByPolicy || !policy) {
      emit({ stage: 'POLICY_LOOKUP', state: 'BLOCKED', message: 'Không có chính sách hiệu lực tại ngày giao dịch' })
      for (const stage of ['PREFLIGHT', 'PRICING', 'RANKING'] as const) emit({ stage, state: 'SKIPPED' })
      return
    }
    emit({ stage: 'POLICY_LOOKUP', state: 'DONE', message: `${policy.policyId} · ${policy.version}` })

    emit({ stage: 'PREFLIGHT', state: 'RUNNING' })
    await sleep(550)
    if (quote.status === 'ABSTAINED') {
      emit({ stage: 'PREFLIGHT', state: 'BLOCKED', message: `Phát hiện ${findings} vấn đề cần thẩm định` })
      for (const stage of ['PRICING', 'RANKING'] as const) emit({ stage, state: 'SKIPPED' })
      return
    }
    emit({ stage: 'PREFLIGHT', state: 'DONE', message: 'Không phát hiện xung đột' })

    emit({ stage: 'PRICING', state: 'RUNNING' })
    await sleep(600)
    if (quote.status === 'CALCULATION_FAILED') {
      emit({ stage: 'PRICING', state: 'BLOCKED', message: 'Kết quả không đạt kiểm tra an toàn tài chính' })
      emit({ stage: 'RANKING', state: 'SKIPPED' })
      return
    }
    emit({ stage: 'PRICING', state: 'DONE', message: `${quote.scenarios.length} phương án` })

    emit({ stage: 'RANKING', state: 'RUNNING' })
    await sleep(350)
    emit({ stage: 'RANKING', state: 'DONE', message: quote.scenarios.find((s) => s.plan === quote.recommendation?.recommendedPlan)?.planLabel })
  }

  function applyPolicyPatch(policy: PolicyVersion, patch: UpdatePolicyDraftRequest) {
    if (patch.title !== undefined) policy.title = patch.title
    if (patch.effectiveFrom !== undefined) policy.effectiveFrom = patch.effectiveFrom
    if (patch.effectiveTo !== undefined) policy.effectiveTo = patch.effectiveTo
    if (patch.sourceDocument !== undefined) policy.sourceDocument = patch.sourceDocument
    if (patch.sourceFileHash !== undefined) policy.sourceFileHash = patch.sourceFileHash
    if (patch.version !== undefined) policy.version = patch.version
    for (const rulePatch of patch.rules ?? []) {
      const target = policy.rules.find((r) => r.ruleCode === rulePatch.ruleCode)
      if (!target) throw new ApiError(422, 'VALIDATION_ERROR', `Không có điều khoản ${rulePatch.ruleCode}.`)
      if (rulePatch.discountRate !== undefined) target.discountRate = rulePatch.discountRate
      if (rulePatch.cashEquivalentVnd !== undefined) target.cashEquivalentVnd = rulePatch.cashEquivalentVnd
      if (rulePatch.interestSupportMonths !== undefined) target.interestSupportMonths = rulePatch.interestSupportMonths
      if (rulePatch.evidenceText !== undefined) target.evidenceText = rulePatch.evidenceText
    }
    for (const r of policy.rules) {
      r.policyVersion = policy.version
      r.source = { ...r.source, policyVersion: policy.version, sourceDocument: policy.sourceDocument, sourceFileHash: policy.sourceFileHash }
    }
  }

  return {
    auth: {
      async login({ email, password }) {
        const state = await db()
        const user = STAFF_FIXTURE.find((u) => u.email.toLowerCase() === email.trim().toLowerCase())
        if (!user || password !== MOCK_PASSWORD) {
          throw new ApiError(401, 'INVALID_CREDENTIALS', 'Email hoặc mật khẩu không đúng.')
        }
        const accessToken = randomToken()
        state.sessions[accessToken] = user.userId
        commit()
        return { accessToken, expiresAt: new Date(Date.now() + 8 * 3_600_000).toISOString(), user: clone(user) }
      },
      async logout() {
        const state = await db()
        const token = getAccessToken()
        if (token) delete state.sessions[token]
        commit()
      },
    },

    catalog: {
      async listProjects() {
        await latency()
        return clone(PROJECTS_FIXTURE)
      },
      async listUnits(filter) {
        const state = await db()
        return clone(
          state.units.filter(
            (u) =>
              (!filter?.projectId || u.projectId === filter.projectId) &&
              (!filter?.status || u.status === filter.status) &&
              (!filter?.bedrooms || u.bedrooms === filter.bedrooms),
          ),
        )
      },
      async getUnit(unitCode) {
        const state = await db()
        return clone(findUnit(state, unitCode))
      },
      async listPaymentPlans() {
        await latency()
        return clone(PAYMENT_PLANS_FIXTURE)
      },
      async getActivePolicy(projectId, date) {
        const state = await db()
        const policy = activePolicyFor(state, projectId, date)
        return policy ? clone(policy) : null
      },
    },

    public: {
      async listProjectOverviews() {
        const state = await db()
        const today = todayIso()
        return PROJECTS_FIXTURE.map<ProjectOverview>((project) => {
          const policy = activePolicyFor(state, project.projectId, today)
          const available = state.units.filter((u) => u.projectId === project.projectId && u.status === 'AVAILABLE')
          return {
            project: clone(project),
            activePolicy: policy ? toPolicyRef(policy) : null,
            promotions: policy ? listPublicPromotions(policy) : [],
            availableUnits: available.length,
            priceFrom: available.length ? Math.min(...available.map((u) => u.listedPrice)) : null,
          }
        })
      },
      async estimate({ unitCode, customerSegment }) {
        const state = await db()
        const unit = findUnit(state, unitCode)
        const policy = activePolicyFor(state, unit.projectId, todayIso())
        return {
          unit: clone(unit),
          policy: policy ? toPolicyRef(policy) : null,
          estimatedAt: now(),
          plans: policy ? estimatePlans({ unit, policy, plans: PAYMENT_PLANS_FIXTURE, customerSegment }) : [],
          gifts: policy
            ? policy.rules
                .filter((r) => r.kind === 'GIFT' && r.cashEquivalentVnd)
                .map((r) => ({ title: r.title, cashEquivalentVnd: r.cashEquivalentVnd ?? 0 }))
            : [],
        }
      },
      async submitLead(input) {
        const state = await db()
        const lead = createLeadRecord(state, input, now())
        commit()
        return { leadId: lead.leadId, createdAt: lead.createdAt, unitCode: lead.unitCode }
      },
      async getSharedQuote(shareToken) {
        const state = await db()
        const at = now()
        const quote = findQuoteByToken(state, shareToken, at)
        markSharedQuoteViewed(state, quote, at)
        commit()
        return clone(toCustomerView(quote))
      },
      async respondToQuote(shareToken, input) {
        const state = await db()
        const at = now()
        const quote = findQuoteByToken(state, shareToken, at)
        respondSharedQuote(state, quote, input, at)
        commit()
        return clone(toCustomerView(quote))
      },
      async verifySharedQuote(shareToken) {
        const state = await db()
        const at = now()
        return verifyQuoteIntegrity(findQuoteByToken(state, shareToken, at), at)
      },
    },

    leads: {
      async list({ scope }) {
        const state = await db()
        const user = currentUser(state)
        const leads = state.leads.filter((l) => {
          if (scope === 'MINE') return l.assignedSaleId === user.userId
          if (scope === 'UNASSIGNED') return l.assignedSaleId === null
          return user.role !== 'SALE' || l.assignedSaleId === user.userId || l.assignedSaleId === null
        })
        return clone(leads)
      },
      async get(leadId) {
        const state = await db()
        currentUser(state)
        return clone(findLead(state, leadId))
      },
      async claim(leadId) {
        const state = await db()
        const user = currentUser(state, ['SALE'])
        const lead = claimLeadRecord(state, user, leadId, now())
        commit()
        return clone(lead)
      },
      async updateStatus(leadId, { status }) {
        const state = await db()
        const user = currentUser(state, ['SALE'])
        const lead = findLead(state, leadId)
        if (lead.assignedSaleId !== user.userId) throw new ApiError(403, 'FORBIDDEN', 'Bạn không phụ trách yêu cầu này.')
        lead.status = status
        lead.updatedAt = now()
        commit()
        return clone(lead)
      },
    },

    quotes: {
      async list(params) {
        const state = await db()
        const user = currentUser(state)
        return clone(
          state.quotes.filter(
            (q) =>
              (user.role !== 'SALE' || q.ownerId === user.userId) &&
              (!params?.status?.length || params.status.includes(q.status)) &&
              (!params?.leadId || q.leadId === params.leadId),
          ),
        )
      },
      async get(quoteId) {
        const state = await db()
        return clone(visibleQuote(state, currentUser(state), quoteId))
      },
      async preflight(input) {
        const state = await db()
        currentUser(state, ['SALE'])
        const unit = findUnit(state, input.unitCode)
        return runPreflight({
          projectName: unit.projectName,
          transactionDate: input.transactionDate,
          activePolicy: activePolicyFor(state, unit.projectId, input.transactionDate),
          selectedRuleCodes: input.selectedRuleCodes,
        })
      },
      async create(input, options) {
        const state = await db()
        const user = currentUser(state, ['SALE'])
        const quote = createQuoteRecord(state, user, input, now())
        commit()
        await replayProgress(quote, options)
        return clone(quote)
      },
      async revise(quoteId, input, options) {
        const state = await db()
        const user = currentUser(state, ['SALE'])
        const quote = reviseQuoteRecord(state, user, quoteId, input, now())
        commit()
        await replayProgress(quote, options)
        return clone(quote)
      },
      async submit(quoteId) {
        const state = await db()
        const quote = submitQuoteRecord(state, currentUser(state, ['SALE']), quoteId, now())
        commit()
        return clone(quote)
      },
      async decide(quoteId, input) {
        const state = await db()
        const quote = await decideQuoteRecord(state, currentUser(state, ['MANAGER']), quoteId, input, now())
        commit()
        return clone(quote)
      },
      async share(quoteId, { channel }) {
        const state = await db()
        const quote = shareQuoteRecord(state, currentUser(state, ['SALE']), quoteId, channel, now())
        commit()
        return clone(quote)
      },
      async verify(quoteId) {
        const state = await db()
        const quote = visibleQuote(state, currentUser(state), quoteId)
        return verifyQuoteIntegrity(quote, now())
      },
    },

    policies: {
      async list() {
        const state = await db()
        currentUser(state)
        return clone([...state.policies].sort((a, b) => b.effectiveFrom.localeCompare(a.effectiveFrom)))
      },
      async get(policyId) {
        const state = await db()
        currentUser(state)
        return clone(findPolicy(state, policyId))
      },
      async createDraft({ fromPolicyId }) {
        const state = await db()
        const user = currentUser(state, ['SALE_ADMIN'])
        const source = findPolicy(state, fromPolicyId)
        state.counters.policy += 1
        const [major, minor] = source.version.replace(/^v/, '').split('.').map((n) => Number(n) || 0)
        const version = `v${major}.${minor + 1}`
        const latestEnd = state.policies
          .filter((p) => p.projectId === source.projectId && p.status === 'PUBLISHED')
          .reduce((max, p) => (p.effectiveTo > max ? p.effectiveTo : max), todayIso())
        const from = new Date(`${latestEnd}T00:00:00Z`)
        from.setUTCDate(from.getUTCDate() + 1)
        const to = new Date(from)
        to.setUTCDate(to.getUTCDate() + 89)
        const draft: PolicyVersion = {
          ...clone(source),
          policyId: `${source.policyId.replace(/-V[\d.]+$/, '')}-V${major}.${minor + 1}-D${String(state.counters.policy).padStart(2, '0')}`,
          version,
          title: source.title,
          status: 'DRAFT',
          effectiveFrom: from.toISOString().slice(0, 10),
          effectiveTo: to.toISOString().slice(0, 10),
          sourceDocument: '',
          sourceFileHash: '',
          createdAt: now(),
          createdBy: user.fullName,
          publishedAt: null,
          publishedBy: null,
        }
        applyPolicyPatch(draft, {})
        draft.rules = draft.rules.map((r) => ({ ...r, policyId: draft.policyId, source: { ...r.source, documentId: draft.policyId } }))
        state.policies.push(draft)
        commit()
        return clone(draft)
      },
      async updateDraft(policyId, patch) {
        const state = await db()
        currentUser(state, ['SALE_ADMIN'])
        const policy = findPolicy(state, policyId)
        if (policy.status !== 'DRAFT') throw new ApiError(409, 'POLICY_LOCKED', 'Chỉ chỉnh sửa được bản nháp.')
        applyPolicyPatch(policy, patch)
        commit()
        return clone(policy)
      },
      async runPublishChecks(policyId) {
        const state = await db()
        currentUser(state, ['SALE_ADMIN'])
        await sleep(500)
        return runPublishChecks(findPolicy(state, policyId), state.policies, now())
      },
      async publish(policyId) {
        const state = await db()
        const user = currentUser(state, ['SALE_ADMIN'])
        const policy = findPolicy(state, policyId)
        const report = runPublishChecks(policy, state.policies, now())
        if (!report.canPublish) throw new ApiError(422, 'PUBLISH_CHECKS_FAILED', 'Bản chính sách chưa vượt qua bộ kiểm tra bắt buộc.')
        policy.status = 'PUBLISHED'
        policy.publishedAt = now()
        policy.publishedBy = user.fullName
        commit()
        return clone(policy)
      },
      async archive(policyId) {
        const state = await db()
        currentUser(state, ['SALE_ADMIN'])
        const policy = findPolicy(state, policyId)
        if (policy.status === 'ARCHIVED') throw new ApiError(409, 'POLICY_ARCHIVED', 'Chính sách đã ngừng áp dụng.')
        policy.status = 'ARCHIVED'
        commit()
        return clone(policy)
      },
    },

    inventory: {
      async updateUnit(unitCode, input) {
        const state = await db()
        currentUser(state, ['SALE_ADMIN'])
        const unit = findUnit(state, unitCode)
        if (input.listedPrice !== undefined) {
          if (!Number.isInteger(input.listedPrice) || input.listedPrice <= 0) {
            throw new ApiError(422, 'VALIDATION_ERROR', 'Giá niêm yết phải là số nguyên dương.')
          }
          unit.listedPrice = input.listedPrice
        }
        if (input.status !== undefined) unit.status = input.status
        commit()
        return clone(unit)
      },
    },

    qa: {
      async runFormulaRegression() {
        const state = await db()
        currentUser(state, ['SALE_ADMIN'])
        await sleep(400)
        return runBenchmarkSuite()
      },
    },
  }
}
