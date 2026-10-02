import { defineConfig } from 'vitest/config'

/**
 * Test của gói UI chạy trong Node (không cần DOM thật): các hàm ở `lib/` đều nhận môi trường qua
 * tham số hoặc qua `window` giả lập tối thiểu, nên không phải cài jsdom — vốn không có sẵn trong
 * môi trường triển khai nội bộ.
 */
export default defineConfig({
  test: {
    environment: 'node',
    testTimeout: 10_000,
  },
})
