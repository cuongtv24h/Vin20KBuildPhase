import { useCallback, useSyncExternalStore } from 'react'

export type Theme = 'dark' | 'light'

const KEY = 'pp-theme'
const listeners = new Set<() => void>()

function read(): Theme {
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark'
}

function apply(theme: Theme) {
  const root = document.documentElement
  // Tắt transition trong một khung hình để mọi bề mặt đổi cùng lúc, không nháy từng phần.
  const style = document.createElement('style')
  style.textContent = '*,*::before,*::after{transition:none!important}'
  document.head.appendChild(style)
  if (theme === 'light') root.setAttribute('data-theme', 'light')
  else root.removeAttribute('data-theme')
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
  const toggle = useCallback(() => apply(read() === 'dark' ? 'light' : 'dark'), [])
  return { theme, toggle }
}
