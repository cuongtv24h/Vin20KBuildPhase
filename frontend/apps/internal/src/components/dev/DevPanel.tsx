import { useQueryClient } from '@tanstack/react-query'
import { FlaskRound, Loader2, RotateCcw, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDemoAccounts, useMockFlags, useResetDemo, useUpdateMockFlags, type MockFlags } from '@pricepolicy/api-client/devtools'
import { useLogin } from '@pricepolicy/api-client/hooks'
import { ROLE_HOME, useSessionStore } from '@/auth/sessionStore'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Switch } from '@pricepolicy/ui/components/ui/switch'
import { ROLE_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'
import { toast } from '@pricepolicy/ui/state/toastStore'

/**
 * Bảng điều khiển môi trường mock — chỉ render khi NEXT_PUBLIC_API_MODE=mock và `npm run dev`
 * (IS_DEV_TOOLS_ENABLED). Không xuất hiện trong bản build hay chế độ real.
 */
export function DevPanel() {
  const [open, setOpen] = useState(false)
  const flags = useMockFlags(open)
  const accounts = useDemoAccounts(open)
  const update = useUpdateMockFlags()
  const reset = useResetDemo()
  const login = useLogin()
  const setSession = useSessionStore((s) => s.setSession)
  const clearSession = useSessionStore((s) => s.clearSession)
  const qc = useQueryClient()
  const navigate = useNavigate()

  const toggle = (key: keyof MockFlags, label: string) => (
    <label className="flex items-center justify-between gap-3 py-1 text-xs">
      <span>{label}</span>
      <Switch checked={Boolean(flags.data?.[key])} onCheckedChange={(v) => update.mutate({ [key]: v })} />
    </label>
  )

  async function switchTo(email: string, password: string) {
    const session = await login.mutateAsync({ email, password })
    qc.clear()
    setSession(session)
    navigate(ROLE_HOME[session.user.role])
  }

  async function handleReset() {
    if (!window.confirm('Xoá toàn bộ dữ liệu demo và nạp lại dữ liệu mẫu?')) return
    await reset.mutateAsync()
    clearSession()
    qc.clear()
    navigate('/')
    toast.success('Đã nạp lại dữ liệu demo')
  }

  return (
    <div className="fixed bottom-4 right-4 z-[60]">
      {open ? (
        <div className="w-72 space-y-3 rounded-xl border border-border bg-card p-3 text-card-foreground shadow-2xl" data-testid="dev-panel">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Mock backend</p>
            <button type="button" onClick={() => setOpen(false)} aria-label="Đóng" className="rounded p-1 hover:bg-muted">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          {flags.isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <div className="divide-y divide-border">
              <div className="flex items-center justify-between py-1 text-xs">
                <span>Mạng</span>
                <div className="flex rounded-md border border-border p-0.5">
                  {(['normal', 'slow'] as const).map((l) => (
                    <button
                      key={l}
                      type="button"
                      onClick={() => update.mutate({ latency: l })}
                      className={cn('rounded px-2 py-0.5', flags.data?.latency === l ? 'bg-primary text-primary-foreground' : 'text-muted-foreground')}
                    >
                      {l === 'normal' ? '200–800ms' : 'Chậm'}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between py-1 text-xs">
                <span>Lỗi 500</span>
                <div className="flex rounded-md border border-border p-0.5">
                  {[0, 0.3, 1].map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => update.mutate({ fail_rate: r })}
                      className={cn('rounded px-2 py-0.5', flags.data?.fail_rate === r ? 'bg-primary text-primary-foreground' : 'text-muted-foreground')}
                    >
                      {r * 100}%
                    </button>
                  ))}
                </div>
              </div>
              {toggle('slow_agent', 'Agent chậm (> 10s)')}
              {toggle('drop_sse_once', 'Ngắt SSE giữa chừng')}
              {toggle('expire_replay', 'Replay hết hạn (410)')}
              {toggle('pdf_worker_fail', 'PDF worker lỗi')}
            </div>
          )}
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Đăng nhập nhanh</p>
            {(accounts.data ?? []).map((a) => (
              <button
                key={a.email}
                type="button"
                disabled={login.isPending}
                onClick={() => void switchTo(a.email, a.password).catch(() => undefined)}
                className="flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-xs hover:bg-muted"
                data-testid={`dev-login-${a.role}`}
              >
                <span className="font-medium">{a.full_name}</span>
                <span className="text-muted-foreground">{ROLE_LABEL[a.role]}</span>
              </button>
            ))}
          </div>
          <Button variant="outline" size="sm" className="w-full" onClick={() => void handleReset()} disabled={reset.isPending}>
            {reset.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />} Reset demo
          </Button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-lg hover:text-foreground"
          aria-label="Mock backend"
          data-testid="dev-panel-toggle"
        >
          <FlaskRound className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
