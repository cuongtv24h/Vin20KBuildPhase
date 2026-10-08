import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { AuthSession, UserRole } from '@pricepolicy/api-client/contracts'

interface SessionState {
  session: AuthSession | null
  setSession: (session: AuthSession) => void
  clearSession: () => void
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      session: null,
      setSession: (session) => set({ session }),
      clearSession: () => set({ session: null }),
    }),
    {
      name: 'pricepolicy.session',
      storage: createJSONStorage(() => sessionStorage),
    },
  ),
)

export function getAccessToken(): string | null {
  const session = useSessionStore.getState().session
  if (!session) return null
  if (new Date(session.expires_at).getTime() < Date.now()) return null
  return session.access_token
}

/** Trang chủ (entry point) của từng vai trò sau khi đăng nhập. */
export const ROLE_HOME: Record<UserRole, string> = {
  ADMIN: '/admin_cp',
  SALE: '/sale',
  MANAGER: '/manager/approvals',
  POLICY_ADMIN: '/admin/policies',
}

// `ROLE_AREA` (tiền tố route theo vai trò) đã bỏ: quyền vào từng khu route khai báo ở `@/auth/roles`
// (AREA_ROLES) và việc "đăng nhập lại thì về trang cũ" xét bằng `canOpenPath` cho chính xác.

