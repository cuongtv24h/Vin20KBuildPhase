import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// UI Nội bộ (Sale/Quản lý/Quản trị chính sách) — origin riêng (:5174), gọi thẳng
// packages/mock-server hoặc backend thật qua NEXT_PUBLIC_API_BASE_URL (URL tuyệt đối, CORS — xem
// API_INTEGRATION.md). Không dùng proxy: hai app là hai origin thật, dev phải khớp topology thật.
export default defineConfig({
  plugins: [react()],
  envPrefix: ['VITE_', 'NEXT_PUBLIC_'],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
})
