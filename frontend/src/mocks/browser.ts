import { setupWorker } from 'msw/browser'
import { getDb, onExternalChange } from './db'
import { handlers } from './handlers'

/**
 * Khởi động backend giả lập trong trình duyệt. Chỉ được import động từ main.tsx khi
 * NEXT_PUBLIC_API_MODE=mock — bundle chế độ real không chứa mã này.
 */
export async function startMockBackend(options: { onExternalChange?: () => void } = {}) {
  const worker = setupWorker(...handlers)
  await worker.start({
    onUnhandledRequest: 'bypass',
    quiet: true,
    serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
  })
  await getDb()
  if (options.onExternalChange) onExternalChange(options.onExternalChange)
}
