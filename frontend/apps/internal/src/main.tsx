import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ApiError } from '@pricepolicy/api-client/errors'
import { setAuthTokenProvider, setSessionInfoProvider } from '@pricepolicy/api-client/http'
import { getAccessToken, useSessionStore } from '@/auth/sessionStore'
import App from './App.tsx'
import './index.css'

setAuthTokenProvider(getAccessToken)
setSessionInfoProvider(() => {
  const session = useSessionStore.getState().session
  if (!session) return null
  return {
    userId: session.user.user_id,
    role: session.user.role,
  }
})

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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
