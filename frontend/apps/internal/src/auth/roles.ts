import type { UserRole } from '@pricepolicy/api-client/contracts'

/** Khu route của cổng nội bộ, đặt theo prefix đường dẫn. */
export type RouteArea = 'sale' | 'lead_inbox' | 'manager' | 'admin' | 'admin_cp'

/**
 * Vai trò được vào từng khu route — nguồn sự thật duy nhất cho `RequireRole`, cho nav và cho test.
 *
 * `lead_inbox` tách khỏi `sale` vì trang Khách hàng (`/sale/leads`) chứa nút **"Gán Sale phụ trách"** —
 * đường DUY NHẤT để cấp chủ sở hữu cho hồ sơ vô chủ (hồ sơ khách tự bàn giao và toàn bộ dữ liệu cũ chưa
 * có `created_by`), và nút đó chỉ ADMIN được bấm. Trước đây cả khu `/sale` chỉ nhận SALE nên ADMIN gõ
 * `/sale/leads` bị đá về `/admin_cp`: tính năng gán chủ sở hữu thành nút chết, không ai mở được.
 *
 * ADMIN chỉ vào đúng trang Khách hàng (xem, gán, sửa, xoá hộ). Các trang Sale còn lại — Trợ lý Copilot,
 * Báo giá, Tin nhắn — vẫn của riêng Sale, vì ADMIN không có nghiệp vụ ở đó và nhiều endpoint chỉ nhận
 * SALE (thêm khách, lập báo giá, chuyển hồ sơ thành báo giá) ⇒ mở ra chỉ để nhận 403.
 */
export const AREA_ROLES: Record<RouteArea, readonly UserRole[]> = {
  sale: ['SALE'],
  lead_inbox: ['SALE', 'ADMIN'],
  manager: ['MANAGER'],
  admin: ['POLICY_ADMIN', 'ADMIN'],
  admin_cp: ['ADMIN'],
}

/** Đường dẫn thuộc khu nào. `admin_cp` phải xét trước `admin`, `sale/leads` trước `sale`. */
export function areaOfPath(path: string): RouteArea | null {
  const clean = path.split(/[?#]/, 1)[0]?.replace(/^\/+/, '') ?? ''
  if (clean === 'sale/leads' || clean.startsWith('sale/leads/')) return 'lead_inbox'
  if (clean.startsWith('sale')) return 'sale'
  if (clean.startsWith('manager')) return 'manager'
  if (clean.startsWith('admin_cp')) return 'admin_cp'
  if (clean.startsWith('admin')) return 'admin'
  return null
}

export function canEnterArea(role: UserRole | undefined, area: RouteArea): boolean {
  if (!role) return false
  return AREA_ROLES[area].includes(role)
}

/** Vai trò này có mở được đường dẫn này không (không mở được thì `RequireRole` sẽ chuyển hướng đi chỗ khác). */
export function canOpenPath(role: UserRole | undefined, path: string): boolean {
  const area = areaOfPath(path)
  return area !== null && canEnterArea(role, area)
}
