import type { AuthSession, LoginRequest, ProjectOverview, ReauthGrant, ReauthRequest } from '@pricepolicy/api-client/contracts'
import { snapshotRefOf } from '../engine/analyze'
import { selectPolicyForDate } from '../engine/conflicts'
import { PROJECTS_FIXTURE } from '../fixtures/units'
import { MOCK_PASSWORD, STAFF_FIXTURE } from '../fixtures/users'
import { MockError, notFound } from '../services/errors'
import { route } from './route'

const token = () => Array.from(crypto.getRandomValues(new Uint8Array(24)), (b) => b.toString(16).padStart(2, '0')).join('')
const today = (now: number) => new Date(now).toISOString().slice(0, 10)

export const catalogHandlers = [
  route('authLogin', async ({ db, now, json }) => {
    const body = await json<LoginRequest>()
    const user = STAFF_FIXTURE.find((u) => u.email.toLowerCase() === body?.email?.trim().toLowerCase())
    if (!user || body.password !== MOCK_PASSWORD) throw new MockError(401, 'UNAUTHORIZED', 'Email hoặc mật khẩu không đúng.')
    const access_token = token()
    const expires_at = now + 8 * 3_600_000
    db.auth[access_token] = { user_id: user.user_id, expires_at }
    const session: AuthSession = { access_token, expires_at: new Date(expires_at).toISOString(), user }
    return { body: session }
  }),

  route('authLogout', ({ db, request }) => {
    const t = /^Bearer (.+)$/.exec(request.headers.get('Authorization') ?? '')?.[1]
    if (t) delete db.auth[t]
    return { status: 204 }
  }),

  /** Re-auth trước khi ký (TD-4.1 §3.2) — token dùng một lần, sống 5 phút. */
  route('authReauth', async ({ db, now, staff, json }) => {
    const user = staff()
    const body = await json<ReauthRequest>()
    if (body?.password !== MOCK_PASSWORD) throw new MockError(403, 'REAUTH_REQUIRED', 'Mật khẩu xác thực không đúng.')
    const reauth_token = token()
    db.reauth[reauth_token] = { user_id: user.user_id, expires_at: now + 5 * 60_000 }
    const grant: ReauthGrant = { reauth_token, expires_at: new Date(now + 5 * 60_000).toISOString() }
    return { body: grant }
  }),

  route('publicProjects', async ({ db, now }) => {
    const overviews: ProjectOverview[] = await Promise.all(
      PROJECTS_FIXTURE.map(async (project) => {
        const policy = selectPolicyForDate(db.policies, project.project_id, today(now))
        const available = db.units.filter((u) => u.project_id === project.project_id && u.status === 'AVAILABLE' && u.listed_price_before_tax_vnd > 100_000_000)
        return {
          project,
          active_policy: policy ? await snapshotRefOf(policy) : null,
          promotions: policy ? policy.rules.filter((r) => !r.is_ambiguous).map((r) => ({ title: r.title, section: r.source.section })) : [],
          available_units: available.length,
          price_from_vnd: available.length ? Math.min(...available.map((u) => u.listed_price_before_tax_vnd)) : null,
        }
      }),
    )
    return { body: overviews }
  }),

  route('units', ({ db, query }) => {
    const projectId = query.get('project_id')
    return { body: db.units.filter((u) => !projectId || u.project_id === projectId) }
  }),

  route('policyList', ({ db, query }) => {
    const projectId = query.get('project_id')
    const status = query.get('status')
    const list = db.policies
      .filter((p) => (!projectId || p.project_id === projectId) && (!status || p.status === status))
      .sort((a, b) => b.effective_from.localeCompare(a.effective_from))
    return { body: list }
  }),

  route('policyActive', ({ db, query }) => {
    const projectId = query.get('project_id') ?? ''
    const date = query.get('date') ?? ''
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Ngày không hợp lệ.')
    return { body: selectPolicyForDate(db.policies, projectId, date) }
  }),

  route('policyDetail', ({ db, params }) => {
    const policy = db.policies.find((p) => p.policy_id === params.policy_id)
    if (!policy) throw notFound(`chính sách ${params.policy_id}`)
    return { body: policy }
  }),
]
