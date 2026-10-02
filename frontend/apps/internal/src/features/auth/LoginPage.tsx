import { Loader2, LogIn, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useAdminSetupStatus, useLogin } from '@pricepolicy/api-client/hooks'
import { ROLE_AREA, ROLE_HOME, getAccessToken, useSessionStore } from '@/auth/sessionStore'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'

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
    <div className="grid min-h-screen lg:grid-cols-[1.1fr,1fr]">
      <div className="relative hidden flex-col justify-between bg-primary p-10 text-primary-foreground lg:flex">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-foreground/10">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <span className="font-display text-xl font-semibold">PricePolicy · VLandFuture</span>
        </Link>
        <div className="max-w-md space-y-3">
          <p className="font-display text-3xl font-semibold leading-tight">Báo giá đúng chính sách, duyệt trong một phút.</p>
        </div>
        <p className="text-xs text-primary-foreground/50">© 2026 VLandFuture</p>
      </div>

      <div className="flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm space-y-6">
          <div className="space-y-1">
            <h1 className="font-display text-2xl font-semibold tracking-tight">Đăng nhập nội bộ</h1>
            <p className="text-sm text-muted-foreground">Nhập tài khoản hoặc email để truy cập theo phân quyền.</p>
          </div>

          {setupStatus && !setupStatus.initialized && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-300">
              <p className="font-semibold">Hệ thống chưa có tài khoản Quản trị viên</p>
              <p className="mt-1">
                Lần đầu vận hành?{' '}
                <Link to="/admin_cp" className="font-bold underline hover:text-amber-900 dark:hover:text-amber-100">
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
                required
              />
            </div>
            {login.isError && <p className="text-sm text-destructive">{errorMessage(login.error)}</p>}
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
              Đăng nhập
            </Button>
          </form>

          {/* Quick Demo Accounts */}
          <div className="pt-2">
            <p className="text-xs text-muted-foreground text-center mb-2 font-medium">Tài khoản demo đăng nhập nhanh:</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="justify-start text-xs h-8 text-left"
                onClick={() => {
                  setAccount('sale')
                  setPassword('sale')
                }}
              >
                💼 Sale (sale)
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="justify-start text-xs h-8 text-left"
                onClick={() => {
                  setAccount('manager')
                  setPassword('manager')
                }}
              >
                👔 Quản lý (manager)
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="justify-start text-xs h-8 text-left"
                onClick={() => {
                  setAccount('admin')
                  setPassword('admin')
                }}
              >
                🛡️ Admin (admin)
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="justify-start text-xs h-8 text-left"
                onClick={() => {
                  setAccount('policy')
                  setPassword('policy')
                }}
              >
                📜 Chính sách (policy)
              </Button>
            </div>
          </div>

          <a href="http://localhost:5173" className="block text-center text-sm text-muted-foreground hover:text-foreground">
            ← Đến Cổng thông tin khách hàng (Dự án & Căn hộ)
          </a>
        </div>
      </div>
    </div>
  )
}
