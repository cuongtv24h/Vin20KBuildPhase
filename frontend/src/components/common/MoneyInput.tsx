import { Input } from '@/components/ui/input'
import { formatNumber } from '@/lib/format'

/** Ô nhập số tiền VNĐ: hiển thị phân tách hàng nghìn, trả về số nguyên (null khi trống). */
export function MoneyInput({ id, value, onChange, placeholder }: { id?: string; value: number | null; onChange: (v: number | null) => void; placeholder?: string }) {
  return (
    <div className="relative">
      <Input
        id={id}
        inputMode="numeric"
        className="pr-8 tabular-nums"
        placeholder={placeholder}
        value={value === null ? '' : formatNumber(value)}
        onChange={(e) => {
          const digits = e.target.value.replace(/\D/g, '')
          onChange(digits ? Number(digits) : null)
        }}
      />
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">đ</span>
    </div>
  )
}
