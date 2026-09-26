import { useSessionStore } from '@/auth/sessionStore'
import type { StaffUser } from '@/types/domain'

/** Người dùng đang đăng nhập — chỉ dùng bên trong route đã bọc RequireRole. */
export function useCurrentUser(): StaffUser {
  const user = useSessionStore((s) => s.session?.user)
  if (!user) throw new Error('useCurrentUser được gọi ngoài vùng đã đăng nhập.')
  return user
}
