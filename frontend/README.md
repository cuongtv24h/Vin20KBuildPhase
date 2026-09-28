# PricePolicy — Frontend

Hai UI độc lập cho PricePolicy AI Agent, **không có link hay menu chuyển giữa hai UI — chỉ trao đổi
qua API** (mục 0 của brief cấu trúc):

| App | Vai trò | Origin (dev) | Đăng nhập |
| :--- | :--- | :--- | :--- |
| **Khách hàng** (`apps/customer`) | Pre-Sales công khai: tư vấn tài chính, phương án tham khảo (F1–F3, F5) | `http://localhost:5173` | Không |
| **Nội bộ** (`apps/internal`) | Sale, Quản lý, Quản trị chính sách | `http://localhost:5174` | Có |

Monorepo npm workspaces, kiến trúc **mock-first, backend-ready**: chạy đầy đủ trên
`packages/mock-server` ngay bây giờ, chuyển sang FastAPI thật chỉ bằng biến môi trường — không sửa
màn hình.

```
apps/customer, apps/internal   Vite + React 18 + TypeScript + Tailwind + TanStack Query
packages/api-client            API client dùng chung (contracts, http, SSE, hooks) — cả hai app phụ thuộc
packages/ui                    Component dùng chung (shadcn primitives, MoneyText, Evidence, ReferencePlanView…)
packages/mock-server           Backend giả lập: chạy như tiến trình Node THẬT trên cổng TCP thật (không phải
                                MSW-trong-trình-duyệt) — để state liên thông giữa 2 app và CORS có ý nghĩa thật
```

## Chạy

```bash
npm install
cp apps/customer/.env.example apps/customer/.env.local
cp apps/internal/.env.example apps/internal/.env.local
npm run dev     # mock-server :8787 + Khách hàng :5173 + Nội bộ :5174 (concurrently)
npm test        # 21 test trên mock-server (18 kịch bản đầu-cuối + unit)
npm run lint && npm run build
```

Chạy riêng từng phần: `npm run dev:mock` · `npm run dev:customer` · `npm run dev:internal`.

Tài khoản nội bộ (mock), mật khẩu `Vland@2026`: `nam.hoang@` (Sale), `trang.le@` (Sale),
`ha.nguyen@` (Quản lý), `minh.tuan@` (Quản trị chính sách) — đuôi `vlandfuture.vn`. Ở app Nội bộ khi
`npm run dev:mock` đang chạy có panel góc dưới phải để đăng nhập nhanh, giả lập mạng chậm / lỗi 500 /
rớt SSE / 410 / PDF lỗi / Agent chậm và reset demo — gọi thẳng `packages/mock-server`, không đi qua
app Khách hàng.

## Kiến trúc

```
Component (chỉ render)  →  Hooks (packages/api-client/hooks)  →  API client (http.ts, sse.ts)
                                                                                    │
                                            gọi qua CORS (2 origin khác nhau) ──────┤
                                                                                    ▼
                                         packages/mock-server (:8787)  hoặc  FastAPI thật
```

Cả hai app gọi thẳng `NEXT_PUBLIC_API_BASE_URL` (URL tuyệt đối) qua CORS — không qua proxy của Vite
dev server, vì đây là hai origin thật, độc lập (không phải app+API cùng origin như một SPA gộp).
`packages/mock-server` bật CORS cho cả hai origin dev; khi ghép backend thật, backend phải cấu hình
CORS tương đương (xem `API_INTEGRATION.md` §"Hai UI riêng biệt · TL-3").

| Thư mục | Vai trò |
| :--- | :--- |
| `packages/api-client/src/contracts/` | Type hợp đồng (snake_case wire format) — thay bằng type sinh từ OpenAPI khi có |
| `packages/api-client/src/endpoints.ts` | Danh bạ endpoint duy nhất (method, path, nguồn TD-4.4 / ĐỀ XUẤT) |
| `packages/api-client/src/hooks/` | `useQuote`, `useQuoteEvents`, `usePreSalesEvents`, `useLeads`, `useComplianceCheck`, … |
| `packages/ui/src/` | Component dùng chung cho cả 2 app: `components/ui` (shadcn), `components/common`, `components/quote/Evidence`, `components/presales/ReferencePlanView`, `lib/` |
| `packages/mock-server/src/` | Backend giả lập chạy Node thật: `server.ts` (cầu nối HTTP↔handler), `handlers/`, `services/`, `engine/` (tính giá, xung đột, F8, pre-sales), `seed.ts` |
| `apps/customer/src/features/customer/` | `CustomerHomePage`, `AdvisorPage` (chat, phương án tham khảo có watermark, SSE) |
| `apps/internal/src/features/` | `sale/`, `manager/`, `admin/` + `auth/` (đăng nhập, RBAC) |

Component **không** import `packages/mock-server`. Chi tiết endpoint → hook → màn hình, danh sách
field đề xuất bổ sung contract, quy ước SSE / idempotency / OCC, và các câu hỏi cần TechLead chốt
(đường dẫn SSE, tên 2 objective còn thiếu…): **[API_INTEGRATION.md](API_INTEGRATION.md)**.

## Route

| App | Route |
| :--- | :--- |
| Khách hàng | `/`, `/tu-van?can=ZEN-A-1205` |
| Nội bộ — Sale | `/login`, `/sale/leads`, `/sale/quotes`, `/sale/quotes/new?dossier=…`, `/sale/quotes/:id`, `/sale/quotes/:id/revise` |
| Nội bộ — Quản lý | `/manager/approvals`, `/manager/approvals/:id` |
| Nội bộ — Quản trị chính sách | `/admin/policies`, `/admin/policies/:id`, `/admin/benchmark` |
