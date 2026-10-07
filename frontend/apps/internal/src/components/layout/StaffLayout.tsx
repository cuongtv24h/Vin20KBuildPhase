import { useQueryClient } from '@tanstack/react-query'
import { ClipboardCheck, FilePlus2, FileStack, FlaskConical, Gauge, Inbox, LogOut, Menu, MessageSquare, ScrollText, ShieldCheck, Sparkles, PanelLeftClose, PanelLeftOpen, Users, type LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api } from '@pricepolicy/api-client/client'
import type { UserRole } from '@pricepolicy/api-client/contracts'
import { useLeads, useQuotes } from '@pricepolicy/api-client/hooks'
import { useSessionStore } from '@/auth/sessionStore'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { ROLE_LABEL } from '@pricepolicy/ui/lib/labels'
import { MANAGER_QUEUE } from '@pricepolicy/ui/lib/quoteRules'
import { cn } from '@pricepolicy/ui/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
  badgeKey?: 'openLeads' | 'managerQueue'
  /** Nhóm hiển thị (nhãn nhỏ phía trên cụm mục — bố cục Square/Cloudflare). */
  group?: string
}

const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  ADMIN: [
    { to: '/admin_cp', label: 'Quản trị Users', icon: ShieldCheck, group: 'Quản trị' },
    { to: '/admin/policies', label: 'Chính sách bán hàng', icon: ScrollText, group: 'Chính sách và chất lượng' },
    { to: '/admin/benchmark', label: 'Kiểm thử công thức', icon: FlaskConical, group: 'Chính sách và chất lượng' },
    { to: '/admin/copilot-quality', label: 'Chất lượng Copilot', icon: Gauge, group: 'Chính sách và chất lượng' },
  ],
  SALE: [
    { to: '/sale/workspace', label: 'Trợ lý Copilot', icon: Sparkles, group: 'Làm việc' },
    { to: '/sale/leads', label: 'Khách hàng', icon: Users, badgeKey: 'openLeads', group: 'Làm việc' },
    { to: '/sale/quotes', label: 'Báo giá', icon: FileStack, group: 'Làm việc' },
    { to: '/sale/messages', label: 'Tin nhắn', icon: MessageSquare, group: 'Làm việc' },
    { to: '/sale/policies', label: 'Chính sách', icon: ScrollText, group: 'Tra cứu' },
  ],
  MANAGER: [{ to: '/manager/approvals', label: 'Phê duyệt báo giá', icon: ClipboardCheck, badgeKey: 'managerQueue', group: 'Phê duyệt' }],
  POLICY_ADMIN: [
    { to: '/admin/policies', label: 'Chính sách bán hàng', icon: ScrollText, group: 'Chính sách và chất lượng' },
    { to: '/admin/benchmark', label: 'Kiểm thử công thức', icon: FlaskConical, group: 'Chính sách và chất lượng' },
    { to: '/admin/copilot-quality', label: 'Chất lượng Copilot', icon: Gauge, group: 'Chính sách và chất lượng' },
  ],
}

function SaleBadges() {
  const leads = useLeads()
  return { openLeads: leads.data?.filter((d) => d.status !== 'CONVERTED_TO_QUOTE').length ?? 0, managerQueue: 0 }
}

function ManagerBadges() {
  const queue = useQuotes({ status: MANAGER_QUEUE }, { live: true })
  return { openLeads: 0, managerQueue: queue.data?.length ?? 0 }
}

const NO_BADGES = () => ({ openLeads: 0, managerQueue: 0 })

/** Mỗi vai trò chỉ gọi endpoint mình có quyền — không bắn request 403 ở nền. */
const BADGE_HOOK: Record<UserRole, () => Record<NonNullable<NavItem['badgeKey']>, number>> = {
  ADMIN: NO_BADGES,
  SALE: SaleBadges,
  MANAGER: ManagerBadges,
  POLICY_ADMIN: NO_BADGES,
}

export function StaffLayout() {
  const session = useSessionStore((s) => s.session)
  const clearSession = useSessionStore((s) => s.clearSession)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  // Thu gọn sidebar (chỉ desktop) — nhớ lựa chọn giữa các lần mở app.
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem('pp-sidebar') === 'collapsed'
    } catch {
      return false
    }
  })
  function toggleCollapsed() {
    setCollapsed((v) => {
      try {
        localStorage.setItem('pp-sidebar', v ? 'expanded' : 'collapsed')
      } catch {
        /* bỏ qua */
      }
      return !v
    })
  }

  const role = session?.user.role ?? 'SALE'
  const badges = BADGE_HOOK[role]()
  const items = NAV_BY_ROLE[role]

  async function handleLogout() {
    try {
      await api.auth.logout().catch(() => undefined)
    } finally {
      clearSession()
      queryClient.clear()
      navigate('/login', { replace: true })
    }
  }

  const location = useLocation()

  // Đóng drawer bằng Esc (trợ năng bàn phím).
  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMobileOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobileOpen])

  const renderNav = (compact: boolean) => (
    <nav aria-label="Điều hướng chính" className="flex flex-1 flex-col gap-0.5 overflow-y-auto">
      {items.map((item, i) => {
        const count = item.badgeKey ? badges[item.badgeKey] : 0
        const startsGroup = item.group && item.group !== items[i - 1]?.group
        return (
          <div key={item.to} className="contents">
            {startsGroup &&
              (compact ? (
                i > 0 && <div aria-hidden="true" className="mx-2 my-2 h-px bg-sidebar-border" />
              ) : (
                <p className={cn('sb-label px-3 pb-1 text-[11px] font-medium uppercase tracking-[0.12em] text-sidebar-muted/80', i > 0 ? 'pt-4' : 'pt-1')}>
                  {item.group}
                </p>
              ))}
            <NavLink
              to={item.to}
              end={item.end}
              onClick={() => setMobileOpen(false)}
              title={compact ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  'group relative flex min-h-11 items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-200 lg:min-h-9',
                  isActive
                    ? 'bg-sidebar-active font-semibold text-sidebar-foreground'
                    : 'font-medium text-sidebar-muted hover:bg-sidebar-active/60 hover:text-sidebar-foreground',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon className={cn('h-[18px] w-[18px] shrink-0', isActive && 'text-primary')} />
                  <span className="sb-label min-w-0 flex-1 truncate whitespace-nowrap">{item.label}</span>
                  {count > 0 && (
                    <span
                      aria-label={`${count} mục đang chờ`}
                      className={cn('inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary/20 px-1.5 text-xs font-semibold leading-none text-gold tabular-nums', compact && 'absolute right-1 top-0.5 h-4 min-w-4 px-1')}
                    >
                      {count}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          </div>
        )
      })}
    </nav>
  )

  const initials = (session?.user.full_name ?? '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(-2)
    .map((w) => w[0]?.toUpperCase())
    .join('')

  const renderSidebar = (compact: boolean, desktop: boolean) => (
    <div className={cn('flex h-full flex-col gap-4 bg-sidebar px-3 py-4 text-sidebar-foreground', desktop ? 'w-60' : 'w-full border-r border-sidebar-border')}>
      <div className={cn('flex items-center gap-2', compact ? 'justify-start' : 'justify-between')}>
      <Link to={items[0].to} title={compact ? 'PricePolicy' : undefined} className={cn('flex min-w-0 items-center gap-3 rounded-lg px-0.5 py-1', compact && 'hidden')}>
        <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-primary/40 text-primary">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <span className="sb-label whitespace-nowrap leading-tight">
          <span className="block font-display text-lg font-semibold tracking-tight">PricePolicy</span>
          <span className="block text-xs uppercase tracking-[0.14em] text-sidebar-muted">VLandFuture</span>
        </span>
      </Link>
        {desktop && (
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={compact ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
            aria-expanded={!compact}
            title={compact ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-sidebar-muted transition-colors hover:bg-sidebar-active hover:text-sidebar-foreground"
          >
            {compact ? <PanelLeftOpen className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
          </button>
        )}
      </div>

      {role === 'SALE' && (
        <Button asChild variant="outline" className="h-10 w-full justify-start border-primary/30 bg-primary/10 px-3 font-semibold text-primary hover:border-primary/50 hover:bg-primary/20 hover:text-primary">
          <Link to="/sale/quotes/new" title={compact ? 'Báo giá khách tại sàn' : undefined} aria-label="Báo giá khách tại sàn" onClick={() => setMobileOpen(false)}>
            <FilePlus2 /> <span className="sb-label">Báo giá khách tại sàn</span>
          </Link>
        </Button>
      )}

      {renderNav(compact)}

      {/* Cụm người dùng ở đáy (bố cục Square/Attio): thẻ tài khoản + hàng hành động gọn */}
      <div className="space-y-2 border-t border-sidebar-border pt-3">
        <div
          title={compact ? `${session?.user.full_name} · ${session?.user.email}` : session?.user.email}
          className="flex items-center gap-3 rounded-lg bg-sidebar-active/50 p-2"
        >
          <span
            aria-hidden="true"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-primary/40 bg-sidebar text-sm font-semibold text-primary"
          >
            {initials}
          </span>
          <div className="sb-label min-w-0 whitespace-nowrap leading-tight">
            <p className="truncate text-sm font-medium">{session?.user.full_name}</p>
            <p className="truncate text-xs text-sidebar-muted">{ROLE_LABEL[role]}</p>
          </div>
        </div>
        <div className={cn('flex gap-1', compact ? 'flex-col items-start' : 'items-center justify-between')}>
          <button
            type="button"
            onClick={handleLogout}
            title="Đăng xuất"
            className="inline-flex min-h-10 items-center gap-2 rounded-lg px-2 text-sm text-sidebar-muted transition-colors hover:bg-sidebar-active hover:text-sidebar-foreground"
          >
            <LogOut className="h-4 w-4 shrink-0" /> <span className="sb-label whitespace-nowrap">Đăng xuất</span>
          </button>
          <ThemeToggle />
        </div>
      </div>
    </div>
  )

  // Trang Trợ lý Copilot tự cuộn bên trong (khung chat + thanh nhập cố định): phải khoá chiều cao
  // đúng bằng khung nhìn. Nếu không, trên màn hình có thanh header 56px (dưới lg) tổng chiều cao
  // vượt khung nhìn → cả trang cuộn → cuộn lên xem tin cũ là thanh nhập bị đẩy khỏi màn hình.
  const isWorkspace = location.pathname.startsWith('/sale/workspace')

  return (
    <div className={cn('flex bg-background', isWorkspace ? 'h-dvh overflow-hidden' : 'min-h-screen')}>
      <aside
        data-collapsed={collapsed}
        className={cn(
          'hidden shrink-0 overflow-hidden border-r border-sidebar-border bg-sidebar transition-[width] duration-200 ease-out lg:block',
          collapsed ? 'w-[4.25rem]' : 'w-60',
          isWorkspace ? 'h-dvh' : 'sticky top-0 h-screen',
        )}
      >
        {renderSidebar(collapsed, true)}
      </aside>

      {/* Menu trượt trên mobile: luôn render để có transition; ẩn khỏi cây trợ năng khi đóng */}
      <div className={cn('fixed inset-0 z-50 lg:hidden', mobileOpen ? '' : 'pointer-events-none')} aria-hidden={!mobileOpen}>
        <button
          type="button"
          tabIndex={mobileOpen ? 0 : -1}
          aria-label="Đóng menu"
          className={cn('absolute inset-0 bg-black/60 transition-opacity duration-200', mobileOpen ? 'opacity-100' : 'opacity-0')}
          onClick={() => setMobileOpen(false)}
        />
        <aside
          className={cn(
            'relative h-full w-72 max-w-[85vw] shadow-xl transition-transform duration-200 ease-out',
            mobileOpen ? 'translate-x-0' : '-translate-x-full',
          )}
        >
          {renderSidebar(false, false)}
        </aside>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border bg-background/95 px-2 backdrop-blur lg:hidden">
          <button
            type="button"
            aria-label="Mở menu"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen(true)}
            className="inline-flex h-11 w-11 items-center justify-center rounded-lg transition-colors hover:bg-accent"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="font-display text-lg font-semibold tracking-tight">PricePolicy</span>
          <span className="max-w-[40%] truncate px-2 text-xs text-muted-foreground">{session?.user.full_name}</span>
        </header>
        <main
          className={cn(
            isWorkspace
              ? 'flex min-h-0 flex-1 flex-col overflow-hidden p-0'
              : 'mx-auto w-full max-w-[1320px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8'
          )}
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
