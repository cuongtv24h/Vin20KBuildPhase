import { hashToGrid } from '@/lib/hash'
import { cn } from '@/lib/utils'

interface HashGridProps {
  hashHex: string
  size?: number
  cell?: number
  className?: string
}

/** Hoạ tiết vuông minh hoạ sinh tất định từ hash — KHÔNG phải mã QR quét được thật. */
export function HashGrid({ hashHex, size = 12, cell = 10, className }: HashGridProps) {
  const grid = hashToGrid(hashHex, size)
  const dimension = size * cell

  return (
    <div className={cn('inline-flex flex-col items-center gap-1.5', className)}>
      <div
        className="grid rounded-md border border-border bg-white p-2 shadow-sm"
        style={{ gridTemplateColumns: `repeat(${size}, ${cell}px)`, width: dimension + 16 }}
      >
        {grid.map((row, rIdx) =>
          row.map((on, cIdx) => (
            <span
              key={`${rIdx}-${cIdx}`}
              style={{ width: cell, height: cell }}
              className={on ? 'bg-primary' : 'bg-transparent'}
            />
          )),
        )}
      </div>
      <p className="max-w-[180px] text-center text-[10px] leading-tight text-muted-foreground">
        Hoạ tiết minh hoạ sinh từ mã băm — không phải mã QR quét được thực tế.
      </p>
    </div>
  )
}
