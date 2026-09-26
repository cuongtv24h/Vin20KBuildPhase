import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { API_MODE } from '@/api'
import { ApiError } from '@/api/errors'
import { onExternalChange } from '@/api/mock/db'
import { useSessionStore } from '@/auth/sessionStore'
import App from './App.tsx'
import './index.css'

/** Phiên hết hạn / bị thu hồi ở backend → xoá phiên, RequireRole sẽ đưa về /login. */
function handleAuthError(error: unknown) {
  if (error instanceof ApiError && error.status === 401) useSessionStore.getState().clearSession()
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleAuthError }),
  mutationCache: new MutationCache({ onError: handleAuthError }),
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    },
  },
})

if (API_MODE === 'mock') {
  // Đồng bộ dữ liệu giữa các tab (ví dụ: Sale ở tab này, khách mở báo giá ở tab khác).
  onExternalChange(() => queryClient.invalidateQueries())
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
