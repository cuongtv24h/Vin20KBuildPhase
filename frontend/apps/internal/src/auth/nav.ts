import {
  ClipboardCheck,
  FileStack,
  FlaskConical,
  Gauge,
  MessageSquare,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Users,
  type LucideIcon,
} from 'lucide-react'
import type { UserRole } from '@pricepolicy/api-client/contracts'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
  badgeKey?: 'openLeads' | 'managerQueue'
  /** Nhóm hiển thị (nhãn nhỏ phía trên cụm mục — bố cục Square/Cloudflare). */
  group?: string
}

/**
 * Menu sidebar theo vai trò. Tách ra khỏi `StaffLayout` để test được trong Node (không cần DOM):
 * mọi mục nav PHẢI mở được bởi chính vai trò đó (`nav.test.ts` đối chiếu với `AREA_ROLES`) — đây là
 * lớp chặn để không lặp lại lỗi "nút Gán Sale của ADMIN nằm trên trang ADMIN không vào được".
 */
export const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  ADMIN: [
    { to: '/admin_cp', label: 'Quản trị Users', icon: ShieldCheck, group: 'Quản trị' },
    // Khu Sale chỉ mở trang Khách hàng cho ADMIN: nơi gán Sale phụ trách (cấp chủ sở hữu hồ sơ vô chủ)
    // và xoá/dọn hộ hồ sơ. ADMIN không thấy "Thêm khách hàng" / "Lập báo giá" / "Hỏi Copilot" —
    // những việc đó là của Sale và endpoint cũng chỉ nhận SALE.
    { to: '/sale/leads', label: 'Khách hàng', icon: Users, group: 'Kinh doanh' },
    { to: '/admin/policies', label: 'Chính sách bán hàng', icon: ScrollText, group: 'Chính sách và chất lượng' },
    { to: '/admin/benchmark', label: 'Kiểm thử công thức', icon: FlaskConical, group: 'Chính sách và chất lượng' },
    { to: '/admin/copilot-quality', label: 'Chất lượng Copilot', icon: Gauge, group: 'Chính sách và chất lượng' },
  ],
  SALE: [
    { to: '/sale/workspace', label: 'Trợ lý Copilot', icon: Sparkles, group: 'Làm việc' },
    { to: '/sale/leads', label: 'Khách hàng', icon: Users, badgeKey: 'openLeads', group: 'Làm việc' },
    { to: '/sale/quotes', label: 'Báo giá', icon: FileStack, group: 'Làm việc' },
    { to: '/sale/messages', label: 'Tin nhắn', icon: MessageSquare, group: 'Làm việc' },
    { to: '/sale/policies', label: 'Chính sách', icon: ScrollText, group: 'Tra cứu' },
  ],
  MANAGER: [{ to: '/manager/approvals', label: 'Phê duyệt báo giá', icon: ClipboardCheck, badgeKey: 'managerQueue', group: 'Phê duyệt' }],
  POLICY_ADMIN: [
    { to: '/admin/policies', label: 'Chính sách bán hàng', icon: ScrollText, group: 'Chính sách và chất lượng' },
    { to: '/admin/benchmark', label: 'Kiểm thử công thức', icon: FlaskConical, group: 'Chính sách và chất lượng' },
    { to: '/admin/copilot-quality', label: 'Chất lượng Copilot', icon: Gauge, group: 'Chính sách và chất lượng' },
  ],
}
