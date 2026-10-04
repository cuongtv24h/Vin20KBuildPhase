import { Briefcase, Loader2, LogIn, ScrollText, ShieldCheck, UserCog, type LucideIcon } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useAdminSetupStatus, useLogin } from '@pricepolicy/api-client/hooks'
import { ROLE_AREA, ROLE_HOME, getAccessToken, useSessionStore } from '@/auth/sessionStore'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import { ThemeToggle } from '@/components/layout/ThemeToggle'

/** Đăng nhập nhanh theo vai trò (tài khoản demo). Icon line thay emoji, vùng bấm ≥ 44px. */
const QUICK_ACCOUNTS: { user: string; label: string; icon: LucideIcon }[] = [
  { user: 'sale', label: 'Sale', icon: Briefcase },
  { user: 'manager', label: 'Quản lý', icon: UserCog },
  { user: 'admin', label: 'Admin', icon: ShieldCheck },
  { user: 'policy', label: 'Chính sách', icon: ScrollText },
]

export function LoginPage() {
  const session = useSessionStore((s) => s.session)
  const setSession = useSessionStore((s) => s.setSession)
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const login = useLogin()
  const { data: setupStatus } = useAdminSetupStatus()
  const [account, setAccount] = useState('')
  const [password, setPassword] = useState('')

  if (session && getAccessToken()) {
    return <Navigate to={ROLE_HOME[session.user.role]} replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const result = await login.mutateAsync({ email: account.trim(), password }).catch(() => null)
    if (!result) return
    setSession(result)
    const redirect = params.get('redirect')
    const role = result.user.role
    navigate(redirect && redirect.startsWith(ROLE_AREA[role]) ? redirect : ROLE_HOME[role], { replace: true })
  }

  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1.1fr,1fr]">
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-sidebar-border bg-gradient-to-br from-sidebar via-sidebar to-primary/15 p-12 text-sidebar-foreground lg:flex">
        {/* Ánh vàng rất nhẹ ở góc — điểm nhấn duy nhất, không lòe loẹt */}
        <div aria-hidden="true" className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-primary/[0.07] blur-3xl" />
        <Link to="/" className="relative flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-primary/40 text-primary">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <span className="font-display text-xl font-semibold tracking-tight">PricePolicy · VLandFuture</span>
        </Link>
        <div className="relative max-w-md space-y-4">
          <p className="eyebrow text-gold">Cổng nội bộ</p>
          <p className="font-display text-4xl font-semibold leading-tight tracking-tight">Báo giá đúng chính sách, duyệt trong một phút.</p>
        </div>
        <p className="relative text-xs text-sidebar-muted">© 2026 VLandFuture</p>
      </div>

      <div className="relative flex items-center justify-center px-4 py-10">
        <div className="absolute right-4 top-4"><ThemeToggle side="bottom" className="text-muted-foreground hover:bg-accent hover:text-foreground" /></div>
        <div className="w-full max-w-sm space-y-6">
          {/* Mobile/tablet: cột trái ẩn nên nhắc lại thương hiệu ở đầu form */}
          <div className="flex items-center gap-2.5 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-primary/40 text-primary">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <span className="font-display text-lg font-semibold tracking-tight">PricePolicy · VLandFuture</span>
          </div>

          <div className="space-y-1.5">
            <h1 className="font-display text-3xl font-semibold tracking-tight">Đăng nhập nội bộ</h1>
            <p className="text-sm text-muted-foreground">Nhập tài khoản hoặc email để truy cập theo phân quyền.</p>
          </div>

          {setupStatus && !setupStatus.initialized && (
            <div className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
              <p className="font-semibold">Hệ thống chưa có tài khoản Quản trị viên</p>
              <p className="mt-1">
                Lần đầu vận hành?{' '}
                <Link to="/admin_cp" className="font-bold underline underline-offset-2 hover:opacity-80">
                  Khởi tạo Quản trị viên ban đầu tại đây →
                </Link>
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="account">Tài khoản (user) hoặc Email</Label>
              <Input
                id="account"
                type="text"
                autoComplete="username"
                placeholder="VD: admin, sale01 hoặc email"
                value={account}
                onChange={(e) => setAccount(e.target.value)}
                className="h-11 text-base sm:text-sm"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Mật khẩu</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="Nhập mật khẩu"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-11 text-base sm:text-sm"
                required
              />
            </div>
            {login.isError && (
              <p role="alert" className="text-sm text-destructive">
                {errorMessage(login.error)}
              </p>
            )}
            <Button type="submit" size="lg" className="w-full" disabled={login.isPending}>
              {login.isPending ? <Loader2 className="animate-spin" /> : <LogIn />}
              {login.isPending ? 'Đang xử lý...' : 'Đăng nhập'}
            </Button>
          </form>

          {/* Đăng nhập nhanh theo vai trò (tài khoản demo) */}
          <div className="space-y-3 border-t border-border pt-5">
            <p className="eyebrow text-center">Tài khoản demo đăng nhập nhanh</p>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_ACCOUNTS.map(({ user, label, icon: Icon }) => (
                <Button
                  key={user}
                  type="button"
                  variant="outline"
                  className="h-12 justify-start gap-3 px-3"
                  onClick={() => {
                    setAccount(user)
                    setPassword(user)
                  }}
                >
                  <Icon className="text-gold" aria-hidden="true" />
                  <span className="flex min-w-0 flex-col items-start leading-tight">
                    <span className="truncate text-sm">{label}</span>
                    <span className="text-xs font-normal text-muted-foreground">({user})</span>
                  </span>
                </Button>
              ))}
            </div>
          </div>

          <a
            href="http://localhost:5173"
            className="block rounded-lg py-2 text-center text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            ← Đến Cổng thông tin khách hàng (Dự án và Căn hộ)
          </a>
        </div>
      </div>
    </div>
  )
}
