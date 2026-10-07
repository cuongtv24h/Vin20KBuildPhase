/**
 * `copilotHistory` — dựng payload lưu lượt và biến câu trả lời thành văn bản gửi khách.
 *
 * Ba trường mới phải đi cùng hội thoại, nếu không khi mở lại lịch sử sẽ mất: mỏ neo `[n]` (bấm mở
 * được căn cứ), ghi chú kiểm duyệt nội bộ, và mốc thời gian dữ liệu (chốt P2.1 · P2.4 · P1.6).
 */
import { describe, expect, it } from 'vitest'

import { customerReadyText, turnToAppendPayload } from './copilotHistory'


// ─── P1.6 · P2.1 · P2.4: ba trường phải sống cùng hội thoại ─────────────────

describe('turnToAppendPayload — ghi kèm dữ liệu hiển thị lại', () => {
  it('mang theo mỏ neo, ghi chú nội bộ và mốc thời gian dữ liệu', () => {
    const payload = turnToAppendPayload({
      conversationId: 'CNV-1',
      question: 'còn căn 3 ngủ không?',
      final: {
        reply: 'Còn 1 căn 3 ngủ[1].',
        citations: [{ policy_id: 'CATALOG-UNITS' }],
        action_type: null,
        internal_notes: 'có số liệu chưa đối chiếu được (2 tỷ)',
        anchors: [{ index: 1, value: '6,1 tỷ', citation_index: 0, label: 'CATALOG-UNITS · Căn ZEN-B-1502' }],
        data_as_of: '2026-10-02T13:29:19+00:00',
      },
    })
    expect(payload.internal_notes).toBe('có số liệu chưa đối chiếu được (2 tỷ)')
    expect(payload.anchors).toHaveLength(1)
    expect(payload.anchors?.[0].label).toContain('ZEN-B-1502')
    expect(payload.data_as_of).toBe('2026-10-02T13:29:19+00:00')
  })

  it('thiếu trường thì để mặc định an toàn (không undefined)', () => {
    const payload = turnToAppendPayload({
      conversationId: null,
      question: 'xin chào',
      final: { reply: 'Dạ em chào anh/chị.', citations: [], action_type: null },
    })
    expect(payload.internal_notes).toBe('')
    expect(payload.anchors).toEqual([])
    expect(payload.data_as_of).toBeNull()
  })
})

describe('customerReadyText — văn bản gửi thẳng cho khách', () => {
  it('bỏ mỏ neo, nhãn số của Sale và ký hiệu markdown', () => {
    const text = customerReadyText(
      'Với ngân sách **2 tỷ** (ngân sách anh/chị nhập), chưa có căn nào khớp[1].\n\n' +
        'Căn 3PN mềm nhất là **ZEN-B-1502** giá 6,1 tỷ[2].',
    )
    expect(text).toBe(
      'Với ngân sách 2 tỷ, chưa có căn nào khớp.\n\n' +
        'Căn 3PN mềm nhất là ZEN-B-1502 giá 6,1 tỷ.',
    )
  })

  it('giữ nguyên nội dung khi không có gì để bỏ', () => {
    expect(customerReadyText('Dạ 8.0% theo chính sách đang hiệu lực.')).toBe(
      'Dạ 8.0% theo chính sách đang hiệu lực.',
    )
  })
})
