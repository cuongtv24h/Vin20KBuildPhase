import { Archive, FlaskConical, LayoutGrid, PlayCircle, ShieldCheck, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { Toaster } from '@/components/Toaster'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/state/appStore'
import type { UserRole } from '@/types/domain'

const NAV_ITEMS = [
  { to: '/', label: 'Tổng quan', icon: LayoutGrid, end: true },
  { to: '/sales', label: 'Sales Copilot', icon: Sparkles },
  { to: '/manager', label: 'Duyệt hồ sơ', icon: ShieldCheck },
  { to: '/audit', label: 'Kiểm toán & Snapshot', icon: Archive },
  { to: '/benchmark', label: 'Benchmark công thức', icon: FlaskConical },
  { to: '/demo', label: 'Kịch bản Demo', icon: PlayCircle },
] as const

const ROLE_OPTIONS: { value: UserRole; label: string; shortLabel: string }[] = [
  { value: 'SALES', label: 'Sales Executive', shortLabel: 'Sales' },
  { value: 'MANAGER', label: 'Sales Manager', shortLabel: 'Manager' },
  { value: 'ADMIN', label: 'Policy Admin', shortLabel: 'Admin' },
]

export function AppShell({ children }: { children: ReactNode }) {
  const role = useAppStore((s) => s.role)
  const setRole = useAppStore((s) => s.setRole)

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="container flex min-h-16 flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="leading-tight">
              <p className="font-display text-base font-semibold tracking-tight text-foreground sm:text-lg">PricePolicy AI Agent</p>
              <p className="text-[11px] text-muted-foreground">VLandFuture · Trust Layer (Frontend Demo)</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden text-xs text-muted-foreground sm:inline">Đang xem với vai trò</span>
            <div className="flex rounded-lg border border-border bg-muted p-0.5">
              {ROLE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setRole(opt.value)}
                  className={cn(
                    'rounded-md px-2 py-1.5 text-xs font-medium transition-colors sm:px-3',
                    role === opt.value
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  <span className="sm:hidden">{opt.shortLabel}</span>
                  <span className="hidden sm:inline">{opt.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <nav className="container flex gap-1 overflow-x-auto pb-2 no-scrollbar">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={'end' in item ? item.end : false}
              className={({ isActive }) =>
                cn(
                  'inline-flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="container flex-1 py-6 sm:py-8">{children}</main>

      <footer className="border-t border-border py-5">
        <div className="container flex flex-col gap-1 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>PricePolicy AI Agent — Frontend-only demo. Toàn bộ dữ liệu là MOCK, không kết nối backend thật.</p>
          <p>Dev 3 · Frontend/UI Engineer</p>
        </div>
      </footer>

      <Toaster />
    </div>
  )
}
