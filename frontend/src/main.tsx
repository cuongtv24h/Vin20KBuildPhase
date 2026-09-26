import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ApiError } from '@/api/errors'
import { setAuthTokenProvider } from '@/api/http'
import { getAccessToken, useSessionStore } from '@/auth/sessionStore'
import App from './App.tsx'
import './index.css'

setAuthTokenProvider(getAccessToken)

/** Phiên hết hạn / bị thu hồi → xoá phiên, RequireRole đưa về /login. */
function handleAuthError(error: unknown) {
  if (error instanceof ApiError && error.status === 401) useSessionStore.getState().clearSession()
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleAuthError }),
  mutationCache: new MutationCache({ onError: handleAuthError }),
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      // Lỗi nghiệp vụ (4xx) hiển thị ngay; lỗi hạ tầng thử lại 1 lần.
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 1,
    },
  },
})

async function bootstrap() {
  // So sánh trực tiếp biến môi trường (thay tĩnh lúc build) để bản build real loại bỏ hẳn MSW & dữ liệu mock.
  if (import.meta.env.NEXT_PUBLIC_API_MODE !== 'real') {
    const { startMockBackend } = await import('./mocks/browser')
    await startMockBackend({ onExternalChange: () => void queryClient.invalidateQueries() })
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

void bootstrap()
