// @vitest-environment node
import { describe, expect, it } from 'vitest'

import {
  NO_UNIT_LABEL,
  extractUnitCodeFromText,
  resolveQuoteCustomerName,
  resolveQuoteUnitCode,
} from './quoteContext'

describe('Ngữ cảnh căn cho luồng lập báo giá (lỗi #16)', () => {
  it('lấy mã căn Sale vừa gõ trong ô chat', () => {
    expect(extractUnitCodeFromText('phương án thanh toán cho căn SAP-D-4201 với 2 tỷ')).toBe('SAP-D-4201')
    expect(extractUnitCodeFromText('so sánh giúp em căn G-03.02')).toBe('G-03.02')
    expect(extractUnitCodeFromText('tư vấn cho khách 3 ngủ')).toBeNull()
  })

  it('ưu tiên căn của hành động rồi tới ngữ cảnh phiên, cuối cùng là hồ sơ khách', () => {
    expect(resolveQuoteUnitCode({ actionUnit: 'SAP-D-4201', sessionUnit: 'ZEN-A-1205', leadUnit: 'ZEN-B-1502' }))
      .toBe('SAP-D-4201')
    expect(resolveQuoteUnitCode({ actionUnit: null, sessionUnit: 'ZEN-A-1205', leadUnit: 'ZEN-B-1502' }))
      .toBe('ZEN-A-1205')
    expect(resolveQuoteUnitCode({ actionUnit: '', sessionUnit: '', leadUnit: 'ZEN-B-1502' })).toBe('ZEN-B-1502')
  })

  it('không có ngữ cảnh nào thì trả null — không mượn mã căn mẫu', () => {
    expect(resolveQuoteUnitCode({})).toBeNull()
    expect(resolveQuoteUnitCode({ actionUnit: '  ', sessionUnit: null, leadUnit: undefined })).toBeNull()
    expect(NO_UNIT_LABEL).toContain('Chưa chọn căn')
  })

  it('chuẩn hoá mã căn viết thường thành chữ hoa', () => {
    expect(resolveQuoteUnitCode({ sessionUnit: 'sap-d-4201' })).toBe('SAP-D-4201')
  })
})

describe('Khách hàng của báo giá', () => {
  it('lấy khách đang chọn, hoặc khách vừa nhắc tới', () => {
    expect(resolveQuoteCustomerName('Chu Thúy Quỳnh', 'Hà My')).toBe('Chu Thúy Quỳnh')
    expect(resolveQuoteCustomerName(null, 'Hà My')).toBe('Hà My')
  })

  it('chưa biết khách thì để trống, không lấy tên mẫu', () => {
    expect(resolveQuoteCustomerName()).toBe('')
  })
})
