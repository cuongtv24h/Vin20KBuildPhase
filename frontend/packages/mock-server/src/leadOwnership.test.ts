// @vitest-environment node
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { api } from '@pricepolicy/api-client/client'
import type { LeadDossier } from '@pricepolicy/api-client/contracts'
import { ApiError } from '@pricepolicy/api-client/errors'
import { setAuthTokenProvider } from '@pricepolicy/api-client/http'
import { commit, getDb, resetDb } from './db'
import { DEFAULT_FLAGS, setFlags } from './flags'
import { server } from './node'

/**
 * Đặc tả quyền sở hữu hồ sơ khách hàng (CRM) ở chế độ mock — phải khớp máy chủ thật từng mã lỗi:
 *
 * 1. Hồ sơ CHƯA ghi người tạo (dữ liệu cũ, hoặc hồ sơ Pre-Sales khách tự bàn giao): Sale bị 403,
 *    chỉ ADMIN xoá được. Trên DB vận hành hiện không hồ sơ nào có `created_by`, nên nới luật cho nhóm
 *    này đồng nghĩa bỏ ngỏ toàn bộ khách hàng.
 * 2. ADMIN gán Sale phụ trách (`POST /leads/{id}/assign-sale`) = cấp chủ sở hữu: hồ sơ vô chủ được đóng
 *    dấu `created_by` bằng Sale đó ⇒ Sale ấy xoá được, Sale khác vẫn 403.
 * 3. Sale KHÔNG tự gán mình làm chủ hồ sơ được (403) — nếu không thì ai cũng tự cấp quyền xoá cho mình.
 * 4. Gán lại hồ sơ ĐÃ có chủ chỉ đổi người phụ trách, không ghi đè người tạo (không ai cướp hồ sơ).
 */

let token: string | null = null
setAuthTokenProvider(() => token)

const PASSWORD = 'Vland@2026'
const SALE_A = 'nam.hoang@vlandfuture.vn' // USR-SALE-001
const SALE_B = 'trang.le@vlandfuture.vn' // USR-SALE-002
const ADMIN_EMAIL = 'admin.crm@vlandfuture.vn'

async function loginAs(email: string) {
  token = (await api.auth.login({ email, password: PASSWORD })).access_token
}

/** ADMIN đầu tiên, tạo qua đúng luồng khởi tạo của sản phẩm (bộ tài khoản mock chưa có vai trò ADMIN). */
async function loginAsAdmin() {
  const status = await api.admin.setupStatus()
  if (!status.has_admin) {
    await api.admin.setup({ user: 'admin.crm', password: PASSWORD, email: ADMIN_EMAIL, full_name: 'Admin CRM' })
  }
  await loginAs(ADMIN_EMAIL)
}

/** Hồ sơ kiểu dữ liệu vận hành cũ: không người tạo, không Sale phụ trách. */
async function seedOwnerlessDossier(customerName: string) {
  const db = await getDb()
  const template = db.dossiers[0]
  const dossier: LeadDossier = {
    ...template,
    dossier_id: `LD-LEGACY-${db.dossiers.length + 1}`,
    status: 'ASSIGNED',
    customer: { ...template.customer, full_name: customerName },
    assigned_sale: null,
    assigned_sales_id: null,
    created_by: null,
    converted_quote_id: null,
  }
  db.dossiers.unshift(dossier)
  commit()
  return dossier.dossier_id
}

async function expectApiError(promise: Promise<unknown>, status: number, code: string) {
  const err = await promise.then(
    () => null,
    (e: unknown) => e,
  )
  expect(err).toBeInstanceOf(ApiError)
  expect({ status: (err as ApiError).status, code: (err as ApiError).code }).toEqual({ status, code })
}

beforeAll(() => {
  setFlags({ ...DEFAULT_FLAGS, time_scale: 0.01 })
  server.listen({ onUnhandledRequest: 'error' })
})
beforeEach(async () => {
  setFlags({ ...DEFAULT_FLAGS, time_scale: 0.01 })
  await resetDb()
  token = null
})
afterAll(() => server.close())

describe('Quyền sở hữu hồ sơ khách hàng', () => {
  it('Hồ sơ chưa có người tạo: Sale bị chặn 403, ADMIN xoá được', async () => {
    await loginAsAdmin()
    const dossierId = await seedOwnerlessDossier('Khách di sản')

    await loginAs(SALE_A)
    // Sale vẫn THẤY hồ sơ trong hộp (hồ sơ chưa gán ai), nhưng không được xoá.
    expect((await api.leads.list()).some((d) => d.dossier_id === dossierId)).toBe(true)
    await expectApiError(api.leads.delete(dossierId), 403, 'UNAUTHORIZED_ACCESS')

    await loginAs(ADMIN_EMAIL)
    await api.leads.delete(dossierId)
    expect((await api.leads.list()).some((d) => d.dossier_id === dossierId)).toBe(false)
  })

  it('ADMIN gán Sale phụ trách thì hồ sơ có chủ: đúng Sale đó xoá được', async () => {
    await loginAsAdmin()
    const dossierId = await seedOwnerlessDossier('Khách chưa ai phụ trách')

    const assigned = await api.leads.assignSale(dossierId, 'USR-SALE-002')
    expect(assigned.created_by).toBe('USR-SALE-002')
    expect(assigned.assigned_sale?.user_id).toBe('USR-SALE-002')

    await loginAs(SALE_A)
    await expectApiError(api.leads.delete(dossierId), 403, 'UNAUTHORIZED_ACCESS')

    await loginAs(SALE_B)
    await api.leads.delete(dossierId)
  })

  it('Sale không tự gán mình làm chủ hồ sơ vô chủ', async () => {
    await loginAsAdmin()
    const dossierId = await seedOwnerlessDossier('Khách vô chủ')

    await loginAs(SALE_A)
    await expectApiError(api.leads.assignSale(dossierId, 'USR-SALE-001'), 403, 'FORBIDDEN')
    // Vẫn vô chủ ⇒ Sale vẫn không xoá được.
    await expectApiError(api.leads.delete(dossierId), 403, 'UNAUTHORIZED_ACCESS')
  })

  it('Gán lại hồ sơ đã có chủ: đổi người phụ trách, không cướp quyền xoá', async () => {
    await loginAsAdmin()
    const dossierId = await seedOwnerlessDossier('Khách của Trang')
    await api.leads.assignSale(dossierId, 'USR-SALE-002')

    const reassigned = await api.leads.assignSale(dossierId, 'USR-SALE-001')
    expect(reassigned.assigned_sale?.user_id).toBe('USR-SALE-001')
    expect(reassigned.created_by).toBe('USR-SALE-002')

    await loginAs(SALE_A)
    await expectApiError(api.leads.delete(dossierId), 403, 'UNAUTHORIZED_ACCESS')
  })

  it('Hồ sơ đã chuyển báo giá: Sale không xoá được (409), ADMIN dọn được', async () => {
    await loginAsAdmin()
    const dossierId = await seedOwnerlessDossier('Khách đã ra báo giá')
    await api.leads.assignSale(dossierId, 'USR-SALE-002')

    // Giả lập trạng thái đã chuyển báo giá (luồng convert đầy đủ nằm ở scenarios.test.ts).
    const db = await getDb()
    const row = db.dossiers.find((d) => d.dossier_id === dossierId)!
    row.status = 'CONVERTED_TO_QUOTE'
    row.converted_quote_id = 'Q-2026-0001'
    commit()

    await loginAs(SALE_B)
    await expectApiError(api.leads.delete(dossierId), 409, 'INVALID_STATE_TRANSITION')

    await loginAs(ADMIN_EMAIL)
    await api.leads.delete(dossierId)
    expect((await api.leads.list()).some((d) => d.dossier_id === dossierId)).toBe(false)
  })

  it('Hồ sơ Sale tự tạo thì ghi nhận người tạo ngay và Sale đó xoá được', async () => {
    await loginAs(SALE_B)
    const created = await api.leads.create({ customer_name: 'Khách của Trang', customer_phone: '0908 000 111' })
    expect(created.created_by).toBe('USR-SALE-002')

    await loginAs(SALE_A)
    await expectApiError(api.leads.delete(created.dossier_id), 403, 'UNAUTHORIZED_ACCESS')

    await loginAs(SALE_B)
    await api.leads.delete(created.dossier_id)
  })
})
