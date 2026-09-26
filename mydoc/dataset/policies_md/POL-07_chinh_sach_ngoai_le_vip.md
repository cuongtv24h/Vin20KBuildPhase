---
policy_id: "POL-2026-VLF-VIP-EXP"
policy_name: "Quy chế Phê duyệt Chiết khấu Ngoại lệ Khách hàng VIP"
version: "v1.0"
effective_from: "2026-01-01T00:00:00+07:00"
effective_to: "2026-12-31T23:59:59+07:00"
applicable_units: ["ALL"]
---

# Điều 1: Thẩm quyền Phê duyệt Ngoại lệ
1. Mọi mức chiết khấu thương mại bổ sung vượt quá tổng trần chính sách công bố (tối đa 10%) đều phải được Tổng Giám đốc phê duyệt bằng Tờ trình ngoại lệ bằng văn bản có chữ ký tươi.
2. Trưởng phòng Kinh doanh và Giám đốc Khối không có thẩm quyền tự ý phê duyệt vượt trần.

# Điều 2: Hướng dẫn Dừng An toàn cho Agent (Safe Abstention)
Khi phát hiện yêu cầu chiết khấu ngoại lệ hoặc điều khoản đặc cách, AI Agent bắt buộc chuyển trạng thái `AMBIGUOUS / PENDING_EXECUTIVE_APPROVAL` và tuyệt đối không được tự động tính toán hoặc đưa vào bảng báo giá chính thức.
