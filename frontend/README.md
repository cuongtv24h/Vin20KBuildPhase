# PricePolicy — Frontend

Multi-role workspace (C-08) cho PricePolicy AI Agent: Khách hàng pre-sale, Sale, Quản lý, Quản trị chính sách.
Vite + React 18 + TypeScript + Tailwind + TanStack Query. Kiến trúc **mock-first, backend-ready**: chạy đầy
đủ trên MSW ngay bây giờ, chuyển sang FastAPI chỉ bằng biến môi trường.

## Chạy

```bash
npm install
cp .env.example .env.local     # NEXT_PUBLIC_API_MODE=mock | real
npm run dev                    # http://localhost:5173
npm test                       # 18 kịch bản đầu-cuối trên MSW + unit test
npm run lint && npm run build
```

Tài khoản (mock), mật khẩu `Vland@2026`: `nam.hoang@` (Sale), `trang.le@` (Sale), `ha.nguyen@` (Quản lý),
`minh.tuan@` (Quản trị chính sách) — đuôi `vlandfuture.vn`. Ở `npm run dev` + mock có panel góc dưới phải để
đăng nhập nhanh, giả lập mạng chậm / lỗi 500 / rớt SSE / 410 / PDF lỗi và reset demo.

## Kiến trúc

```
Component (chỉ render)  →  Hooks (src/api/hooks)  →  API client (src/api/client.ts, http.ts, sse.ts)  →  /api/v1/…
                                                                                                   ↑
                                                                         MSW (src/mocks) khi mode = mock
```

| Thư mục | Vai trò |
| :--- | :--- |
| `src/api/contracts/` | Type hợp đồng (snake_case wire format) — thay bằng type sinh từ OpenAPI khi có |
| `src/api/endpoints.ts` | Danh bạ endpoint duy nhất (method, path, nguồn TD-4.4 / ĐỀ XUẤT) |
| `src/api/hooks/` | `useQuote`, `useQuoteEvents`, `useLeads`, `useComplianceCheck`, … — thứ duy nhất màn hình gọi |
| `src/mocks/` | Backend giả lập: handler MSW, engine tính giá / xung đột / F8 / pre-sales, seed dữ liệu |
| `src/features/` | Màn hình theo vai trò: `customer`, `sale`, `manager`, `admin` |
| `src/components/` | UI dùng chung; `quote/` (kết quả, chứng cứ, tiến trình Agent), `compliance/`, `presales/` |

Component **không** import `src/mocks`. Chi tiết endpoint → hook → màn hình, danh sách field đề xuất bổ sung
contract và quy ước SSE / idempotency / OCC: **[API_INTEGRATION.md](API_INTEGRATION.md)**.

## Route

| Vai trò | Route |
| :--- | :--- |
| Khách hàng | `/`, `/tu-van?can=ZEN-A-1205` |
| Sale | `/sale/leads`, `/sale/quotes`, `/sale/quotes/new?dossier=…`, `/sale/quotes/:id`, `/sale/quotes/:id/revise` |
| Quản lý | `/manager/approvals`, `/manager/approvals/:id` |
| Quản trị chính sách | `/admin/policies`, `/admin/policies/:id`, `/admin/benchmark` |
