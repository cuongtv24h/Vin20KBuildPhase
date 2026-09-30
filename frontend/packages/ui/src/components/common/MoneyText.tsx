import { formatVnd } from '@pricepolicy/ui/lib/format'
import { cn } from '@pricepolicy/ui/lib/utils'

interface MoneyTextProps {
  amount: number
  className?: string
  size?: 'sm' | 'base' | 'lg' | 'xl'
  tone?: 'default' | 'muted' | 'success' | 'destructive'
}

const SIZE_CLASS: Record<NonNullable<MoneyTextProps['size']>, string> = {
  sm: 'text-sm',
  base: 'text-base',
  lg: 'text-lg font-semibold',
  xl: 'font-display text-[1.65rem] font-semibold leading-tight tracking-tight',
}

const TONE_CLASS: Record<NonNullable<MoneyTextProps['tone']>, string> = {
  default: 'text-foreground',
  muted: 'text-muted-foreground',
  success: 'text-success',
  destructive: 'text-destructive',
}

/** Hiển thị số tiền VNĐ căn phải, tabular-nums, dùng thống nhất mọi nơi trong app. */
export function MoneyText({ amount, className, size = 'base', tone = 'default' }: MoneyTextProps) {
  return (
    <span className={cn('whitespace-nowrap tabular-nums', SIZE_CLASS[size], TONE_CLASS[tone], className)}>{formatVnd(amount)}</span>
  )
}
