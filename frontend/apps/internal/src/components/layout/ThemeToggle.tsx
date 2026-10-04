import { Eye, Moon, Sun } from 'lucide-react'
import { cn } from '@pricepolicy/ui/lib/utils'
import { THEME_CONFIG, useTheme } from '@/lib/theme'

/** Nút chuyển 3 phong cách giao diện: Tối (Luxury Black) → Sáng (Ngà ấm) → Dịu mắt (Xanh trắng). */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggle } = useTheme()
  const config = THEME_CONFIG[theme]
  const title = `Giao diện: ${config.label} (${config.description}) — Bấm để chuyển sang ${config.nextLabel}`

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={title}
      title={title}
      className={cn(
        'inline-flex h-9 w-9 items-center justify-center rounded-lg text-sidebar-muted transition-colors hover:bg-sidebar-active hover:text-sidebar-foreground',
        className,
      )}
    >
      {theme === 'dark' && <Moon className="h-4 w-4 text-amber-300/90" />}
      {theme === 'light' && <Sun className="h-4 w-4 text-amber-600" />}
      {theme === 'calm' && <Eye className="h-4 w-4 text-sky-500" />}
    </button>
  )
}
