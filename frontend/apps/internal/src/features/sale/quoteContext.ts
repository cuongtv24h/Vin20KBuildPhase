/**
 * Ngữ cảnh cho luồng lập báo giá (chốt đợt 20 — lỗi #16).
 *
 * Lỗi người dùng bắt được: sau khi bấm "Chọn PA vay 0%", thẻ **"Xác nhận tham số tạo báo giá"** vẫn ghi
 * *"Chưa chọn căn — chọn trên card báo giá"* dù mã căn nằm ngay trong lượt trò chuyện trước đó.
 *
 * Nguyên nhân: chỉ thẻ Copilot có mã căn, còn luồng xác nhận lại đọc **duy nhất** `hồ sơ khách`.
 * Từ nay mọi luồng (thẻ xác nhận, nút trong ngăn hồ sơ, chip gợi ý) dùng chung một hàm giải mã căn theo
 * thứ tự ưu tiên: căn của lượt gọi ⇒ căn ngữ cảnh phiên ⇒ căn trong hồ sơ khách ⇒ `null`.
 *
 * Không bao giờ trả về một mã căn "mẫu" khi chưa có ngữ cảnh — thà hỏi lại Sale còn hơn báo giá nhầm căn.
 */

/** Mã căn của dự án (ví dụ `SAP-D-4201`, `ZEN-A-1205`) hoặc căn thấp tầng (`G-03.02`, `SH-01`). */
export const UNIT_CODE_PATTERN = /\b([A-Z]{2,4}-[A-Z0-9]{1,3}-\d{3,4}|[A-Z]{1,3}-\d{2}\.\d{2})\b/i

/** Bóc mã căn Sale gõ trong ô chat ('' nghĩa là câu không nhắc căn nào). */
export function extractUnitCodeFromText(text: string): string | null {
  const match = UNIT_CODE_PATTERN.exec(text || '')
  return match ? match[1].toUpperCase() : null
}

/** Ngữ cảnh hiện có để suy ra căn của báo giá. */
export interface QuoteUnitContext {
  /** Căn gắn với hành động đang bấm (ví dụ `data.unit_code` của thẻ so sánh phương án). */
  actionUnit?: string | null
  /** Căn đang mở trong phiên Copilot (bóc từ câu hỏi gần nhất). */
  sessionUnit?: string | null
  /** Căn trong ràng buộc hồ sơ khách đang chọn. */
  leadUnit?: string | null
}

/** Căn dùng để lập báo giá, hoặc `null` khi thật sự chưa có ngữ cảnh nào. */
export function resolveQuoteUnitCode(context: QuoteUnitContext): string | null {
  const candidates = [context.actionUnit, context.sessionUnit, context.leadUnit]
  for (const candidate of candidates) {
    const code = (candidate || '').trim()
    if (code) return code.toUpperCase()
  }
  return null
}

/** Nhãn hiển thị trên thẻ xác nhận khi chưa có căn — chỉ dùng khi `resolveQuoteUnitCode` trả `null`. */
export const NO_UNIT_LABEL = 'Chưa chọn căn — chọn trên card báo giá'

/**
 * Khách hàng của báo giá: tên hồ sơ đang chọn, hoặc khách vừa tạo trong phiên.
 * Không có cả hai ⇒ để trống cho Sale tự chọn, không lấy tên khách mẫu.
 */
export function resolveQuoteCustomerName(
  primaryName?: string | null,
  fallbackName?: string | null,
): string {
  return (primaryName || fallbackName || '').trim()
}
