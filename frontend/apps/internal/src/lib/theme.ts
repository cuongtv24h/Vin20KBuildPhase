import { useCallback, useSyncExternalStore } from 'react'

export type Theme = 'dark' | 'light' | 'calm'

export const THEME_CONFIG: Record<
  Theme,
  { label: string; next: Theme; nextLabel: string; description: string }
> = {
  dark: {
    label: 'Tối',
    next: 'light',
    nextLabel: 'Sáng (Ngà ấm)',
    description: 'Luxury Black sang trọng, hiện đại',
  },
  light: {
    label: 'Sáng',
    next: 'calm',
    nextLabel: 'Dịu mắt (Xanh trắng)',
    description: 'Ivory & Champagne ấm áp',
  },
  calm: {
    label: 'Dịu mắt',
    next: 'dark',
    nextLabel: 'Tối (Luxury Black)',
    description: 'Xanh da trời sáng dịu mắt',
  },
}

const KEY = 'pp-theme'
const listeners = new Set<() => void>()

function read(): Theme {
  const attr = document.documentElement.getAttribute('data-theme')
  if (attr === 'light') return 'light'
  if (attr === 'calm') return 'calm'
  return 'dark'
}

type Origin = { x: number; y: number }

function commit(theme: Theme) {
  const root = document.documentElement
  if (theme === 'dark') {
    root.removeAttribute('data-theme')
  } else {
    root.setAttribute('data-theme', theme)
  }
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    /* chế độ riêng tư: bỏ qua, vẫn đổi được trong phiên */
  }
  listeners.forEach((l) => l())
}

/**
 * Đổi giao diện có hiệu ứng:
 * - Trình duyệt hỗ trợ View Transitions: màu mới loang tròn ra từ điểm vừa bấm.
 * - Không hỗ trợ: các bề mặt chuyển màu mượt (fade) khoảng 0,35 giây.
 * - Người dùng bật "giảm chuyển động": đổi tức thì, không hiệu ứng.
 */
function apply(theme: Theme, origin?: Origin) {
  const root = document.documentElement
  if (read() === theme) return
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  if (reduced) {
    // Tắt transition trong một khung hình để mọi bề mặt đổi cùng lúc, không nháy từng phần.
    const style = document.createElement('style')
    style.textContent = '*,*::before,*::after{transition:none!important}'
    document.head.appendChild(style)
    commit(theme)
    void getComputedStyle(root).color
    requestAnimationFrame(() => requestAnimationFrame(() => style.remove()))
    return
  }

  if (typeof document.startViewTransition === 'function') {
    const x = origin?.x ?? window.innerWidth / 2
    const y = origin?.y ?? window.innerHeight / 2
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))
    const transition = document.startViewTransition(() => commit(theme))
    void transition.ready
      .then(() => {
        root.animate(
          { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
          { duration: 650, easing: 'cubic-bezier(0.4, 0, 0.2, 1)', pseudoElement: '::view-transition-new(root)' },
        )
      })
      .catch(() => undefined)
    return
  }

  root.classList.add('theme-fading')
  commit(theme)
  window.setTimeout(() => root.classList.remove('theme-fading'), 450)
}

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, read, () => 'dark' as Theme)
  const setTheme = useCallback((t: Theme, origin?: Origin) => apply(t, origin), [])
  const toggle = useCallback(() => {
    const current = read()
    apply(THEME_CONFIG[current].next)
  }, [])
  return { theme, setTheme, toggle }
}
