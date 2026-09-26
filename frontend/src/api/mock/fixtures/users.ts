import type { StaffUser } from '@/types/domain'

/** Mật khẩu chung của mọi tài khoản ở chế độ mock. */
export const MOCK_PASSWORD = 'Vland@2026'

export const STAFF_FIXTURE: StaffUser[] = [
  {
    userId: 'USR-SALE-001',
    fullName: 'Hoàng Nam',
    email: 'nam.hoang@vlandfuture.vn',
    phone: '0903 123 456',
    role: 'SALE',
    title: 'Chuyên viên kinh doanh',
  },
  {
    userId: 'USR-SALE-002',
    fullName: 'Lê Thu Trang',
    email: 'trang.le@vlandfuture.vn',
    phone: '0908 222 789',
    role: 'SALE',
    title: 'Chuyên viên kinh doanh',
  },
  {
    userId: 'USR-MGR-001',
    fullName: 'Hà Nguyễn',
    email: 'ha.nguyen@vlandfuture.vn',
    phone: '0909 555 010',
    role: 'MANAGER',
    title: 'Quản lý kinh doanh',
  },
  {
    userId: 'USR-ADM-001',
    fullName: 'Tuấn Minh',
    email: 'minh.tuan@vlandfuture.vn',
    phone: '0912 000 321',
    role: 'SALE_ADMIN',
    title: 'Admin Sale',
  },
]
