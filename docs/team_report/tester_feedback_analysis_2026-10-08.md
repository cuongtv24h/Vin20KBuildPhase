# Phân tích phản hồi Tester — 2026-10-08

**Trạng thái: CHỈ PHÂN TÍCH, CHƯA SỬA CODE.** Người dùng yêu cầu tìm nguyên nhân và hướng xử lý trước.

Mười hai phản hồi của Tester quy về **9 nguyên nhân gốc** (RC-1…RC-9). Nhiều triệu chứng trông khác nhau
nhưng chung một gốc — ví dụ "mã căn nào cũng tạo được báo giá", "báo giá không có khách hàng" và
"Đã lên báo giá: 0 dù có 4 báo giá" đều từ **RC-1**.

Một nhận xét xuyên suốt, đúng như Tester ba lần ghi chú ("Prompt chỉ che bằng timeout ở giao diện",
"Prompt chỉ đổi phần hiển thị", "Prompt chỉ sửa cách hiển thị"): **các lần vá trước xử lý ở tầng
prompt/hiển thị, không sửa ở tầng dữ liệu**. Đề xuất thành nguyên tắc làm việc: bug dữ liệu phải sửa
bằng validation/derivation ở server, và mỗi bug phải kèm một test chốt (regression) — nếu liên quan
Copilot thì thêm một ca trong `eval/copilot/sale_scenarios.json`.

| RC | Nguyên nhân gốc | Triệu chứng của Tester | Độ nặng |
|---|---|---|---|
| RC-1 | Báo giá tạo từ dữ liệu client khai, không neo giỏ hàng canonical, không gắn hồ sơ khách | mã căn gì cũng tạo được; báo giá thiếu khách/SĐT/ngày giao dịch; căn 0PN-0m²; "Đã lên báo giá: 0" dù có 4 báo giá | **Nghiêm trọng** |
| RC-2 | Dữ liệu demo viết cứng trong UI, lấy từ `dataset/fixtures/` | tổng 4.655.200.000 ₫ cố định; mỏ neo `POL-2026-VLF-PROG` ≠ danh mục `…PROGRESS`; version v3.0/v2.0 ≠ v1.0; hiệu lực INTERIOR lệch hai trang | **Nghiêm trọng** |
| RC-3 | Trạng thái chính sách là chuỗi lưu sẵn, không suy từ hiệu lực theo ngày | hết hạn 30/06 và 31/05 vẫn "Đã ban hành"; "Đang áp dụng 11/12" và "Chiết khấu tối đa 8%–9,5%" gộp cả chính sách hết hạn; mẫu tin dẫn chiết khấu 8% của VLF-EARLY, mỏ neo ghi "Đang dùng" | **Nghiêm trọng** |
| RC-4 | Giá trị LLM sinh ra được lưu thẳng, không chuẩn hoá/validate ở server | "None" từ ghép chuỗi; tên "Chu Thúy Quỳnh, số"; ghi chú dính "₫.ngân sách"; khách tên "t" | Cao |
| RC-5 | SĐT thật không bao giờ trả về client, nhưng ô sửa ghi đè được | ô điện thoại chứa chuỗi che, bấm "Lưu cập nhật" có thể ghi đè số thật | **Nghiêm trọng (mất dữ liệu)** |
| RC-6 | 404 — phải phân biệt "không có route" và "không thấy bản ghi" | nhật ký hồ sơ not found; gửi quản lý duyệt not found; API nhật ký 404 | Cao (chặn luồng duyệt) |
| RC-7 | Copilot hết vòng lặp thì trả câu chốt CANNED, UI che bằng timeout 45s | tool `tra_cuu_gio_hang` trả kết quả nhưng không có câu trả lời cuối | Cao |
| RC-8 | Giá trị tài chính mặc định bịa sẵn trong form | vốn 1,5 tỷ và chi trả 25 triệu lặp lại ở nhiều khách | Cao |
| RC-9 | Nhãn trạng thái và công thức đếm lệch nhau | "Đang tư vấn: 5" nhưng cả 5 khách đều "Chờ tiếp nhận" | Trung bình |

---

## RC-1 · Báo giá được tạo từ dữ liệu client khai, không neo vào giỏ hàng và hồ sơ khách

**Triệu chứng:** "Đặt mã căn là gì cũng tạo được báo giá (khê)" · "Báo giá không có khách hàng, điện thoại,
ngày giao dịch. Căn có 0PN và 0 m²" · "Đã lên báo giá: 0 trong khi Báo giá có 4 hồ sơ".

**Bằng chứng:**

- `src/api/endpoints/quotes.py:61-69` — `CreateQuoteRequest` chỉ có `project_id`, `unit_code`,
  `listed_price_before_tax_vnd`, `deposit_amount_vnd`, `own_funds_vnd`, `monthly_capacity_vnd`, `objective`,
  `tenant_id`. **Không có** `lead_dossier_id`, `customer_name`, `customer_phone`, `transaction_date`.
- `src/api/endpoints/quotes.py:150-175` — `create_quote`:
  - `unit_code` **không được đối chiếu với giỏ hàng canonical** (bảng `units`) → mã căn bịa vẫn tạo được;
  - `total_contract_price_vnd = req.listed_price_before_tax_vnd` → **giá do client tự khai**, không lấy từ
    dữ liệu canonical;
  - `quote_id = f"Q-{req.unit_code}-…"` → mã căn nằm trong khoá chính; mã căn chứa `/`, khoảng trắng hay
    dấu tiếng Việt sẽ phá URL ở các lời gọi sau (một ứng viên của RC-6);
  - snapshot ban đầu chỉ có 8 trường tài chính/dự án → **không có** `bedrooms`, `area`, khách hàng,
    `transaction_date` ⇒ UI đọc thiếu thì hiện 0PN/0 m².
- `frontend/apps/internal/src/features/sale/LeadInboxPage.tsx:171` — `converted = leads.filter(l => l.status === 'CONVERTED_TO_QUOTE')`.
  Báo giá tạo qua `QuoteFormPage` **không chạm vào hồ sơ khách** nên không hồ sơ nào đổi trạng thái ⇒
  thẻ "Đã lên báo giá" vĩnh viễn 0 dù `/quotes` có 4 bản ghi. Đường đúng (`POST /leads/{id}/convert-to-quote`)
  tồn tại nhưng form tạo báo giá không đi qua đó.

**Hướng xử lý (đề xuất, chưa làm):**

1. `create_quote` phải **tra `units` theo `(project_id, unit_code)`**; không thấy → `404 UNIT_NOT_FOUND`
   (hoặc 422) kèm danh sách gợi ý. Không bao giờ nhận giá niêm yết từ client: lấy `listed_price`,
   `bedrooms`, `area_m2`, `direction`, `floor`… **từ canonical** và ghi vào snapshot.
2. Thêm `lead_dossier_id` (bắt buộc khi tạo từ CRM) + `customer_name`/`customer_phone` (lấy từ hồ sơ, không
   cho client tự khai) + `transaction_date` vào snapshot; chuẩn hoá `quote_id` (không nhúng mã căn thô —
   dùng slug đã làm sạch hoặc bỏ hẳn mã căn khỏi id).
3. Cùng một giao dịch: tạo báo giá ⇒ cập nhật `lead_dossiers.status = CONVERTED_TO_QUOTE` + `quote_id`
   (logic đã có trong `convert-to-quote`/`PreSalesDossierService`), để KPI CRM và màn Quản lý khớp sự thật.
4. Test chốt: tạo báo giá với mã căn không tồn tại → 4xx; tạo đúng → snapshot có đủ `bedrooms`/`area`/khách/
   `transaction_date`; hồ sơ liên quan đổi trạng thái.

**Ước lượng:** 1-1,5 ngày (backend là chính, kèm migration nhẹ cho snapshot + test).

---

## RC-2 · Dữ liệu demo viết cứng trong UI, nguồn từ `dataset/fixtures/`

**Triệu chứng:** "Tổng tiền 4.655.200.000 ₫ là số cố định dù chưa chọn khách" · "Mỏ neo ghi
POL-2026-VLF-PROG, danh mục ghi POL-2026-VLF-PROGRESS. Phiên bản mỏ neo v3.0 và v2.0, danh mục v1.0" ·
"Hiệu lực INTERIOR lệch giữa hai trang (01/01–31/12 và 01/02–31/05)" · "Mẫu tin dẫn chiết khấu 8% của
VLF-EARLY (hết 30/06/2026), mỏ neo ghi 'Đang dùng'".

**Bằng chứng:** toàn bộ số liệu này là **chuỗi viết cứng trong frontend**, trùng khớp fixture:

- `frontend/apps/internal/src/features/sale/SaleMessagesPage.tsx:28,40,46` — `'v3.0 · 01/01/2026 → 30/06/2026'`,
  `'v1.0 · 01/01/2026 → 31/12/2026'`, `'v2.0 · 01/01/2026 → 30/06/2026'`;
  `:51` — `'POL-2026-VLF-PROG — Thanh toán Giãn tiến độ'` (**id bị cắt ngắn**, khác `POL-2026-VLF-PROGRESS`
  trong danh mục thật); `:148,178,223-224` — ba biến thể giọng điệu đều hardcode
  `chiết khấu 8%` + `4.655.200.000 ₫` + mỏ neo `[1]/[2]`.
- `frontend/apps/internal/src/features/sale/SalesWorkspacePage.tsx:1397` — `draftContent` mặc định cũng là
  một câu demo viết cứng ("căn R-02.02 … chiết khấu 8% … [2]").
- `dataset/fixtures/golden_scenarios.json:12,21,42-43,…` — chứa `POL-2026-VLF-EARLY`, `POL-2026-VLF-PROGRESS`,
  `POL-2026-VLF-INTERIOR` và `contract_price_vnd: 4655200000`. Tức là **UI đã chép số từ bộ fixture benchmark**
  (golden case BENCH-01) ra màn hình thật.

**Vì sao đây là lỗi chứ không phải "demo cho đẹp":** nguyên tắc vận hành đã chốt là sản phẩm chạy
**dữ liệu thật, không mock/fixture trong đường chạy** (`ALLOW_FIXTURE_DATA` mặc định TẮT ở backend).
Frontend hardcode số fixture là vi phạm cùng nguyên tắc đó, và hậu quả nghiệp vụ thật: Sale có thể gửi
cho khách một tin nhắn chứa **chiết khấu của chính sách đã hết hạn** và **tổng tiền không liên quan căn
đang chọn**.

**Hướng xử lý:**

1. `SaleMessagesPage` phải dựng mẫu tin từ **báo giá thật + bộ chứng cứ thật**: `GET /quotes/{id}`,
   `/quotes/{id}/evidence` (đã có, trả `bundle_id`, `claims`, điều khoản nguồn) và chính sách **hiệu lực tại
   `transaction_date`**. Mỏ neo `[1]/[2]` phải trỏ tới `policy_code` + version + khoảng hiệu lực **lấy từ
   evidence bundle**, không phải chuỗi gõ tay.
2. Chưa nối được dữ liệu thật thì **ẩn/ gỡ trang** (tiền lệ: người dùng đã duyệt xoá hẳn endpoint
   `/api/v1/pricing` mock thay vì để stub). Không để một màn hình có khả năng sinh tin nhắn sai số liệu.
3. Dọn `draftContent` mặc định ở `SalesWorkspacePage` thành rỗng (hoặc placeholder), tránh Sale bấm gửi
   một câu demo có số liệu bịa.
4. Test chốt: không còn chuỗi `4.655.200.000`/`POL-2026-VLF-PROG` trong `frontend/apps`; mọi mỏ neo trong
   mẫu tin đều truy được về `policy_code` có thật trong DB.

**Ước lượng:** nối dữ liệu thật ~1-1,5 ngày; ẩn trang tạm thời ~15 phút (nên làm ngay để chặn rủi ro).

---

## RC-3 · Trạng thái chính sách lưu sẵn, không suy ra từ hiệu lực

**Triệu chứng:** "Hôm nay 03/10/2026 nhưng VLF-EARLY, VLF-BANK (hết hạn 30/06) và VLF-INTERIOR (hết hạn
31/05) vẫn 'Đã ban hành'. Chính sách 'Khởi động 2025 (Đã Hết Hiệu Lực)' cũng vậy. Thẻ 'Đang áp dụng 11/12'
và 'Chiết khấu tối đa 8%–9,5%' lấy cả các chính sách này."

**Bằng chứng:**

- `src/db/models.py:51-54` — `PolicyModel` có `version`, `effective_from`, `effective_to`, và
  `status: str = "ACTIVE"` **lưu sẵn**. Không có trường suy dẫn "còn hiệu lực tại ngày X".
- `frontend/apps/internal/src/features/sale/SalePoliciesPage.tsx:184` — `<SelectItem value="PUBLISHED">Đang áp dụng</SelectItem>`:
  nhãn "Đang áp dụng" được gán cho **trạng thái ban hành**, không phải hiệu lực thời điểm.
  `:125` và `PolicyListPage.tsx:349` cùng kiểu.
- Hệ quả: bộ đếm "Đang áp dụng 11/12" và dải "Chiết khấu tối đa 8%–9,5%" tổng hợp theo `status`, nên chính
  sách hết hạn từ 30/06 vẫn được tính — và chính những chính sách đó được RC-2 dẫn trong mẫu tin.
- Điều đáng tiếc: **logic thời gian đã có sẵn** trong hệ thống (`TemporalScopeFilter`, time-travel retrieval
  theo `T0/T1/T2`) nhưng chỉ dùng cho RAG, chưa dùng cho danh sách/thẻ/cổng compliance.

**Hướng xử lý:**

1. Backend trả thêm trường **suy dẫn**: `effective_status` = `UPCOMING | IN_EFFECT | EXPIRED` tính từ
   `effective_from/effective_to` so với ngày tham chiếu (mặc định hôm nay, hoặc `transaction_date` khi xem
   theo phiên giao dịch) + `is_current: bool`. Không đổi `status` (vẫn là trạng thái ban hành) — **tách bạch
   "đã ban hành" và "đang hiệu lực"** trong nhãn UI.
2. UI: thẻ "Đang áp dụng x/y" và "Chiết khấu tối đa" chỉ tổng hợp các chính sách `IN_EFFECT` tại ngày tham
   chiếu; danh sách hiển thị hai nhãn riêng ("Đã ban hành" + "Hết hiệu lực từ 30/06/2026").
3. **Cổng F8/compliance phải chặn** mẫu tin dẫn chính sách không hiệu lực tại `transaction_date`
   (đây là chỗ chặn thật sự của triệu chứng "mỏ neo ghi Đang dùng"), thay vì chỉ đổi cách hiển thị.
4. Dọn dữ liệu: rà các chính sách có `effective_to < hôm nay` nhưng `status` vẫn ACTIVE/PUBLISHED —
   quyết định đổi `status` hay chỉ dựa vào trường suy dẫn (khuyến nghị: dựa trường suy dẫn, không sửa tay
   dữ liệu, để khỏi mất dấu vết ban hành).
5. Test chốt: chính sách hết hạn không được đếm vào "Đang áp dụng"; cổng F8 từ chối mẫu tin dẫn chính sách
   hết hạn tại ngày giao dịch.

**Ước lượng:** ~1 ngày (backend derive + UI nhãn/đếm + 1 rule compliance + test).

---

## RC-4 · Giá trị LLM sinh ra được lưu thẳng, thiếu chuẩn hoá và validate ở server

**Triệu chứng:** "Giá trị 'None' sinh ra từ lúc ghép chuỗi. Tên 'Chu Thúy Quỳnh, số' có phần thừa, ghi chú
dính '₫.ngân sách'. Có khách tên 't'."

**Bằng chứng:**

- `src/agents/copilot/intents.py:437-459` — `needs_bits = [f"Khách {name or 'mới'}"]`, các bit tiếp theo dùng
  `grounding.format_vnd(...)` (hàm này trả chuỗi có " ₫" — `src/agents/copilot/grounding.py:43-46`), rồi
  `", ".join(needs_bits) + "."`; `customer_name: name` được giữ **nguyên văn** kết quả bóc tách.
- `src/agents/copilot/prompts.py:123-129` — tool tạo khách nhận `needs_summary` dưới dạng **văn bản tự do do
  LLM viết**, và prompt đã phải dặn "`customer_name` phải SẠCH: không chứa 'tạo khách', 'mới', 'tên',
  'anh/chị', ', số', ', số điện thoại'". Dòng dặn đó chính là bằng chứng cho nhận xét của Tester:
  **vá ở tầng prompt**. Prompt không phải là hàng rào — model vẫn sinh "Chu Thúy Quỳnh, số 09…",
  "…1.500.000.000 ₫.ngân sách…" hay "None".
- `src/api/endpoints/leads.py:29-41` — `LeadCreateRequest`: `customer_name: str` (**không `min_length`**),
  `customer_phone: str` (**không pattern**), các trường tiền mặc định 0 ⇒ khách tên "t" và SĐT rỗng được nhận.

**Hướng xử lý:**

1. **Validate ở biên server** (không phụ thuộc prompt): `customer_name` `min_length=2`, chặn các giá trị
   rác (`t`, `test`, `None`, `khách mới`), cắt phần đuôi kiểu ", số …" / ", số điện thoại …" và **tách
   SĐT ra khỏi tên** (nếu tên chứa dãy 9-11 số thì đưa sang `customer_phone`); `customer_phone` theo
   regex SĐT VN sau khi bỏ khoảng trắng/dấu chấm, từ chối chuỗi chứa `*`.
2. `needs_summary` **không nhận văn bản tự do**: dựng tất định từ các trường đã kiểu hoá
   (vốn, khoảng ngân sách, số phòng ngủ, mã căn), mỗi trường thiếu thì ghi "chưa rõ" — **không bao giờ
   để `None` lọt vào chuỗi ghép**; dùng hàm format duy nhất (đã có `format_vnd`) và nối bằng dấu phẩy +
   khoảng trắng nhất quán.
3. Giữ quy tắc prompt như lớp hỗ trợ, nhưng thêm **test chốt ở tầng service**: đưa đầu vào bẩn
   ("Chu Thúy Quỳnh, số 0912345678", name="t", None) và khẳng định kết quả lưu đã sạch.

**Ước lượng:** ~0,5-1 ngày.

---

## RC-5 · SĐT thật không trả về client, nhưng ô sửa có thể ghi đè số thật

**Triệu chứng:** "Ô số điện thoại chứa chuỗi che, bấm 'Lưu cập nhật' có thể ghi đè số thật. Prompt chỉ đổi
phần hiển thị."

**Bằng chứng:**

- `src/api/endpoints/leads.py:95-96` — `_dossier_to_response` trả `customer_name` và
  **`customer_phone_masked`**; SĐT thật **không bao giờ** về client (đúng ý đồ bảo mật).
- `frontend/apps/internal/src/features/sale/LeadInboxPage.tsx:144,354` — `const phone = d.customer?.phone || d.customer_phone_masked || ''`:
  chuỗi **che** được dùng làm giá trị khi không có bản thật; `:860` — `placeholder={maskPhone(...)}`.
- `:730` — payload cập nhật `customer_phone: customerPhone.trim() || undefined`.
- `src/api/endpoints/leads.py:270-278` — `PUT /leads/{id}` chuyển `payload.customer_phone` **thẳng** vào
  `update_dossier`, không kiểm tra định dạng ⇒ chuỗi `"09****1111"` được lưu, **số thật mất vĩnh viễn**
  (không có bản sao nào khác vì API không trả số thật).

**Hướng xử lý:**

1. **Chặn ở server trước tiên** (rẻ và chắc): `PUT/PATCH /leads/{id}` từ chối `customer_phone` chứa `*`
   hoặc không khớp regex SĐT VN → 422 `INVALID_PHONE`. Đây là hàng rào thật, không phụ thuộc UI.
2. UI: ô SĐT **không bao giờ** được seed từ giá trị che. Để trống + placeholder kiểu
   "Đang che 09****1111 — nhập số mới nếu cần thay", và **chỉ gửi trường này khi Sale thực sự gõ**.
3. Nếu nghiệp vụ cần Sale thấy số thật (để gọi khách), làm **endpoint reveal riêng** có ghi audit và chỉ
   cho chủ hồ sơ/ADMIN — thay vì bỏ che hàng loạt.
4. Rà dữ liệu: tìm các hồ sơ có `customer_phone` chứa `*` để biết đã mất bao nhiêu số (cần chạy trên VM,
   không làm được từ repo).
5. Test chốt: PUT với `"09****1111"` → 422 và giá trị trong DB không đổi.

**Ước lượng:** ~0,5 ngày (chưa kể việc khôi phục dữ liệu đã mất).

---

## RC-6 · 404 "not found" — ba khả năng khác nhau, phải phân biệt trước khi sửa

**Triệu chứng:** "Nhật ký hồ sơ trả về not found" · "Gửi quản lý duyệt cái báo giá cũng trả về not found" ·
"API nhật ký trả 404".

**Bằng chứng — các route này CÓ tồn tại:**

- `GET /api/v1/quotes/{id}/audit-trail` (và alias `/audit`) — `quotes.py:694-695`. Quan trọng: handler này
  **không tra báo giá**, chỉ đọc audit events và trả `event_count: 0` khi rỗng ⇒ **không thể 404**.
  Vậy "nhật ký 404" gần như chắc chắn đến từ **một lời gọi khác trên cùng trang**
  (`GET /quotes/{id}/evidence` hoặc `GET /quotes/{id}/events` — `SaleQuoteDetailPage.tsx:5` dùng cả
  `useQuoteAudit`, `useQuoteEvents`, `useQuoteEvidence`), hoặc từ một id không tồn tại.
- `POST /api/v1/quotes/{id}/submit-review` (alias `/submit`) — `quotes.py:357-379`. 404 **chỉ** khi
  `QuoteRepository.get_by_id(db, quote_id, principal.tenant_id)` trả None.
- `src/db/repositories/quotes.py:26-32` — tra cứu lọc **cả `tenant_id`**; `src/api/deps.py:153` — tenant lấy
  từ header client `X-Tenant-Id`, mặc định `"DEFAULT"`; frontend **không gửi** header này
  (không có trong `packages/api-client/src/http.ts`); `GET /quotes` cũng lọc tenant (`quotes.py:203-209`).
- Đối chiếu toàn bộ endpoint FE ↔ router backend (chạy 2026-10-08): **6 endpoint FE khai báo mà backend
  không có route** ⇒ chắc chắn 404 trên bản live: `POST /compliance/draft-message`,
  `POST /policies/{id}/publish`, `POST /policies/{id}/rules/test`, `GET /pre-sales/sessions/{id}/events`,
  `POST /pre-sales/sessions/{id}/handoff`, `POST /pre-sales/sessions/{id}/plan`. (Đúng dòng nợ #12 trong
  `docs/CODEBASE_MAP.md`.)

**Ba giả thuyết, xếp theo khả năng:**

1. **Màn hình Tester xem được nuôi bằng dữ liệu mock/fixture, còn hành động thì gọi backend thật.**
   Danh sách (mock) hiện 4 báo giá ⇒ bấm vào chi tiết/gửi duyệt (backend thật) ⇒ id không tồn tại ⇒ 404.
   Giả thuyết này khớp cả triệu chứng "Đã lên báo giá: 0 trong khi Báo giá có 4 hồ sơ" (hai nguồn dữ liệu
   khác nhau). Cần kiểm tra build FE trên VM có trỏ mock không (`VITE_*`/`API_BASE_URL`, `packages/api-client/src/config.ts`).
2. **`quote_id` bị phá bởi mã căn tự do** (RC-1): `Q-{unit_code}-…` với mã căn chứa `/` hoặc ký tự đặc biệt
   ⇒ URL không khớp route ⇒ 404 kiểu "không có route" chứ không phải "không thấy bản ghi".
3. **Tenant lệch**: bản ghi được tạo ngoài luồng FE (script seed, curl, tài khoản khác tenant) ⇒ FE
   (luôn `DEFAULT`) không thấy.

**Việc cần làm TRƯỚC khi sửa (chẩn đoán, 10 phút trên VM):**

```bash
# 404 kiểu nào? "Not Found" của FastAPI = không có route; {"code":"NOT_FOUND","message":"Quote ... not found"} = không thấy bản ghi
sudo tail -n 400 /var/log/nginx/access.log | grep ' 404 ' | tail -30
pm2 logs p096-backend --lines 300 --nostream | grep -i "404\|not found" | tail -30
# id thật của 4 báo giá đang có trên DB, và tenant của chúng
psql "$DATABASE_URL" -c "select quote_id, tenant_id, unit_code, status, created_by from quotes order by created_at desc limit 10;"
```

**Hướng xử lý sau khi biết 404 thuộc loại nào:**

- Nếu là route thiếu (6 endpoint trên): hoặc **bổ sung backend**, hoặc **gỡ tính năng khỏi UI** — không để
  nút bấm gọi vào khoảng không. Ưu tiên `POST /compliance/draft-message` và `POST /pre-sales/.../handoff`
  vì thuộc luồng MVP.
- Nếu là id không tồn tại: sửa theo RC-1 (id sạch) + bảo đảm FE chỉ dùng dữ liệu backend thật.
- Nếu là tenant: chốt tenant từ **token/phiên** thay vì header client (liên quan nợ #13 trong CODEBASE_MAP),
  hoặc bỏ lọc tenant khi sản phẩm chỉ một tenant — nhưng phải quyết định rõ, không để nửa vời.
- Riêng "Nhật ký hồ sơ": nếu bản ghi chưa có audit event nào thì phải trả **danh sách rỗng + câu giải thích**
  ("Hồ sơ chưa có hoạt động nào được ghi"), không bao giờ là 404.

**Ước lượng:** chẩn đoán 10 phút; sửa 0,5-2 ngày tuỳ loại.

---

## RC-7 · Copilot chạy tool xong nhưng không có câu trả lời thật; UI che bằng timeout 45 giây

**Triệu chứng:** "Công cụ `tra_cuu_gio_hang` đã trả kết quả nhưng không có câu trả lời cuối. Prompt chỉ che
bằng timeout ở giao diện."

**Bằng chứng:**

- `src/agents/copilot/graph.py:920-934` — khi hết `max_iterations` mà LLM chưa chốt, backend phát sự kiện
  `final` với **câu viết sẵn**: "Em đã thu thập đủ dữ liệu cần thiết. Anh/chị xem tóm tắt bên dưới và cho em
  biết bước tiếp theo nhé." kèm cờ `truncated: True`. Về mặt kỹ thuật là "có câu trả lời", nhưng với người
  dùng đó là **không có câu trả lời** — đúng như Tester mô tả.
- `frontend/apps/internal/src/features/sale/SalesWorkspacePage.tsx:872` — `COPILOT_UI_TIMEOUT_MS = 45_000`;
  `:1635-1644` — quá 45s thì **dừng spinner và cho bấm thử lại**, không nói rõ nguyên nhân. Đây chính là
  "che bằng timeout ở giao diện".

**Hướng xử lý:**

1. Nhánh `truncated` phải **tổng hợp câu trả lời thật từ `observations`** (dữ liệu tool đã có trong tay —
   hệ thống đã có đường offline ReAct và các hàm tóm tắt), kèm ghi chú trung thực kiểu
   "Em liệt kê kết quả đối chiếu; chưa kịp chốt khuyến nghị" — thay vì một câu xã giao.
2. UI phải phân biệt ba trạng thái: (a) đang xử lý, (b) **có kết quả nhưng bị cắt ngắn** (hiện cờ
   `truncated` + lý do + nút "Chốt giúp em"), (c) lỗi/thật sự hết thời gian (hiện mã lỗi + nút thử lại).
   Không gộp (b) và (c) vào một timeout.
3. Ghi lại **sự kiện SSE cuối cùng** của mỗi lượt vào lịch sử hội thoại (đã lưu turn) để hỗ trợ chẩn đoán
   mà không cần mở log server.
4. Thêm ca eval vào `eval/copilot/sale_scenarios.json`: "tool trả kết quả nhưng yêu cầu câu chốt" — chạy
   `scripts/run_copilot_eval.py --mode llm --strict` để lỗi này không tái diễn âm thầm.

**Ước lượng:** ~1 ngày (backend 0,5 + UI 0,5) + ca eval.

---

## RC-8 · Giá trị tài chính mặc định bịa sẵn trong form

**Triệu chứng:** "Vốn 1,5 tỷ và chi trả 25 triệu có vẻ là giá trị mặc định ở nhiều khách."

**Bằng chứng — đúng là mặc định cứng, ở cả FE lẫn BE:**

- `frontend/apps/internal/src/features/sale/LeadInboxPage.tsx:93-94,129-130` — `own_funds_vnd: 1500000000`,
  `monthly_capacity_vnd: 25000000`.
- `frontend/apps/internal/src/features/sale/SalesWorkspacePage.tsx:950-951` — cùng hai giá trị.
- `frontend/packages/mock-server/src/handlers/copilot.ts:428`, `workflows.ts:61` — cùng mặc định trong mock.
- Backend cũng có mặc định bịa: `quotes.py:66-67` (`own_funds_vnd = 1_000_000_000`,
  `monthly_capacity_vnd = 50_000_000`); `quotes.py:266-268` — khi snapshot thiếu thì suy ra
  `own_funds = int(price * 0.3)` và `monthly_cap = 50_000_000`, tức **tự bịa hồ sơ tài chính** rồi đưa vào
  engine tính và bộ chứng cứ.

**Vì sao nguy hiểm:** hai con số này quyết định khả năng chi trả/phương án thanh toán và đi vào
**evidence bundle** — nghĩa là một hồ sơ bịa có thể sinh ra khuyến nghị tài chính trông như đã đối chiếu.

**Hướng xử lý:** để **trống** (không mặc định), bắt buộc khai trước khi tính báo giá; chỗ nào thiếu thì
hiện "chưa khai" và **không** suy diễn `price * 0.3`; engine/bộ chứng cứ phải từ chối hoặc đánh dấu
`CONDITIONAL` khi thiếu hồ sơ tài chính. Test chốt: tạo hồ sơ không khai vốn ⇒ không có giá trị 1,5 tỷ
trong DB; tính báo giá khi thiếu ⇒ bị chặn hoặc gắn nhãn thiếu dữ liệu.

**Ước lượng:** ~0,5 ngày (cần rà thêm engine để không phá luồng demo đang chạy).

---

## RC-9 · Nhãn trạng thái và công thức đếm lệch nhau

**Triệu chứng:** "'Đang tư vấn: 5' nhưng cả 5 khách đều 'Chờ tiếp nhận'."

**Bằng chứng:**

- `frontend/apps/internal/src/features/sale/LeadInboxPage.tsx:167-173` — `inProgress = leads.filter(l => l.status === 'NEW' || l.status === 'ASSIGNED').length`.
- Cùng file `:334-336` — nhãn trạng thái: `NEW` = "Chờ tiếp nhận", `ASSIGNED` = "Đang tư vấn",
  `CONVERTED_TO_QUOTE` = "Đã lên báo giá".

⇒ Thẻ "Đang tư vấn" đếm **cả NEW**, nên 5 hồ sơ "Chờ tiếp nhận" bị báo là "Đang tư vấn: 5".

**Hướng xử lý:** đếm đúng theo nhãn (thêm thẻ "Chờ tiếp nhận" riêng cho `NEW`, "Đang tư vấn" chỉ `ASSIGNED`),
hoặc đổi tên thẻ thành "Chờ + đang tư vấn". Kèm test FE chốt công thức đếm theo từng trạng thái.

**Ước lượng:** ~1 giờ.

---

## Thứ tự đề xuất (nếu được duyệt làm)

| Ưu tiên | Việc | Vì sao trước | Công |
|---|---|---|---|
| P0-a | RC-5 chặn ghi đè SĐT ở server (422 với chuỗi chứa `*`) | Mất dữ liệu không khôi phục được, sửa rẻ nhất | 2 giờ |
| P0-b | RC-2 ẩn/gỡ màn mẫu tin đang hardcode số fixture | Sale có thể gửi khách số liệu sai + chính sách hết hạn | 15 phút |
| P0-c | RC-6 chẩn đoán 404 bằng log VM | Không biết loại 404 thì sửa mò | 10 phút + log |
| P1-a | RC-1 báo giá neo vào giỏ hàng + gắn hồ sơ khách | Lõi MVP, gốc của 4 triệu chứng | 1-1,5 ngày |
| P1-b | RC-3 trạng thái hiệu lực suy dẫn + cổng F8 chặn chính sách hết hạn | Rủi ro tuân thủ | 1 ngày |
| P1-c | RC-7 câu chốt thật khi tool đã có dữ liệu + bỏ timeout che lỗi | Lời hứa cốt lõi của sản phẩm | 1 ngày |
| P2-a | RC-4 validate/chuẩn hoá dữ liệu LLM sinh ra ở server | Dữ liệu CRM bẩn dần | 0,5-1 ngày |
| P2-b | RC-8 bỏ mặc định tài chính bịa | Hồ sơ tài chính sai dẫn tới khuyến nghị sai | 0,5 ngày |
| P2-c | RC-9 sửa công thức đếm KPI | Số liệu quản lý gây hiểu nhầm | 1 giờ |

Tổng cộng khoảng **5-6 ngày công** cho toàn bộ, trong đó 3 việc P0 làm được trong buổi.

## Những gì cần Tester/VM cung cấp để chốt chẩn đoán

1. Ba dòng log 404 (nginx + pm2) và kết quả truy vấn 10 báo giá gần nhất (lệnh ở RC-6) — quyết định giả thuyết 1/2/3.
2. Build FE trên VM có trỏ mock không: `grep -R "VITE_\|API_BASE_URL" frontend/apps/internal/dist/assets | head`
   hoặc nội dung `frontend/packages/api-client/src/config.ts` lúc build.
3. Một ảnh chụp màn "Nhật ký hồ sơ" lúc 404 (để biết lời gọi nào bắn ra — DevTools → Network).
4. Một lượt hội thoại Copilot bị lỗi RC-7 (mã hội thoại hoặc ảnh chụp) để soi sự kiện `final`/`truncated` trong DB.
5. Danh sách hồ sơ có `customer_phone` chứa `*` (nếu có) — để biết RC-5 đã gây mất mát tới đâu.
