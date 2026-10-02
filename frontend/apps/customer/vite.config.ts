import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// UI Khách hàng — origin riêng (:5173), gọi thẳng packages/mock-server hoặc backend thật qua
// NEXT_PUBLIC_API_BASE_URL (URL tuyệt đối, CORS — xem API_INTEGRATION.md). Không dùng proxy: hai
// app (Khách hàng, Nội bộ) là hai origin thật, dev phải khớp topology thật để CORS được kiểm chứng.
export default defineConfig({
  plugins: [react()],
  envDir: path.resolve(import.meta.dirname, '../../../'),
  envPrefix: ['VITE_', 'NEXT_PUBLIC_'],
  server: {
    port: 5173,
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
})
