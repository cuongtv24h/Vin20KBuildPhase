/**
 * Chốt bất biến "nav ↔ quyền route": mọi mục menu phải mở được bởi chính vai trò nhìn thấy nó.
 *
 * Lỗi thật đã xảy ra (2026-10-08): nút "Gán Sale phụ trách" — đường DUY NHẤT cấp chủ sở hữu cho hồ sơ
 * vô chủ — nằm ở `/sale/leads` và chỉ ADMIN bấm được, nhưng khu `/sale` chỉ cho SALE nên ADMIN gõ
 * đường dẫn đó bị `RequireRole` đá về `/admin_cp`. Tính năng thành nút chết. Bộ test này để lỗi kiểu đó
 * không lặp lại: thêm trang mới cho một vai trò mà quên mở quyền khu route là test đỏ ngay.
 */

import { describe, expect, it } from 'vitest'
import type { UserRole } from '@pricepolicy/api-client/contracts'
import { NAV_BY_ROLE } from './nav'
import { AREA_ROLES, areaOfPath, canEnterArea, canOpenPath } from './roles'

const ALL_ROLES: UserRole[] = ['ADMIN', 'SALE', 'MANAGER', 'POLICY_ADMIN']

describe('quyền vào từng khu route (AREA_ROLES)', () => {
  it('ADMIN vào được trang Khách hàng /sale/leads để gán Sale phụ trách', () => {
    expect(AREA_ROLES.lead_inbox).toContain('ADMIN')
    expect(canOpenPath('ADMIN', '/sale/leads')).toBe(true)
    expect(canOpenPath('SALE', '/sale/leads')).toBe(true)
  })

  it('ADMIN KHÔNG vào phần còn lại của khu Sale (tránh bấm rồi bị đá về /admin_cp)', () => {
    expect(canOpenPath('ADMIN', '/sale')).toBe(false)
    expect(canOpenPath('ADMIN', '/sale/workspace')).toBe(false)
    expect(canOpenPath('ADMIN', '/sale/quotes/new')).toBe(false)
    expect(canOpenPath('SALE', '/sale/workspace')).toBe(true)
  })

  it('các vai trò khác giữ nguyên khu của mình', () => {
    expect(canOpenPath('MANAGER', '/manager/approvals')).toBe(true)
    expect(canOpenPath('MANAGER', '/sale/leads')).toBe(false)
    expect(canOpenPath('POLICY_ADMIN', '/admin/policies')).toBe(true)
    expect(canOpenPath('POLICY_ADMIN', '/sale/leads')).toBe(false)
    expect(canOpenPath('SALE', '/admin_cp')).toBe(false)
    expect(canOpenPath('ADMIN', '/admin_cp')).toBe(true)
  })

  it('chưa đăng nhập thì không vào được khu nào', () => {
    for (const area of Object.keys(AREA_ROLES) as (keyof typeof AREA_ROLES)[]) {
      expect(canEnterArea(undefined, area)).toBe(false)
    }
  })
})

describe('areaOfPath — phân giải đường dẫn thành khu route', () => {
  it('không nhầm admin_cp với admin, sale/leads với sale', () => {
    expect(areaOfPath('/admin_cp')).toBe('admin_cp')
    expect(areaOfPath('/admin/policies')).toBe('admin')
    expect(areaOfPath('/admin/copilot-quality')).toBe('admin')
    expect(areaOfPath('/sale/leads')).toBe('lead_inbox')
    expect(areaOfPath('/sale/workspace')).toBe('sale')
    expect(areaOfPath('/manager/approvals/QT-01')).toBe('manager')
  })

  it('bỏ qua query/hash và không phụ thuộc dấu / thừa', () => {
    expect(areaOfPath('/sale/leads?id=LD-2026-001')).toBe('lead_inbox')
    expect(areaOfPath('/sale/leads#chi-tiet')).toBe('lead_inbox')
    expect(areaOfPath('sale/leads')).toBe('lead_inbox')
  })

  it('đường dẫn ngoài các khu (login, 404) trả null', () => {
    expect(areaOfPath('/login')).toBeNull()
    expect(areaOfPath('/')).toBeNull()
    expect(areaOfPath('/khong-ton-tai')).toBeNull()
  })
})

describe('nav theo vai trò', () => {
  it('MỌI mục menu đều mở được bởi chính vai trò đó', () => {
    for (const role of ALL_ROLES) {
      for (const item of NAV_BY_ROLE[role]) {
        expect(canOpenPath(role, item.to), `${role} thấy menu "${item.label}" nhưng không mở được ${item.to}`).toBe(true)
      }
    }
  })

  it('ADMIN có mục "Khách hàng" trỏ tới /sale/leads', () => {
    const leadItem = NAV_BY_ROLE.ADMIN.find((item) => item.to === '/sale/leads')
    expect(leadItem, 'ADMIN phải có lối vào trang Khách hàng từ sidebar').toBeDefined()
    expect(leadItem?.label).toBe('Khách hàng')
  })

  it('mục đếm số lead đang chờ chỉ gắn cho Sale (ADMIN không bắn request nền)', () => {
    for (const role of ALL_ROLES) {
      for (const item of NAV_BY_ROLE[role]) {
        if (item.badgeKey === 'openLeads') expect(role).toBe('SALE')
        if (item.badgeKey === 'managerQueue') expect(role).toBe('MANAGER')
      }
    }
  })

  it('vai trò nào cũng có ít nhất một mục menu, nhãn không trùng trong cùng vai trò', () => {
    for (const role of ALL_ROLES) {
      const items = NAV_BY_ROLE[role]
      expect(items.length).toBeGreaterThan(0)
      expect(new Set(items.map((item) => item.label)).size).toBe(items.length)
    }
  })
})
