# PricePolicy AI Agent — Frontend (Demo)

Frontend **thuần** (không backend) cho PricePolicy AI Agent — Trust Layer định giá & quản trị
chính sách bán hàng bất động sản VLandFuture. Dựng theo bản demo tĩnh đã duyệt, bám sát các tài
liệu nghiệp vụ trong `docs/` (`1.requirement-analysis.md`, `2.product-discovery.md`,
`3.architecture-design.md`, `4.1-technical-architecture-runtime-deployment.md`).

## Đây là gì — và KHÔNG phải là gì

- ✅ React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui (tự viết theo recipe chuẩn) +
  lucide-react + react-router-dom + Zustand.
- ✅ Toàn bộ dữ liệu là **MOCK** (căn hộ, chính sách, quotes) — không có server, không có API
  route thật, không kết nối database.
- ✅ Toàn bộ logic tính toán (deterministic pricing, conflict detection, ranking, benchmark) là
  TypeScript thuần trong `src/engine/`, có thể unit-test độc lập với UI.
- ✅ Mã băm SHA-256 khi Quản lý phê duyệt là **THẬT** — tính bằng Web Crypto API
  (`crypto.subtle.digest`) trên nội dung JSON Snapshot đã chuẩn hoá (key sắp xếp đệ quy).
- ❌ Không có SSE/WebSocket thật — trạng thái "đang xử lý" được mô phỏng bằng state/async, không
  có hạ tầng streaming.
- ❌ Không có xác thực/JWT thật — bộ chuyển vai trò (Sales/Manager/Admin) ở góc trên chỉ đổi
  `role` trong Zustand store để demo nhanh.
- ❌ "Mã QR" trên báo giá chính thức là hoạ tiết lưới minh hoạ sinh từ hash, **không phải mã QR
  quét được thật** (đã ghi chú rõ ngay trên UI).

## Kiến trúc thư mục

```
src/
  components/ui/        shadcn/ui primitives (Button, Card, Badge, Tabs, Dialog, Select, ...)
  components/            Component nghiệp vụ (ScenarioCard, ApprovalQueueTable, SnapshotViewer...)
  engine/                 Logic thuần TypeScript, có unit test (Vitest):
                            calculator.ts       — Deterministic Pricing Engine (làm tròn từng bước)
                            conflictDetector.ts — Preflight / Safe Abstention Gate (3 cấp xung đột)
                            recommend.ts         — Xếp hạng phương án theo 4 tiêu chí tối ưu hoá
                            benchmark.ts         — 15 test case cố định (Formula Regression)
                            quoteFactory.ts      — Ráp preflight + calculator + recommend → Quote
  data/                   Lớp MOCK DATA — đổi ở đây khi nối API thật:
                            units.mock.ts        — Bảng hàng căn hộ (thay bằng GET /api/v1/units)
                            policies.mock.ts     — 2 phiên bản chính sách Time-Travel
                            plans.mock.ts         — Cấu hình dòng tiền 3 phương án
                            demoScenarios.ts      — 6 kịch bản diễn tập 1-click
                            quotes.store.ts       — Seed rỗng cho danh sách quotes
  state/appStore.ts       Zustand store: role hiện tại + danh sách quotes + toàn bộ action
  pages/                  OverviewPage, SalesCopilotPage, ManagerApprovalPage, AuditPage,
                          BenchmarkPage, DemoScenariosPage
  lib/                    utils.ts (cn), format.ts (VNĐ/ngày vi-VN), hash.ts (SHA-256 + canonical JSON)
  types/domain.ts         Toàn bộ type dùng chung (PolicyDecisionStatus, WorkflowStatus, Quote...)
```

## Điểm cần thay khi nối API thật

Chỉ cần sửa trong `src/data/` và một vài chỗ gọi trực tiếp — UI và `engine/` không cần đổi:

| File mock | Thay bằng |
| :--- | :--- |
| `data/units.mock.ts` | `GET /api/v1/units` (CRM/ERP read-only snapshot) |
| `data/policies.mock.ts` | `retrieve_policy_by_date` — API tra cứu chính sách theo ngày (Time-Travel) |
| `state/appStore.ts` → `submitFromCopilot` | `POST /api/v1/quotes` (theo TD-4.1, trả `202` + SSE stream) |
| `state/appStore.ts` → `approveQuote` | `POST /api/v1/quotes/{id}/approve` (chữ ký Ed25519 qua KMS thật, không chỉ SHA-256 phía client) |
| `engine/quoteFactory.ts` → `hashSnapshot` | Vẫn giữ nguyên logic canonical JSON, nhưng chữ ký nên do backend ký (client chỉ hiển thị) |

`engine/calculator.ts`, `conflictDetector.ts`, `recommend.ts` có thể tái sử dụng gần như nguyên
vẹn ở backend (Python) nếu muốn — vì đây là logic thuần, không phụ thuộc DOM/React.

## Chạy dự án

```bash
npm install
npm run dev        # http://localhost:5173
npm run test       # Vitest — 15/15 test case Benchmark phải Exact Match 100%
npm run build      # tsc -b && vite build
npm run lint        # oxlint
```

## Vai trò demo

Góc trên bên phải có bộ chuyển vai trò **Sales Executive / Sales Manager / Policy Admin** — đổi
ngay lập tức, không cần đăng nhập, chỉ để tiện demo tất cả các workspace trong 1 phiên trình
duyệt.

## Kịch bản Demo (trang "Kịch bản Demo")

1 Happy Path + 5 Failure Cases đã hardcode sẵn transaction context, chạy được bằng 1 click:
xung đột Cấp 1, hết hiệu lực chính sách (EXPIRED), mơ hồ (AMBIGUOUS), lỗi tính toán
(CALCULATION_FAILED — validator thật chặn kết quả bị cấu hình lỗi cố tình), và Quản lý từ chối
phê duyệt (REJECTED).
