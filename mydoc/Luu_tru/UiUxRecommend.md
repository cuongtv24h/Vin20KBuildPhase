Có. Với sản phẩm này, **không nên thiết kế theo kiểu “một ô chat lớn + câu trả lời dài”**. Vì bản chất PricePolicy AI không chỉ là chatbot, mà là một **tư vấn viên tài chính tương tác có khả năng tính toán, giải thích và chuyển giao cho Sale**.

Hướng UI/UX phù hợp là:

> **Conversational Financial Workspace**  
> Hội thoại là trung tâm, nhưng mỗi câu trả lời phải biến thành một hành động, một con số, một lựa chọn hoặc một bằng chứng có thể kiểm tra.

---

# 1. Không mở đầu bằng ô chat trống

Màn hình chat trống thường gây cảm giác:

- cũ;
- thiếu định hướng;
- người dùng không biết hỏi gì;
- giống chatbot RAG thông thường.

Thay vào đó, mở đầu bằng một màn hình:

## “Bạn đang muốn giải quyết điều gì?”

```text
Chào anh/chị, em có thể giúp mình tìm phương án phù hợp hơn.

[ Tìm phương án trong ngân sách của tôi ]
[ Tính số tiền cần chuẩn bị ban đầu ]
[ So sánh các gói thanh toán ]
[ Tôi đã biết căn muốn mua ]
[ Tôi muốn được chuyên viên liên hệ ]
```

Bên dưới có thể hiển thị:

```text
⏱ Mất khoảng 1 phút
🔒 Thông tin chỉ dùng để tính phương án tham khảo
✓ Có căn cứ chính sách
```

Người dùng bắt đầu bằng lựa chọn, không phải tự nghĩ prompt.

---

# 2. Dùng “guided conversation” thay cho chat tự do hoàn toàn

Agent vẫn cho phép nhập tự do, nhưng chủ yếu dẫn dắt bằng các câu hỏi ngắn và lựa chọn trực quan.

Ví dụ:

```text
Mục đích mua căn hộ của anh/chị là gì?

[ Mua để ở ] [ Đầu tư ] [ Cho thuê ] [ Chưa quyết định ]
```

Sau đó:

```text
Mức vốn tự có của anh/chị khoảng bao nhiêu?

[ Dưới 500 triệu ]
[ 500 triệu – 1 tỷ ]
[ 1 – 2 tỷ ]
[ Nhập con số khác ]
```

Sau khi chọn, UI hiển thị một “summary chip”:

```text
Mục đích: Mua để ở
Vốn tự có: 900 triệu
Khả năng trả/tháng: Chưa xác định
```

Người dùng có thể bấm sửa từng giá trị, thay vì phải gõ lại toàn bộ.

---

# 3. Tạo cảm giác tiến bộ rõ ràng

Người dùng sẽ thấy chatbot nhàm chán nếu không biết đã đi đến đâu.

Nên có thanh tiến trình nhẹ:

```text
01 Nhu cầu
   ↓
02 Khả năng tài chính
   ↓
03 Phương án
   ↓
04 Kết nối chuyên viên
```

Trong giao diện mobile có thể dùng:

```text
Bước 2/4 · Xác định khả năng tài chính
```

Không nên biểu diễn trực tiếp toàn bộ StateGraph kỹ thuật. Khách hàng không cần thấy:

```text
retrieve_policy
safe_decision_gate
validate_explanation
```

Thay vào đó, chuyển thành ngôn ngữ dễ hiểu:

```text
Đang kiểm tra chính sách phù hợp
Đang tính các phương án thanh toán
Đang kiểm tra điều kiện áp dụng
```

---

# 4. Câu trả lời nên là “decision card”, không phải đoạn văn dài

Thay vì Agent trả:

> Với thông tin anh cung cấp, phương án PA-NHANH có thể phù hợp vì...

Nên trả một card:

```text
┌────────────────────────────────────┐
│ PHƯƠNG ÁN PHÙ HỢP NHẤT             │
│ PA-NHANH · Thanh toán sớm           │
│                                    │
│ Cần chuẩn bị ban đầu                │
│ 675.000.000 ₫                       │
│                                    │
│ Thanh toán dự kiến                  │
│ 20.000.000 ₫/tháng                  │
│                                    │
│ Tiết kiệm dự kiến                   │
│ 360.000.000 ₫                       │
│                                    │
│ [ Xem tiến độ ] [ Vì sao? ]         │
└────────────────────────────────────┘
```

Bên dưới có các nút:

```text
[ So sánh 3 phương án ]
[ Thay đổi vốn tự có ]
[ Tính lại theo mục tiêu khác ]
[ Gửi cho chuyên viên ]
```

Điểm quan trọng: mỗi câu trả lời phải dẫn đến hành động tiếp theo.

---

# 5. Cho người dùng “điều khiển” phương án bằng slider

Đây là điểm tạo cảm giác khác biệt mạnh so với chatbot.

Ví dụ:

```text
Vốn tự có của bạn
[━━━━━━●━━━━━━] 900 triệu

Khả năng thanh toán mỗi tháng
[━━━━●━━━━━━━━] 20 triệu

Mục tiêu ưu tiên
[● Tiền ban đầu thấp] [Giá thấp nhất] [Nhận nhà sớm]
```

Khi người dùng kéo slider:

```text
Bạn thay đổi vốn tự có từ 900 triệu → 1,1 tỷ
```

Hệ thống hiển thị:

```text
✓ Có thêm 2 phương án phù hợp
↓ Số tiền vay dự kiến giảm
↓ Áp lực thanh toán hàng tháng giảm
```

Không nhất thiết phải gọi LLM sau mỗi thao tác. Có thể:

- calculator chạy local/server deterministic;
- chỉ gọi Agent khi cần giải thích;
- cập nhật UI gần realtime.

---

# 6. Hiển thị phương án theo “trade-off”, không chỉ xếp hạng

Người dùng thường không có một mục tiêu duy nhất.

Nên thể hiện ba trục:

```text
Giá thấp nhất
Tiền ban đầu thấp nhất
Áp lực hàng tháng thấp nhất
```

Ví dụ giao diện:

```text
              Giá thấp
                 ▲
                 │    PA-NHANH
                 │
Tiền đầu thấp ───┼──────────────► Dễ trả hàng tháng
                 │
                 │    PA-LINH-HOAT
                 │
                 ▼
```

Hoặc dùng 3 cards:

| Mục tiêu | Phương án |
|---|---|
| Tiết kiệm tổng tiền | PA-NHANH |
| Ít tiền ban đầu | PA-LINH-HOAT |
| Thanh toán đơn giản | PA-CHUẨN |

Điều này giúp Agent giống một công cụ ra quyết định, không phải chatbot đọc tài liệu.

---

# 7. Progressive disclosure cho evidence

Không nên đưa toàn bộ citation và hash vào khu vực chính vì sẽ làm giao diện nặng và khó hiểu.

Nên hiển thị ba lớp:

## Lớp 1 — Dễ hiểu

```text
✓ Có căn cứ chính sách
```

## Lớp 2 — Tóm tắt

```text
Theo Chính sách bán hàng 2026, Điều 4.2
```

## Lớp 3 — Audit detail

Khi bấm “Xem căn cứ”:

```text
Policy: POL-2026-VLAND-01
Version: v3
Clause: CLAUSE-4.2.1
Document: Chính sách bán hàng tháng 09/2026
Page: 12
Hash: sha256:...
```

Có thể highlight đoạn văn trong PDF.

Như vậy vừa thân thiện với khách, vừa tạo niềm tin với Sale/Manager/Auditor.

---

# 8. Thiết kế “Why / Why not” dạng mở rộng

Thay vì trả một đoạn giải thích dài:

```text
Vì sao đề xuất PA-NHANH?
```

Dùng accordion:

```text
▾ Giá trị ban đầu thấp hơn
  Bạn cần chuẩn bị khoảng 675 triệu ở đợt đầu.
  [Xem cách tính] [Xem nguồn]

▾ Phù hợp mục tiêu của bạn
  Bạn chọn mục tiêu “giảm tiền cần chuẩn bị”.
  [Thay đổi mục tiêu]

▸ Vì sao không chọn PA-CHUẨN?
▸ Điều kiện cần lưu ý
```

Điều này làm giao diện có chiều sâu nhưng không gây quá tải thông tin.

---

# 9. Dùng “assumption chips” để tránh hiểu nhầm

Một trong những vấn đề lớn của tư vấn tài chính là người dùng không biết kết quả dựa trên giả định nào.

Nên hiển thị ngay trong card:

```text
Dựa trên:
[ Vốn tự có: 900 triệu × ]
[ Trả hàng tháng: 20 triệu × ]
[ Mua để ở × ]
[ Nhận nhà trong năm nay × ]
```

Khi bấm vào một chip:

```text
Bạn muốn thay đổi “Vốn tự có”?
[900 triệu] → nhập giá trị mới
```

Nếu kết quả phụ thuộc vào giả định chưa xác nhận:

```text
⚠ Kết quả này đang dùng mức lãi suất tham khảo.
[ Xác nhận ] [ Thay đổi ]
```

---

# 10. Thiết kế Agent có trạng thái rõ ràng, không giả lập suy nghĩ

Không nên dùng animation kiểu:

```text
Agent đang suy nghĩ...
```

quá lâu hoặc giả lập reasoning nội bộ.

Nên hiển thị tiến trình nghiệp vụ:

```text
✓ Đã hiểu nhu cầu
✓ Đã tìm chính sách đang hiệu lực
✓ Đã tính 3 phương án
✓ Đã kiểm tra điều kiện áp dụng
```

Nếu có vấn đề:

```text
⚠ Chưa đủ thông tin về khả năng thanh toán hàng tháng
[ Bổ sung thông tin ] [ Tiếp tục với giả định ]
```

Điều này tăng niềm tin hơn animation “AI đang suy nghĩ”.

---

# 11. Thêm “moment of delight” nhưng không lạm dụng

Một số điểm tạo ấn tượng tốt:

## 11.1. Tóm tắt thông minh sau mỗi câu trả lời

```text
Em đã ghi nhận:
Mua để ở · 2 phòng ngủ · vốn tự có 900 triệu
```

## 11.2. So sánh trước/sau

```text
Nếu tăng vốn tự có thêm 100 triệu:

Khoản cần vay       ↓ 100 triệu
Tiền trả hàng tháng  ↓ 2,4 triệu
```

## 11.3. “Next best action”

```text
Bước tiếp theo phù hợp nhất:
[ Xem tiến độ thanh toán ]
```

## 11.4. Chuyển tiếp mượt sang Sale

```text
Bạn đã có phương án phù hợp.
Muốn chuyên viên gửi mặt bằng và căn đang còn hàng không?

[ Có, kết nối tôi với chuyên viên ]
[ Tôi muốn xem thêm phương án ]
```

---

# 12. Giao diện Sales Dashboard nên khác giao diện khách

Không nên dùng cùng một UI cho khách hàng và Sale.

## Khách hàng

Ưu tiên:

```text
đơn giản
trực quan
ít thuật ngữ
nhiều lựa chọn nhanh
```

## Sale

Ưu tiên:

```text
thông tin có cấu trúc
evidence
financial inputs
claim compliance
next best action
```

Sales Dashboard có thể dùng bố cục ba cột:

```text
┌──────────────┬────────────────────┬────────────────────┐
│ Lead dossier │ Phương án tài chính │ Message Composer   │
│              │                    │                    │
│ nhu cầu      │ 3 scenario cards   │ tạo/soạn tin       │
│ ngân sách    │ calculation        │ compliance status   │
│ intent       │ evidence           │ copy/send          │
└──────────────┴────────────────────┴────────────────────┘
```

---

# 13. Đề xuất màn hình MVP

## Màn hình 1 — Welcome/Discovery

Mục tiêu: bắt đầu nhanh, không giống chatbot trống.

## Màn hình 2 — Guided Conversation

Mục tiêu: thu thập nhu cầu bằng chips, cards, input ngắn.

## Màn hình 3 — Financial Plan

Mục tiêu: hiển thị 1–3 phương án dạng card, trade-off và slider.

## Màn hình 4 — Evidence/Why

Mục tiêu: giải thích theo accordion, citation progressive disclosure.

## Màn hình 5 — Handoff

Mục tiêu: xác nhận consent và chuyển Sale.

## Màn hình 6 — Sales Dashboard

Mục tiêu: dossier, scenario, evidence và message composer.

## Màn hình 7 — Manager Approval

Có thể dùng mockup hiện tại, bổ sung:

- approval package;
- risk flags;
- evidence;
- exception;
- audit;
- PDF status.

---

# 14. Phong cách hình ảnh đề xuất

## Nên dùng

- nền sáng;
- card bo góc vừa phải;
- màu xanh navy/xanh dương cho trust;
- màu xanh lá cho kết quả hợp lệ;
- màu vàng cho assumption/cảnh báo;
- màu đỏ chỉ dùng cho claim sai/rủi ro;
- typography rõ;
- icon nhẹ;
- đồ thị dòng tiền;
- progress timeline;
- chips và buttons.

## Không nên dùng

- robot/avatar hoạt hình quá nhiều;
- bong bóng chat giống Messenger thuần túy;
- animation “AI magic” không có giá trị;
- quá nhiều gradient/neon;
- biểu đồ phức tạp không giúp ra quyết định;
- hiển thị technical hash ở màn hình chính;
- claim marketing như “AI hiểu mọi chính sách”.

---

# 15. Một concept UI phù hợp nhất

## “AI Financial Concierge”

Thay vì gọi là chatbot, có thể định vị giao diện là:

> **Trợ lý chọn phương án tài chính**

Cấu trúc màn hình:

```text
┌──────────────────────────────────────┐
│ Trợ lý tài chính cho kế hoạch mua nhà │
│                                      │
│ ① Nhu cầu của bạn                    │
│ ② Khả năng tài chính                 │
│ ③ Phương án phù hợp                  │
│ ④ Kết nối chuyên viên                │
│                                      │
│ Bạn muốn bắt đầu từ đâu?             │
│ [Tôi có ngân sách cụ thể]             │
│ [Tôi muốn biết cần trả bao nhiêu]    │
│ [Tôi muốn so sánh các phương án]     │
└──────────────────────────────────────┘
```

Đây là sự kết hợp giữa:

```text
chatbot
+
form thông minh
+
financial calculator
+
decision dashboard
```

Phù hợp hơn nhiều so với một khung chat đơn thuần.

---

# Khuyến nghị triển khai

Đối với MVP, nên ưu tiên 5 kỹ thuật UX:

1. **Guided conversation với quick reply và chips.**
2. **Scenario cards thay cho đoạn văn dài.**
3. **Slider/what-if để người dùng tự thay đổi giả định.**
4. **Progressive disclosure cho evidence.**
5. **Một-click handoff sang Sale.**

Không cần triển khai ngay:

- avatar 3D;
- voice assistant;
- knowledge graph tương tác phức tạp;
- animation quá nhiều;
- giao diện metaverse;
- full conversational memory dài hạn.

## Kết luận

Giao diện khác biệt không nhất thiết phải “lạ mắt” bằng hiệu ứng. Điểm nổi bật của PricePolicy AI nên đến từ việc:

```text
Người dùng nói nhu cầu
→ hệ thống hiểu và xác nhận
→ người dùng điều chỉnh giả định
→ hệ thống cho thấy trade-off
→ từng kết luận có căn cứ
→ khách chuyển tiếp tự nhiên sang Sale
```

Đó là trải nghiệm của một **trợ lý ra quyết định tài chính**, không phải một chatbot hỏi–đáp tài liệu.
