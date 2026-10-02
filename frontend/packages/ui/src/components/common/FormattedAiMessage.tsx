import { useMemo, type ReactNode } from 'react'
import { cn } from '@pricepolicy/ui/lib/utils'

/** Một mỏ neo `[n]` trong câu trả lời (máy tự chèn — xem `src/agents/copilot/anchors.py`). */
export interface AiAnchor {
  index: number
  /** Nhãn nguồn hiển thị ở tooltip, ví dụ `CATALOG-UNITS · Căn ZEN-B-1502`. */
  label?: string
}

interface FormattedAiMessageProps {
  content: string
  className?: string
  onCommandClick?: (command: string) => void
  /** Mỏ neo có trong câu trả lời — bấm `[n]` sẽ mở đúng căn cứ (chốt P2.1). */
  anchors?: AiAnchor[]
  onAnchorClick?: (anchor: AiAnchor) => void
}

/**
 * Hiển thị câu trả lời của AI một cách trực quan, phân tách ngữ nghĩa rõ ràng:
 * - Tiêu đề đề mục (Headers ###, ##, #) có thanh điểm nhấn
 * - Bảng so sánh (Markdown Table | Col 1 | Col 2 |) có kẻ ô, màu nền xen kẽ
 * - Danh sách gạch đầu dòng (- / * / •) có icon bullet màu nhấn
 * - Danh sách số (1. 2. 3.) có huy hiệu số thứ tự tròn
 * - Trích dẫn/Căn cứ pháp lý (> Blockquote)
 * - Lệnh tắt (/tao-khach, /baogia...) hiển thị dạng nút bấm tương tác (clickable pill)
 * - Mỏ neo [n] hiển thị dạng chip nhỏ bấm mở căn cứ (Trust Engine cho Sale)
 */
export function FormattedAiMessage({
  content,
  className,
  onCommandClick,
  anchors,
  onAnchorClick,
}: FormattedAiMessageProps) {
  const blocks = useMemo(() => parseMarkdownBlocks(content), [content])
  const render = (text: string) => renderInlineText(text, onCommandClick, anchors, onAnchorClick)

  return (
    <div className={cn('space-y-2 text-xs leading-relaxed text-foreground', className)}>
      {blocks.map((block, idx) => renderBlock(block, idx, render))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Block Parsing Types & Logic
// ---------------------------------------------------------------------------

type Block =
  | { type: 'header'; level: number; text: string }
  | { type: 'table'; headers: string[]; rows: string[][] }
  | { type: 'quote'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: { num: string; text: string }[] }
  | { type: 'paragraph'; text: string }

function parseMarkdownBlocks(rawText: string): Block[] {
  if (!rawText) return []
  const lines = rawText.split(/\r?\n/)
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    // 1. Dòng trống
    if (!trimmed) {
      i++
      continue
    }

    // 2. Headers (#, ##, ###)
    const headerMatch = trimmed.match(/^(#{1,4})\s+(.+)$/)
    if (headerMatch) {
      blocks.push({
        type: 'header',
        level: headerMatch[1].length,
        text: headerMatch[2],
      })
      i++
      continue
    }

    // 3. Blockquote (> ...)
    if (trimmed.startsWith('>')) {
      const quoteLines: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s*/, ''))
        i++
      }
      blocks.push({
        type: 'quote',
        text: quoteLines.join(' '),
      })
      continue
    }

    // 4. Markdown Table (| col 1 | col 2 |)
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && trimmed.includes('|')) {
      const tableLines: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        tableLines.push(lines[i].trim())
        i++
      }
      if (tableLines.length >= 2) {
        const parseRow = (r: string) =>
          r
            .slice(1, -1)
            .split('|')
            .map((c) => c.trim())

        const headers = parseRow(tableLines[0])
        // Bỏ qua hàng phân cách |--|--| nếu có
        const dataRows = tableLines.slice(1).filter((l) => !/^\|[\s\-:|]+\|$/.test(l))
        const rows = dataRows.map(parseRow)

        blocks.push({
          type: 'table',
          headers,
          rows,
        })
        continue
      }
    }

    // 5. Unordered List (- , * , • )
    if (/^[-*•]\s+/.test(trimmed)) {
      const items: string[] = []
      while (i < lines.length && /^[-*•]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*•]\s+/, ''))
        i++
      }
      blocks.push({
        type: 'ul',
        items,
      })
      continue
    }

    // 6. Ordered List (1. , 2. )
    if (/^\d+\.\s+/.test(trimmed)) {
      const items: { num: string; text: string }[] = []
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        const m = lines[i].trim().match(/^(\d+)\.\s+(.+)$/)
        if (m) {
          items.push({ num: m[1], text: m[2] })
        }
        i++
      }
      blocks.push({
        type: 'ol',
        items,
      })
      continue
    }

    // 7. Đoạn văn thường (Paragraph)
    const pLines: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().match(/^(#{1,4})\s+/) &&
      !lines[i].trim().startsWith('>') &&
      !(lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) &&
      !/^[-*•]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim())
    ) {
      pLines.push(lines[i])
      i++
    }
    if (pLines.length > 0) {
      blocks.push({
        type: 'paragraph',
        text: pLines.join('\n'),
      })
    }
  }

  return blocks
}

// ---------------------------------------------------------------------------
// Block Rendering
// ---------------------------------------------------------------------------

type InlineRenderer = (text: string) => ReactNode

function renderBlock(block: Block, key: number, render: InlineRenderer): ReactNode {
  switch (block.type) {
    case 'header': {
      if (block.level === 1 || block.level === 2) {
        return (
          <div key={key} className="mt-3.5 mb-1.5 flex items-center gap-2 border-b border-border/60 pb-1">
            <span className="h-3.5 w-1 rounded-full bg-primary" />
            <h4 className="font-semibold text-xs tracking-tight text-foreground uppercase">{render(block.text)}</h4>
          </div>
        )
      }
      return (
        <div key={key} className="mt-2.5 mb-1 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-primary/70" />
          <h5 className="font-medium text-xs text-foreground">{render(block.text)}</h5>
        </div>
      )
    }

    case 'table': {
      return (
        <div key={key} className="my-2.5 overflow-x-auto rounded-lg border border-border bg-card/60 shadow-xs">
          <table className="w-full border-collapse text-[11px]">
            <thead>
              <tr className="border-b border-border bg-muted/50 text-left font-semibold text-muted-foreground">
                {block.headers.map((h, hi) => (
                  <th key={hi} className="px-2.5 py-1.5 whitespace-nowrap">
                    {render(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {block.rows.map((row, ri) => (
                <tr key={ri} className="transition-colors hover:bg-muted/20">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-2.5 py-1.5">
                      {render(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    case 'quote': {
      return (
        <blockquote
          key={key}
          className="my-2 rounded-r-md border-l-2 border-primary bg-primary/[0.04] px-3 py-1.5 text-[11px] text-muted-foreground italic"
        >
          {render(block.text)}
        </blockquote>
      )
    }

    case 'ul': {
      return (
        <ul key={key} className="my-1.5 space-y-1 pl-1">
          {block.items.map((item, ii) => (
            <li key={ii} className="flex items-start gap-2 leading-relaxed">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/70" />
              <div className="flex-1">{render(item)}</div>
            </li>
          ))}
        </ul>
      )
    }

    case 'ol': {
      return (
        <ol key={key} className="my-1.5 space-y-1.5 pl-0.5">
          {block.items.map((item, ii) => (
            <li key={ii} className="flex items-start gap-2 leading-relaxed">
              <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[9.5px] font-bold text-primary mt-0.5">
                {item.num}
              </span>
              <div className="flex-1">{render(item.text)}</div>
            </li>
          ))}
        </ol>
      )
    }

    case 'paragraph': {
      return (
        <p key={key} className="leading-relaxed whitespace-pre-line text-foreground/90">
          {render(block.text)}
        </p>
      )
    }
  }
}

// ---------------------------------------------------------------------------
// Inline Parsing (Bold, Italic, Code, Slash Commands, Highlights)
// Danh sách các lệnh tắt chính thức được phép hiển thị dạng nút bấm
const KNOWN_SLASH_COMMANDS = new Set([
  '/tao-khach',
  '/tim-khach',
  '/khach-hang',
  '/baogia',
  '/chinh-sach',
  '/tinh-lai',
  '/soan-tin',
])

function renderInlineText(
  text: string,
  onCommandClick?: (cmd: string) => void,
  anchors?: AiAnchor[],
  onAnchorClick?: (anchor: AiAnchor) => void,
): ReactNode {
  if (!text) return null

  // Regex nhận diện các thành phần inline:
  // 1. Bold: \*\*(.*?)\*\*
  // 2. Italic: \*(.*?)\*
  // 3. Inline code: `(.*?)`
  // 4. Lệnh tắt chính thức: chỉ bắt khi đứng độc lập (có khoảng trắng hoặc đầu dòng phía trước),
  //    TUYỆT ĐỐI không bắt các từ tiếng Việt chứa dấu gạch chéo thông thường như 'anh/chị', 'm2/tháng', 'và/hoặc'
  const tokenRegex =
    /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[\d{1,2}\]|(?<=^|\s)\/(?:tao-khach|tim-khach|khach-hang|baogia|chinh-sach|tinh-lai|soan-tin)(?=\s|[.,;!?)]|$))/g

  const parts = text.split(tokenRegex)

  return parts.map((part, index) => {
    if (!part) return null

    // Bold **text**
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      const inner = part.slice(2, -2)
      return (
        <strong key={index} className="font-semibold text-foreground">
          {inner}
        </strong>
      )
    }

    // Italic *text*
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      const inner = part.slice(1, -1)
      return (
        <em key={index} className="italic text-foreground/90">
          {inner}
        </em>
      )
    }

    // Code `code`
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      const inner = part.slice(1, -1)
      return (
        <code key={index} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-primary">
          {inner}
        </code>
      )
    }

    // Mỏ neo [n] → chip bấm mở căn cứ (P2.1)
    const anchorMatch = /^\[(\d{1,2})\]$/.exec(part)
    if (anchorMatch) {
      const index = Number(anchorMatch[1])
      const meta = anchors?.find((a) => a.index === index)
      return (
        <button
          key={index}
          type="button"
          onClick={() => onAnchorClick?.({ index, label: meta?.label })}
          title={meta?.label ? `Mở căn cứ: ${meta.label}` : `Mở căn cứ [${index}]`}
          aria-label={meta?.label ? `Mở căn cứ: ${meta.label}` : `Mở căn cứ số ${index}`}
          className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full border border-primary/30 bg-primary/10 px-1 align-super text-[9.5px] font-semibold text-primary hover:bg-primary/20 transition-colors cursor-pointer"
        >
          {index}
        </button>
      )
    }

    // Slash command pill (chỉ áp dụng cho lệnh hệ thống hợp lệ)
    if (part.startsWith('/') && KNOWN_SLASH_COMMANDS.has(part.toLowerCase())) {
      return (
        <button
          key={index}
          type="button"
          onClick={() => onCommandClick?.(part)}
          title={`Bấm để dùng lệnh ${part}`}
          className="inline-flex items-center gap-1 mx-0.5 px-1.5 py-0.5 rounded-md bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 font-mono text-[11px] font-semibold transition-colors cursor-pointer select-none"
        >
          <span>⚡</span>
          <span>{part}</span>
        </button>
      )
    }

    return part
  })
}
