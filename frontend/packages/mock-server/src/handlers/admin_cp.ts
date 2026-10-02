import type { AdminUser, StaffUser, UserRole } from '@pricepolicy/api-client/contracts'
import { nextId } from '../db'
import { STAFF_FIXTURE } from '../fixtures/users'
import { MockError, notFound } from '../services/errors'
import { route } from './route'

/**
 * Admin CP giả lập — song song với `src/api/endpoints/admin_cp.py` của backend thật.
 *
 * Vì sao cần: `ENDPOINTS` có 6 route `/admin/*` nhưng mock-server trước đây chưa phủ, khiến test
 * "mọi endpoint trong danh bạ đều có handler mock" đỏ và màn Hình Quản trị không chạy được ở chế độ
 * mock. Hành vi bám theo backend: khởi tạo 1 lần duy nhất, RBAC chỉ ADMIN, chặn tự xoá và xoá
 * Admin cuối cùng, filter `role`/`search` khi liệt kê.
 */

const VALID_ROLES: UserRole[] = ['ADMIN', 'MANAGER', 'SALE', 'POLICY_ADMIN']

let users: AdminUser[] = STAFF_FIXTURE.map((u) => ({
  user: u.email.split('@')[0],
  email: u.email,
  phone: u.phone,
  role: u.role,
  user_id: u.user_id,
  full_name: u.full_name,
  title: u.title ?? null,
  is_active: true,
  created_at: '2026-01-01T00:00:00.000Z',
  updated_at: '2026-01-01T00:00:00.000Z',
}))

const hasAdmin = () => users.some((u) => u.role === 'ADMIN')

const toStaff = (u: AdminUser): StaffUser => ({
  user_id: u.user_id ?? u.user,
  full_name: u.full_name ?? u.user,
  email: u.email,
  phone: u.phone ?? '',
  role: u.role,
  title: u.title ?? '',
})

const normalizeRole = (role: string): UserRole => {
  const upper = role.trim().toUpperCase() as UserRole
  if (!VALID_ROLES.includes(upper)) {
    throw new MockError(422, 'INPUT_VALIDATION_ERROR', `Vai trò không hợp lệ. Phải là một trong: ${VALID_ROLES.join(', ')}`)
  }
  return upper
}

const makeToken = () => Array.from(crypto.getRandomValues(new Uint8Array(24)), (b) => b.toString(16).padStart(2, '0')).join('')

export const adminCpHandlers = [
  route('adminSetupStatus', () => ({
    body: {
      initialized: hasAdmin(),
      total_users: users.length,
      has_admin: hasAdmin(),
      message: hasAdmin() ? 'Hệ thống đã có Quản trị viên' : 'Chưa có Quản trị viên. Cần khởi tạo tài khoản đầu tiên.',
    },
  })),

  /** POST /admin/setup — chỉ chạy được khi chưa có ADMIN nào. Public theo danh bạ. */
  route('adminSetup', async ({ db, now, json }) => {
    if (hasAdmin()) {
      throw new MockError(400, 'INVALID_STATE_TRANSITION', 'Hệ thống đã có Quản trị viên (ADMIN). Không thể thực hiện khởi tạo lại.')
    }
    const body = await json<{ user: string; password: string; email: string; phone?: string; full_name?: string }>()
    const userName = (body?.user || body?.full_name || '').trim()
    const email = (body?.email ?? '').trim().toLowerCase()
    if (!userName || !email) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Thiếu tên tài khoản hoặc email.')
    if (users.some((u) => u.user.toLowerCase() === userName.toLowerCase() || u.email.toLowerCase() === email)) {
      throw new MockError(409, 'INVALID_STATE_TRANSITION', `Tài khoản '${userName}' hoặc email '${email}' đã được sử dụng.`)
    }
    const admin: AdminUser = {
      user: userName,
      email,
      phone: body.phone?.trim() || null,
      role: 'ADMIN',
      user_id: `USR-ADM-${String(nextId(db, 'user')).padStart(3, '0')}`,
      full_name: body.full_name ?? userName,
      title: 'Quản trị viên',
      is_active: true,
      created_at: new Date(now).toISOString(),
      updated_at: new Date(now).toISOString(),
    }
    users = [...users, admin]
    STAFF_FIXTURE.push(toStaff(admin))
    const access_token = makeToken()
    const expires_at = now + 8 * 3_600_000
    db.auth[access_token] = { user_id: admin.user_id ?? admin.user, expires_at }
    return {
      status: 201,
      body: {
        status: 'success',
        message: 'Khởi tạo tài khoản Quản trị viên đầu tiên thành công!',
        access_token,
        expires_at: new Date(expires_at).toISOString(),
        user: admin,
      },
    }
  }),

  route('adminUsersList', ({ staff, query }) => {
    const role = query.get('role')
    const search = (query.get('search') ?? '').trim().toLowerCase()
    const me = staff()
    if (me.role !== 'ADMIN') throw new MockError(403, 'FORBIDDEN', 'Chỉ Quản trị viên (ADMIN) mới có quyền truy cập trang quản trị.')
    const filtered = users.filter(
      (u) =>
        (!role || u.role === role.toUpperCase()) &&
        (!search ||
          u.user.toLowerCase().includes(search) ||
          u.email.toLowerCase().includes(search) ||
          (u.phone ?? '').toLowerCase().includes(search)),
    )
    return { body: filtered }
  }),

  route('adminUserCreate', async ({ json, staff }) => {
    const me = staff()
    if (me.role !== 'ADMIN') throw new MockError(403, 'FORBIDDEN', 'Chỉ Quản trị viên (ADMIN) mới có quyền thêm người dùng.')
    const body = await json<{ user: string; password: string; email: string; phone?: string; role?: string; full_name?: string }>()
    const userName = (body?.user || body?.full_name || '').trim()
    if (!userName) throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Tên người dùng (user) không được để trống.')
    const email = (body?.email ?? '').trim().toLowerCase()
    if (users.some((u) => u.user.toLowerCase() === userName.toLowerCase() || u.email.toLowerCase() === email)) {
      throw new MockError(409, 'INVALID_STATE_TRANSITION', `Tài khoản '${userName}' hoặc email '${email}' đã tồn tại trong hệ thống.`)
    }
    const created: AdminUser = {
      user: userName,
      email,
      phone: body.phone?.trim() || null,
      role: normalizeRole(body.role ?? 'SALE'),
      user_id: `USR-${String(users.length + 1).padStart(3, '0')}`,
      full_name: body.full_name ?? userName,
      title: null,
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    users = [...users, created]
    STAFF_FIXTURE.push(toStaff(created))
    return { status: 201, body: created }
  }),

  route('adminUserUpdate', async ({ params, json, staff }) => {
    const me = staff()
    if (me.role !== 'ADMIN') throw new MockError(403, 'FORBIDDEN', 'Chỉ Quản trị viên (ADMIN) mới có quyền chỉnh sửa người dùng.')
    const index = users.findIndex((u) => u.user === params.user_id || u.user_id === params.user_id)
    if (index < 0) throw notFound(`người dùng '${params.user_id}'`)
    const body = await json<{ email?: string; phone?: string; role?: string; full_name?: string; title?: string; is_active?: boolean }>()
    const updated: AdminUser = { ...users[index], updated_at: new Date().toISOString() }
    if (body?.email !== undefined) updated.email = body.email.trim().toLowerCase()
    if (body?.phone !== undefined) updated.phone = body.phone.trim() || null
    if (body?.role !== undefined) updated.role = normalizeRole(body.role)
    if (body?.full_name !== undefined) updated.full_name = body.full_name
    if (body?.title !== undefined) updated.title = body.title
    if (body?.is_active !== undefined) updated.is_active = body.is_active
    users = users.map((u, i) => (i === index ? updated : u))
    return { body: updated }
  }),

  route('adminUserDelete', ({ params, staff }) => {
    const me = staff()
    if (me.role !== 'ADMIN') throw new MockError(403, 'FORBIDDEN', 'Chỉ Quản trị viên (ADMIN) mới có quyền xóa người dùng.')
    const target = users.find((u) => u.user === params.user_id || u.user_id === params.user_id)
    if (!target) throw notFound(`người dùng '${params.user_id}'`)
    if (target.email.toLowerCase() === me.email.toLowerCase()) {
      throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Không thể tự xóa tài khoản của chính mình.')
    }
    if (target.role === 'ADMIN' && users.filter((u) => u.role === 'ADMIN').length <= 1) {
      throw new MockError(422, 'INPUT_VALIDATION_ERROR', 'Không thể xóa Quản trị viên cuối cùng của hệ thống.')
    }
    users = users.filter((u) => u !== target)
    return { body: { status: 'success', message: `Đã xóa tài khoản '${target.user}'.` } }
  }),
]
