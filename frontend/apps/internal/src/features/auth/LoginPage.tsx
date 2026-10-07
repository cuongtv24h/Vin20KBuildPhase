import { Briefcase, Eye, EyeOff, FileCheck2, Loader2, LogIn, ScrollText, ShieldCheck, Sparkles, UserCog, type LucideIcon } from 'lucide-react'
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

/** Điểm nổi bật ở cột thương hiệu (bố cục Neon: khẩu hiệu + 3 lợi ích ngắn). */
const HIGHLIGHTS: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Sparkles, title: 'Trợ lý AI cho Sale', text: 'Tra chính sách, so sánh phương án thanh toán ngay trong cuộc trò chuyện.' },
  { icon: ShieldCheck, title: 'Kiểm soát rủi ro', text: 'Cờ Xanh/Vàng/Đỏ tự động, tách biệt người lập và người duyệt.' },
  { icon: FileCheck2, title: 'Duyệt và ký số', text: 'Báo giá chính thức được thẩm định và ký số trước khi gửi khách.' },
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
  const [showPassword, setShowPassword] = useState(false)

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
        {/* Lưới chấm mờ (bố cục Vapi) tạo chiều sâu cho nền tối */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-[0.18] [background-image:radial-gradient(hsl(var(--sidebar-foreground)/0.5)_1px,transparent_1px)] [background-size:22px_22px] [mask-image:linear-gradient(to_bottom,transparent,black_30%,black_70%,transparent)]"
        />
        <div aria-hidden="true" className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-primary/[0.07] blur-3xl" />
        <Link to="/" className="relative flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-primary/40 text-primary">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <span className="font-display text-xl font-semibold tracking-tight">PricePolicy · VLandFuture</span>
        </Link>
        <div className="relative max-w-md space-y-8">
          <div className="space-y-4">
            <p className="eyebrow text-gold">Cổng nội bộ</p>
            <p className="font-display text-4xl font-semibold leading-tight tracking-tight">Báo giá đúng chính sách, duyệt trong một phút.</p>
          </div>
          <ul className="space-y-4">
            {HIGHLIGHTS.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="text-sm leading-snug">
                  <span className="block font-medium">{title}</span>
                  <span className="text-sidebar-muted">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-sidebar-muted">© 2026 VLandFuture</p>
      </div>

      <div className="relative flex items-center justify-center px-4 py-10">
        <div className="absolute right-4 top-4"><ThemeToggle side="bottom" className="text-muted-foreground hover:bg-accent hover:text-foreground" /></div>
        <div className="w-full max-w-sm space-y-6 sm:rounded-2xl sm:border sm:border-border sm:bg-card sm:p-8 sm:shadow-sm">
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
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Nhập mật khẩu"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="h-11 pr-11 text-base sm:text-sm"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  aria-pressed={showPassword}
                  title={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  className="absolute right-1 top-1/2 inline-flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
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

        </div>
      </div>
    </div>
  )
}
