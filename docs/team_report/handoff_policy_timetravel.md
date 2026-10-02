# Bàn giao việc #3 — Sửa lỗi "chính sách đúng ngày hiệu lực" (time-travel)

**Người nhận:** Gemini (được người dùng giao ngày 2026-10-02).
**Người giao:** phiên làm việc trước (Arena agent) — đã phân tích nguyên nhân, **chưa sửa** vì chờ người dùng chốt phương án.
**Trạng thái mong muốn sau khi làm xong:** `CS-08` và `POL-04` chuyển từ "lỗi đang báo" thành tiêu chí kiểm thật
và ĐẠT; không được làm hỏng bộ câu hỏi vàng (34 câu) hay bộ kịch bản Sale (58 câu).

---

## 1. Nhiệm vụ

Copilot phải trả lời **đúng chính sách có hiệu lực tại ngày giao dịch**, và khi **không có** chính sách nào
hiệu lực thì phải **nói thẳng là không có** — tuyệt đối không được trả về một văn bản không phủ ngày đó.

## 2. Hiện trạng sai (bằng chứng chạy thật, chế độ tất định)

Câu hỏi `CS-08` trong `eval/copilot/sale_scenarios.json` (ngày giao dịch 15/07/2026, dự án The Zen Park),
câu trả lời hiện tại:

> *Chính sách canonical đang hiệu lực tại 2026-07-15 **(VLandFuture Sapphire)**:*
> *- [**CSBH-ZEN-2026-V3.1** · Điều 4, Khoản 2b] Chiết khấu thanh toán sớm 95%*
> *Trích dẫn: "Khách hàng lựa chọn thanh toán sớm 95% ... được hưởng chiết khấu 8.0% ..."*

Tiêu đề ghi **Sapphire**, nội dung trích **The Zen Park**, mà `CSBH-ZEN-2026-V3.1` chỉ hiệu lực
**01/08/2026 → 31/12/2026** — tức là bản đó **chưa có hiệu lực** tại ngày hỏi. Hệ quả nghiệp vụ: Sale có
thể trích sai văn bản chính sách cho một giao dịch tháng 7.

Dữ liệu hiện có (fixture `POLICIES_DATA`, `src/api/endpoints/catalog.py:327`):

| policy_id | dự án | hiệu lực |
|---|---|---|
| `CSBH-ZEN-2026-V3.1` | The Zen Park | 2026-08-01 → 2026-12-31 |
| `CSBH-SAPPHIRE-2026-V1.0` | VLandFuture Sapphire | 2026-01-01 → 2026-12-31 |

## 3. Ba nguyên nhân (đã xác định, cần sửa cả ba)

| # | Nguyên nhân | Vị trí |
|---|---|---|
| a | **Dữ liệu thiếu**: không có bản nào của The Zen Park hiệu lực ngày 15/07/2026 | `POLICIES_DATA` (`src/api/endpoints/catalog.py:327`) |
| b | **Code rơi về ứng viên đầu tiên**: khi không có bản nào phủ ngày, hàm vẫn trả về chính sách đầu tiên của dự án ⇒ câu trả lời vẫn ghi "đang hiệu lực tại &lt;ngày&gt;" | `grounding.resolve_active_policy` (`src/agents/copilot/grounding.py:45`, dòng 57: `return candidates[0] if candidates else None`); đường trả lời ở `tools.tra_cuu_chinh_sach` (`src/agents/copilot/tools.py:72`, nhánh "Chính sách canonical đang hiệu lực tại …") |
| c | **Tên dự án không được truyền xuống tool**: `_args_for(LOOKUP_POLICY)` chỉ truyền câu hỏi + ngày ⇒ tool tra trên toàn bộ chính sách rồi trộn hai dự án | `planner._args_for` (`src/agents/copilot/planner.py:67`, cần bóc tên dự án từ câu hỏi thành tham số `du_an`) |

## 4. Hành vi đúng sau khi sửa

1. `resolve_active_policy` **không bao giờ** trả về bản nằm ngoài khoảng hiệu lực; không có bản nào phủ ngày
   ⇒ trả `None`. **Không** dùng fallback "ứng viên đầu tiên" cho đường trả lời ngày hiệu lực.
2. `tra_cuu_chinh_sach` khi không có bản phủ ngày phải trả lời theo mẫu:

   > *Chưa có chính sách nào của **The Zen Park** hiệu lực tại 15/07/2026. Hiện có: `CSBH-ZEN-2026-V3.1`
   > (hiệu lực 01/08/2026 → 31/12/2026) — anh/chị cần em tra theo ngày khác không ạ?*

   Lưu ý kỹ thuật: ca này **vẫn là lượt tra cứu thành công** (`tra_cuu_chinh_sach` nằm trong
   `_GROUNDED_LOOKUP_TOOLS`) nên sẽ `grounded = True` và **không** sinh ghi chú nội bộ "chưa đối chiếu" —
   đừng tự thêm nhãn cảnh báo vào văn bản trả lời (vi phạm chốt P2.4).
3. Tên dự án trong câu hỏi phải được truyền xuống tool (`du_an`), để câu trả lời không trộn hai dự án.
4. Mọi quy tắc hiện có vẫn giữ: câu trả lời sạch để gửi khách, mỏ neo `[n]` do máy chèn, mọi con số phải
   từ tool.

## 5. Cần người dùng chốt (hỏi trước khi code — hai phương án)

| | Việc | Khi nào dùng |
|---|---|---|
| **B** | Sửa đúng hành vi ở mục 4 (code) — **không** thêm dữ liệu | Mặc định đề xuất: sửa lỗi đúng/sai, rẻ, chắc chắn |
| **C** | B + thêm **dữ liệu lịch sử** `CSBH-ZEN-2026-V2.0` (ví dụ hiệu lực 01/05/2026 → 31/07/2026, 2–3 rule) | Nếu muốn demo năng lực time-travel chọn đúng phiên bản |

Nếu chọn **C**, phải xác nhận **nguồn dữ liệu thật trên VM**: `grounding` ưu tiên RAG/DB khi đã seed,
`POLICIES_DATA` chỉ là nguồn dự phòng — thêm vào fixture mà DB có dữ liệu khác thì VM vẫn không thấy V2.0.

## 6. Tiêu chí nghiệm thu

- [ ] Không có đường nào trả về chính sách ngoài khoảng hiệu lực (kể cả khi chỉ có một bản).
- [ ] Ngày không có chính sách phủ ⇒ trả lời "chưa có chính sách hiệu lực cho &lt;dự án&gt; tại &lt;ngày&gt;" + liệt kê các bản đang có kèm khoảng hiệu lực.
- [ ] Câu hỏi nêu tên dự án ⇒ chỉ tra dự án đó (không trộn The Zen Park với Sapphire).
- [ ] Cập nhật kỳ vọng bộ đề cho khớp phương án đã chốt:
  - Chọn **B**: `CS-08` bỏ `known_gap`, đặt `expect_citation: false`, `must_contain` gồm "chưa có chính sách" và mã bản đang có (`V3.1`), `expect_no_internal_notes: true`; sửa `POL-04` trong `eval/copilot/golden_questions.json` (hiện đang đòi `V2.0` — không thể đạt) thành kỳ vọng "chưa có chính sách hiệu lực".
  - Chọn **C**: `POL-04` **giữ** kỳ vọng `V2.0` và phải PASS thật; thêm kịch bản cho ngày 15/10/2026 phải ra `V3.1`.
- [ ] `CS-07` là câu hỏi cùng nội dung nhưng **phải chạy ở `--mode llm`** (lớp tất định không bóc được
      ngày "15/07/2026" từ câu chữ). `CS-08` là bản chạy được cả offline (ngày nằm trong
      `context.transaction_date`) nên dùng `CS-08` làm ca nghiệm thu chính; sửa `CS-07` nếu tiện.
- [ ] Sau khi tất cả xanh mới bật cổng `must_contain` trong CI: thêm `--strict` vào lệnh chạy eval (hiện là cờ tuỳ chọn, cố ý chưa bật vì `POL-04` đang đỏ).

## 7. Cách kiểm chứng (dán nguyên lệnh)

```bash
.venv/bin/python -m pytest tests/ -q                     # hiện: 633 passed — không được giảm
.venv/bin/python -m ruff check src/ tests/ scripts/      # phải sạch
.venv/bin/python scripts/run_copilot_eval.py             # bộ vàng 34 câu — rc phải = 0
.venv/bin/python scripts/run_copilot_eval.py \
    --questions eval/copilot/sale_scenarios.json --strict  # bộ kịch bản 58 câu — rc phải = 0
```

Xem nhanh kết quả một câu:

```bash
.venv/bin/python - <<'PY'
import asyncio, sys; sys.path.insert(0, '.'); sys.path.insert(0, 'scripts')
from scripts.run_copilot_eval import run_eval, SALE_SCENARIOS_PATH
res, _, _ = asyncio.run(run_eval('offline', None, SALE_SCENARIOS_PATH))
print({r['id']: r['reply'] for r in res if r['id'] == 'CS-08'}['CS-08'])
PY
```

## 8. Ràng buộc kỹ thuật của dự án (bắt buộc tuân thủ)

- **Không thêm thư viện mới**; chạy được **offline** (không cần API key) vì CI chạy chế độ tất định.
- **Không nới lỏng** các cổng an toàn hiện có (guardrail, cổng phân khúc P3.2, cổng nội dung/hình thức).
  Các cổng này **chặn CI mặc định** — xem `scripts/run_copilot_eval.py::main`.
- Câu ghi nhận lỗ hổng đã biết dùng cờ `known_gap` (vẫn chạy, vẫn báo cáo, không tính vào mẫu số) — sửa
  xong thì **bỏ cờ** thay vì xoá kịch bản.
- **Bản ghi chuẩn của dự án là `docs/team_report/upgrade_new.md`** — viết tiếp **§17** cho đợt này (mục §16
  là đợt 14–15 do phiên trước làm), kèm bằng chứng chạy thật và các việc còn lại. `upgrade/` là thư mục
  lịch sử, chỉ trỏ về bản chuẩn.
- Tệp `eval/results/*.json` là **báo cáo sinh tự động** — chạy lại eval để cập nhật, đừng sửa tay.
- Bộ chấm hỗ trợ sẵn `must_not_contain`, `notes_contain`, `expect_table`, `max_questions`: dùng chúng khi
  cần kiểm chiều cấm, không phải viết thêm mã chấm.

## 9. Ghi chú để không làm hỏng việc khác

- Đường trả lời "không có chính sách" **không** được sinh ghi chú nội bộ: nội dung đó là dữ liệu thật.
- Nếu thêm dữ liệu V2.0: kiểm tra `scripts/seed_data.py` / DB trên VM, và nhớ rằng `POLICIES_DATA` chỉ là
  dự phòng — nêu rõ trong §17 là đã xác nhận nguồn nào.
- Giữ nguyên văn phong đã chốt: Rõ ràng → Ngắn gọn → Đầy đủ, 4–6 câu phần chính, không tên tool/tham số
  nội bộ trong văn bản (P1.7, P2.5).
