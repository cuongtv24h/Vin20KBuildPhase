import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// UI Nội bộ (Sale/Quản lý/Quản trị chính sách) — origin riêng (:5174), gọi thẳng
// packages/mock-server hoặc backend thật qua NEXT_PUBLIC_API_BASE_URL (URL tuyệt đối, CORS — xem
// API_INTEGRATION.md). Không dùng proxy: hai app là hai origin thật, dev phải khớp topology thật.
export default defineConfig({
  plugins: [react()],
  envDir: path.resolve(import.meta.dirname, '../../../'),
  envPrefix: ['VITE_', 'NEXT_PUBLIC_'],
  server: {
    port: 5174,
    // Dev trong sandbox/preview trỏ tới host ngoài localhost → phải bind 0.0.0.0 và cho phép host lạ.
    // Chỉ áp dụng cho máy chủ dev, không ảnh hưởng bản build.
    host: true,
    allowedHosts: true,
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
