import { defineConfig } from 'vitest/config'

/**
 * Test của `api-client`: phần lớn là hàm thuần (trạng thái phiên chat, dựng payload…) nên chạy ở
 * môi trường Node là đủ — không cần DOM, không cần chạy mock server.
 */
export default defineConfig({
  test: {
    environment: 'node',
    testTimeout: 10_000,
  },
})
