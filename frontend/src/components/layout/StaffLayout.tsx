import { useQueryClient } from '@tanstack/react-query'
import {
  Archive,
  Building2,
  ClipboardCheck,
  FilePlus2,
  FileStack,
  FlaskConical,
  Inbox,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useState, type ComponentType } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api } from '@/api'
import { useLeads, useQuotes } from '@/api/hooks'
import { useSessionStore } from '@/auth/sessionStore'
import { Button } from '@/components/ui/button'
import { MANAGER_QUEUE_STATUSES } from '@/engine/workflow'
import { ROLE_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { UserRole } from '@/types/domain'

interface NavItem {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
  end?: boolean
  badgeKey?: 'unassignedLeads' | 'managerQueue'
}

const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  SALE: [
    { to: '/sale', label: 'Tổng quan', icon: LayoutDashboard, end: true },
    { to: '/sale/leads', label: 'Yêu cầu khách hàng', icon: Inbox, badgeKey: 'unassignedLeads' },
    { to: '/sale/quotes', label: 'Hồ sơ báo giá', icon: FileStack },
  ],
  MANAGER: [
    { to: '/manager', label: 'Tổng quan', icon: LayoutDashboard, end: true },
    { to: '/manager/approvals', label: 'Phê duyệt báo giá', icon: ClipboardCheck, badgeKey: 'managerQueue' },
  ],
  SALE_ADMIN: [
    { to: '/admin', label: 'Tổng quan', icon: LayoutDashboard, end: true },
    { to: '/admin/policies', label: 'Chính sách bán hàng', icon: ScrollText },
    { to: '/admin/inventory', label: 'Bảng hàng', icon: Building2 },
    { to: '/admin/quotes', label: 'Tra cứu hồ sơ', icon: Archive },
    { to: '/admin/formula-tests', label: 'Kiểm thử công thức', icon: FlaskConical },
  ],
}

function useNavBadges(role: UserRole) {
  const leads = useLeads({ scope: 'UNASSIGNED' })
  const queue = useQuotes({ status: MANAGER_QUEUE_STATUSES })
  return {
    unassignedLeads: role === 'SALE' ? (leads.data?.length ?? 0) : 0,
    managerQueue: role === 'MANAGER' ? (queue.data?.length ?? 0) : 0,
  }
}

export function StaffLayout() {
  const session = useSessionStore((s) => s.session)
  const clearSession = useSessionStore((s) => s.clearSession)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)

  const role = session?.user.role ?? 'SALE'
  const badges = useNavBadges(role)
  const items = NAV_BY_ROLE[role]

  async function handleLogout() {
    try {
      await api.auth.logout()
    } finally {
      clearSession()
      queryClient.clear()
      navigate('/login', { replace: true })
    }
  }

  const nav = (
    <nav className="flex flex-col gap-0.5">
      {items.map((item) => {
        const count = item.badgeKey ? badges[item.badgeKey] : 0
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive ? 'bg-primary-foreground/15 text-primary-foreground' : 'text-primary-foreground/70 hover:bg-primary-foreground/10 hover:text-primary-foreground',
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            <span className="flex-1">{item.label}</span>
            {count > 0 && (
              <span className="rounded-full bg-gold px-1.5 py-0.5 text-[10px] font-semibold leading-none text-gold-foreground tabular-nums">
                {count}
              </span>
            )}
          </NavLink>
        )
      })}
    </nav>
  )

  const sidebar = (
    <div className="flex h-full flex-col gap-6 bg-primary px-3 py-5 text-primary-foreground">
      <Link to={items[0].to} className="flex items-center gap-2.5 px-2">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-foreground/10">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <span className="leading-tight">
          <span className="block font-display text-base font-semibold">PricePolicy</span>
          <span className="block text-[11px] text-primary-foreground/60">VLandFuture</span>
        </span>
      </Link>

      {role === 'SALE' && (
        <Button asChild variant="secondary" className="justify-start">
          <Link to="/sale/quotes/new" onClick={() => setMobileOpen(false)}>
            <FilePlus2 className="h-4 w-4" /> Lập báo giá
          </Link>
        </Button>
      )}

      {nav}

      <div className="mt-auto space-y-3 border-t border-primary-foreground/15 px-2 pt-4">
        <div className="leading-tight">
          <p className="text-sm font-medium">{session?.user.fullName}</p>
          <p className="text-xs text-primary-foreground/60">{ROLE_LABEL[role]}</p>
          <p className="truncate text-xs text-primary-foreground/50">{session?.user.email}</p>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="inline-flex items-center gap-1.5 text-xs text-primary-foreground/70 hover:text-primary-foreground"
        >
          <LogOut className="h-3.5 w-3.5" /> Đăng xuất
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 lg:block">{sidebar}</aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button type="button" aria-label="Đóng menu" className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <aside className="relative h-full w-64">{sidebar}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur lg:hidden">
          <button type="button" aria-label="Mở menu" onClick={() => setMobileOpen(true)} className="rounded-md p-1.5 hover:bg-muted">
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <span className="font-display font-semibold">PricePolicy</span>
          <span className="text-xs text-muted-foreground">{session?.user.fullName}</span>
        </header>
        <main className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
