import { describe, expect, it } from 'vitest'

import {
  alignRow,
  isNumericCell,
  isWideColumn,
  splitGluedTables,
  stripCellEmphasis,
  stripColumnMark,
} from './markdownTables'

const GLUED =
  'Em đã lọc giỏ hàng The Zen Park: hiện có **3 căn** đáp ứng. ' +
  '| Mã căn | Phòng ngủ | Diện tích | Giá niêm yết (trước thuế) | |---|---|---|---| ' +
  '| **ZEN-B-0803** | 3PN | 98.0 m² | **3.800.000.000 ₫** | ' +
  '| **ZEN-C-1501** | 3PN | 105.5 m² | **4.200.000.000 ₫** | ' +
  '➡️ Tổng cộng giỏ hàng The Zen Park có **4 căn**.'

describe('splitGluedTables', () => {
  it('tách bảng dính câu văn về đúng dòng của nó', () => {
    const lines = splitGluedTables(GLUED).split('\n')
    expect(lines[0]).toBe('Em đã lọc giỏ hàng The Zen Park: hiện có **3 căn** đáp ứng.')
    expect(lines[1]).toBe('')
    expect(lines[2]).toBe('| Mã căn | Phòng ngủ | Diện tích | Giá niêm yết (trước thuế) |')
    expect(lines[3]).toBe('|---|---|---|---|')
    expect(lines[4]).toBe('| **ZEN-B-0803** | 3PN | 98.0 m² | **3.800.000.000 ₫** |')
    expect(lines[5]).toBe('| **ZEN-C-1501** | 3PN | 105.5 m² | **4.200.000.000 ₫** |')
    expect(lines[7]).toBe('➡️ Tổng cộng giỏ hàng The Zen Park có **4 căn**.')
  })

  it('giữ nguyên bảng đã đúng định dạng', () => {
    const good =
      'Có 2 căn:\n\n| Mã căn | Giá |\n| --- | --- |\n| A | 2 tỷ |\n| B | 3 tỷ |\n'
    expect(splitGluedTables(good)).toBe(good)
  })

  it('tách khi tiêu đề dính câu văn nhưng hàng phân cách ở dòng dưới', () => {
    const out = splitGluedTables('Có 2 căn phù hợp: | Mã căn | Giá |\n|---|---|\n| A | 2 tỷ |').split('\n')
    expect(out[0]).toBe('Có 2 căn phù hợp:')
    expect(out[2]).toBe('| Mã căn | Giá |')
  })

  it('không đụng tới văn bản không có bảng', () => {
    const text = 'Phân khúc 3PN hiện có 1 căn, giá mềm nhất 6,1 tỷ.'
    expect(splitGluedTables(text)).toBe(text)
  })
})

describe('ô bảng', () => {
  it('bỏ đậm trong ô', () => {
    expect(stripCellEmphasis('**3.800.000.000 ₫**')).toBe('3.800.000.000 ₫')
  })

  it('nhận diện ô số để canh phải', () => {
    expect(isNumericCell('**3.800.000.000 ₫**')).toBe(true)
    expect(isNumericCell('98.0 m²')).toBe(true)
    expect(isNumericCell('31.8%')).toBe(true)
    expect(isNumericCell('3PN')).toBe(false)
    expect(isNumericCell('ZEN-B-0803')).toBe(false)
    expect(isNumericCell('Mã căn')).toBe(false)
  })
})

describe('cột mở rộng cho màn hình rộng', () => {
  it('nhận diện và bóc dấu * của cột mở rộng', () => {
    expect(isWideColumn('Tầng*')).toBe(true)
    expect(isWideColumn('View*')).toBe(true)
    expect(isWideColumn('Mã căn')).toBe(false)
    expect(isWideColumn('Dự án')).toBe(false)
    expect(stripColumnMark('Tầng*')).toBe('Tầng')
    expect(stripColumnMark('View*')).toBe('View')
    expect(stripColumnMark('Mã căn')).toBe('Mã căn')
  })

  it('cột cơ bản không bị coi là cột mở rộng', () => {
    // Tránh nhầm với ô in đậm `**…**` còn sót trong tiêu đề.
    expect(isWideColumn('Giá niêm yết (trước thuế)')).toBe(false)
    expect(isWideColumn('**')).toBe(false)
  })
})

describe('alignRow', () => {
  it('bù ô trống khi hàng thiếu ô (chống lệch cột)', () => {
    expect(alignRow(['A', '2PN'], 4)).toEqual(['A', '2PN', '', ''])
  })

  it('cắt ô thừa khi hàng nhiều hơn tiêu đề', () => {
    expect(alignRow(['A', 'B', 'C'], 2)).toEqual(['A', 'B'])
  })

  it('giữ nguyên hàng đã đúng số cột', () => {
    const row = ['A', 'B', 'C']
    expect(alignRow(row, 3)).toBe(row)
  })
})
