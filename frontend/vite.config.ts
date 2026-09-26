/// <reference types="vitest/config" />
import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    // Giữ tên biến NEXT_PUBLIC_* theo TD-4.1 (Next.js) — xem src/api/config.ts.
    envPrefix: ['VITE_', 'NEXT_PUBLIC_'],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname, './src'),
      },
    },
    server: {
      // NEXT_PUBLIC_API_MODE=real + NEXT_PUBLIC_API_BASE_URL=/api/v1 → dev server chuyển tiếp tới FastAPI, không cần CORS.
      proxy: {
        '/api': { target: env.API_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      // fetch trong Node cần URL tuyệt đối; MSW khớp mọi origin.
      env: { NEXT_PUBLIC_API_BASE_URL: 'http://localhost/api/v1' },
      testTimeout: 20_000,
    },
  }
})
