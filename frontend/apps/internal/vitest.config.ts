import { defineConfig } from 'vitest/config'

/**
 * Test của app nội bộ chạy trong Node (không cần DOM thật): chỉ kiểm tra các hàm thuần trong
 * `features/*` — ví dụ ngữ cảnh căn/khách cho luồng lập báo giá (lỗi #16 đợt 20).
 */
export default defineConfig({
  test: {
    environment: 'node',
    testTimeout: 10_000,
    include: ['src/**/*.test.ts'],
  },
})
