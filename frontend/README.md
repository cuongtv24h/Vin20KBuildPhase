# Frontend — Next.js Multi-Role Workspace (C-08 → C-11 UI)

Vùng code của **Dev 3**. Backend FastAPI chạy ở `../src` — mọi call đi qua
`NEXT_PUBLIC_API_URL` (xem `.env.example`), KHÔNG hardcode localhost trong code.

## Khởi tạo (khi bắt đầu implement)

```bash
cd frontend
npx create-next-app@latest . --typescript --app --tailwind
```

## Các workspace cần dựng (theo ImplementPlan — Dev 3)

| Workspace | Components | Nội dung chính |
|---|---|---|
| `app/(customer)` | C-09 | Chat khám phá nhu cầu, xác nhận ràng buộc F2, bảng so sánh phương án + watermark `NOT AN OFFICIAL QUOTE`, popover mỏ neo `[1]`/`[2]` |
| `app/(sales)` | C-10, C-11 | Tiếp nhận Lead Dossier (SLA countdown, 1-click convert), Message Composer live-check debounce 500ms, cờ Đỏ/Vàng/Xanh, khóa nút Gửi khi vi phạm |
| `app/(manager)` | C-08 | Duyệt báo giá, bảng cờ rủi ro, ký số Ed25519, preview PDF có mã QR |
| `app/(policy-admin)` | C-08 | Upload văn bản chính sách, quản lý hiệu lực, theo dõi audit log |

## Yêu cầu kỹ thuật bắt buộc

1. **SSE client** — xử lý `GET /quotes/{id}/events` với auto-reconnect gửi
   `Last-Event-ID` (hợp đồng sự kiện: `src/contracts/events.py`).
2. **Type-safe contracts** — sinh TypeScript types từ Pydantic schemas trong
   `../src/contracts/` (mock trước khi backend xong: nguyên tắc Contracts-First
   ngày 1 trong `../mydoc/ImplementPlan.md`).
3. **Ranh giới pre-sales** — mọi output pre-sales phải hiển thị watermark
   "NOT AN OFFICIAL QUOTE" (INV-RT-09, TD-4.1).
4. **Compliance feedback** — dùng `POST /compliance/check-message` (debounce
   500ms), nút Gửi chỉ bật khi verdict cho phép (`ON_FINAL_SEND` do backend
   chốt chặn, UI không tự quyết).

Wireframe & UI flow: `../docs/team_report/Wireframe_UI_Flow.md`, mockup:
`../docs/team_report/ui_mockup.html`.
