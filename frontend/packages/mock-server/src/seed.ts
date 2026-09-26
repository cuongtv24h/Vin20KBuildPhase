import type { StaffUser, TransactionContext } from '@pricepolicy/api-client/contracts'
import { SCHEMA_VERSION, type MockDb } from './db'
import { POLICIES_FIXTURE } from './fixtures/policies'
import { UNITS_FIXTURE } from './fixtures/units'
import { actorOf, STAFF_FIXTURE } from './fixtures/users'
import { confirmConstraints, convertDossier, createSession, generatePlan, handoff, receiveMessage } from './services/presales'
import { createQuote, createVersion, decideQuote, findRecord, settle, submitQuote } from './services/quotes'

const staff = (id: string): StaffUser => {
  const u = STAFF_FIXTURE.find((x) => x.user_id === id)
  if (!u) throw new Error(`Seed: thiếu ${id}`)
  return u
}
const NAM = staff('USR-SALE-001')
const TRANG = staff('USR-SALE-002')
const HA = staff('USR-MGR-001')

const MIN = 60_000
const HOUR = 60 * MIN
const day = (ms: number) => new Date(ms).toISOString().slice(0, 10)
const ANALYSIS_DONE = 10_000

/**
 * Dữ liệu vận hành mẫu, dựng bằng chính các service của backend giả lập (không ghi tay JSON)
 * nên mọi hồ sơ nhất quán với luồng thật: hash chain, SSE event log, phiên bản.
 */
export async function buildSeedState(now = Date.now()): Promise<MockDb> {
  const db: MockDb = {
    schema_version: SCHEMA_VERSION,
    units: UNITS_FIXTURE.map((u) => ({ ...u })),
    policies: structuredClone(POLICIES_FIXTURE),
    quotes: [],
    dossiers: [],
    presales: [],
    presales_pending: {},
    presales_events: {},
    auth: {},
    reauth: {},
    idempotency: {},
    checks: {},
    counters: {},
  }

  // ─── Hồ sơ khách từ Pre-Sales (F6/F7) ────────────────────────────────────
  async function dossierFrom(at: number, unit: string | null, messages: string[], customer: { full_name: string; phone: string }, sale: StaffUser) {
    const s = createSession(db, unit, at)
    for (const m of messages) receiveMessage(db, s, m, at)
    confirmConstraints(db, s, s.constraints, at + MIN)
    await generatePlan(db, s, at + MIN)
    const receipt = handoff(db, s, { ...customer, consent: true, consent_text_version: 'consent-v1' }, at + 2 * MIN)
    const dossier = db.dossiers.find((d) => d.dossier_id === receipt.dossier_id)
    if (dossier) dossier.assigned_sale = actorOf(sale)
    return receipt.dossier_id
  }

  await dossierFrom(
    now - 25 * MIN,
    'ZEN-A-1205',
    ['Tôi có sẵn 1,5 tỷ, trả góp được 30 triệu/tháng', 'Tôi đã mua căn của VLandFuture', 'Giá mua thấp nhất'],
    { full_name: 'Nguyễn Văn An', phone: '0912 345 678' },
    NAM,
  )
  await dossierFrom(
    now - 3 * HOUR,
    null,
    ['The Zen Park, căn 3PN', 'Vốn tự có 1,2 tỷ, mỗi tháng trả được 25 triệu', 'Đây là lần đầu tôi mua', 'Trả trước ít nhất'],
    { full_name: 'Trần Thị Bích', phone: '0905 667 312' },
    NAM,
  )
  await dossierFrom(
    now - 30 * HOUR,
    'ZEN-A-0803',
    ['Vốn 600 triệu, 15 triệu/tháng', 'Khách mới', 'Nhiều quà tặng nhất'],
    { full_name: 'Vũ Hải Đăng', phone: '0983 004 771' },
    NAM,
  )
  await dossierFrom(
    now - 5 * HOUR,
    'SAP-D-2604',
    ['Tôi có 2 tỷ, trả 40 triệu/tháng', 'Đã sở hữu căn VLandFuture', 'Trả trước ít nhất'],
    { full_name: 'Đỗ Minh Châu', phone: '0868 225 190' },
    TRANG,
  )
  const huyDossier = await dossierFrom(
    now - 50 * HOUR,
    'SAP-C-2201',
    ['Tôi có sẵn 9 tỷ, 50 triệu/tháng', 'Đã mua căn của VLandFuture', 'Giá mua thấp nhất'],
    { full_name: 'Phạm Quốc Huy', phone: '0918 456 221' },
    NAM,
  )

  // ─── Hồ sơ báo giá ở đủ trạng thái ───────────────────────────────────────
  const ctx = (c: Partial<TransactionContext> & Pick<TransactionContext, 'unit_code' | 'customer_name' | 'customer_phone'>, at: number): TransactionContext => ({
    transaction_date: day(at),
    customer_segment: 'NEW_CUSTOMER',
    units_quantity: 1,
    selected_rule_codes: [],
    objective: 'MIN_NET_PRICE',
    requested_policy_id: null,
    ...c,
  })
  const done = async (at: number) => settle(db, at + ANALYSIS_DONE)

  // 1. Đã duyệt, PDF đã phát hành (từ hồ sơ khách Phạm Quốc Huy).
  let t = now - 48 * HOUR
  const huy = await convertDossier(
    db,
    NAM,
    huyDossier,
    ctx({ unit_code: 'SAP-C-2201', customer_name: 'Phạm Quốc Huy', customer_phone: '0918 456 221', customer_segment: 'EXISTING_RESIDENT', selected_rule_codes: ['EARLY_PAY_DISCOUNT', 'MANAGEMENT_FEE_GIFT'] }, t),
    t,
  )
  await done(t)
  await submitQuote(db, NAM, findRecord(db, huy.quote_id), t + 2 * MIN)
  await decideQuote(db, HA, findRecord(db, huy.quote_id), 'APPROVED', 'Đúng chính sách Sapphire v1.0.', t + 40 * MIN)
  await settle(db, t + 50 * MIN)

  // 2. Quản lý yêu cầu sửa v1 → Sale lập v2 (v1 chỉ đọc) → chờ duyệt.
  t = now - 26 * HOUR
  const mai = await createQuote(
    db,
    NAM,
    ctx({ unit_code: 'ZEN-B-0301', customer_name: 'Lý Thanh Mai', customer_phone: '0937 880 145', selected_rule_codes: ['SMARTHOME_GIFT', 'BULK_PURCHASE_DISCOUNT'] }, t),
    null,
    t,
  )
  await done(t)
  await submitQuote(db, NAM, findRecord(db, mai.quote_id), t + MIN)
  await decideQuote(db, HA, findRecord(db, mai.quote_id), 'REVISION_REQUESTED', 'Khách đăng ký mua 2 căn — cập nhật số lượng căn = 2 để áp dụng chiết khấu mua sỉ Điều 5.', t + 30 * MIN)
  const maiV2 = t + 2 * HOUR
  await createVersion(
    db,
    NAM,
    findRecord(db, mai.quote_id),
    ctx({ unit_code: 'ZEN-B-0301', customer_name: 'Lý Thanh Mai', customer_phone: '0937 880 145', units_quantity: 2, selected_rule_codes: ['SMARTHOME_GIFT', 'BULK_PURCHASE_DISCOUNT'] }, t),
    maiV2,
  )
  await done(maiV2)
  await submitQuote(db, NAM, findRecord(db, mai.quote_id), maiV2 + MIN)

  // 3. Chờ duyệt — cờ vàng (tổng ưu đãi 12%).
  t = now - 6 * HOUR
  const khanh = await createQuote(
    db,
    TRANG,
    ctx({ unit_code: 'ZEN-A-0803', customer_name: 'Bùi Gia Khánh', customer_phone: '0909 118 623', customer_segment: 'EXISTING_RESIDENT', units_quantity: 2, selected_rule_codes: ['EARLY_PAY_DISCOUNT', 'BULK_PURCHASE_DISCOUNT', 'SMARTHOME_GIFT'] }, t),
    null,
    t,
  )
  await done(t)
  await submitQuote(db, TRANG, findRecord(db, khanh.quote_id), t + MIN)

  // 4. Dừng an toàn — chọn 2 ưu đãi loại trừ nhau (Điều 6.2) → hàng đợi ngoại lệ của Quản lý.
  t = now - 4 * HOUR
  await createQuote(
    db,
    NAM,
    ctx({ unit_code: 'ZEN-B-1502', customer_name: 'Đặng Quang Vinh', customer_phone: '0938 771 002', objective: 'MAX_BENEFIT_VALUE', selected_rule_codes: ['EARLY_PAY_DISCOUNT', 'FURNITURE_GIFT'] }, t),
    null,
    t,
  )
  await done(t)

  // 5. Bị từ chối.
  t = now - 20 * HOUR
  const vy = await createQuote(
    db,
    TRANG,
    ctx({ unit_code: 'SAP-D-0905', customer_name: 'Ngô Thảo Vy', customer_phone: '0976 312 908', objective: 'MIN_INITIAL_OUTFLOW', selected_rule_codes: ['BANK_LOAN_HTLS'] }, t),
    null,
    t,
  )
  await done(t)
  await submitQuote(db, TRANG, findRecord(db, vy.quote_id), t + MIN)
  await decideQuote(db, HA, findRecord(db, vy.quote_id), 'REJECTED', 'Căn đã có khách đặt giữ chỗ trước, đề nghị tư vấn căn khác.', t + 3 * HOUR)

  // 6. Hồ sơ do chính Quản lý lập hộ — không được tự duyệt (SoD).
  t = now - 2 * HOUR
  const walkIn = await createQuote(
    db,
    HA,
    ctx({ unit_code: 'ZEN-B-2207', customer_name: 'Lâm Chí Thành', customer_phone: '0977 334 556', selected_rule_codes: ['SMARTHOME_GIFT'] }, t),
    null,
    t,
  )
  await done(t)
  await submitQuote(db, HA, findRecord(db, walkIn.quote_id), t + MIN)

  await settle(db, now)
  return db
}
