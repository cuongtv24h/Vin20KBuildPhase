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
  onTransactionDateChange: (date: string | null) => void
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
  onTransactionDateChange,
  className,
}: CopilotContextChipsProps) {
  const hasAny = value.unitCode || value.dossierLabel || value.projectLabel || value.transactionDate
  if (!hasAny) {
    return (
      <div className={cn('mb-2 text-[11px] text-muted-foreground', className)}>
        Chưa gắn ngữ cảnh — Copilot sẽ hỏi lại nếu câu lệnh thiếu mã căn/hồ sơ.
      </div>
    )
  }

  const chip = 'flex items-center gap-1 rounded-full border border-primary/25 bg-primary/[0.04] px-2 py-0.5 text-[11px] text-foreground'
  const clearButton = 'ml-0.5 rounded-full p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground'

  return (
    <div className={cn('mb-2 flex flex-wrap items-center gap-1.5', className)} aria-label="Ngữ cảnh Copilot đang dùng">
      {value.dossierLabel && (
        <span className={chip} title="Hồ sơ khách hàng gửi kèm">
          <FileStack className="h-3 w-3 text-primary" />
          {value.dossierLabel}
          <button type="button" className={clearButton} onClick={onClearDossier} aria-label="Bỏ hồ sơ khách hàng khỏi ngữ cảnh">
            <X className="h-3 w-3" />
          </button>
        </span>
      )}
      {value.unitCode && (
        <span className={chip} title="Mã căn gửi kèm">
          <Home className="h-3 w-3 text-primary" />
          {value.unitCode}
          <button type="button" className={clearButton} onClick={onClearUnit} aria-label="Bỏ mã căn khỏi ngữ cảnh">
            <X className="h-3 w-3" />
          </button>
        </span>
      )}
      {value.projectLabel && <span className={chip}>{value.projectLabel}</span>}
      <span className={cn(chip, 'pr-1.5')} title="Ngày giao dịch dùng để tra chính sách (time-travel)">
        <CalendarDays className="h-3 w-3 text-primary" />
        <label className="sr-only" htmlFor="copilot-tx-date">
          Ngày giao dịch
        </label>
        <input
          id="copilot-tx-date"
          type="date"
          value={value.transactionDate ?? ''}
          onChange={(e) => onTransactionDateChange(e.target.value || null)}
          className="w-[104px] bg-transparent text-[11px] text-foreground outline-none"
        />
        {value.transactionDate && (
          <button
            type="button"
            className={clearButton}
            onClick={() => onTransactionDateChange(null)}
            aria-label="Bỏ ngày giao dịch khỏi ngữ cảnh"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </span>
    </div>
  )
}
