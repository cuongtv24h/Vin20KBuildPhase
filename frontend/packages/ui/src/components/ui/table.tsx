import * as React from 'react'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { cn } from '@pricepolicy/ui/lib/utils'

/** Phần tử tương tác trong dòng: bấm vào đây thì giữ hành vi riêng, không mở khung xem nhanh. */
const INTERACTIVE = 'a, button, input, select, textarea, label, [role="button"], [role="checkbox"], [role="switch"], [role="combobox"], [data-no-preview]'

/** Thẻ không bao giờ được đưa vào khung xem nhanh (chạy mã / nhúng nội dung ngoài / điều khiển tương tác). */
const FORBIDDEN_TAGS = 'script, style, iframe, object, embed, link, meta, base, form, button, input, select, textarea'

/**
 * Làm sạch bản sao của một ô trước khi hiển thị lại: bỏ thẻ nguy hiểm, mọi thuộc tính `on*`, và URL
 * `javascript:` / `data:` — nên dù ô được dựng từ HTML thô (dangerouslySetInnerHTML ở nơi khác) cũng không
 * mang theo mã chạy được. Bản sao được gắn vào khung bằng DOM (appendChild), KHÔNG qua phân tích chuỗi HTML.
 */
export function sanitizeClone(root: HTMLElement) {
  root.querySelectorAll(FORBIDDEN_TAGS).forEach((n) => n.remove())
  const all = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))]
  for (const el of all) {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase()
      const value = attr.value.trim().toLowerCase()
      const unsafeUrl = (name === 'href' || name === 'src' || name === 'xlink:href' || name === 'action') && /^(javascript|data|vbscript):/.test(value)
      if (name.startsWith('on') || unsafeUrl) el.removeAttribute(attr.name)
    }
  }
}

/** Gắn nút DOM đã làm sạch vào ô giá trị (không dùng innerHTML). */
function PreviewValue({ node }: { node: HTMLElement }) {
  const ref = React.useRef<HTMLElement | null>(null)
  React.useEffect(() => {
    const host = ref.current
    if (!host) return
    host.replaceChildren(...Array.from(node.childNodes).map((c) => c.cloneNode(true)))
  }, [node])
  return <dd ref={ref} className="min-w-0 break-words" />
}

interface RowPreview {
  title: string
  fields: { label: string; node: HTMLElement }[]
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
        const clone = cell.cloneNode(true) as HTMLElement
        sanitizeClone(clone)
        const hasVisual = clone.querySelector('svg, img') !== null
        if (!clone.textContent?.trim() && !hasVisual) return null
        const label = headRow?.cells[i]?.textContent?.trim() || `Cột ${i + 1}`
        return { label, node: clone }
      })
      .filter((f): f is { label: string; node: HTMLElement } => f !== null)
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
