import type { StaffUser } from '@/api/contracts'

/** Mật khẩu chung của mọi tài khoản ở chế độ mock. */
export const MOCK_PASSWORD = 'Vland@2026'

export const STAFF_FIXTURE: StaffUser[] = [
  {
    user_id: 'USR-SALE-001',
    full_name: 'Hoàng Nam',
    email: 'nam.hoang@vlandfuture.vn',
    phone: '0903 123 456',
    role: 'SALE',
    title: 'Chuyên viên kinh doanh',
  },
  {
    user_id: 'USR-SALE-002',
    full_name: 'Lê Thu Trang',
    email: 'trang.le@vlandfuture.vn',
    phone: '0908 222 789',
    role: 'SALE',
    title: 'Chuyên viên kinh doanh',
  },
  {
    user_id: 'USR-MGR-001',
    full_name: 'Hà Nguyễn',
    email: 'ha.nguyen@vlandfuture.vn',
    phone: '0909 555 010',
    role: 'MANAGER',
    title: 'Quản lý kinh doanh',
  },
  {
    user_id: 'USR-ADM-001',
    full_name: 'Tuấn Minh',
    email: 'minh.tuan@vlandfuture.vn',
    phone: '0912 000 321',
    role: 'POLICY_ADMIN',
    title: 'Chuyên viên quản trị chính sách',
  },
]

export const staffById = (userId: string) => STAFF_FIXTURE.find((u) => u.user_id === userId)
export const actorOf = (u: StaffUser) => ({ user_id: u.user_id, full_name: u.full_name, role: u.role })
