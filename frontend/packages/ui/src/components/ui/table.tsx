import * as React from 'react'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { cn } from '@pricepolicy/ui/lib/utils'

/** Phần tử tương tác trong dòng: bấm vào đây thì giữ hành vi riêng, không mở khung xem nhanh. */
const INTERACTIVE = 'a, button, input, select, textarea, label, [role="button"], [role="checkbox"], [role="switch"], [role="combobox"], [data-no-preview]'

const SVG_NS = 'http://www.w3.org/2000/svg'
const XHTML_NS = 'http://www.w3.org/1999/xhtml'

/** Chỉ những thẻ này được dựng lại trong khung xem nhanh; thẻ khác bị bỏ vỏ, giữ chữ bên trong. */
const HTML_TAGS = new Set(['div', 'span', 'p', 'b', 'strong', 'i', 'em', 'small', 'br', 'ul', 'ol', 'li', 'code', 'sub', 'sup'])
const SVG_TAGS = new Set(['svg', 'g', 'path', 'circle', 'ellipse', 'rect', 'line', 'polyline', 'polygon'])
/** Thẻ bị bỏ HẲN cả nội dung (chạy mã, nhúng nội dung ngoài, điều khiển tương tác, tham chiếu ngoài trong SVG). */
const DROP_TAGS = new Set([
  'script', 'style', 'iframe', 'frame', 'object', 'embed', 'template', 'noscript', 'link', 'meta', 'base', 'form',
  'button', 'input', 'select', 'textarea', 'img', 'audio', 'video', 'canvas', 'title',
  'use', 'foreignobject', 'image', 'animate', 'animatetransform', 'set', 'a',
])
const COMMON_ATTRS = new Set(['class', 'title', 'aria-label', 'aria-hidden'])
const SVG_ATTRS = new Set([
  'viewbox', 'd', 'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'width', 'height', 'points',
  'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'fill-rule', 'clip-rule', 'opacity', 'transform',
])

/** Giá trị thuộc tính an toàn: không có lược đồ thực thi / hàm CSS ngoài (cho phép `url(#id)` nội bộ của SVG). */
const safeAttrValue = (v: string) => !/(javascript|vbscript|data)\s*:|expression\s*\(|url\s*\(\s*(?!['"]?#)/i.test(v)

function appendSafe(src: Node, parent: Node) {
  if (src.nodeType === Node.TEXT_NODE) {
    parent.appendChild(document.createTextNode(src.textContent ?? ''))
    return
  }
  if (!(src instanceof Element)) return
  const tag = src.localName.toLowerCase()
  if (DROP_TAGS.has(tag)) return
  const isSvg = SVG_TAGS.has(tag) && src.namespaceURI === SVG_NS
  const isHtml = HTML_TAGS.has(tag) && src.namespaceURI === XHTML_NS
  let target: Node = parent
  if (isSvg || isHtml) {
    const el = isSvg ? document.createElementNS(SVG_NS, tag) : document.createElement(tag)
    for (const attr of Array.from(src.attributes)) {
      const name = attr.name.toLowerCase()
      if ((COMMON_ATTRS.has(name) || (isSvg && SVG_ATTRS.has(name))) && safeAttrValue(attr.value)) el.setAttribute(attr.name, attr.value)
    }
    parent.appendChild(el)
    target = el
  }
  // Thẻ không nằm trong danh sách: bỏ vỏ nhưng giữ chữ/phần tử con (cũng qua bộ lọc này).
  for (const child of Array.from(src.childNodes)) appendSafe(child, target)
}

/**
 * Dựng lại nội dung một ô cho khung xem nhanh theo **danh sách cho phép** (allowlist): chỉ tạo mới các thẻ và
 * thuộc tính liệt kê ở trên bằng `createElement`, không sao chép nguyên nút gốc và không qua phân tích chuỗi HTML.
 * Nhờ vậy mọi vector không có trong danh sách (thuộc tính `on*`, `style`, `href`/`src`, `<use>`, `<foreignObject>`,
 * mã hoá lạ, thẻ HTML mới…) đơn giản là không bao giờ được tạo ra, thay vì phải đoán để chặn từng cái.
 */
export function buildSafeCopy(cell: Element): DocumentFragment {
  const fragment = document.createDocumentFragment()
  for (const child of Array.from(cell.childNodes)) appendSafe(child, fragment)
  return fragment
}

/** Gắn bản sao an toàn vào ô giá trị (không dùng innerHTML). */
function PreviewValue({ node }: { node: DocumentFragment }) {
  const ref = React.useRef<HTMLElement | null>(null)
  React.useEffect(() => {
    ref.current?.replaceChildren(node.cloneNode(true))
  }, [node])
  return <dd ref={ref} className="min-w-0 break-words" />
}

interface RowPreview {
  title: string
  fields: { label: string; node: DocumentFragment }[]
  /** Dòng vốn có hành động riêng (chuyển trang): khung xem nhanh có thêm nút mở trang đầy đủ. */
  row: HTMLTableRowElement | null
}

/**
 * Bấm một dòng dữ liệu thì khung xem nhanh "bật ra" (phóng nhẹ từ giữa, nền mờ) liệt kê các cột của dòng đó.
 * Tự dựng từ đầu cột + nội dung ô nên dùng được cho mọi bảng. Tắt cho cả bảng bằng `data-preview="off"`,
 * cho một dòng bằng `data-preview="off"` trên TableRow.
 */
function RowPreviewHost({ disabled, children }: { disabled: boolean; children: React.ReactNode }) {
  const [preview, setPreview] = React.useState<RowPreview | null>(null)
  const bypass = React.useRef(false)

  const onClickCapture = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled || bypass.current) return
    const target = e.target as HTMLElement
    const row = target.closest('tbody tr') as HTMLTableRowElement | null
    if (!row || !e.currentTarget.contains(row) || row.dataset.preview === 'off') return
    const hit = target.closest(INTERACTIVE)
    if (hit && hit !== row && row.contains(hit)) return
    if (window.getSelection()?.toString()) return // đang bôi đen để copy: không bật khung
    const cells = Array.from(row.cells)
    if (cells.length < 2) return // dòng "Không có dữ liệu" / dòng gộp ô

    const table = row.closest('table')
    const headRow = table?.tHead?.rows[table.tHead.rows.length - 1]
    const fields = cells
      .map((cell, i) => {
        const copy = buildSafeCopy(cell)
        const hasVisual = copy.querySelector('svg') !== null
        if (!copy.textContent?.trim() && !hasVisual) return null
        const label = headRow?.cells[i]?.textContent?.trim() || `Cột ${i + 1}`
        return { label, node: copy }
      })
      .filter((f): f is { label: string; node: DocumentFragment } => f !== null)
    if (fields.length === 0) return

    const first = (cells[0].firstElementChild ?? cells[0]).textContent?.trim() ?? ''
    e.stopPropagation() // chặn onClick chuyển trang của dòng; nút "Mở trang đầy đủ" sẽ gọi lại sau
    setPreview({
      title: first && first.length <= 60 ? first : 'Chi tiết dòng dữ liệu',
      fields,
      row: row.classList.contains('cursor-pointer') ? row : null,
    })
  }

  const openFull = () => {
    const row = preview?.row
    setPreview(null)
    if (!row) return
    bypass.current = true
    row.click()
    bypass.current = false
  }

  return (
    <div className="relative max-h-[70vh] w-full overflow-auto" onClickCapture={onClickCapture}>
      {children}
      <Dialog open={preview !== null} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="pop-dialog max-w-md">
          <DialogHeader>
            <DialogTitle className="pr-6">{preview?.title}</DialogTitle>
            <DialogDescription>Xem nhanh dòng dữ liệu</DialogDescription>
          </DialogHeader>
          <dl className="divide-y divide-border rounded-xl border border-border bg-background/40 px-3">
            {preview?.fields.map((f, i) => (
              <div key={i} className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3 py-2.5 text-sm">
                <dt className="pt-0.5 text-xs font-medium uppercase tracking-[0.06em] text-muted-foreground">{f.label}</dt>
                <PreviewValue node={f.node} />
              </div>
            ))}
          </dl>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPreview(null)}>
              Đóng
            </Button>
            {preview?.row && (
              <Button type="button" onClick={openFull}>
                Mở trang đầy đủ
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

const Table = React.forwardRef<HTMLTableElement, React.HTMLAttributes<HTMLTableElement>>(
  ({ className, ...props }, ref) => (
    <RowPreviewHost disabled={(props as Record<string, unknown>)['data-preview'] === 'off'}>
      <table ref={ref} className={cn('w-full caption-bottom text-sm', className)} {...props} />
    </RowPreviewHost>
  ),
)
Table.displayName = 'Table'

const TableHeader = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => <thead ref={ref} className={cn('[&_tr]:border-b', className)} {...props} />,
)
TableHeader.displayName = 'TableHeader'

const TableBody = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => <tbody ref={ref} className={cn('[&_tr:last-child]:border-0', className)} {...props} />,
)
TableBody.displayName = 'TableBody'

const TableFooter = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <tfoot ref={ref} className={cn('border-t bg-muted/50 font-medium [&>tr]:last:border-b-0', className)} {...props} />
  ),
)
TableFooter.displayName = 'TableFooter'

const TableRow = React.forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement>>(
  ({ className, ...props }, ref) => (
    <tr
      ref={ref}
      className={cn('border-b border-border transition-colors hover:bg-accent/60 data-[state=selected]:bg-muted', className)}
      {...props}
    />
  ),
)
TableRow.displayName = 'TableRow'

const TableHead = React.forwardRef<HTMLTableCellElement, React.ThHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <th
      ref={ref}
      className={cn(
        'sticky top-0 z-10 h-10 whitespace-nowrap bg-card px-3 text-left align-middle text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground [&:has([role=checkbox])]:pr-0',
        className,
      )}
      {...props}
    />
  ),
)
TableHead.displayName = 'TableHead'

const TableCell = React.forwardRef<HTMLTableCellElement, React.TdHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <td ref={ref} className={cn('px-3 py-2.5 align-middle [&:has([role=checkbox])]:pr-0', className)} {...props} />
  ),
)
TableCell.displayName = 'TableCell'

const TableCaption = React.forwardRef<HTMLTableCaptionElement, React.HTMLAttributes<HTMLTableCaptionElement>>(
  ({ className, ...props }, ref) => (
    <caption ref={ref} className={cn('mt-4 text-sm text-muted-foreground', className)} {...props} />
  ),
)
TableCaption.displayName = 'TableCaption'

export { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption }
