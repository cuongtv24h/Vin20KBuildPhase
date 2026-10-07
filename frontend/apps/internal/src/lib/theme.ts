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

function apply(theme: Theme) {
  const root = document.documentElement
  // Tắt transition trong một khung hình để mọi bề mặt đổi cùng lúc, không nháy từng phần.
  const style = document.createElement('style')
  style.textContent = '*,*::before,*::after{transition:none!important}'
  document.head.appendChild(style)
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
  void getComputedStyle(root).color
  requestAnimationFrame(() => requestAnimationFrame(() => style.remove()))
  listeners.forEach((l) => l())
}

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, read, () => 'dark' as Theme)
  const setTheme = useCallback((t: Theme) => apply(t), [])
  const toggle = useCallback(() => {
    const current = read()
    apply(THEME_CONFIG[current].next)
  }, [])
  return { theme, setTheme, toggle }
}
