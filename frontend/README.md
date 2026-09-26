# PricePolicy — Frontend

Ứng dụng web cho hệ thống lập báo giá, phê duyệt và quản trị chính sách bán hàng bất động sản
VLandFuture. Gồm 4 luồng riêng cho 4 nhóm người dùng, chạy được ngay với backend giả lập trong
trình duyệt, và chuyển sang backend thật bằng một biến môi trường.

React 18 · TypeScript · Vite · Tailwind CSS · shadcn/ui · TanStack Query · Zustand · React Router.

## Chạy dự án

```bash
npm install
npm run dev        # http://localhost:5173
npm run test       # Vitest — engine, máy trạng thái, luồng API xuyên vai trò
npm run build      # tsc -b && vite build
npm run lint       # oxlint
```

Mặc định `VITE_API_MODE=mock`: dữ liệu lưu trong `localStorage` của trình duyệt, có sẵn dữ liệu
vận hành mẫu. Phiên đăng nhập lưu theo **từng tab** — có thể mở Sale, Quản lý, Admin Sale và trang
khách hàng ở các tab khác nhau cùng lúc; thay đổi ở tab này tự cập nhật sang tab kia.

Khôi phục dữ liệu mẫu: xoá key `pricepolicy.mock-db` trong localStorage (DevTools → Application)
rồi tải lại trang.

### Tài khoản (chế độ mock)

Mật khẩu chung: `Vland@2026`. Trang `/login` có nút chọn nhanh tài khoản khi chạy mock.

| Vai trò | Email | Sau đăng nhập |
| :--- | :--- | :--- |
| Chuyên viên kinh doanh (Sale) | `nam.hoang@vlandfuture.vn`, `trang.le@vlandfuture.vn` | `/sale` |
| Quản lý kinh doanh (Manager) | `ha.nguyen@vlandfuture.vn` | `/manager` |
| Admin Sale | `minh.tuan@vlandfuture.vn` | `/admin` |

## Luồng theo vai trò

### Khách hàng (Pre-sale) — công khai, không đăng nhập

| Màn hình | Route | Khách làm gì |
| :--- | :--- | :--- |
| Dự án & bảng hàng | `/` | Xem 2 dự án, ưu đãi đang áp dụng, lọc căn theo dự án / số phòng ngủ |
| Chi tiết căn hộ | `/units/:unitCode` | Xem giá tham khảo 3 phương án thanh toán (bật "đã sở hữu sản phẩm VLandFuture" để thấy chiết khấu khách hiện hữu), gửi yêu cầu báo giá → nhận mã `LEAD-…` |
| Báo giá chính thức | `/quote/:shareToken` | Mở link Sale gửi: so sánh 3 phương án, chi tiết giá & lịch thanh toán, quét QR / kiểm tra toàn vẹn, **Đồng ý & đặt lịch ký cọc** hoặc **Cần tư vấn thêm** |

Link mẫu có sẵn: `/quote/Sp7Kq9ZtHuy2201xVm` (báo giá đã duyệt của khách Phạm Quốc Huy).

### Sale — `/sale`

| Màn hình | Route | Nội dung |
| :--- | :--- | :--- |
| Tổng quan | `/sale` | Chỉ số cá nhân + **Việc cần làm**: yêu cầu mới, hồ sơ bị trả, bản nháp, hồ sơ đã duyệt chưa gửi, phản hồi của khách |
| Yêu cầu khách hàng | `/sale/leads` | Tab *Chờ tiếp nhận* / *Tôi phụ trách*; **Tiếp nhận & lập báo giá** |
| Hồ sơ báo giá | `/sale/quotes` | Lọc theo nhóm trạng thái, tìm kiếm |
| Lập báo giá | `/sale/quotes/new[?leadId=…]` | 3 bước: *Khách hàng & căn hộ* → *Ưu đãi & mục tiêu* (kiểm tra xung đột ngay khi tick) → *Kết quả phân tích* (tiến trình 4 bước của agent, 3 phương án, đề xuất) → **Gửi Quản lý duyệt** |
| Chi tiết hồ sơ | `/sale/quotes/:quoteId` | Trạng thái, ghi chú Quản lý, lịch sử; **Chỉnh sửa & trình lại** / **Gửi báo giá cho khách** (Zalo/SMS/Email → link khách) / theo dõi khách đã xem, đã phản hồi |
| Chỉnh sửa | `/sale/quotes/:quoteId/revise` | Phân tích lại thành phiên bản mới |

### Quản lý — `/manager`

| Màn hình | Route | Nội dung |
| :--- | :--- | :--- |
| Tổng quan | `/manager` | Số hồ sơ chờ duyệt / ngoại lệ / chạm trần ưu đãi, thời gian ra quyết định trung bình, hàng đợi ưu tiên, số liệu theo chuyên viên |
| Hàng đợi | `/manager/approvals?tab=review\|exception\|done` | Sắp theo mức rủi ro rồi theo thời gian chờ |
| Thẩm định | `/manager/approvals/:quoteId` | Toàn bộ phân tích + bảng quyết định: **Phê duyệt** (xác nhận ký số), **Yêu cầu sửa**, **Từ chối** (bắt buộc ghi chú, có mẫu ghi chú nhanh). Xong tự mở hồ sơ kế tiếp. Hồ sơ ngoại lệ không phê duyệt được, chỉ trả lại hoặc từ chối |

### Admin Sale — `/admin`

| Màn hình | Route | Nội dung |
| :--- | :--- | :--- |
| Tổng quan | `/admin` | Cảnh báo chính sách sắp hết hiệu lực chưa có phiên bản kế tiếp, chỉ số bảng hàng, chính sách theo dự án |
| Chính sách bán hàng | `/admin/policies` | Mọi phiên bản theo dự án; **Tạo phiên bản mới** (sao chép từ phiên bản cũ) |
| Chi tiết chính sách | `/admin/policies/:policyId` | Bản nháp: sửa tên, dải hiệu lực, giá trị từng điều khoản, tải văn bản gốc (băm SHA-256) → **Kiểm tra & ban hành** (7 kiểm tra bắt buộc) → **Ban hành**. Đã ban hành: xem, **Ngừng áp dụng** |
| Bảng hàng | `/admin/inventory` | Sửa giá niêm yết, trạng thái căn (mở bán / giữ chỗ / đã bán) |
| Tra cứu hồ sơ | `/admin/quotes[/:quoteId]` | Mọi hồ sơ (kể cả bị từ chối, dừng an toàn), bản lưu JSON đã ký, **Kiểm tra toàn vẹn** |
| Kiểm thử công thức | `/admin/formula-tests` | Chạy 15 ca kiểm thử hồi quy công thức tính giá |

### Kịch bản xuyên vai trò

1. **Khách** mở `/units/ZEN-A-1205` → gửi yêu cầu.
2. **Sale** (Hoàng Nam) → *Yêu cầu khách hàng* → **Tiếp nhận & lập báo giá** → tick *Thanh toán sớm 95%* + *Gói nội thất* (thấy cảnh báo loại trừ) → đổi sang *Smarthome* → **Phân tích** → **Gửi Quản lý duyệt**.
3. **Quản lý** (Hà Nguyễn) → hồ sơ nằm đầu hàng đợi → **Phê duyệt** → **Ký duyệt**.
4. **Sale** → **Gửi báo giá cho khách** → mở link.
5. **Khách** → **Kiểm tra toàn vẹn** → **Đồng ý & đặt lịch ký cọc**.
6. **Sale** thấy phản hồi ở hồ sơ và ở *Việc cần làm*.
7. **Admin Sale** (Tuấn Minh) → cảnh báo chính sách v3.1 sắp hết hạn → mở bản nháp v4.0 → **Kiểm tra & ban hành**. Sau đó Sale lập báo giá có ngày giao dịch từ 01/11/2026 sẽ dùng v4.0.

Dữ liệu mẫu còn có sẵn các tình huống: hồ sơ bị trả (khách mua 2 căn), bị từ chối, ngoại lệ do
ưu đãi loại trừ nhau, cờ vàng chạm trần 12%, bản nháp chưa gửi.

## Cấu trúc thư mục

```
src/
  api/
    contracts.ts        Hợp đồng API: DTO + interface ApiClient + route REST của từng method
    hooks.ts            React Query hooks — màn hình chỉ lấy/ghi dữ liệu qua đây
    index.ts            Chọn client theo VITE_API_MODE
    http/httpClient.ts  Client REST + SSE cho backend thật
    mock/               Backend giả lập: db (localStorage), services (nghiệp vụ server), seed, fixtures
  auth/                 Phiên đăng nhập, RequireRole, ROLE_HOME
  engine/               Logic thuần (có test): calculator, conflictDetector, recommend, quoteFactory,
                        workflow (máy trạng thái), schedule, estimate, policyChecks, benchmark
  features/
    customer/           Cổng khách hàng
    auth/               Đăng nhập nhân viên
    sale/  manager/  admin/
  components/
    layout/             CustomerLayout, StaffLayout (menu theo vai trò), Toaster
    quote/              Thành phần hồ sơ báo giá dùng chung giữa các vai trò
    common/             Badge trạng thái, tiền tệ, trạng thái trang
    ui/                 shadcn/ui primitives
  lib/                  format, labels (nhãn tiếng Việt cho mọi enum), hash, links
  types/domain.ts       Domain model dùng chung
```

## Ghép nối backend

Xem [docs/INTEGRATION.md](docs/INTEGRATION.md): danh sách endpoint, quy ước lỗi/xác thực, máy
trạng thái, định dạng SSE và checklist. Tóm tắt:

```bash
cp .env.example .env.local   # đặt VITE_API_MODE=http
npm run dev                  # /api/* được proxy tới http://localhost:8000
```
