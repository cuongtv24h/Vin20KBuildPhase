# Rà soát tổng thể tài liệu & mã nguồn — P-096 (Vin20K Build Phase)

**Ngày rà soát:** 2026-10-02
**Phạm vi:** `src/`, `tests/`, `frontend/` (2 app + 3 package), `docs/` (44 file), `eval/`, `dataset/`, `deploy/`, `.github/workflows/ci.yml`
**Nguyên tắc:** mọi kết luận dưới đây đều có lệnh chạy thật kèm theo (xem §5). Không đánh giá theo cảm nhận hay theo tài liệu tự khai.

---

## 1. Đánh giá thực trạng

### 1.1 Quy mô đã dựng (đo trực tiếp)

| Hạng mục | Số liệu | Ghi chú |
| :--- | ---: | :--- |
| Python `src/` | 20.145 dòng · 11 router API | 16 bảng DB, 2 graph agent (Pre-Sales, Official Quote) |
| Python `tests/` | 10.512 dòng · **455 test** | Chạy 10,35 s, 0 failed |
| Frontend TS/TSX | 21.708 dòng | `apps/customer` (:5173), `apps/internal` (:5174), `packages/{api-client,ui,mock-server}` |
| Hợp đồng API | 49 endpoint | Mock-server phủ **49/49** sau buổi này |
| Frontend test | **22 test / 2 file** | `npm test` chạy trên MSW, không cần backend |
| Tài liệu | 44 file `.md` + guide 10 chương | `docs/guide/chapter-01..10.md` |

### 1.2 Những gì đã vững (đã kiểm chứng bằng test hoặc đọc code)

1. **Tầng tính toán tất định (điểm mạnh nhất của dự án).** Không dùng float cho tiền; 6 sanity check trước khi phát hành; benchmark công thức 17/17 khớp tuyệt đối Δ = 0 VNĐ; golden dataset 17 case khoá cứng (`dataset/fixtures/golden_scenarios.json`). Đây là năng lực khó làm giả nhất và đang được bảo vệ bằng test thật.
2. **Cổng tuân thủ F8.** 3 checkpoint (ON_DRAFT / DEBOUNCE / FINAL_SEND) × 4 mức (SUPPORTED / CONDITIONAL / UNSUPPORTED / PROHIBITED), POL-08 chặn 4 nhóm phát ngôn cấm, hash khoá cổng gửi. Mock-server mô phỏng đúng cả luồng `COMPLIANCE_BLOCKED`.
3. **RAG + bằng chứng.** PEC-RAG, đóng bao TDEC, abstention certificate, hash-chain audit — có test hồi quy riêng.
4. **Vòng đời báo giá.** OCC (`If-Match`), idempotency (fingerprint + replay header), SoD 403, re-auth trước khi duyệt, SSE reconnect `Last-Event-ID`, FAIL-01..05 — đều có kịch bản test chạy được.
5. **ReAct Copilot (mới, xem §3.1).** Đã thay endpoint chat một-phát bằng vòng lặp ReAct có tool, có trace, có guardrail và có chế độ offline tất định.

### 1.3 Vấn đề tồn tại (xếp theo mức độ)

**P0 — Sai lệch tài liệu so với thực tế (gây mất niềm tin khi chấm/demo):**

- `README.md` vẫn ghi badge **"pytest 32/32 passed"**, tiêu đề "Chạy Toàn Bộ Test Suite (32/32 Passed in 1.70s)" và cây thư mục mô tả `test_services/ # 24 tests`, `test_agents/ # 3 tests`… — trong khi thực tế là **455 test**. Đây là loại lỗi khiến người phản biện nghi ngờ toàn bộ số liệu khác.
- `README` mục "Kết quả Benchmark mới nhất" là **benchmark RAG** (recall/latency), dễ bị đọc nhầm thành Formula Regression Benchmark.

**P0 — Kiểm soát chất lượng frontend còn hở:**

- CI (`.github/workflows/ci.yml`) **chỉ có job Python**; không chạy `npm test`, `tsc`, `oxlint` cho frontend.
- `tsc -b apps/*` chỉ include `src` của từng app, **không typecheck `packages/api-client` và `packages/mock-server`**; `mock-server` thậm chí không có `tsconfig.json`. Kiểm tra thủ công phát hiện 8 dòng lỗi type (6 ở `scenarios.test.ts` do hợp đồng quote chưa đồng bộ; 2 dòng còn lại phụ thuộc cấu hình lib/types) — chúng không bao giờ nổi lên trong CI hiện tại.
- Copilot backend mới có 12 test cho graph/tool; **`tra_cuu_gio_hang` chưa có test trực tiếp**; hook `useCopilotTurn` và `ReasoningTrace` chưa có unit test (chỉ có 1 kịch bản tích hợp trong mock-server).

| Lỗi type tiềm ẩn (phát hiện bằng typecheck thủ công) | Vị trí | Bản chất |
| :--- | :--- | :--- |
| `TransactionContext` ≠ `QuoteCreatePayload` | `scenarios.test.ts:87,275,285` | Client/types đã đổi sang hợp đồng backend thật (sync 201), còn test + mock vẫn dùng hợp đồng TD-4.1 cũ (202 + SSE) |
| `QuoteCreateResult` không có `stream_url` | `scenarios.test.ts:89,276,287` | Type thiếu trường mà mock trả về — hợp đồng chưa đồng bộ |
| Thiếu `tsconfig` chuẩn cho `packages/*` | — | Không có nguồn chân lý type cho 2 package dùng chung |

**P1 — UI còn dữ liệu/tiến trình "giả" (rủi ro demo):**

- `SalesWorkspacePage.tsx` vẫn tự chạy **stepper giả bằng `setInterval`** (dòng ~970–984) thay vì phát tiến trình thật; `EVIDENCE_DB` tĩnh (dòng 81); nút **hoàn tác 8 giây** mô phỏng (dòng 738–809); **nudge mô phỏng** (dòng 1048); `customer_card` render bằng `dangerouslySetInnerHTML` (dòng 1732); danh sách slash command hardcode.
- `AdvisorPage.tsx` trước đây có `PlanSteps` chạy `setInterval` giả — **đã sửa trong buổi này** (trạng thái thật + đồng hồ chờ + nút kiểm tra lại).

**P1 — Chế độ mock không còn bật được bằng biến môi trường:**

- `packages/api-client/src/config.ts` ghim `API_MODE = 'real'`; comment tài liệu nói đổi `NEXT_PUBLIC_API_MODE=mock` nhưng code **không đọc biến này**. Hệ quả: "mock-first" chỉ còn trên giấy; muốn chạy mock phải tự set `NEXT_PUBLIC_API_BASE_URL` tuyệt đối (đã thêm `vitest.config.ts` cho test, nhưng dev vẫn thủ công).

**P2 — Tồn đọng nhỏ:** một số comment/số liệu trong ảnh chụp tài liệu cũ (WORKLOG dừng ở 2026-09-28), `docs/team_report/*` còn câu "15 test cases" trong phần mô tả (đã sửa 3 chỗ), `.oxlintrc` bật nhưng 151 cảnh báo chưa được dọn.

### 1.4 Bảng "tài liệu nói" ↔ "code làm" (các điểm đã sửa trong buổi này)

| Tài liệu/UI nói | Thực tế trước | Xử lý |
| :--- | :--- | :--- |
| Formula Benchmark 15/15 | Engine chạy 17 case (BENCH-01/02 + TC-01..15), dataset 17 | Cập nhật test/UI/comment/docs về 17 (mốc OP-02 là "ít nhất 15") |
| Mock phủ mọi endpoint | Thiếu handler `admin/*`, `leads/{id}` (GET/PUT/DELETE) | Bổ sung handler; registry test xanh |
| Copilot chỉ trả lời 1 phát | Đã thay bằng ReAct có tool + trace | Xem §3.1 |
| AdvisorPage tiến trình giả | `setInterval` tự chạy | Tiến trình thật + `aria-live` + nút tải lại |
| Test backend 451 passed / 1 failed | `test_admin_cp` dùng nhầm session DB thật → `no such table: users` | Dùng `async_test_session_factory` in-memory → **455 passed, 0 failed** |

---

## 2. UI/UX — nên tập trung cải thiện như thế nào

### 2.1 Bốn niềm tin cần giữ cho người dùng Sale

1. **Tin số liệu** — mọi con số đến từ engine tất định, có thể mở bảng tính chi tiết.
2. **Tin nguồn** — mọi khẳng định về chính sách phải mở được tới điều/khoản trích dẫn.
3. **Biết hệ thống đang làm gì** — tiến trình thật, không phải hiệu ứng.
4. **Luôn thoát được** — huỷ, thử lại, hoàn tác đúng nghĩa.

Ưu tiên dưới đây bám đúng 4 niềm tin này, không chạy theo "đẹp".

### 2.2 P0 — Làm ngay (1–2 ngày, tác động cao, rủi ro thấp)

| # | Việc | Hiện trạng → Đích | Tiêu chí nghiệm thu |
| :-: | :--- | :--- | :--- |
| 1 | **Timeline ReAct thật** | Đã có `ReasoningTrace` + `CitationChips` (thought → action → observation → final, huỷ, thử lại) | Sale thấy đúng tool đang chạy và mở được trích dẫn |
| 2 | **Bỏ stepper giả** trong `SalesWorkspacePage` | `setInterval` (dòng ~970–984) → nối vào `message.data.steps` thật từ Copilot/SSE, hoặc ẩn khi không có dữ liệu | Không còn bước tự chạy khi mạng lỗi; dừng đúng lúc nhận `final` |
| 3 | **Citation mở đúng điều khoản** | Đã có modal động `evidenceDetail`; cần hiển thị `document_hash`/`clause_id` và nút sao chép | Bấm citation → thấy điều khoản + hash, không còn chỉ số `EVIDENCE_DB` tĩnh |
| 4 | **Trạng thái lỗi & hết hạn 10 s** | Hook có fallback SSE → JSON; UI cần banner "không kết nối được, thử lại" + nút | Không còn spinner treo; mọi lỗi mạng đều có đường thoát |
| 5 | **Bỏ `dangerouslySetInnerHTML`** ở `customer_card` | Render bằng React + formatter | Không còn HTML thô từ dữ liệu |

### 2.3 P1 — Tăng tốc thao tác (3–5 ngày)

6. **Slash command palette thật**: tìm kiếm + phím tắt + "dùng gần đây"; bỏ danh sách hardcode. (`/chính sách`, `/giỏ hàng`, `/báo giá`, `/soạn tin` …)
7. **Context chips**: hiển thị rõ đang gắn với căn/hồ sơ/ngày giao dịch nào, cho phép sửa ngay trong khung chat.
8. **Hàng chờ nudge thật**: lấy từ API trạng thái hồ sơ thay vì mô phỏng `setTimeout`.
9. **Hoàn tác có thật**: hoặc gắn với mutation + audit log (undo trong 8 s), hoặc bỏ nút để không hứa sai.
10. **Nhất quán trạng thái rỗng/đang tải/lỗi** trên cả 4 tab (`hoso | baogia | tinnhan | chinhsach`) — skeleton + empty state có hành động.

### 2.4 P2 — Bóng bẩy & tiếp cận (khi còn thời gian)

11. Điều hướng bàn phím toàn cục: `/` mở palette, `↑/↓` chọn, `Enter` chạy, `Esc` đóng (chat đã có).
12. A11y: giữ `role="log"` + `aria-live`, thêm nhãn cho nút huỷ/gửi, focus về ô nhập sau khi trả lời.
13. Responsive cho Sale ngoài hiện trường (hiện tối ưu desktop).
14. Dọn 151 cảnh báo `oxlint` để cảnh báo mới có ý nghĩa.

---

## 3. ReAct Copilot — làm sao thông minh hơn

### 3.1 Hiện trạng kỹ thuật (đã dựng và đã kiểm chứng)

| Thành phần | Nội dung |
| :--- | :--- |
| `src/agents/copilot/graph.py` | Vòng lặp ReAct: LLM `bind_tools` → `ToolMessage` phản hồi, tối đa 4 vòng; phát event `guardrail / thought / action / observation / final / error` |
| `src/agents/copilot/tools.py` | 6 tool có grounding: `tra_cuu_chinh_sach`, `tra_cuu_gio_hang`, `tinh_phuong_an_thanh_toan`, `kiem_tra_phat_ngon_f8`, `tra_cuu_ho_so_khach_hang`, `soan_tin_tu_van` |
| Chống ảo giác | Guardrail chặn prompt injection mức HIGH/CRITICAL; output chỉ nhận dữ kiện từ Observation; `grounded=false` khi không có citation và UI cảnh báo |
| Chế độ offline | LLM lỗi → ReAct tất định (rule-based) vẫn gọi đúng tool thật, gắn `mode="offline_react"` |
| API | `POST /copilot/chat` (gom) + `POST /copilot/chat/stream` (SSE, `event: copilot`, ping 15 s); giữ shape cũ để UI không vỡ |
| UI | `ReasoningTrace` + `CitationChips`; hook `useCopilotTurn` (send/cancel/retry, fallback JSON); nút dừng khi đang stream |

### 3.2 Giới hạn còn lại (xếp theo mức cản trở "thông minh hơn")

1. **Chưa đo được độ thông minh.** Không có bộ eval cho Copilot (câu hỏi vàng → tool kỳ vọng → câu trả lời chuẩn). Không đo thì mọi cải tiến prompt/tool đều là phỏng đoán.
2. **Tool tra hồ sơ chưa scale.** `tra_cuu_ho_so_khach_hang` kéo tối đa 50 bản ghi rồi lọc bằng Python; sẽ sai/thiếu khi dữ liệu lớn.
3. **Không có bộ nhớ hội thoại thật.** Chỉ truyền tối đa 6 tin gần nhất, không tóm tắt, không lưu slot (căn nào, khách nào, ngày nào).
4. **Không có bước Planner/Verifier.** Câu hỏi nhiều ý (ví dụ "tính phương án cho căn này rồi soạn tin cho khách") bị xử lý tuyến tính trong 4 vòng; câu trả lời không được kiểm lại xem có vượt quá Observation không.
5. **Xử lý lỗi tool còn thô.** Tool lỗi → coi như Observation rỗng, chưa retry, chưa phân biệt lỗi tạm thời/lỗi dữ liệu.
6. **Chưa có tín hiệu học.** Không thu thập phản hồi (thumbs, sửa tin, chọn phương án) để cải thiện.
7. **Chi phí/độ trễ chưa được kiểm soát:** không cache tool, không ngân sách token, không theo dõi P95.

### 3.3 Lộ trình 3 nấc

**P0 — Đo lường & sửa lỗi nền (1–2 ngày)**

- Viết `eval/copilot/golden_questions.json` (~30 câu phủ 6 tool + 5 tình huống từ chối) và script chạy tự động; đo 4 chỉ số: **tool-selection accuracy**, **citation precision**, **hallucination rate**, **P95 latency**.
- Sửa `tra_cuu_ho_so_khach_hang` sang truy vấn SQL có `WHERE`/`LIKE` + index thay vì kéo 50 dòng; thêm test cho `tra_cuu_gio_hang`.
- Tool lỗi: retry 1 lần với backoff, Observation lỗi có mã (`DB_DOWN`, `NOT_FOUND`…) để LLM biết đường xử lý; không tính vòng retry vào hạn mức 4 vòng.
- Cắt Observation dài (giữ phần đầu + citation) để không phình prompt.

**P1 — Thông minh hơn có kiểm soát (3–5 ngày)**

- **Planner nhẹ:** tách câu hỏi nhiều ý thành kế hoạch nhiều bước (tra chính sách → tính tiền → soạn tin) và cho phép nhiều tool trong một lượt; hiển thị kế hoạch lên `ReasoningTrace`.
- **Memory có cấu trúc:** tóm tắt hội thoại dài + lưu slot (`current_unit`, `lead_dossier_id`, `transaction_date`) và tự điền khi Sale nói thiếu.
- **Verifier:** kiểm tra câu trả lời chỉ chứa dữ kiện có trong Observation; nếu không → abstain hoặc gọi thêm tool, tuyệt đối không bịa.
- **Ngữ cảnh chủ động:** nạp trạng thái hồ sơ/giỏ hàng/chính sách hiệu lực vào prompt thay vì để LLM tự đoán.

**P2 — Nâng cấp khi nền đã vững**

- Critic vòng 2 cho câu trả lời quan trọng (tự phản biện trước khi trả).
- Học từ phản hồi: log thumbs/sửa tin → few-shot động.
- Cache tool + ngân sách token/latency; dashboard chi phí.
- Nudge chủ động dựa trên trạng thái hồ sơ (SLA sắp trễ, khách chưa phản hồi).

---

## 4. Kế hoạch hành động 1–2 tuần (gợi ý)

| Tuần | Việc | Kết quả cần thấy |
| :--- | :--- | :--- |
| 1 | Dọn README; thêm job frontend vào CI (`npm test` + `tsc -b` 2 app + typecheck package); P0 UI (bỏ stepper giả, bỏ `dangerouslySetInnerHTML`) | CI xanh cả 2 phía; không còn số liệu sai trong README |
| 1 | Eval Copilot golden 30 câu + sửa tool hồ sơ/giỏ hàng | Có bảng điểm Copilot trước/sau |
| 2 | Planner nhẹ + Verifier + Memory slot | Câu hỏi nhiều ý chạy đúng; hallucination rate giảm đo được |
| 2 | P1 UI (palette, context chips, empty/loading/lỗi) | Thao tác chat nhanh hơn, ít lỗi thao tác |

---

## 5. Phụ lục — bằng chứng & thay đổi trong buổi rà soát

### 5.1 Lệnh đã chạy

```bash
.venv/bin/python -m pytest tests/ -q            # 455 passed, 2 warnings, 10.35s
.venv/bin/ruff check src/ tests/                # All checks passed!
cd frontend && npm test                         # 2 files, 22 tests passed
npx tsc -b apps/customer/tsconfig.json apps/internal/tsconfig.json   # exit 0
npx tsc -p /tmp/tscheck.json                    # typecheck tay packages/* — còn 8 dòng lỗi có sẵn, xem §1.3
```

### 5.2 File đã sửa/ tạo trong buổi này

- **Copilot backend:** `src/agents/copilot/{__init__,graph,tools,intents,prompts,grounding,service}.py`, `src/api/endpoints/copilot.py`
- **Test backend:** `tests/test_agents/copilot/test_copilot_react.py` (12), `tests/test_api/test_copilot_endpoints.py` (4), `tests/test_api/test_admin_cp.py` (sửa session in-memory)
- **Frontend client:** `packages/api-client/src/{contracts/copilot.ts,copilotStream.ts,hooks/copilot.ts,hooks/index.ts,endpoints.ts,client.ts,contracts/index.ts}`
- **UI:** `packages/ui/src/components/common/ReasoningTrace.tsx`; `apps/internal/.../SalesWorkspacePage.tsx`; `apps/customer/.../AdvisorPage.tsx`
- **Mock-server:** `handlers/copilot.ts`, `handlers/admin_cp.ts`, `handlers/workflows.ts` (lead GET/PUT/DELETE), `handlers/index.ts`, `vitest.config.ts`, `src/scenarios.test.ts`
- **Tài liệu:** `docs/RASOAT_TONGTHE_2026-10-02.md` (file này), cập nhật số liệu 17 case tại `docs/team_report/{1.requirement-analysis,2.product-discovery}.md`

### 5.3 Việc còn tồn (nên làm ngay sau tài liệu này)

1. `README.md`: cập nhật số test thật (455), xoá badge 32/32, sửa cây thư mục `tests/`.
2. Thêm job frontend vào CI và một `tsconfig` chuẩn cho `packages/*`; xử lý 8 dòng lỗi type có sẵn (6 dòng ở `scenarios.test.ts` do hợp đồng quote cũ ↔ thật).
3. Quyết định dứt điểm hợp đồng quote cho mock-server: giữ TD-4.1 (202 + SSE) hay theo backend thật (201 đồng bộ) — hiện đang lẫn cả hai.
