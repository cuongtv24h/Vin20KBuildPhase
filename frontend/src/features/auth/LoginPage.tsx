import { Loader2, LogIn, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { errorMessage } from '@/api/errors'
import { useLogin } from '@/api/hooks'
import { ROLE_AREA, ROLE_HOME, getAccessToken, useSessionStore } from '@/auth/sessionStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

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
            <h1 className="font-display text-2xl font-semibold tracking-tight">Đăng nhập</h1>
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

          <Link to="/" className="block text-center text-sm text-muted-foreground hover:text-foreground">
            ← Về trang dự án
          </Link>
        </div>
      </div>
    </div>
  )
}
