import { useEffect, useRef, useState } from 'react'
import { Check, Eye, Moon, Palette, Sun } from 'lucide-react'
import { cn } from '@pricepolicy/ui/lib/utils'
import { THEME_CONFIG, useTheme, type Theme } from '@/lib/theme'

const OPTIONS: { value: Theme; icon: typeof Moon; swatch: [string, string] }[] = [
  { value: 'dark', icon: Moon, swatch: ['#121214', '#C9A961'] },
  { value: 'light', icon: Sun, swatch: ['#F8F5EE', '#AA8C3B'] },
  { value: 'calm', icon: Eye, swatch: ['#F8FAFC', '#0F6CBD'] },
]

/**
 * Nút giao diện: bấm mở danh sách các giao diện hiện có để chọn.
 * `side` là hướng mở menu (mặc định mở lên vì nút nằm cuối sidebar).
 */
export function ThemeToggle({
  className,
  side = 'top',
}: {
  className?: string
  side?: 'top' | 'bottom'
}) {
  const { theme, setTheme } = useTheme()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`Giao diện: ${THEME_CONFIG[theme].label}. Bấm để chọn giao diện`}
        title="Chọn giao diện"
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          'inline-flex h-9 w-9 items-center justify-center rounded-lg text-sidebar-muted transition-colors hover:bg-sidebar-active hover:text-sidebar-foreground',
          className,
        )}
      >
        <Palette className="h-4 w-4" />
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Chọn giao diện"
          className={cn(
            'absolute right-0 z-50 w-64 rounded-xl border border-border bg-popover p-1.5 text-popover-foreground shadow-lg',
            side === 'top' ? 'bottom-full mb-2' : 'top-full mt-2',
          )}
        >
          {OPTIONS.map(({ value, icon: Icon, swatch }) => {
            const cfg = THEME_CONFIG[value]
            const active = theme === value
            return (
              <button
                key={value}
                type="button"
                role="menuitemradio"
                aria-checked={active}
                onClick={(e) => {
                  setTheme(value, { x: e.clientX, y: e.clientY })
                  setOpen(false)
                }}
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-accent',
                  active && 'bg-accent',
                )}
              >
                {/* Ô xem trước: màu cố định theo từng giao diện, không phụ thuộc theme đang bật */}
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border"
                  style={{ background: swatch[0] }}
                >
                  <span className="h-3 w-3 rounded-full" style={{ background: swatch[1] }} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5 text-sm font-medium">
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                    {cfg.label}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {cfg.description}
                  </span>
                </span>
                {active && <Check className="h-4 w-4 shrink-0 text-gold" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
