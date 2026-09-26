import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { AuthSession } from '@/api/contracts'
import type { UserRole } from '@/types/domain'

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
  if (new Date(session.expiresAt).getTime() < Date.now()) return null
  return session.accessToken
}

/** Trang chủ (entry point) của từng vai trò sau khi đăng nhập. */
export const ROLE_HOME: Record<UserRole, string> = {
  SALE: '/sale',
  MANAGER: '/manager',
  SALE_ADMIN: '/admin',
}
