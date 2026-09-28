import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ApiError } from '@pricepolicy/api-client/errors'
import App from './App.tsx'
import './index.css'

const queryClient = new QueryClient({
  queryCache: new QueryCache(),
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      // Lỗi nghiệp vụ (4xx) hiển thị ngay; lỗi hạ tầng thử lại 1 lần. Khách không có phiên đăng
      // nhập nên 401 không cần xử lý riêng (mọi route /public đều công khai).
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
