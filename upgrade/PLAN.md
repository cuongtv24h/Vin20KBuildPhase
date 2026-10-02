# Kế hoạch nâng cấp — thứ tự ưu tiên

Nguyên tắc chọn ưu tiên: **cái gì làm tăng độ tin cậy đo được thì làm trước**; cái gì chỉ làm
đẹp mà không kiểm chứng được thì làm sau.

## A. Copilot thông minh hơn — P0 (làm trước vì mọi cải tiến sau đây cần thước đo)

| # | Việc | Vì sao P0 | Tiêu chí nghiệm thu |
| :-: | :--- | :--- | :--- |
| A1 | Tool `tra_cuu_ho_so_khach_hang` lọc bằng SQL thay vì kéo 50 dòng | Sai/thiếu khi dữ liệu lớn; là tool duy nhất chưa scale | Có test chứng minh lọc ở tầng DB, khớp không dấu |
| A2 | Tool lỗi: mã lỗi + retry 1 lần, không tính vào hạn mức 4 vòng | Hiện coi lỗi = Observation rỗng → LLM bịa | Có test DB_DOWN/NOT_FOUND; retry không tiêu vòng lặp |
| A3 | Observation dài bị cắt thông minh (giữ số liệu + citation) | Prompt phình → giảm chất lượng & tăng chi phí | Có test độ dài |
| A4 | Planner nhẹ: câu nhiều ý → nhiều bước | Hiện trả lời tuyến tính, bỏ sót ý thứ 2 | Có test "tính phương án rồi soạn tin" chạy 2 tool |
| A5 | Memory có slot (căn/hồ sơ/ngày) + tóm tắt hội thoại | Sale nói thiếu ngữ cảnh → Copilot hỏi lại vô ích | Slot tự điền từ lịch sử; có test |
| A6 | Verifier: câu trả lời không được chứa số liệu ngoài Observation | Chống ảo giác bằng máy, không chỉ bằng prompt | Reply có số sai → `verified=false` + cảnh báo |

## B. Eval harness — P0

| # | Việc | Tiêu chí |
| :-: | :--- | :--- |
| B1 | `eval/copilot/golden_questions.json` (~30 câu, phủ 6 tool + 5 tình huống từ chối) | Chạy được không cần API key |
| B2 | `scripts/run_copilot_eval.py` đo 4 chỉ số | In bảng + ghi JSON vào `eval/results/` |
| B3 | Test CI cho bộ eval | Ngưỡng tối thiểu được assert trong pytest |

## C. UI/UX P0

| # | Việc | Tiêu chí |
| :-: | :--- | :--- |
| C1 | Bỏ stepper giả `setInterval` trong SalesWorkspacePage | Không còn bước tự chạy |
| C2 | Bỏ `dangerouslySetInnerHTML` ở `customer_card` | Render bằng React |
| C3 | Citation mở đúng điều khoản + hash + nút sao chép | Modal động |
| C4 | Banner lỗi + nút thử lại cho mọi lỗi mạng | Không spinner treo |

## D. UI/UX P1

| # | Việc | Tiêu chí |
| :-: | :--- | :--- |
| D1 | Slash command palette: tìm kiếm + phím tắt + gần đây | Bỏ danh sách hardcode |
| D2 | Context chips: căn/hồ sơ/ngày giao dịch sửa được tại chỗ | Hiển thị đúng ngữ cảnh gửi lên |
| D3 | Nudge thật từ API hoặc bỏ mô phỏng | Không hứa sai |
| D4 | Hoàn tác gắn mutation thật hoặc bỏ nút | Không hứa sai |

## E. CI + type

| # | Việc | Tiêu chí |
| :-: | :--- | :--- |
| E1 | Job frontend trong CI (`npm test` + `tsc` + `oxlint`) | CI xanh 2 phía |
| E2 | `tsconfig` chuẩn cho `packages/*` + sửa lỗi type tồn đọng | `npm run typecheck` exit 0 |

## F. Tài liệu

| # | Việc | Tiêu chí |
| :-: | :--- | :--- |
| F1 | Cập nhật số liệu thật vào README/guide | Không còn số cũ |
| F2 | `upgrade/CHANGELOG.md` là biên bản đầy đủ | Đọc là dựng lại được |

---

## Trạng thái thực hiện (cuối đợt)

| Nhóm | Trạng thái | Ghi chú |
| :--- | :--- | :--- |
| A1–A3 (scale, lỗi tool, cắt Observation) | ✅ | `tools.py` SQL + `_execute_tool` retry/code + `_trim_tool_message` |
| A4–A6 (planner, memory, verifier) | ✅ | `planner.py`, `memory.py`, `verifier.py` + test riêng |
| A7 (P2: cache tool + ngân sách ngữ cảnh) | ✅ | `_tool_cache_key` + `MAX_TOTAL_OBSERVATION_CHARS`, có test |
| A8 (P2: critic vòng 2, học từ phản hồi) | ⏸ hoãn | xem `CHANGELOG.md` §Còn lại — cần đo chi phí trước |
| B1–B3 (eval + cổng CI) | ✅ | 32 câu vàng, 4 chỉ số, ngưỡng assert trong pytest |
| C1–C4 (UI P0) | ✅ | stepper thật, bỏ innerHTML, citation + hash + copy, banner retry |
| D1–D5 (UI P1) | ✅ | palette, chips, nudge thật (báo giá + SLA), yêu cầu sửa thật, 4 trạng thái nhất quán |
| D6 (tinnhan loading/error) | ⏸ một phần | tab soạn tin chưa có query nền để bọc |
| E1–E2 (CI job frontend, tsconfig packages) | ✅ | 8 lỗi type cũ đã hết |
| F1–F2 (tài liệu + biên bản) | ✅ | README 479, DEMO_RUNBOOK, `CHANGELOG.md` |
