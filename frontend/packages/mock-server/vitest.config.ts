import { defineConfig } from 'vitest/config'

/**
 * Test của mock-server chạy API client trong Node (không có `window`), nên `config.ts` không thể
 * suy ra base URL và sẽ rơi về '/api/v1' — fetch tương đối không hợp lệ ở Node. MSW chặn mọi
 * origin khớp `*​/api/v1`, nên chỉ cần một base URL tuyệt đối trỏ về PORT mặc định của server.ts.
 *
 * Trước đây phải chạy `NEXT_PUBLIC_API_BASE_URL=... npm test`; cấu hình này để lệnh `npm test`
 * mặc định xanh mà không cần biến môi trường thủ công.
 */
export default defineConfig({
  define: {
    'import.meta.env.NEXT_PUBLIC_API_BASE_URL': JSON.stringify('http://localhost:8787/api/v1'),
  },
  test: {
    environment: 'node',
    // Mỗi test đi qua nhiều lượt HTTP thật + độ trễ mô phỏng của mock (flags.time_scale), nên 5s mặc
    // định của vitest là quá sát: test "nguồn ENV → DB" cần 4 test con (login, khởi tạo ADMIN, CRUD)
    // và từng chạm trần 5s khi máy chậm. 20s là mức an toàn, không che giấu test treo thật.
    testTimeout: 20_000,
  },
})
