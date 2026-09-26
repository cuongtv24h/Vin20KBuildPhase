import { Loader2, LogIn, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { API_MODE } from '@/api'
import { errorMessage } from '@/api/errors'
import { useLogin } from '@/api/hooks'
import { MOCK_PASSWORD, STAFF_FIXTURE } from '@/api/mock/fixtures/users'
import { ROLE_HOME, getAccessToken, useSessionStore } from '@/auth/sessionStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ROLE_LABEL } from '@/lib/labels'

export function LoginPage() {
  const session = useSessionStore((s) => s.session)
  const setSession = useSessionStore((s) => s.setSession)
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  if (session && getAccessToken()) {
    return <Navigate to={ROLE_HOME[session.user.role]} replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const result = await login.mutateAsync({ email, password }).catch(() => null)
    if (!result) return
    setSession(result)
    const redirect = params.get('redirect')
    const home = ROLE_HOME[result.user.role]
    navigate(redirect && redirect.startsWith(home) ? redirect : home, { replace: true })
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
          <p className="text-sm text-primary-foreground/70">Hệ thống lập báo giá, phê duyệt và quản trị chính sách bán hàng nội bộ.</p>
        </div>
        <p className="text-xs text-primary-foreground/50">© 2026 VLandFuture</p>
      </div>

      <div className="flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm space-y-6">
          <div className="space-y-1">
            <h1 className="font-display text-2xl font-semibold tracking-tight">Đăng nhập</h1>
            <p className="text-sm text-muted-foreground">Dùng tài khoản email công ty.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                placeholder="ten.ho@vlandfuture.vn"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Mật khẩu</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
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

          {API_MODE === 'mock' && (
            <div className="space-y-2 rounded-lg border border-dashed border-border p-3">
              <p className="text-xs font-medium text-muted-foreground">Tài khoản môi trường thử nghiệm</p>
              <div className="grid gap-1.5">
                {STAFF_FIXTURE.map((u) => (
                  <button
                    key={u.userId}
                    type="button"
                    data-testid={`quick-login-${u.userId}`}
                    onClick={() => {
                      setEmail(u.email)
                      setPassword(MOCK_PASSWORD)
                    }}
                    className="flex items-center justify-between rounded-md px-2.5 py-1.5 text-left text-sm hover:bg-muted"
                  >
                    <span className="font-medium">{u.fullName}</span>
                    <span className="text-xs text-muted-foreground">{ROLE_LABEL[u.role]}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <Link to="/" className="block text-center text-sm text-muted-foreground hover:text-foreground">
            ← Về trang dự án
          </Link>
        </div>
      </div>
    </div>
  )
}
