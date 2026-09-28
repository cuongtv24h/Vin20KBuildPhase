import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ROLE_HOME, getAccessToken, useSessionStore } from '@/auth/sessionStore'
import type { UserRole } from '@pricepolicy/api-client/contracts'

/** Chặn truy cập theo vai trò: chưa đăng nhập → /login; sai vai trò → trang chủ của vai trò đó. */
export function RequireRole({ role, children }: { role: UserRole; children: ReactNode }) {
  const session = useSessionStore((s) => s.session)
  const location = useLocation()

  if (!session || !getAccessToken()) {
    return <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname + location.search)}`} replace />
  }
  if (session.user.role !== role) {
    return <Navigate to={ROLE_HOME[session.user.role]} replace />
  }
  return <>{children}</>
}
