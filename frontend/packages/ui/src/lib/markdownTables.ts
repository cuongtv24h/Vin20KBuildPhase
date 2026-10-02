/**
 * Tiện ích dựng bảng markdown cho câu trả lời AI — thuần chuỗi, không phụ thuộc React.
 *
 * Vì sao cần: model ngôn ngữ hay viết bảng **dính vào câu văn**
 * (`... đáp ứng. | Mã căn | Phòng ngủ | ... |`) hoặc bỏ đậm từng ô. Bộ hiển thị markdown nhận bảng
 * theo *dòng* bắt đầu bằng `|`, nên bảng dính sẽ hiện ra như một cục chữ có gạch dọc.
 *
 * Backend đã chuẩn hoá (`src/agents/copilot/reply_format.py`) cho câu trả lời mới; lớp này lo phần
 * **dữ liệu cũ đã lưu** và là lưới an toàn nếu model vẫn viết ẩu:
 * - `splitGluedTables`: tách bảng dính về đúng dòng của nó.
 * - `stripCellEmphasis`: bỏ `**` trong ô bảng (bảng vốn đã có kẻ ô).
 * - `isNumericCell`: nhận diện ô số để canh phải, dễ so sánh theo cột.
 */

const DIVIDER_CELL = ':?-{2,}:?'
const DIVIDER_RE = new RegExp(`\\|?\\s*${DIVIDER_CELL}\\s*(?:\\|\\s*${DIVIDER_CELL}\\s*)+\\|?`)
const DIVIDER_ONLY_RE = new RegExp(`^\\|?\\s*${DIVIDER_CELL}\\s*(?:\\|\\s*${DIVIDER_CELL}\\s*)*\\|?$`)
const FENCE_RE = /^\s*```/
const NUMBER_CELL_RE = /^[-+]?\d[\d.,]*\s*(₫|%|m²|m2|tỷ|triệu|tr|năm)?$/i

/** Số cột suy ra từ hàng phân cách `|---|---|` (có thể không có gạch dọc ngoài cùng). */
function dividerColumns(divider: string): number {
  const text = divider.trim()
  const pipes = (text.match(/\|/g) ?? []).length
  if (text.startsWith('|') && text.endsWith('|')) return pipes - 1
  return pipes + 1
}

function pipeIndexes(line: string): number[] {
  const indexes: number[] = []
  for (let i = 0; i < line.length; i += 1) {
    if (line[i] === '|') indexes.push(i)
  }
  return indexes
}

interface GluedParts {
  prefix: string
  block: string[]
  suffix: string
}

function splitGluedLine(line: string): GluedParts | null {
  const match = DIVIDER_RE.exec(line)
  if (!match) return null

  const columns = dividerColumns(match[0])
  if (columns < 1) return null
  const perRow = columns + 1

  const pipes = pipeIndexes(line)
  const head = pipes.filter((p) => p < match.index)
  const tail = pipes.filter((p) => p >= match.index + match[0].length)
  if (head.length < perRow || tail.length < perRow) return null

  const headPipes = head.slice(-perRow)
  const rows: number[][] = []
  for (let i = 0; i + perRow <= tail.length; i += perRow) {
    rows.push(tail.slice(i, i + perRow))
  }
  if (!rows.length) return null

  let divider = match[0].trim()
  if (!divider.startsWith('|')) divider = `|${divider}`
  if (!divider.endsWith('|')) divider = `${divider}|`

  return {
    prefix: line.slice(0, headPipes[0]).trim(),
    block: [
      line.slice(headPipes[0], headPipes[headPipes.length - 1] + 1).trim(),
      divider,
      ...rows.map((row) => line.slice(row[0], row[row.length - 1] + 1).trim()),
    ],
    suffix: line.slice(rows[rows.length - 1][rows[rows.length - 1].length - 1] + 1).trim(),
  }
}

/** Tách mọi bảng bị viết dính câu văn về đúng dòng, kèm dòng trống trước/sau. */
export function splitGluedTables(raw: string): string {
  if (!raw || !raw.includes('|')) return raw
  const lines = raw.split(/\r?\n/)
  const out: string[] = []
  let inFence = false

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    if (FENCE_RE.test(line)) {
      inFence = !inFence
      out.push(line)
      continue
    }
    if (inFence || !line.trim() || !line.includes('|')) {
      out.push(line)
      continue
    }

    const parts = splitGluedLine(line)
    if (parts) {
      if (parts.prefix) out.push(parts.prefix, '')
      out.push(...parts.block)
      if (parts.suffix) out.push('', parts.suffix)
      continue
    }

    // Tiêu đề bảng dính câu văn nhưng hàng phân cách nằm ở dòng dưới.
    const next = lines[index + 1] ?? ''
    if (DIVIDER_ONLY_RE.test(next.trim()) && next.includes('-')) {
      const columns = dividerColumns(next)
      const perRow = columns + 1
      const pipes = pipeIndexes(line)
      if (columns >= 1 && pipes.length >= perRow) {
        const headPipes = pipes.slice(-perRow)
        const header = line.slice(headPipes[0], headPipes[headPipes.length - 1] + 1).trim()
        const prefix = line.slice(0, headPipes[0]).trim()
        if (prefix) out.push(prefix, '')
        out.push(header)
        continue
      }
    }

    out.push(line)
  }

  return out.join('\n')
}

/** Ô bảng không cần đậm — bảng đã có kẻ ô phân cách cột. */
export function stripCellEmphasis(cell: string): string {
  return cell.replace(/\*\*/g, '').trim()
}

/** Ô số (tiền, phần trăm, diện tích) → canh phải và dùng chữ số đều nhau cho dễ so sánh. */
export function isNumericCell(cell: string): boolean {
  return NUMBER_CELL_RE.test(stripCellEmphasis(cell))
}
