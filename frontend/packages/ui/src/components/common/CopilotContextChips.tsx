import { CalendarDays, FileStack, Home, X } from 'lucide-react'
import { cn } from '@pricepolicy/ui/lib/utils'

export interface CopilotContextValue {
  unitCode: string | null
  dossierLabel: string | null
  transactionDate: string | null
  projectLabel: string | null
}

interface CopilotContextChipsProps {
  value: CopilotContextValue
  onClearUnit: () => void
  onClearDossier: () => void
  className?: string
}

/**
 * Chip ngữ cảnh Copilot: cho Sale thấy CHÍNH XÁC dữ liệu nào sẽ được gửi kèm câu hỏi
 * (căn · hồ sơ · ngày giao dịch · dự án) và sửa/xoá được ngay tại chỗ.
 *
 * Trước đây ngữ cảnh nằm im trong logic gửi nên Sale không biết Copilot đang "nhìn" căn nào —
 * nguồn gốc của các câu trả lời sai ngữ cảnh.
 */
export function CopilotContextChips({
  value,
  onClearUnit,
  onClearDossier,
  className,
}: CopilotContextChipsProps) {
  const hasAny = value.unitCode || value.dossierLabel || value.projectLabel
  if (!hasAny) {
    return (
      <div className={cn('hidden text-xs text-muted-foreground sm:block', className)}>
        Chưa gắn ngữ cảnh — Copilot sẽ hỏi lại nếu câu lệnh thiếu mã căn/hồ sơ.
      </div>
    )
  }

  const chip = 'flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/[0.06] px-2.5 py-1 text-xs text-foreground'
  const clearButton =
    'ml-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground'

  return (
    <div className={cn('flex flex-wrap items-center gap-1.5', className)} aria-label="Ngữ cảnh Copilot đang dùng">
      {value.dossierLabel && (
        <span className={chip} title="Hồ sơ khách hàng gửi kèm">
          <FileStack className="h-3.5 w-3.5 text-gold" />
          {value.dossierLabel}
          <button type="button" className={clearButton} onClick={onClearDossier} aria-label="Bỏ hồ sơ khách hàng khỏi ngữ cảnh">
            <X className="h-3 w-3" />
          </button>
        </span>
      )}
      {value.unitCode && (
        <span className={chip} title="Mã căn gửi kèm">
          <Home className="h-3.5 w-3.5 text-gold" />
          {value.unitCode}
          <button type="button" className={clearButton} onClick={onClearUnit} aria-label="Bỏ mã căn khỏi ngữ cảnh">
            <X className="h-3 w-3" />
          </button>
        </span>
      )}
      {value.projectLabel && <span className={chip}>{value.projectLabel}</span>}
    </div>
  )
}

/** Ô "Ngày giao dịch" (time-travel tra chính sách) — nằm cùng hàng với ô chọn Khách hàng. */
export function TransactionDateField({
  value,
  onChange,
  className,
}: {
  value: string | null
  onChange: (date: string | null) => void
  className?: string
}) {
  return (
    <div className={cn('flex min-w-0 flex-col gap-1', className)} title="Ngày giao dịch dùng để tra chính sách (time-travel)">
      <label htmlFor="copilot-tx-date" className="eyebrow">
        Ngày giao dịch
      </label>
      <div className="relative">
        <CalendarDays aria-hidden="true" className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 sm:left-3 -translate-y-1/2 text-muted-foreground" />
        <input
          id="copilot-tx-date"
          type="date"
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value || null)}
          className="h-10 w-full rounded-lg border border-input bg-background pl-8 pr-8 text-sm sm:pl-9 sm:pr-9 text-foreground outline-none transition-[border-color,box-shadow] duration-200 hover:border-primary/30 focus-visible:border-primary/60 focus-visible:ring-2 focus-visible:ring-ring/60 md:h-9 [&::-webkit-calendar-picker-indicator]:opacity-60"
        />
        {value && (
          <button
            type="button"
            onClick={() => onChange(null)}
            aria-label="Bỏ ngày giao dịch khỏi ngữ cảnh"
            className="absolute right-1.5 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}
