# Tối ưu giao diện "Luxury black" — PricePolicy · VLandFuture

Phạm vi: `frontend/apps/internal` (Sale, Quản lý, Admin, Chính sách) và `frontend/packages/ui` (dùng chung).
Không đổi logic nghiệp vụ, API, phân quyền, nội dung tiếng Việt. App Khách hàng (`apps/customer`) giữ giao diện sáng; chỉ thêm token `warning-ink` để component dùng chung không đổi hành vi ở đó.

Ảnh: `before/` (trước), `after/` (sau). Tên file: `<vai trò>-<trang>-<mobile|tablet|laptop|desktop>.png` (375 / 768 / 1024 / 1280px).

## 1. Vấn đề đã tìm thấy (theo ưu tiên)

| # | Mức | Vấn đề | Cách xử lý |
|---|-----|--------|-----------|
| 1 | P0 | Header chat chật < 1000px: tiêu đề "Trợ lý Copilot AI" bị bóp thành 3 dòng | `min-w-0 + truncate + whitespace-nowrap`; nút phụ thu thành icon-only (có `aria-label` + `title`) dưới 1280px |
| 2 | P0 | Cuộn ngang ngoài ý muốn: Tin nhắn (mobile, +82px), Phê duyệt (mobile +177px, 1024 +56px) | `flex-wrap` hàng nút; `max-w-full` cho `TabsList`; bộ lọc xuống hàng dưới `xl` |
| 3 | P0 | Nút tròn nổi (FAB) đè ô nhập/nút mic | Bỏ FAB; chuyển thành nút "Bảng dữ liệu" trong header, thêm nút đóng bảng trên mobile |
| 4 | P1 | Emoji khắp UI (chip, badge, select, tiêu đề modal, nút 👍👎…) | Thay bằng icon lucide hoặc chấm màu token; 0 emoji còn lại trong `src` (trừ test/comment) |
| 5 | P1 | Ô ngày nằm lạc một hàng; 3 lớp thanh nhập lẫn vào nhau | Ngữ cảnh (Khách hàng + Ngày giao dịch có nhãn) → gợi ý nhanh → ô nhập |
| 6 | P1 | Chữ phụ xám nhạt, nhiều chỗ 9–11px | Chữ phụ `#A1A1AA` (≥6.2:1); mọi cỡ < 12px nâng lên 12px (≈300 chỗ) |
| 7 | P1 | Màu trạng thái hard-code (emerald/amber/sky/purple…, ~230 chỗ) không hợp nền tối | Chuyển toàn bộ sang token `success/warning/destructive/info` |
| 8 | P1 | Màn chào trống, chỉ 1 thẻ | Một component `PriorityCard` (4 loại: quá hạn, chỉnh sửa, chờ duyệt, VIP), nút hành động rõ ("Mở hồ sơ") |
| 9 | P2 | Vùng bấm < 44px (nút `h-6/h-7/h-8`) ở header chat, chip, nút gửi, mic | Header/chip/gửi/mic ≥ 40–44px trên mobile |
| 10 | P2 | Đăng nhập: nút demo emoji, thấp; không có thương hiệu trên mobile | Icon lucide, `h-12`, thêm logo ở đầu form mobile |
| 11 | P2 | Badge vai trò ở Admin dùng `bg-*` đè lên variant → chữ tối trên nền tối | Dùng `Badge variant` (gold/info/success/warning) |
| 12 | P2 | Chưa có chế độ sáng / nút chuyển theme | `data-theme="light"`, nhớ lựa chọn, đặt trước khi vẽ (không nháy) |

## 2. Design tokens

Nguồn duy nhất: [`frontend/apps/internal/src/index.css`](../../frontend/apps/internal/src/index.css) (giá trị) và [`tailwind.config.ts`](../../frontend/apps/internal/tailwind.config.ts) (ánh xạ tên → `hsl(var(--x) / <alpha-value>)`, nên `bg-primary/15` dùng được).

| Token | Dark (mặc định) | Light |
|---|---|---|
| `background` | #121214 | #FAFAF9 |
| `card` / `popover` | #1A1A1D | #FFFFFF |
| `sidebar` (sidebar, cột trái đăng nhập) | #0A0A0B | #0A0A0B (giữ đen) |
| `foreground` / `muted-foreground` | #F5F5F4 / #A1A1AA | #18181B / hsl(240 4% 38%) |
| `primary` (nhấn duy nhất) / hover | #C9A961 / #D8BC7A | #A8873A / đậm hơn |
| `gold` (vàng dùng làm chữ) | = primary | tối hơn để đạt AA |
| `success` / `warning` / `destructive` | #4ADE80 / #F5B544 / #F87171 | bản đậm tương ứng |
| `border` | ≈ rgba(255,255,255,.08) | hsl(60 5% 87%) |
| `--radius` | 0.625rem → `rounded-lg` nút/input, `rounded-2xl` card | |

Tương quan độ tương phản đã tính (WCAG): chữ chính 17:1; chữ phụ 6.2–7.4:1; vàng trên nền đen 7.8–8.4:1; chữ đen trên nút vàng 8.8:1; success/warning/destructive/info trên card 6.4–10.1:1. Light: chữ phụ 6.3:1, chữ vàng 5.9:1, chữ đen trên nút vàng 5.3:1.

## 3. Danh sách thay đổi (mỗi dòng một lý do)

**Tầng token & cấu hình**
- `index.css` — viết lại tokens dark + light, focus-visible vàng toàn app, icon lucide nét 1.5px, `.eyebrow`, `.stream-caret`, tôn trọng `prefers-reduced-motion`.
- `tailwind.config.ts` — màu theo `<alpha-value>`, thêm `info`, `sidebar.*`, `warning.ink`, `boxShadow` theo token; `darkMode` theo `data-theme`.
- `index.html` — font bằng `<link preconnect>` + `display=swap` (bỏ `@import` chặn render); script đặt theme trước khi vẽ.
- `lib/theme.ts`, `ThemeToggle.tsx` — chuyển sáng/tối, lưu `localStorage`, tắt transition 1 khung hình để không nháy.

**Component dùng chung (`packages/ui`)**
- `button` — `rounded-lg`, hover/active/focus/disabled, nút mặc định vàng, cao 40px trên mobile.
- `input/select/textarea` — `rounded-lg`, viền vàng khi focus, 40px trên mobile.
- `card` (`rounded-2xl`), `dialog`, `toast`, `alert`, `tabs`, `badge` (variant `info` theo token).
- `table` — header cố định (`sticky`, cuộn trong `max-h-[70vh]`), hover hàng, cuộn ngang trong khung.
- `PageStates` — loading có khung xương, empty có biểu tượng trong vòng tròn, error có nút "Thử lại" kèm icon.
- `CopilotContextChips` — chỉ còn chip ngữ cảnh; thêm `TransactionDateField` có nhãn "Ngày giao dịch".
- `ReasoningTrace` — con trỏ nhấp nháy khi đang suy luận; `FormattedAiMessage` — icon thay emoji.

**App nội bộ**
- `StaffLayout` — CTA "Báo giá khách tại sàn" nền vàng chữ đen; mục chọn có nền sáng hơn một bậc + thanh vàng bên trái; badge số cùng kích thước (`h-5 min-w-5`); chân sidebar có đường kẻ, avatar, đăng xuất, nút theme; menu mobile trượt (transition, Esc, `aria-expanded`).
- `SalesWorkspacePage` — header responsive (`HeaderAction`); thanh nhập 3 lớp; ô nhập bo `2xl`, focus vàng, nút gửi chỉ sáng khi có nội dung; chip gợi ý dùng icon (cuộn ngang mobile, xuống dòng từ 768px); màn chào cân đối + `PriorityCard`; bong bóng chat cỡ 14px; bỏ FAB.
- `PriorityCard.tsx` (mới) — một mẫu thẻ cho mọi việc ưu tiên; thẻ quá hạn đỏ dịu.
- `LoginPage` — 2 cột (trái đen than + tiêu đề serif, phải theo theme); nút vai trò dùng icon, 48px; nút "Đang xử lý..." khi gửi.
- Các trang Admin/Quản lý/Sale khác — hưởng token; thay emoji, badge, màu trạng thái hard-code; sửa cuộn ngang.

## 4. Checklist cuối

- [x] **Màu từ tokens** — còn 0 lớp màu cố định (`emerald/amber/sky/slate/red…`, `text-white`) trong `apps/internal/src` và `packages/ui/src`; chỉ còn `bg-black/50` làm lớp phủ modal.
- [x] **Responsive 375/768/1024/1280** — chụp 10 màn × 4 độ rộng, `scrollWidth − innerWidth = 0` ở tất cả (bảng rộng cuộn trong khung của nó).
- [~] **4 trạng thái** — loading / empty / error đã làm lại ở `PageStates` (dùng bởi các màn dùng `QueryState`). Success dùng toast sẵn có; chưa thêm toast mới cho từng thao tác.
- [x] **Focus/hover** — `focus-visible` vàng toàn app; hover/active/disabled ở nút, input, mục sidebar, hàng bảng; transition 200ms.
- [x] **Contrast** — xem bảng ở mục 2, mọi cặp chính ≥ 4.5:1 (cả hai theme).
- [x] **Trợ năng** — nút chỉ có icon đều có `aria-label` (header chat, mic, gửi, theme, menu); ô Khách hàng/Ngày giao dịch có `<label>`.
- [x] Kiểm tra: `tsc` sạch, `vitest` internal 6/6 + ui 17/17, build internal và customer thành công. `oxlint` còn các cảnh báo cũ (import thừa…) không thuộc thay đổi này.

## 5. Chưa làm / cần lưu ý

- Chưa chụp được các màn cần dữ liệu thật (chi tiết báo giá, bàn phê duyệt có hồ sơ, chi tiết chính sách, hội thoại đang streaming). Chúng được đổi qua token và thay emoji nhưng **chưa xem bằng mắt**.
- Câu trả lời của Copilot hiện hiện một lần ở cuối (không stream từng chữ); con trỏ nhấp nháy gắn vào dòng "Trợ lý đang suy luận…".
- Chưa kiểm thử bàn phím ảo trên thiết bị thật; ô nhập dùng `h-dvh`, `safe-area-inset-bottom` và cỡ chữ 16px (tránh iOS tự zoom).
- Sau khi sửa `tailwind.config.ts` cần **khởi động lại Vite dev server**, nếu không các class mới (`bg-sidebar`, `bg-info`…) không được sinh.
