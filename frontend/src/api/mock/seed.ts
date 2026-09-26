import type { CreateQuoteRequest } from '@/api/contracts'
import { SCHEMA_VERSION, type MockDbState } from '@/api/mock/db'
import { POLICIES_FIXTURE } from '@/api/mock/fixtures/policies'
import { UNITS_FIXTURE } from '@/api/mock/fixtures/units'
import { STAFF_FIXTURE } from '@/api/mock/fixtures/users'
import {
  claimLeadRecord,
  createLeadRecord,
  createQuoteRecord,
  decideQuoteRecord,
  findQuote,
  markSharedQuoteViewed,
  shareQuoteRecord,
  submitQuoteRecord,
} from '@/api/mock/services'
import type { StaffUser } from '@/types/domain'

const staff = (userId: string): StaffUser => {
  const user = STAFF_FIXTURE.find((u) => u.userId === userId)
  if (!user) throw new Error(`Seed: thiếu user ${userId}`)
  return user
}

const NAM = staff('USR-SALE-001')
const TRANG = staff('USR-SALE-002')
const HA = staff('USR-MGR-001')

/** Giờ Việt Nam (UTC+7) → ISO UTC. */
const vn = (date: string, time: string) => new Date(`${date}T${time}:00+07:00`).toISOString()

/** Token cố định cho báo giá mẫu đã gửi khách, để có thể mở trực tiếp /quote/{token}. */
export const SEED_SHARE_TOKEN = 'Sp7Kq9ZtHuy2201xVm'

/**
 * Dữ liệu vận hành mẫu: yêu cầu khách hàng + hồ sơ báo giá ở đủ các trạng thái, để mỗi vai
 * trò đăng nhập vào đều có việc thật để xử lý.
 */
export async function buildSeedState(): Promise<MockDbState> {
  const db: MockDbState = {
    schemaVersion: SCHEMA_VERSION,
    units: UNITS_FIXTURE.map((u) => ({ ...u })),
    policies: structuredClone(POLICIES_FIXTURE),
    leads: [],
    quotes: [],
    sessions: {},
    counters: { quote: 0, lead: 0, event: 0, policy: 0 },
  }

  const lead = (input: Parameters<typeof createLeadRecord>[1], at: string) => createLeadRecord(db, input, at).leadId
  const quote = (actor: StaffUser, input: CreateQuoteRequest, at: string) => createQuoteRecord(db, actor, input, at).quoteId

  // ─── Yêu cầu từ cổng khách hàng ──────────────────────────────────────────
  const leadHuy = lead(
    {
      fullName: 'Phạm Quốc Huy',
      phone: '0918 456 221',
      email: 'huy.pham@gmail.com',
      unitCode: 'SAP-C-2201',
      customerSegment: 'EXISTING_RESIDENT',
      objective: 'MIN_NET_PRICE',
      note: 'Đã sở hữu 1 căn tại The Zen Park, muốn thanh toán nhanh để được chiết khấu tốt nhất.',
    },
    vn('2026-09-20', '10:05'),
  )
  const leadMai = lead(
    {
      fullName: 'Lý Thanh Mai',
      phone: '0937 880 145',
      email: 'mai.ly@outlook.com',
      unitCode: 'ZEN-B-0301',
      customerSegment: 'NEW_CUSTOMER',
      objective: 'MIN_NET_PRICE',
      note: 'Mua 2 căn liền kề cho 2 con.',
    },
    vn('2026-09-21', '15:20'),
  )
  const leadVy = lead(
    {
      fullName: 'Ngô Thảo Vy',
      phone: '0976 312 908',
      email: '',
      unitCode: 'SAP-D-0905',
      customerSegment: 'EXISTING_RESIDENT',
      objective: 'MIN_INITIAL_OUTFLOW',
      note: '',
    },
    vn('2026-09-22', '09:10'),
  )
  const leadBich = lead(
    {
      fullName: 'Trần Thị Bích',
      phone: '0905 667 312',
      email: 'bich.tran@yahoo.com',
      unitCode: 'ZEN-B-1502',
      customerSegment: 'NEW_CUSTOMER',
      objective: 'MIN_INITIAL_OUTFLOW',
      note: 'Cần vay ngân hàng, muốn số tiền trả trước thấp.',
    },
    vn('2026-09-23', '14:30'),
  )
  const leadDang = lead(
    {
      fullName: 'Vũ Hải Đăng',
      phone: '0983 004 771',
      email: 'dang.vu@vng.com.vn',
      unitCode: 'ZEN-A-1205',
      customerSegment: 'EXISTING_RESIDENT',
      objective: 'MAX_BENEFIT_VALUE',
      note: 'Quan tâm gói nội thất.',
    },
    vn('2026-09-24', '08:45'),
  )
  const leadKhanh = lead(
    {
      fullName: 'Bùi Gia Khánh',
      phone: '0909 118 623',
      email: 'khanh.bui@fpt.com',
      unitCode: 'ZEN-A-0803',
      customerSegment: 'EXISTING_RESIDENT',
      objective: 'MIN_NET_PRICE',
      note: 'Mua 2 căn để đầu tư cho thuê.',
    },
    vn('2026-09-24', '10:15'),
  )
  lead(
    {
      fullName: 'Nguyễn Văn An',
      phone: '0912 345 678',
      email: 'an.nguyen@gmail.com',
      unitCode: 'ZEN-A-1205',
      customerSegment: 'EXISTING_RESIDENT',
      objective: 'MIN_NET_PRICE',
      note: 'Muốn xem phương án thanh toán sớm.',
    },
    vn('2026-09-25', '08:40'),
  )
  lead(
    {
      fullName: 'Đỗ Minh Châu',
      phone: '0868 225 190',
      email: 'chau.do@gmail.com',
      unitCode: 'SAP-D-2604',
      customerSegment: 'NEW_CUSTOMER',
      objective: 'MAX_BENEFIT_VALUE',
      note: '',
    },
    vn('2026-09-25', '09:55'),
  )

  // ─── Hồ sơ báo giá ───────────────────────────────────────────────────────

  // 1. Đã duyệt & đã gửi khách, khách đã mở xem.
  claimLeadRecord(db, NAM, leadHuy, vn('2026-09-20', '10:30'))
  const qHuy = quote(
    NAM,
    {
      leadId: leadHuy,
      unitCode: 'SAP-C-2201',
      transactionDate: '2026-09-20',
      customerSegment: 'EXISTING_RESIDENT',
      unitsQuantity: 1,
      selectedRuleCodes: ['EARLY_PAY_DISCOUNT', 'MANAGEMENT_FEE_GIFT'],
      objective: 'MIN_NET_PRICE',
      customerName: 'Phạm Quốc Huy',
      customerPhone: '0918 456 221',
    },
    vn('2026-09-20', '11:02'),
  )
  submitQuoteRecord(db, NAM, qHuy, vn('2026-09-20', '11:04'))
  await decideQuoteRecord(db, HA, qHuy, { decision: 'APPROVED', notes: 'Đúng chính sách Sapphire v1.0.' }, vn('2026-09-20', '11:40'))
  shareQuoteRecord(db, NAM, qHuy, 'ZALO', vn('2026-09-20', '13:15'))
  const huy = findQuote(db, qHuy)
  if (huy.distribution) {
    huy.distribution.shareToken = SEED_SHARE_TOKEN
    huy.distribution.expiresAt = vn('2026-12-31', '23:59')
  }
  markSharedQuoteViewed(db, huy, vn('2026-09-20', '19:42'))

  // 2. Quản lý yêu cầu chỉnh sửa (khách mua 2 căn nhưng Sale lập cho 1 căn).
  claimLeadRecord(db, NAM, leadMai, vn('2026-09-22', '08:30'))
  const qMai = quote(
    NAM,
    {
      leadId: leadMai,
      unitCode: 'ZEN-B-0301',
      transactionDate: '2026-09-22',
      customerSegment: 'NEW_CUSTOMER',
      unitsQuantity: 1,
      selectedRuleCodes: ['SMARTHOME_GIFT', 'BULK_PURCHASE_DISCOUNT'],
      objective: 'MIN_NET_PRICE',
      customerName: 'Lý Thanh Mai',
      customerPhone: '0937 880 145',
    },
    vn('2026-09-22', '09:05'),
  )
  submitQuoteRecord(db, NAM, qMai, vn('2026-09-22', '09:06'))
  await decideQuoteRecord(
    db,
    HA,
    qMai,
    {
      decision: 'NEEDS_REVISION',
      notes: 'Khách đăng ký mua 2 căn — cập nhật số lượng căn = 2 để áp dụng chiết khấu mua sỉ Điều 5 rồi trình lại.',
    },
    vn('2026-09-22', '10:20'),
  )

  // 3. Bị từ chối (thiếu chứng từ khách hàng thân thiết).
  claimLeadRecord(db, TRANG, leadVy, vn('2026-09-22', '09:30'))
  const qVy = quote(
    TRANG,
    {
      leadId: leadVy,
      unitCode: 'SAP-D-0905',
      transactionDate: '2026-09-22',
      customerSegment: 'EXISTING_RESIDENT',
      unitsQuantity: 1,
      selectedRuleCodes: ['BANK_LOAN_HTLS'],
      objective: 'MIN_INITIAL_OUTFLOW',
      customerName: 'Ngô Thảo Vy',
      customerPhone: '0976 312 908',
    },
    vn('2026-09-22', '10:02'),
  )
  submitQuoteRecord(db, TRANG, qVy, vn('2026-09-22', '10:03'))
  await decideQuoteRecord(
    db,
    HA,
    qVy,
    {
      decision: 'REJECTED',
      notes: 'Khách chưa cung cấp chứng từ chứng minh đã sở hữu sản phẩm VLandFuture. Lập hồ sơ mới theo diện khách hàng mới.',
    },
    vn('2026-09-22', '14:10'),
  )

  // 4. Chờ duyệt — khách vay ngân hàng.
  claimLeadRecord(db, NAM, leadBich, vn('2026-09-23', '15:00'))
  const qBich = quote(
    NAM,
    {
      leadId: leadBich,
      unitCode: 'ZEN-B-1502',
      transactionDate: '2026-09-23',
      customerSegment: 'NEW_CUSTOMER',
      unitsQuantity: 1,
      selectedRuleCodes: ['BANK_LOAN_HTLS', 'SMARTHOME_GIFT'],
      objective: 'MIN_INITIAL_OUTFLOW',
      customerName: 'Trần Thị Bích',
      customerPhone: '0905 667 312',
    },
    vn('2026-09-24', '09:15'),
  )
  submitQuoteRecord(db, NAM, qBich, vn('2026-09-24', '09:17'))

  // 5. Dừng an toàn — chọn 2 ưu đãi loại trừ nhau → hàng đợi ngoại lệ.
  claimLeadRecord(db, TRANG, leadDang, vn('2026-09-24', '09:00'))
  quote(
    TRANG,
    {
      leadId: leadDang,
      unitCode: 'ZEN-A-1205',
      transactionDate: '2026-09-24',
      customerSegment: 'EXISTING_RESIDENT',
      unitsQuantity: 1,
      selectedRuleCodes: ['EARLY_PAY_DISCOUNT', 'FURNITURE_GIFT'],
      objective: 'MAX_BENEFIT_VALUE',
      customerName: 'Vũ Hải Đăng',
      customerPhone: '0983 004 771',
    },
    vn('2026-09-24', '09:40'),
  )

  // 6. Chờ duyệt — cờ vàng (tổng ưu đãi chạm trần 12%).
  claimLeadRecord(db, TRANG, leadKhanh, vn('2026-09-24', '10:30'))
  const qKhanh = quote(
    TRANG,
    {
      leadId: leadKhanh,
      unitCode: 'ZEN-A-0803',
      transactionDate: '2026-09-24',
      customerSegment: 'EXISTING_RESIDENT',
      unitsQuantity: 2,
      selectedRuleCodes: ['EARLY_PAY_DISCOUNT', 'BULK_PURCHASE_DISCOUNT', 'SMARTHOME_GIFT'],
      objective: 'MIN_NET_PRICE',
      customerName: 'Bùi Gia Khánh',
      customerPhone: '0909 118 623',
    },
    vn('2026-09-24', '11:05'),
  )
  submitQuoteRecord(db, TRANG, qKhanh, vn('2026-09-24', '11:06'))

  // 7. Bản nháp — khách vãng lai tại sàn, chưa gửi duyệt.
  quote(
    NAM,
    {
      leadId: null,
      unitCode: 'ZEN-A-1205',
      transactionDate: '2026-09-25',
      customerSegment: 'NEW_CUSTOMER',
      unitsQuantity: 1,
      selectedRuleCodes: ['SMARTHOME_GIFT', 'FURNITURE_GIFT'],
      objective: 'MAX_BENEFIT_VALUE',
      customerName: 'Đặng Quang Vinh',
      customerPhone: '0938 771 002',
    },
    vn('2026-09-25', '09:20'),
  )

  return db
}
