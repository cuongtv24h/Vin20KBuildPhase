# `upgrade_new.md` — Biên bản đợt nâng cấp 2026-10-02 (theo `docs/RASOAT_TONGTHE_2026-10-02.md`)

> **Đây là bản ghi chính thức của toàn bộ thay đổi trong đợt nâng cấp.**
> Code nằm ở đúng vị trí chuẩn của repo; file này là bản đồ + biên bản: đã đổi gì, vì sao,
> và **bằng chứng chạy thật**. Đọc file này là dựng lại được toàn bộ đợt việc.
>
> Thư mục `upgrade/` (README/PLAN/CHANGELOG) là bản nháp trước đó; từ nay **file này là bản canonical**.

- Nguồn yêu cầu: `docs/RASOAT_TONGTHE_2026-10-02.md` (§2 UI/UX P0–P2, §3 Copilot P0–P2, §4 kế hoạch, §5 tồn đọng).
- Thứ tự thực hiện (tự đánh giá ưu tiên): **đo được trước, làm đẹp sau** — Copilot P0 + eval → UI P0 → UI P1 → CI/type → tài liệu → Copilot P2.
- Nguyên tắc xuyên suốt: **không hứa điều hệ thống không làm được**. Mọi chỗ trước đây "diễn" (stepper giả, nudge bịa, hoàn tác giả, F8 tự chế) đều được thay bằng API thật, hoặc nói thẳng là không có dữ liệu.

---

## 1. Kết quả kiểm chứng cuối đợt (chạy thật)

| Lệnh | Kết quả |
| :--- | :--- |
| `.venv/bin/python -m pytest tests/ -q` | **498 passed**, 1 warning |
| `.venv/bin/python -m ruff check src/ tests/ scripts/` | **All checks passed** (trước: 9 lỗi ở `scripts/`) |
| `.venv/bin/python scripts/run_copilot_eval.py` | tool **1.00** · citation **1.00** · bịa **0.00** · p95 **4 ms** |
| `cd frontend && npx tsc -p packages/tsconfig.json` | **exit 0** (trước: 8 lỗi type) |
| `cd frontend && npx tsc -b apps/internal apps/customer` | **exit 0** |
| `cd frontend && npm test` | **24/24 passed** (2 file, trước 22) |
| `cd frontend && npx oxlint` | **0 error**, 124 warning (trước: 151) |
| `cd frontend && npm run build` | build Vite thành công |
| Smoke `filterCommands` (lọc lệnh không dấu) | 6/6 kịch bản khớp đúng |
| **Smoke end-to-end qua Vite proxy** (mock-server :8000 + app nội bộ :5174) | Sale gọi `/copilot/feedback/recent` → **403**; ADMIN → 200 với SĐT đã che `091***78`; `/summary` trả `by_day`/`by_mode`/`top_failing_tools` đúng dữ liệu vừa gửi |
| `pytest tests/test_agents/copilot tests/test_api/test_copilot_endpoints.py -q` | **59 passed** (Copilot + API phản hồi) |

---

## 2. Copilot — `src/agents/copilot/`

### 2.1 P0: đo lường & sửa lỗi nền

| Hạng mục | File | Nội dung |
| :--- | :--- | :--- |
| Eval harness | `eval/copilot/golden_questions.json` **(mới)** | **32 câu vàng**, 10 nhóm (policy, units, scenarios, compose, compliance, customer, smalltalk, refusal, multi_intent, memory); mỗi câu khai báo `any_tools/required_tools/expect_no_tools/expect_citation/expect_grounded/expect_refusal/must_contain` |
| Chạy eval | `scripts/run_copilot_eval.py` **(mới)** | Chạy **offline không cần API key**; tính 4 chỉ số + khối `quality` (critic, số bước, ký tự Observation, cache); ghi `eval/results/copilot_report.json` |
| Cổng CI | `tests/test_agents/copilot/test_copilot_eval.py` **(mới)** | tool ≥ 0.9 · citation ≥ 0.9 · bịa ≤ 0.05 · p95 < 2000 ms · câu từ chối phải dùng 0 tool · ≥ 30 câu phủ 6 tool/10 nhóm · `mode ∈ {react, offline_react, guardrail}` · critic gắn cờ ≤ 3 · có ≥ 1 câu nhiều bước |
| Tool scale | `tools.py` | `tra_cuu_ho_so_khach_hang` lọc bằng **SQL WHERE/LIKE + LIMIT** thay vì kéo 50 dòng rồi lọc bằng Python |
| Lỗi tool | `graph.py` | `_execute_tool()` retry 1 lần + backoff, Observation lỗi có `error_code` (`DB_DOWN`, `NOT_FOUND`, `UNKNOWN_TOOL`…), **không tính vào hạn mức 4 vòng** |
| Observation dài | `graph.py` | `_trim_tool_message()` rút gọn `summary` nhưng **giữ JSON hợp lệ** + giữ `citations` |

**Số thật:** tool 1.00 · citation 1.00 · hallucination 0.00 · p95 3.8 ms (32 câu, chế độ offline tất định).

### 2.2 P1: thông minh hơn có kiểm soát

| Năng lực | File | Nội dung |
| :--- | :--- | :--- |
| Planner | `planner.py` **(mới)** | Tách câu nhiều ý thành ≤ 3 bước đúng thứ tự nghiệp vụ (tra chính sách → tính tiền → soạn tin); phát event `plan` xuống UI |
| Memory | `memory.py` **(mới)** | Slot phiên (`current_unit`, `lead_dossier_id`, `transaction_date`) tự điền từ lịch sử; `summarize_history()` cho hội thoại dài |
| Verifier | `verifier.py` **(mới)** | Mọi con số trong câu trả lời phải có trong Observation; chuẩn hoá số kiểu VN (`8.0 %`, `4.655.200.000`); không đạt → `verified=false` + chèn cảnh báo |
| Ngữ cảnh chủ động | `prompts.py` | Prompt nạp chính sách đang hiệu lực, giỏ hàng canonical, căn/hồ sơ đang mở, kế hoạch, tóm tắt hội thoại |
| Guardrail | `tools/guardrails.py` | Thêm mẫu prompt-injection; `scan_output_leakage` chạy ở đầu ra |

### 2.3 P2: critic, học từ phản hồi, chi phí

| Hạng mục | File | Nội dung |
| :--- | :--- | :--- |
| **Critic vòng 2** | `critic.py` **(mới)** | Soi **lập luận/phát ngôn** (khác verifier chỉ soi con số): `MONEY_WITHOUT_ANCHOR`, `OVER_PROMISE`, `OFFER_WITHOUT_CONDITION`. Chạy bằng luật (không tốn lượt LLM ⇒ không nhân đôi độ trễ), chỉ ở lượt quan trọng, bỏ qua đoạn trích nguyên văn và bảng do engine sinh; chèn "_Kiểm duyệt nội bộ: …_" khi cần |
| **Học từ phản hồi** | `feedback.py` **(mới)** + `POST /api/v1/copilot/feedback` + `GET /copilot/feedback/summary` | Log append-only JSONL (`COPILOT_FEEDBACK_PATH`, mặc định `eval/results/copilot_feedback.jsonl`); thống kê hài lòng + tag bị chê; **few-shot động**: câu bị chê gần nhất được nhét vào prompt ở mục "ĐIỀU CẦN TRÁNH" |
| **Cache tool + ngân sách ngữ cảnh** | `graph.py` | `_tool_cache_key()` (tham số chuẩn hoá thứ tự) → gọi lại y hệt một tool trong cùng lượt không chạy lại; `MAX_TOTAL_OBSERVATION_CHARS` siết dần Observation; `context_budget` báo cáo lại UI/report |
| **Bảng chi phí trong eval** | `scripts/run_copilot_eval.py` | In khối "Chi phí & kiểm duyệt": số câu bị critic gắn cờ, số câu nhiều bước, tổng ký tự Observation, số lần dùng lại cache |
| API | `src/api/endpoints/copilot.py`, `service.py` | DTO thêm `verified`, `verification`, `plan[]`, `slots{}`, `critique`, `context_budget`; thêm 2 endpoint phản hồi (validate `rating ∈ [-1, 1]`, an toàn khi chưa có log) |

### 2.4 Trang **Quản trị chất lượng Copilot** (bổ sung theo yêu cầu review nội bộ)

> Câu hỏi đặt ra: *"Học từ phản hồi — trong user admin có nên có mục quản lý để theo dõi đánh giá chất lượng không?"*
> **Có.** Không có màn hình theo dõi thì vòng lặp phản hồi chỉ chạy một chiều (ghi log mà không ai đọc),
> và không ai phát hiện được chất lượng đang đi xuống. Đã dựng đầy đủ:

| Hạng mục | File | Nội dung |
| :--- | :--- | :--- |
| Trang quản trị | `frontend/apps/internal/src/features/admin/CopilotQualityPage.tsx` **(mới)** | 4 thẻ KPI (tổng phản hồi · **tỉ lệ hài lòng** · lượt chưa đạt · nhãn bị chê nhiều nhất); **biểu đồ xu hướng 14 ngày** (cột xanh/đỏ theo ngày, có `role="img"` + `aria-label`, ngày trống vẫn hiện để không hiểu sai là mất dữ liệu); thẻ **"Cần cải thiện ở đâu"** (tool hay xuất hiện ở lượt bị chê, phân bố theo chế độ `react/offline_react/guardrail`); bảng **phản hồi chi tiết** lọc theo *tất cả / chưa đạt / hữu ích*, mỗi dòng có câu hỏi, câu trả lời, lý do Sale nêu, nhãn, tool đã dùng và nút **sao chép** để đưa vào biên bản cải tiến |
| Điều hướng | `App.tsx`, `components/layout/StaffLayout.tsx` | Trang **riêng**, route riêng `/admin/copilot-quality` (không nhúng vào `/admin_cp` — khác vai: `/admin_cp` quản trị *tài khoản*, đây quản trị *chất lượng AI*); menu **"Chất lượng Copilot"** cho cả `ADMIN` và `POLICY_ADMIN` |
| Lối vào từ `/admin_cp` | `AdminCpPage.tsx` | Thêm thẻ chỉ đường (banner nhỏ) ngay trên thanh lọc: mô tả ngắn + nút **"Mở trang chất lượng"** → giúp Admin đang ở trang quản trị tài khoản vẫn tìm thấy |
| API thống kê | `GET /api/v1/copilot/feedback/summary` (mở rộng) | Thêm `by_mode[]`, `by_day[]` (14 ngày, đã điền ngày trống), `top_failing_tools[]`, `recent_negative[]` |
| API chi tiết | `GET /api/v1/copilot/feedback/recent` **(mới)** | `limit` (1–200) + `rating` (−1/0/1), mới nhất trước |
| **Phân quyền** | `src/api/endpoints/copilot.py`, `ENDPOINTS.copilotFeedbackRecent` | Chỉ `ADMIN` / `POLICY_ADMIN`; Sale gọi → **403** |
| **Che PII** | `feedback.mask_pii()` | Câu hỏi của Sale thường kèm tên + SĐT khách → server che SĐT (`091***78`) và email (`***@***`) **trước khi rời server**; trang chất lượng cần nội dung nghiệp vụ, không cần dữ liệu khách |
| Mock + test | `handlers/copilot.ts`, `scenarios.test.ts`, `tests/test_api/test_copilot_endpoints.py` | Mock có đủ 2 endpoint (đi qua `route()` nên RBAC được thực thi), test 403 cho Sale, test che PII, test lọc theo điểm, test xu hướng/chế độ |

**Vì sao tách khỏi `/admin_cp`:** `/admin_cp` là quản trị *tài khoản* (vòng đời user), còn đây là quản trị
*chất lượng AI* — gộp vào một trang sẽ phình và sai vai. Trang mới nằm cùng nhóm với "Chính sách bán hàng"
và "Kiểm thử công thức", đúng chỗ cho người theo dõi chất lượng.

---

## 3. UI/UX — `frontend/`

### 3.1 P0: bỏ chỗ "diễn"

| # | Trước | Sau |
| :-: | :--- | :--- |
| C1 | `handleConfirmQuoteAction` vẽ 4 bước bằng `setInterval` rồi in kết quả bịa ("Đề xuất PA-VAY…") | Gọi API thật `catalog.units()` → `quotes.create()`; tiến trình phản ánh vòng đời thật; thiếu mã căn/dự án thì **nói thẳng là thiếu**; lỗi thì đánh dấu bước hỏng (`failed`) |
| C2 | `customer_card` render bằng `dangerouslySetInnerHTML` + regex tự chế | `FormattedAiMessage` (React render). Số lần `dangerouslySetInnerHTML` trong trang: **0** |
| C3 | Modal căn cứ chỉ 3 dòng tĩnh | Thêm **Điều/khoản** + **hash tài liệu đầy đủ** + nút **Sao chép căn cứ** (kèm hash để đối soát) |
| C4 | Lỗi mạng → spinner treo | Banner `role="alert"` + nút **Thử lại** chạy lại đúng câu với đúng ngữ cảnh (`failedTurn` + `handleRetryFailedTurn`) |

### 3.2 P1: công cụ làm việc thật

| # | Trước | Sau |
| :-: | :--- | :--- |
| D1 | Danh sách slash command hardcode, không render, không tìm kiếm | `SlashCommandPalette.tsx` + `lib/slashCommands.ts` **(mới)**: lọc **không dấu** (NFD + `đ→d`, nhiều token AND), nhóm "gần đây" (localStorage `copilot.recentSlash`, tối đa 4), 8 lệnh (thêm `/gio-hang`), ↑/↓/Enter/Esc, `role="listbox"` + `aria-activedescendant` |
| D2 | Không thấy ngữ cảnh gửi lên; luôn gửi `transactionDate: null` | `CopilotContextChips.tsx` **(mới)**: chip **căn / hồ sơ / ngày giao dịch** sửa–xoá tại chỗ; `copilot.send()` gửi đúng `copilotUnit` + `copilotTxDate` (mặc định `2026-09-26`) |
| D3 | `setTimeout(6000)` bịa nudge "Mr. Hùng đang xem Q-00092" | Nudge **từ dữ liệu thật**: báo giá `NEEDS_REVISION`/`REJECTED` kèm lý do thật của quản lý; thêm nudge **SLA ≤ 10 phút** (quét mỗi phút, mỗi mốc hạn nhắc một lần) |
| D4 | Nút "Hoàn tác (8s)" chỉ đổi state UI | **Yêu cầu sửa** gọi thật `quotes.requestRevision()`; `quotes.submit()` cũng gọi thật và chỉ hiện receipt khi server xác nhận |
| D5 | Bốn tab `hoso/baogia/tinnhan/chinhsach` mỗi nơi một kiểu trạng thái | Thống nhất `QueryState/EmptyState/ErrorState` (đủ 4 trạng thái loading/error/empty/data); tab hồ sơ chưa chọn khách có màn hình hướng dẫn |
| D6 | Tab soạn tin kiểm F8 bằng heuristic tự chế | **Gọi F8 thật** `POST /compliance/check-message` (debounce 500 ms, `AbortController` huỷ request cũ); API lỗi → rơi về luật dự phòng **và nói rõ đang ở chế độ dự phòng**; badge hiển thị `đang kiểm… / dự phòng` |

`ReasoningTrace.tsx`: render thêm bước **`plan`** (danh sách bước + tool dự kiến); **critic gắn cờ** → hiện cảnh báo vàng ngay dưới câu trả lời.

### 3.3 P2: phản hồi & trải nghiệm

- **Nút 👍/👎 trên mỗi câu trả lời** → `api.copilot.feedback()`; ghi nhận lạc hậu không chặn UI; trạng thái "đã ghi nhận cảm ơn anh/chị" tại chỗ.
- Mock-server có handler cho 2 endpoint mới (giữ luật "mọi endpoint trong danh bạ đều có mock").
- **a11y**: `role="listbox"/"option"` + `aria-activedescendant` cho palette, `role="alert"` cho banner lỗi/F8 dự phòng, `aria-live` cho stepper, `aria-label` cho nút đánh giá.
- **Dọn cảnh báo lint**: 151 → **125** (0 error), riêng tệp trang bán hàng giảm 19 cảnh báo.

---

## 4. Hạ tầng & tài liệu

| Hạng mục | File | Nội dung |
| :--- | :--- | :--- |
| CI frontend | `.github/workflows/ci.yml` | Job `frontend`: Node 22 → `npm ci` → `tsc -p packages/tsconfig.json` → `tsc -b apps/internal apps/customer` → `oxlint` → `npm test` |
| TSConfig dùng chung | `frontend/packages/tsconfig.json` **(mới)** | Typecheck cho `api-client` · `ui` · `mock-server` |
| 8 lỗi type tồn đọng | `contracts/models.ts`, `contracts/copilot.ts`, `client.ts`, `mock-server/src/server.ts`, `scenarios.test.ts` | Thêm `QuoteCreateOutcome` (dung hoà **201 đồng bộ** của backend vs **202 + SSE** của TD-4.1/mock); `CopilotStepType` thêm `plan`; `Buffer → BodyInit` tường minh; 3 chỗ `stream_url` nullable được khẳng định rõ hợp đồng |
| Ruff toàn repo | `ruff.toml`, `scripts/seed_canonical_inventory.py` | Dọn 9 lỗi tồn đọng ở `scripts/`; ghi rõ per-file ignore `E402` cho script phải chèn `sys.path` trước import |
| Sửa script khởi động mock | `packages/mock-server/package.json` | `start` dùng `node --experimental-strip-types` **không resolve được import không đuôi** (`./db`) → đổi sang `tsx` (đã có sẵn trong devDependencies, khớp `dev`). Phát hiện khi dựng preview để tự kiểm chứng trang mới |
| Dev server cho preview | `apps/internal/vite.config.ts` | Thêm `host: true` + `allowedHosts: true` để chạy được sau proxy preview (trước đó Vite chỉ nghe localhost); chỉ ảnh hưởng dev server, không ảnh hưởng bản build |
| README | `README.md` | Badge + số test **479 → 498**; mục **chạy eval Copilot** kèm bảng ngưỡng CI/số thật; giới thiệu trang Chất lượng Copilot |
| Demo runbook | `docs/team_report/DEMO_RUNBOOK.md` | Kỳ vọng "71 passed" (số cũ nhiều tháng) → 498 |
| Biên bản | `docs/team_report/upgrade_new.md` | **File này** — bản ghi chính thức |
| Nháp trước đó | `upgrade/README.md`, `upgrade/PLAN.md`, `upgrade/CHANGELOG.md` | Giữ lại làm lịch sử; `upgrade/README.md` trỏ về file này |

---

## 5. Danh sách kiểm theo đề xuất gốc

| Đề xuất (§) | Trạng thái | Bằng chứng |
| :--- | :--- | :--- |
| §2 P0 — timeline ReAct thật | ✅ | `ReasoningTrace` nhận `thought/action/observation/plan`; không stepper giả |
| §2 P0 — bỏ stepper giả | ✅ | `handleConfirmQuoteAction` gọi API thật |
| §2 P0 — citation có `document_hash`/`clause_id` + copy | ✅ | Modal căn cứ + nút sao chép |
| §2 P0 — banner lỗi + retry | ✅ | Banner `role="alert"` + `handleRetryFailedTurn` |
| §2 P0 — bỏ `dangerouslySetInnerHTML` | ✅ | 0 lần trong `SalesWorkspacePage.tsx` |
| §2 P1 — slash palette thật | ✅ | Palette + `filterCommands` (6/6 smoke) |
| §2 P1 — context chips sửa được | ✅ | `CopilotContextChips` |
| §2 P1 — nudge thật | ✅ | Nudge báo giá + nudge SLA |
| §2 P1 — undo thật | ✅ | `quotes.requestRevision` (endpoint thật) |
| §2 P1 — nhất quán loading/error/empty 4 tab | ✅ | `QueryState` ở `hoso/baogia/tinnhan(F8)/chinhsach` |
| §2 P2 — bàn phím + a11y | ✅ | ↑/↓/Enter/Esc, aria listbox/alert/live |
| §2 P2 — giảm cảnh báo lint | ✅ (một phần) | 151 → 125 (0 error); 129 lượt là `no-unused-vars` rải ở trang cũ |
| §3 P0 — eval 4 chỉ số | ✅ | 32 câu vàng + cổng CI |
| §3 P0 — tool hồ sơ SQL + test giỏ hàng | ✅ | `tools.py`, test trong bộ intelligence |
| §3 P0 — lỗi tool có mã + retry | ✅ | `_execute_tool`, `error_code`, không tiêu vòng lặp |
| §3 P0 — cắt Observation dài | ✅ | `_trim_tool_message` + `_trim_with_budget` |
| §3 P1 — planner | ✅ | `planner.py` + event `plan` |
| §3 P1 — memory slot + tóm tắt | ✅ | `memory.py` |
| §3 P1 — verifier | ✅ | `verifier.py` |
| §3 P1 — ngữ cảnh chủ động | ✅ | `prompts.py` nạp chính sách/giỏ hàng/hồ sơ |
| §3 P2 — critic vòng 2 | ✅ | `critic.py` + cảnh báo trên UI + cổng CI (0 gắn cờ trên bộ vàng) |
| §3 P2 — học từ phản hồi | ✅ | `feedback.py` + nút 👍/👎 + few-shot động |
| Bổ sung — trang quản trị chất lượng cho vòng lặp phản hồi | ✅ | `/admin/copilot-quality` (KPI, xu hướng 14 ngày, tool kém, bảng chi tiết, RBAC, che PII) |
| §3 P2 — cache tool + ngân sách token/latency | ✅ | `_tool_cache_key`, `MAX_TOTAL_OBSERVATION_CHARS`, khối chi phí trong eval |
| §3 P2 — nudge chủ động theo trạng thái hồ sơ | ✅ | Nudge SLA + nudge trạng thái báo giá |
| §5.3 — CI frontend + tsconfig package | ✅ | Job `frontend`, `packages/tsconfig.json` |
| §5.3 — sửa 8 lỗi type | ✅ | `tsc` exit 0 cả hai phía |
| §4 — kế hoạch 2 tuần | ✅ | Việc W1/W2 nằm trong các mục trên |

---

## 6. Đợt 4 (2026-10-02) — Khu đo lường chất lượng & cổng ban hành chính sách

Yêu cầu: (a) đã có khu **benchmark/kiểm thử chất lượng** chưa; (b) khi **POLICY_ADMIN tải lên + duyệt một bộ tài liệu mới** thì đánh giá có **nhất quán** không;
(c) mục **"Kiểm thử công thức" trong `/admin_cp` đang "chưa hoạt động"** — phải sửa cho chạy được, không chỉ giải thích.

### 6.1 Khu đo lường chất lượng hiện có (trả lời (a): **có**, 4 tầng)

| Tầng | Vị trí | Đo cái gì | Bằng chứng |
| :--- | :--- | :--- | :--- |
| Hồi quy công thức | `/admin/benchmark` (UI) · `POST /api/v1/evaluation/benchmark-runs` · `dataset/fixtures/golden_scenarios.json` (17 ca FCS v2.6) | Δ tuyệt đối = 0 VNĐ trên 5 trường tiền tệ, AC-FIN-01, p50/p95 | **17/17 · 100%** (chạy thật bên dưới) |
| Chất lượng Copilot | `eval/copilot/golden_questions.json` (**32 câu**) + `scripts/run_copilot_eval.py` | tool-selection, citation precision, hallucination, p95 | tool **1.00** · citation **1.00** · bịa **0.00** · p95 **4 ms** |
| Giám sát vận hành | `/admin/copilot-quality` + `GET /copilot/feedback/summary` / `/recent` | điểm hài lòng, xu hướng 14 ngày, tool hỏng nhiều, phản hồi tiêu cực (che PII) | 5 phản hồi: react 3 / offline_react 1 / guardrail 1 |
| Cổng trước ban hành | `POST /api/v1/policies/rules/test` (+ nút "Kiểm tra trước ban hành" ở `PolicyDetailPage`) | 17 ca golden + trạng thái ban hành + đối chiếu bản golden đang khoá | gate 17/17 · `can_publish=true` |

### 6.2 Ba lỗi làm "Chạy kiểm thử" **không hoạt động** (đã sửa, (c))

1. **Lệch hợp đồng mock ↔ API thật** — nguyên nhân chính của màn hình trắng/lỗi khi chạy với backend thật:
   frontend đọc `total / passed / exact_match_rate / cases[]` (shape của mock), còn `BenchmarkRunReport` thật trả
   `total_cases / passed_cases / accuracy_rate / results[]` → `data.cases.map` nổ `undefined`, màn hình không render được.
   *Sửa:* `src/services/pricing/evaluation.py` bổ sung **additive** đúng contract hiển thị (`started_at`, `finished_at`, `total`,
   `passed`, `exact_match_rate`, `cases`; mỗi ca có `name`, `listed_price_before_tax_vnd`, `expected`, `actual`, `passed`,
   `status`, `execution_time_ms`). Ca bị chặn nghiệp vụ (`EXCEPTION_HANDLED`) trả `expected/actual = null` — UI hiện "—",
   không bịa số. Có test khoá lại: `tests/test_api/test_evaluation_router.py::test_benchmark_report_matches_frontend_contract`.
2. **RBAC lệch giữa nav và endpoint** — nav "Kiểm thử công thức" hiện cho cả ADMIN lẫn POLICY_ADMIN, nhưng mock chặn `auth: ['POLICY_ADMIN']`
   → tài khoản ADMIN tạo từ `/admin_cp` bấm vào ăn **403**; còn API thật lại **không gác quyền** (ai cũng gọi được).
   *Sửa:* `endpoints.ts` → `auth: ['POLICY_ADMIN','ADMIN']`; endpoint thật thêm `Depends(get_current_principal)` + kiểm tra vai trò
   (403 với SALE/không token — `test_benchmark_run_requires_quality_role`).
3. **Cổng trước ban hành ở backend thật chỉ là stub** — `rules/test` trả 3 check hình thức, 0 xung đột, `closure_completeness=1.0`, **không hề chạy hồi quy**;
   `publish` ban hành thẳng và không lưu bằng chứng nào. Mock-server thì làm đúng (chạy 17 ca) → hai bên kể hai câu chuyện khác nhau.
   *Sửa:* `_run_publish_gate()` trong `src/api/endpoints/policies.py` chạy **engine thật**: 6 hạng mục (mã văn bản, bộ ca vàng, **hồi quy 17 ca**,
   câu hỏi vàng, trạng thái ban hành, đối chiếu golden), trả đúng contract `RulesTestReport` (`checked_at`, `checks[]`, `conflict_findings[]`,
   `regression`, `can_publish`) **và** giữ các field cũ để không phá API cũ. `publish` gọi lại cổng: chưa đạt → **422 `POLICY_TEST_GATE_FAILED`**;
   đạt → trả kèm khối `benchmark` (run id, tỉ lệ, văn bản golden, mức khớp) và **đăng ký lần chạy vào cache** của `/evaluation/benchmark-runs/{run_id}`
   để tra cứu lại được bằng chứng. Mock được nâng cho khớp: `runBenchmark` nhận ngữ cảnh văn bản, sinh `policy_alignment`.

### 6.3 Nhất quán khi POLICY_ADMIN duyệt văn bản mới (trả lời (b))

- **Đã nhất quán ở phần chạy được:** mỗi lần ban hành đều **chạy lại 17 ca golden trên engine thật**, có mã lần chạy làm bằng chứng,
  và bản ghi ban hành gắn với kết quả đó → không còn cảnh "duyệt xong không biết công thức còn đúng không".
- **Bộ golden đối chiếu đúng nghĩa nào?** (làm rõ sau câu hỏi review) Bộ 17 ca vàng **không phải** cấu hình đang chạy của hệ thống:
  nó là *bộ đề kiểm tra* (input + kết quả kỳ vọng, khoá cứng) dùng để phát hiện hồi quy công thức.
  **Engine tính giá chạy thật KHÔNG đọc bộ này** — nó đọc văn bản chính sách *đang hiệu lực* theo `transaction_date`
  (`resolve_active_policy`: `status=PUBLISHED` + trong dải `effective_from..effective_to`) và tính từ điều khoản của văn bản đó.
  Nên **ban hành văn bản mới KHÔNG bị áp sai tỷ lệ cũ** — đã kiểm chứng bằng thực nghiệm (mục dưới).
- **Vì sao vẫn gắn `DRIFT`:** bộ vàng khoá cứng theo `POL-2026-VLF-GEN v2.6` (`DEFAULT_POLICY_REF`); văn bản mới *chưa có đề riêng*
  nên nó chỉ chứng minh được "engine không hồi quy", **không** chứng minh được "con số của văn bản mới đúng".
  Hệ thống nói thẳng điều đó (`GOLDEN_ALIGNMENT` = WARN, `policy_alignment` = DRIFT) thay vì báo xanh giả.
- **Thực nghiệm đã chạy (mock, đúng luồng `PolicyDetailPage`):** giao dịch `2026-11-15` khi `CSBH-ZEN-2027-V4.0` còn DRAFT
  → quote `ABSTAINED` + `POLICY_NOT_FOUND` ("không có chính sách hiệu lực") — **không lấy trộm số của v2.6**;
  sau khi POLICY_ADMIN ban hành v4.0 → cùng giao dịch đó chạy bình thường, `policy_snapshot_ref` = `CSBH-ZEN-2027-V4.0 v4.0`,
  tổng chiết khấu **10.5%** (1.5% cư dân + **9.0%** thanh toán sớm theo văn bản mới), `risk_flag` GREEN.
  Cùng lúc đó benchmark vẫn **17/17** nhưng gắn `DRIFT` + WARN `GOLDEN_ALIGNMENT` — đúng chủ ý: 17/17 nghĩa là
  *"engine không hồi quy"*, **không** nghĩa là *"văn bản mới đã được kiểm chứng"*.
- **Đã thêm để cảnh báo có ích hơn:** WARN giờ liệt kê luôn **tỷ lệ chưa có ca vàng** của văn bản mới
  (ví dụ v4.0 → `tỷ lệ chưa có ca vàng: 9.0%`), để Policy Admin biết chính xác phải soạn thêm ca nào.
  Mock `runBenchmark` cũng nhận `policy_id/policy_version` như API thật (trước đó mock bỏ qua, ghi nhầm văn bản golden).
- **Muốn hết DRIFT:** phải **soạn bộ ca vàng cho văn bản đó** (input + số kỳ vọng do nghiệp vụ chốt) — hiện là việc thủ công,
  chưa tự sinh từ văn bản. Đây là quy trình đúng: máy không được phép tự nghĩ ra "số đúng" rồi tự chấm điểm chính mình.
- **Giới hạn đã biết:** lịch sử lần chạy nằm **in-memory** (mất khi restart) ở cả backend thật lẫn mock;
  backend thật còn trả `POST /policies/publish` khác shape mock (mock trả PolicyDocument, thật trả PublishPolicyResponse).

### 6.4 Kiểm chứng đợt 4 (chạy thật)

| Lệnh / kịch bản | Kết quả |
| :--- | :--- |
| `.venv/bin/python -m pytest -q` | **503 passed** |
| `cd frontend && npm test` | **25/25 passed** (trước 24) |
| Thực nghiệm văn bản mới (mock, mục 6.3) | 15/11/2026 khi v4.0 DRAFT → **ABSTAINED** `POLICY_NOT_FOUND`; sau ban hành → **10.5%** (1.5% + 9.0%), `risk_flag` GREEN; benchmark vẫn 17/17 + **DRIFT** |
| `cd frontend && npx tsc -b apps/internal apps/customer` | **exit 0** |
| `cd frontend && npx oxlint` | **0 error**, 124 warning (không tăng) |
| `npm run build -w @pricepolicy/internal` | build thành công |
| Smoke qua Vite proxy: `/admin/setup` tạo ADMIN → `POST /evaluation/benchmark-runs` | **201** · 17/17 · `MATCH` · case BENCH-01 kỳ vọng = thực tế = 4.739.840.000 |
| Smoke qua Vite proxy: SALE gọi benchmark | **403** (giữ đúng quyền) |
| Smoke qua Vite proxy: POLICY_ADMIN `POST /policies/{id}/rules/test` | 17/17 · `can_publish=true` · `GOLDEN_ALIGNMENT` WARN khi văn bản DRAFT lệch bản golden |
| Smoke backend thật: publish → tra cứu bằng chứng | publish **200** kèm khối `benchmark`; `GET /evaluation/benchmark-runs/{run_id}` **200** |

### 6.5 Đối chiếu lộ trình P0–P2 của yêu cầu này

| Mốc | Trạng thái | Ghi chú |
| :--- | :--- | :--- |
| P0 · eval 30 câu vàng (tool/citation/hallucination/P95) | ✅ **vượt** | 17 ca công thức + **32 câu** Copilot; 4 chỉ số đã đo và có ngưỡng CI |
| P0 · tra cứu hồ sơ khách hàng lọc ở SQL | ✅ | `tra_cuu_ho_so_khach_hang` lọc bằng `WHERE` + `LIMIT` trong DB (không kéo cả bảng rồi lọc bằng Python) |
| P0 · retry tool lỗi + nén Observation | ✅ | vòng retry + `_trim_with_budget` (đợt 2, §2.1) |
| P1 · planner nhẹ + memory slot + verifier | ✅ | `planner.py`, `memory.py`, `verifier.py` (đợt 2) |
| P2 · critic vòng 2 + học từ phản hồi + cache/token | ✅ | `critic.py`, `feedback.py`, `/admin/copilot-quality`, cache theo phiên |
| Bổ sung đợt 4 · benchmark chạy được với API thật + cổng ban hành có bằng chứng | ✅ | §6.2 |

*Ghi chú kỹ thuật cho vòng sau:* `LIKE '%từ khoá%'` (có ký tự đại diện ở đầu) không dùng được B-tree index —
muốn nhanh thật thì cần **FTS5** (SQLite) / **pg_trgm** (Postgres) chứ không phải thêm `index=True` hình thức.

---

## 7. Còn lại (nói thẳng, không hứa quá)

1. **Học từ phản hồi mới ở mức "log + few-shot + màn hình theo dõi"**, chưa fine-tune/weight-tuning.
   Trang `/admin/copilot-quality` đã trả lời được "chất lượng đang lên hay xuống, kém ở đâu".
   Còn thiếu: **phân loại tag tự động** (hiện Sale gửi tag thô) và **tiêu chí gỡ** một "điều cần tránh"
   khỏi prompt khi nó đã được sửa — cả hai cần thêm dữ liệu thật mới đáng làm.
2. **Critic chưa gọi LLM sửa lời**: hiện critic *phát hiện + nhắc*, không tự viết lại. Đã có cờ `COPILOT_CRITIC=1` để bật một lượt sửa, nhưng **cố ý để mặc định TẮT** vì nhân đôi độ trễ mà chưa có dashboard chi phí.
3. **Trôi hợp đồng mock vs backend (TD-4.1)** mới xử lý ở tầng type (`QuoteCreateOutcome`) và ở lớp benchmark/cổng ban hành (§6.2 — nay hai bên trả cùng shape); triệt để thì mock-server nên đổi sang **201 đồng bộ** cho khớp backend thật, và `POST /policies/publish` của backend thật nên trả `PolicyDocument` như type frontend đang khai.
4. **125 cảnh báo oxlint** còn lại: 129 lượt `no-unused-vars` (đã bù bằng phần dọn trong trang bán hàng) ở `LeadInboxPage`, `PolicyListPage`… — dọn tiếp là việc cơ học, không rủi ro.
5. **Cache tool hiện trong-một-lượt** (theo phiên chat). Cache xuyên lượt/TTL cần thêm khoá theo `transaction_date` + chính sách hiệu lực để không trả dữ liệu cũ — nên làm cùng lúc với dashboard chi phí.
6. **Eval mới chạy offline tất định** (không cần API key). Muốn đo chất lượng LLM thật thì chạy `python scripts/run_copilot_eval.py --mode llm` khi có `OPENAI_API_KEY`; bộ ngưỡng CI hiện bám chế độ offline để phù hợp môi trường không có key.
