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

## 8. Đợt 5 (2026-10-02) — Ba yêu cầu người dùng nêu trực tiếp

Đợt này xử lý đúng ba việc được yêu cầu "làm trước", theo thứ tự ưu tiên: hội thoại phải giữ được →
câu trả lời không được lộ lệnh → Admin tự khai báo nhà cung cấp/đơn giá và đo được chi phí.

### 8.1 Lỗi mất hội thoại khi đổi trang (P1 — bug, không phải tính năng mới)

**Trước:** nội dung chat chỉ nằm trong `useState` của `SalesWorkspacePage`. Đổi route (sang CRM rồi
quay lại) hoặc F5 là mất sạch; không có cách nào tra lại câu hỏi/câu trả lời cũ.

**Nay — lưu ở server, không phải localStorage:**

| Tầng | Việc đã làm |
| :--- | :--- |
| Lưu trữ | `src/agents/copilot/history.py` — lưu **theo từng nhân viên** xuống `data/copilot_conversations.json` (append-theo-lượt, có khoá luồng), trần 50 cuộc/người và 200 lượt/cuộc; đọc lại được cả sau khi restart backend |
| API | `GET/POST /api/v1/copilot/conversations`, `GET /conversations/{id}`, `POST /conversations/turns` (tự tạo cuộc khi để trống `conversation_id`), `PATCH /conversations/{id}` (đổi tên), `DELETE /conversations/{id}` — tất cả yêu cầu đăng nhập và **chỉ thấy dữ liệu của chính mình** (người khác nhận 404, không phải 403) |
| UI | `SalesWorkspacePage` nhớ `conversation_id` đang mở qua `localStorage` (chỉ id, không phải nội dung), nạp lại cuộc cũ khi vào trang, có **thanh bên "Hội thoại đã lưu"** để mở lại cuộc bất kỳ, nút "Mới" để bắt đầu cuộc khác, xoá được từng cuộc |
| Ghi lượt | Mỗi câu trả lời cuối được ghi kèm trích dẫn + loại hành động; ghi **fire-and-forget có hàng đợi tuần tự** nên lỗi mạng không chặn hội thoại, và câu hỏi luôn khớp đúng lượt trả lời kể cả khi Sale bấm nhanh liên tiếp |
| Nhất quán mock | Mock giữ hội thoại trong bộ nhớ tiến trình (đủ để demo "đổi trang vẫn còn"), có hook `onReset()` để `POST /__mock/reset` và test dọn state |

Chủ ý **không** lưu các lượt chưa kiểm chứng (`grounded=false`, chế độ offline) vào lịch sử: mở lại
sau này sẽ không còn thấy cảnh báo "chưa đối chiếu được dữ liệu" đi kèm, nên thà không lưu.
Khi dựng lại khung chat từ lịch sử, chỉ tái hiện phần văn bản + trích dẫn — các thẻ tương tác một lần
(xác nhận, stepper, biên nhận) không dựng lại vì trạng thái của chúng đã chết.

### 8.2 Lệnh gạch chéo lọt vào câu trả lời

**Trước:** Sale gõ `/chinh-sach` hoặc gõ tắt `/ch` thì chính chuỗi lệnh đó đi thẳng vào prompt/ngữ
cảnh, có đường lọt nguyên văn vào câu trả lời.

**Nay, chặn ở cả hai bên:**

- Backend `src/agents/copilot/commands.py`: `normalize_user_message()` dịch lệnh đầy đủ thành câu lệnh
  tự nhiên (`/chinh-sach` → "Tra cứu chính sách đang hiệu lực", `/baogia căn ZEN-A-1205` →
  "Xem pipeline báo giá căn ZEN-A-1205", gõ tắt `/ch` → bỏ hẳn token lệnh); `strip_command_mentions()`
  dọn tàn dư trong câu trả lời sinh ra; `sanitize_history()` dọn lệnh còn sót trong lịch sử gửi kèm.
  Các chuỗi hợp lệ như `km/h`, `/api/v1`, `Anh/chị` **không** bị chạm tới.
- Mock (nơi lỗi này tái hiện được trong chế độ demo): `translateSlash()` chạy **trước** `parseIntent`,
  nên `/ch` không còn rơi vào nhánh "smalltalk" rồi bị đọc nguyên văn.

### 8.3 Admin tự khai báo nhà cung cấp LLM + tab Chi phí & hiệu năng

**Nguyên tắc ưu tiên (đúng như yêu cầu):** có nhà cung cấp **đang hoạt động trong DB** → dùng DB;
DB trống → rơi về biến môi trường; không có cả hai → chế độ suy luận tất định. API trả kèm `source`
(`db` | `env` | `none`) và màn hình nói rõ đang chạy bằng nguồn nào — không bắt Admin đoán.

| Hạng mục | Chi tiết |
| :--- | :--- |
| Bảng | `llm_providers` (`provider_id`, name, provider, base_url, model_name, `api_key_encrypted`, input/output_price_per_1m, currency, temperature, priority, is_active, last_test_*) |
| Bảo mật khoá | Mã hoá Fernet (`LLM_SECRET_KEY`/`SECRET_KEY`), lưu tiền tố `enc::`; **mọi phản hồi chỉ trả khoá đã che** `sk-t…abcd`; PUT để trống `api_key` = giữ khoá cũ |
| Ưu tiên chạy | `priority` tăng dần; phần tử đầu là primary, phần còn lại là chuỗi dự phòng (`with_fallbacks`) |
| Kiểm tra kết nối | `POST /admin/llm/providers/{id}/test` gọi `{base_url}/models` (timeout 8 s), lưu lại `last_test_status/latency/timestamp` |
| Đo lường | Mỗi lượt gọi LLM ghi JSONL (`data/llm_usage.jsonl`): token vào/ra, độ trễ, lỗi, lượt dự phòng, và **chi phí quy từ đơn giá** = `in/1M × đơn giá_in + out/1M × đơn giá_out` |
| Tổng hợp | `GET /admin/llm/usage/summary?days=` → tổng chi phí, tỉ lệ lỗi, p50/p95 độ trễ, bình quân/lượt, theo nhà cung cấp, theo ngày; `GET /admin/llm/usage/records?limit=` → log thô |
| UI `admin_cp` | Trang quản trị nay có **3 khu vực tách tab**: *Người dùng & phân quyền* (như cũ) · *Nhà cung cấp LLM* (thêm/sửa/xoá, khoá che, nút kiểm tra kết nối, cảnh báo khi đang chạy bằng ENV) · *Chi phí & hiệu năng* (thẻ tổng, bảng theo nhà cung cấp/model, biểu đồ theo ngày, log lượt gần nhất; chọn 7/14/30 ngày) |
| Quyền | Toàn bộ API `/api/v1/admin/llm/*` chỉ ADMIN (nhân viên thường 403); tab chỉ hiện trong `admin_cp` vốn đã chặn theo vai `ADMIN` |

Sửa kèm trong mock (phát hiện khi kiểm thử luồng thật): tài khoản ADMIN khởi tạo đầu tiên bị cấp
`USR-ADM-001` trùng với hồ sơ `minh.tuan` (POLICY_ADMIN) trong fixture, khiến `staffById()` trả về
hồ sơ cũ và **mọi API ADMIN đều 403 dù đã đăng nhập đúng**. Nay id được cấp bỏ qua id đã tồn tại.

### 8.4 Kiểm chứng đợt 5 (chạy thật)

| Lệnh / kịch bản | Kết quả |
| :--- | :--- |
| `.venv/bin/python -m pytest -q` | **526 passed** (đợt 4: 503; +23 test mới) |
| `cd frontend && npm test` | **33/33 passed** (đợt 4: 25/25; +8 test vòng 5) |
| `cd frontend && npx tsc -b apps/internal apps/customer` (+ `--force`) | **exit 0** |
| `cd frontend && npm run lint` | **0 error**, 124 warning (không tăng so với đợt 4) |
| Chuẩn hoá lệnh (backend, kiểm trực tiếp `commands.py`) | `/chinh-sach` → "Tra cứu chính sách đang hiệu lực"; `/ch` → `ch` (bỏ token lệnh); `km/h`, `/api/v1`, `Anh/chị` giữ nguyên |
| Chat với `/chinh-sach` trên mock | câu trả lời **không** còn chuỗi `/chinh-sach` lẫn `/(^|\s)ch`, vẫn `grounded=true` |
| Hội thoại trên mock (curl) | ghi lượt → `CNV-000001` 2 lượt, tiêu đề lấy từ câu hỏi đầu; `GET /copilot/conversations` → `total=1`; nhân viên khác đọc được? **404** |
| Admin LLM trên mock (curl) | `GET /admin/llm/providers` → `source=env`, `total=0` → `POST` → `LLM-0001`, khoá `sk-l…3456`; `GET /usage/summary` → 1 lượt, chi phí 0.000203 USD, p95 391 ms |
| API thật (pytest `tests/test_api/test_llm_admin.py`) | tạo thiếu `api_key` → **422**; PUT `api_key=null` giữ khoá cũ; nguồn `db`/`env`; chi phí `1M in + 0.5M out @ 0.15/0.60 = 0.45 USD`; `error_rate` và p95 đúng |

---

## 9. Đợt 6 (2026-10-02) — Phím tắt gửi tin & Copilot đọc câu trả lời (TTS)

Hai việc người dùng yêu cầu trực tiếp. Phím tắt là **sửa hành vi**; TTS là **năng lực mới**, nên phần
TTS được chia rõ: cái gì chạy được hôm nay, và cái gì cần chốt ngân sách/chính sách dữ liệu mới nối.

### 9.1 Enter = gửi, Ctrl/Cmd + Enter = xuống dòng

| Trước | Sau |
| :--- | :--- |
| `Enter` xuống dòng, `Ctrl/Cmd + Enter` gửi | **`Enter` gửi ngay**, `Ctrl/Cmd + Enter` chèn dòng mới tại vị trí con trỏ (giữ nguyên vùng chọn bị thay thế) |

Chi tiết đã xử lý để không sinh lỗi mới:

- Menu lệnh gạch chéo mở thì `Enter` **chọn lệnh** (người dùng đang chọn trong danh sách, chưa gửi) —
  giữ nguyên hành vi cũ, tránh gửi nhầm khi đang gõ `/baogia`.
- `Shift + Enter` cũng xuống dòng (thói quen phổ biến).
- Placeholder và dòng gợi ý dưới câu trả lời đổi thành “Enter để gửi · Ctrl+Enter để xuống dòng”.

### 9.2 Copilot đọc câu trả lời thành tiếng

Đã chạy được (không cần khoá, không cần ngân sách):

| Hạng mục | Chi tiết |
| :--- | :--- |
| Đọc từng câu trả lời | Nút **Đọc** dưới mỗi bong bóng trả lời; bấm lần hai = dừng (barge-in) |
| Tự đọc câu trả lời mới | Công tắc trong hộp thoại **Giọng đọc** ở header workspace (chế độ rảnh tay) |
| Dọn văn bản trước khi đọc | Bỏ markdown/citation/emoji, ngắt “(Điều 4, Khoản 2b)” — không đọc cả dấu sao |
| Chọn nhà cung cấp & giọng | `GET/PUT /api/v1/settings/tts`: danh mục 7 nhà cung cấp kèm đơn giá niêm yết, mã giọng tiếng Việt, cờ “đã có khoá” (không bao giờ trả khoá) |
| Phân quyền | Hồ sơ riêng của từng nhân viên (`scope=user`) thắng mặc định; **mặc định dùng chung chỉ ADMIN/MANAGER** đổi được — một Sale không đổi giọng cho 20k người |
| Đo chi phí | `cost_hint` quy từ đơn giá × ký tự, cắt theo trần ký tự/lượt; UI nói trước “tối đa X USD/lượt” |
| Chọn giọng theo dữ liệu | 👍/👎 ngay trong hộp thoại → `POST /settings/tts/feedback` → tỉ lệ hài lòng theo từng giọng |
| Admin nhìn thấy | Tab **Giọng đọc (TTS)** trong `admin_cp`: chọn giọng dùng chung, xem bảng giá + tình trạng khoá + mức hài lòng |
| Máy chưa có giọng tiếng Việt | Báo rõ “Máy này chưa có giọng tiếng Việt…” thay vì im lặng đọc sai tiếng |

**Chưa nối (nói thẳng):** endpoint tổng hợp audio (`POST /api/v1/tts/speak`) và cache audio. Hiện audio do
**trình duyệt** tổng hợp (0 đồng, giọng tuỳ máy), nên khi chọn nhà cung cấp trả phí thì UI báo đúng là
“chưa nối endpoint tổng hợp audio — đang đọc bằng giọng máy”. Hợp đồng API, bảng giá, bài toán chi phí
theo quy mô và các câu hỏi cần chốt (ngân sách, dữ liệu có được ra ngoài) nằm ở
`docs/team_report/tts_integration_plan.md`.

### 9.3 Kiểm chứng đợt 6 (chạy thật)

| Lệnh / kịch bản | Kết quả |
| :--- | :--- |
| `.venv/bin/python -m pytest -q` | **535 passed** (đợt 5: 526; +9 test TTS) |
| `cd frontend && npm test` | **38/38 passed** (đợt 5: 33; +5 test TTS) |
| `cd frontend && npx tsc -b apps/internal` | **exit 0** |
| `cd frontend && npm run lint` | **0 error**, 124 warning (không tăng) |
| Smoke mock: `GET /api/v1/settings/tts` | `browser` / `vi-VN` / chi phí **0 USD**; danh mục 4 nhà cung cấp kèm giá + cờ khoá |
| Smoke mock: Sale `PUT scope=user` sang Google | nhận `vi-VN-Wavenet-A`, `cost_hint` = **0,0024 USD** cho 600 ký tự |
| Smoke mock: Sale `PUT scope=default` | **403** kèm hướng dẫn; MANAGER đổi được → `viettel` / `hn_female_ngochuyen` |
| Smoke mock: 👍/👎 giọng đọc | `feedback_summary` = 1 ổn / 1 chưa ổn → **50% hài lòng** |
| Kiểm tra hàm đọc (Node, không có Web Speech) | trả `ok=false` + lý do rõ ràng; `toSpeakableText()` bỏ markdown/citation/emoji đúng mong đợi |

---

## 11. Đợt 7 (2026-10-02) — Vá lỗi `git up` trên VM & viết lại script triển khai

### 11.1 Lỗi gốc (người dùng dán nguyên văn)

```
Updating f34acb0..acffa01
error: Your local changes to the following files would be overwritten by merge:
        frontend/package-lock.json
Please commit your changes or stash them before you merge.
Aborting
```

**Nguyên nhân:** script deploy cũ chạy `npm install` trên server. `npm install` **tự sửa**
`frontend/package-lock.json` (khác lockfile trong git), nên lần deploy sau `git pull` từ chối ghi đè
thay đổi cục bộ và dừng giữa đường — code mới không về, service vẫn chạy bản cũ mà người deploy
không biết. Vấn đề lặp lại mỗi lần `npm install` chạm lockfile, không phải sự cố một lần.

Đã kiểm chứng trong sandbox: `npm ci` (bản mới dùng) **không** làm đổi `package-lock.json` (md5 trước/sau giống nhau).

### 11.2 Đã viết gì

| File | Nội dung |
| :--- | :--- |
| `deploy/deploy.sh` (viết lại, 512 dòng) | `git fetch` + `checkout -B` thay `git pull`; sao lưu drift thành patch rồi mới dọn; `npm ci` thay `npm install`; bỏ qua bước không cần; `flock`; health-check; tự lùi khi hỏng; `--dry-run`; log + state |
| `deploy/rollback.sh` (mới) | Lùi về commit đã deploy thành công (`--to <sha>` / `--auto`), build lại, reload pm2, kiểm tra `/health`, ghi lại state để lùi tiếp được |
| `deploy/install-git-up.sh` (mới) | Cài alias `git up` (sao lưu `~/.gitconfig`, dọn drift đang chặn deploy, tự chạy thử `--dry-run`) |
| `deploy/README.md` (mới) | Runbook: 3 bước cho VM hiện tại, bảng cờ, xử lý sự cố, mô tả file log/state |

**Điểm quan trọng:** bản deploy cũ **không** hề cài `deploy/p096.nginx.conf` vào `/etc/nginx/...` — nếu
sửa file này thì reload vô nghĩa. Bản mới tự copy vào `/etc/nginx/sites-available/p096.conf` khi file
đổi (chỉ khi `sudo -n true` chạy được, tức không hỏi mật khẩu), `nginx -t` trước, và tự khôi phục bản
cũ nếu config mới sai.

### 11.3 Tối ưu (bản cũ luôn chạy hết mọi bước)

| Bước | Bản cũ | Bản mới |
| :--- | :--- | :--- |
| Cập nhật code | `git pull` (kẹt khi server có drift) | `fetch` + `checkout -B` — không bao giờ kẹt; drift được sao lưu trước khi dọn |
| Python deps | `.venv/bin/pip install -r requirements.txt` mỗi lần | chỉ khi `requirements.txt` đổi (sha256 trong `.deploy-stamps/`) hoặc chưa có `.venv` |
| Node deps | `npm install` mỗi lần (sửa lockfile!) | `npm ci` chỉ khi lockfile đổi hoặc chưa có `node_modules` |
| Build | build **cả 2 app** mỗi lần | chỉ khi `frontend/` đổi; mặc định chỉ app nội bộ (nginx phục vụ nó) — `--all-apps` khi cần |
| pm2 | `reload` + `save` mỗi lần | chỉ reload khi backend/requirements đổi; zero-downtime |
| nginx | `nginx -t` + `reload` mỗi lần | chỉ khi `p096.nginx.conf` đổi (và có quyền sudo không mật khẩu) |
| Kiểm tra sau deploy | không có (báo "thành công" dù backend chết) | curl `/health` (dừng ngay khi OK) + restart 1 lần + **tự lùi** về commit tốt gần nhất |
| Deploy chồng nhau | không chặn | `flock logs/.deploy.lock` — lần thứ hai báo lỗi rõ, không build chồng |
| Kiểm tra trước | không có | node ≥ 20, ổ đĩa ≥ 1 GB, nhánh tồn tại trên origin |
| Sửa file `deploy.sh` giữa lúc chạy | bash đọc dở file → script đứt tay | tự chạy bằng bản sao `/tmp/p096-deploy-*.sh` (giữ PID/tham số) |
| Thời gian điển hình | luôn ~2–4 phút | sửa backend ~10–20 giây; sửa frontend ~1–2 phút |

### 11.4 Vá tiếp: `git up` báo "không đổi gì" dù vừa có code mới (phát hiện từ log chạy thật trên VM)

Chạy trên VM sau khi kéo code bằng tay, log ra:

```
Bỏ qua pip (requirements.txt không đổi)
Bỏ qua npm ci (lockfile không đổi, node_modules còn nguyên)
4/8 Build frontend
Bỏ qua build (frontend không đổi, dist còn nguyên)
5/8 Backend (pm2)
Bỏ qua reload (backend không đổi)
```

**Đây là lỗi thiết kế thật, không phải người dùng làm sai.** Bản §11.2 so `HEAD` với `origin/<nhánh>`
để quyết định "có gì đổi không". Nhưng khi code về máy bằng `git pull` tay (đúng thao tác gỡ kẹt ở
§11.6) thì `HEAD` đã bằng `origin` → script tưởng "không có gì đổi" → **bỏ qua build & reload**, để
lại web chạy bundle cũ và backend chạy code cũ trong khi code trên đĩa đã mới.

Đã sửa:

1. **Mốc so sánh = commit đã deploy THÀNH CÔNG** (`logs/deploy-state: current`), không phải `HEAD`.
   Chưa có mốc → chạy đủ bước; mốc không còn trong repo (force-push) hoặc không phải tổ tiên của
   commit đích → chạy đủ bước.
2. **Lưới an toàn cho build**: `dist/index.html` cũ hơn file nguồn trong `frontend/**/src/` → build lại.
3. **Lưới an toàn cho pm2**: mã nguồn backend (`src/*.py`, `requirements.txt`, `run.py`) mới hơn thời
   điểm tiến trình pm2 khởi động (`pm2 jlist → pm2_env.pm_uptime`) → reload. Dùng mtime file thay vì
   mốc thời gian commit để tránh commit mang ngày tương lai (lệch đồng hồ máy khác) gây reload vô ích.
4. Log nói rõ lý do: "Code trên server đã là <sha> nhưng CHƯA deploy bằng script này (kéo code tay…)".
5. Khi không có bước nào cần chạy, in gợi ý `git up --force`.

**Kiểm chứng (fixture, pm2/health giả):**

| Kịch bản | Kết quả |
| :--- | :--- |
| Lần đầu chạy script (chưa có mốc) | chạy đủ bước: `pip=1 npm-ci=1 build=1` + reload |
| Chạy lại ngay sau deploy thành công | bỏ qua build + **0** lần reload (không báo động giả) |
| **Kéo tay `git pull` rồi mới `git up`** | nhận ra "CHƯA deploy bằng script", diff `2 file` từ mốc cũ → build + reload |
| **Mốc đã trùng `HEAD` nhưng dist & pm2 cũ hơn nguồn** (đúng trạng thái VM hiện tại) | lưới an toàn bắt: "Mã nguồn frontend mới hơn bản build" → build; "Mã nguồn backend mới hơn tiến trình" → reload |
| Commit chỉ sửa frontend | build, **0** reload |
| Commit chỉ sửa backend | reload, không build |
| Deploy lỗi (health 500) | tự lùi về `state.current`, `prev < current`, exit 1 |
| Lùi tay 2 lần | đi về quá khứ liên tiếp, không quay lại commit vừa bỏ |
| `git up` sau rollback | tự về nhánh `develop` đúng bằng `origin/develop` |
| `bash -n` + `shellcheck -S style` cả 3 script | sạch |


### 11.8 Nhánh & remote mặc định của `git up` (theo câu hỏi người dùng)

Trước đây mặc định **luôn cứng là `develop`**, không nhớ lần trước — `git up main` rồi `git up` lần sau
sẽ quay về `develop`, trái với mong đợi "chỉ cần chỉ định một lần". Đã sửa:

Thứ tự chọn nhánh: **(1)** chỉ định trong lệnh (`git up main`) → **(2)** `DEPLOY_BRANCH` → **(3)** nhánh
đã deploy **thành công** gần nhất (`logs/deploy-state: branch`, do chính script ghi ở bước 8) → **(4)**
`develop`. Remote mặc định `origin`, đổi bằng `git up --remote=<tên>` hoặc `DEPLOY_REMOTE`.

Mỗi lần chạy in rõ: `Nguồn : origin/develop (mặc định cho remote · nhớ từ lần deploy thành công trước cho nhánh)`,
kèm gợi ý đổi nhánh khi đang dùng trí nhớ. Lỗi cũng rõ ràng: remote không tồn tại → liệt kê các remote đang có;
nhánh không tồn tại → gợi ý `git ls-remote --heads <remote>` / `git up --branch=<nhánh>`.

Alias `git up` cũng được viết lại thành một hàm có `exec` (đúng mã thoát, không thêm tiến trình) và
gọi trần để **không bao giờ nhân đôi tham số**. Ghi chú: `git up --help` / `git up -h` do **git** chặn
(in ra định nghĩa alias) — dùng `bash deploy/deploy.sh --help`.

**Kiểm chứng (fixture 2 remote `origin` + `upstream`, 3 nhánh `develop`/`main`):**

| Kịch bản | Kết quả |
| :--- | :--- |
| VM mới, chưa deploy lần nào, `git up` | `origin/develop` (mặc định) |
| `git up main` | deploy `main`, `logs/deploy-state` ghi `branch=main` |
| **`git up` (không tham số) sau đó** | **nhớ `main`**, không quay về `develop` |
| `DEPLOY_BRANCH=develop git up` | ghi đè trí nhớ → `origin/develop`; lần `git up` sau nhớ `develop` |
| `git up --remote=upstream develop` | `Nguồn : upstream/develop`, in rõ URL remote đang dùng |
| `git up --branch=khong-co-nhanh-nay` | lỗi rõ + gợi ý (`git ls-remote --heads origin`), exit 1 |
| `git up --remote=khong-co` | lỗi rõ + liệt kê remote hiện có (`origin upstream`), exit 1 |
| `--branch=` để trống | lỗi rõ, exit 2 |
| `git up --dry-run` | in đúng nguồn, không đổi gì |


### 11.5 Kiểm chứng (chạy thật trong sandbox, không phải trên VM thật)

Vì sandbox không có SSH tới VM, việc kiểm chứng được làm bằng **repo fixture** (repo bare giả làm
`origin`, một clone giả làm server) + `pm2` giả + health server giả:

| Kịch bản | Kết quả |
| :--- | :--- |
| `bash -n` cả 3 script | exit 0 |
| Server có drift `frontend/package-lock.json` + file rác + `.env`/`data/` | deploy chạy hết: drift lưu `logs/deploy-backups/dirty-*.patch` (patch hợp lệ, `git apply --check --reverse` pass), file rác bị dọn, `.env`/`data/`/`.venv`/`.deploy-stamps` **giữ nguyên**; kết thúc sạch (`git status` rỗng), `HEAD == origin` |
| Tái hiện lỗi cũ (drift + `git pull`) | không còn xảy ra vì không dùng `git pull` |
| Chạy lại khi không có commit mới | bỏ qua cập nhật code, bỏ qua pip/npm/build/reload, vẫn health-check → thành công |
| Commit mới chỉ chạm `src/` | `pip=0 npm-ci=0 build=0 backend=1` → chỉ reload pm2 |
| Commit mới chạm `requirements.txt` + `frontend/` + `src/` + nginx | `requirements=1 lockfile=1 frontend=1 backend=1 nginx=1` → chạy đủ bước |
| Backend chết (health 500) sau khi reload | `die()` → tự lùi về commit tốt gần nhất (`state.current`), health OK sau 14s, `logs/deploy-state` ghi `rolled_back=1`, exit code 1 |
| Deploy khi đang có tiến trình khác | thoát ngay với mã 3 + thông báo rõ (không build chồng) |
| `install-git-up.sh` (HOME giả) | sao lưu `.gitconfig`, in alias cũ, đặt alias mới; `git up`, `git up develop`, `git up develop --dry-run --check` truyền tham số **một lần** (không nhân đôi) |
| `rollback.sh` sau deploy thành công | `HEAD` detached đúng commit trước, state đảo `prev/current`, `git up` lần sau tự về nhánh `develop` |

**Chưa kiểm chứng:** chạy thật trên VM (không có SSH từ sandbox) và đường đi `nginx` (sandbox không có nginx/sudo).
Ba lệnh ở §11.6 là bước chạy thật trên VM.

### 11.6 Người dùng cần chạy (một lần, ~1 phút)

```bash
cd ~/vland
git checkout -- frontend/package-lock.json   # gỡ kẹt do npm install cũ
git pull origin develop                      # lấy script mới
bash deploy/install-git-up.sh                # cài alias git up (tự chạy thử --dry-run)
git up                                       # deploy thật từ nay
```

Nếu chỉ muốn gỡ kẹt để deploy tiếp mà chưa đổi script: `git checkout -- frontend/package-lock.json && git pull`.

### 11.7 Chống tái phát

Thêm bước CI `bash -n deploy/*.sh` (`.github/workflows/ci.yml`) để script deploy sai cú pháp không lọt vào nhánh.

---

## 12. Đợt 8 (2026-10-02) — Sửa lỗi "không mở được lịch sử cũ / mất hội thoại khi đổi trang" & mặc định ẩn khung lịch sử

### 12.1 Ba lỗi tìm được (có bằng chứng, không phải phỏng đoán)

**Lỗi 1 — Không lượt nào được lưu khi backend chạy chế độ dự phòng (nguyên nhân chính, phía frontend).**
`SalesWorkspacePage` có đoạn `if (!final.grounded && final.mode !== 'react') { …; return }` — bỏ qua
**không lưu** câu trả lời "chưa đối chiếu được dữ liệu". Chế độ `offline_react` (không có khoá LLM) luôn
cho `grounded=false`, nên trên môi trường đó **mọi lượt đều không được ghi** → danh sách "Hội thoại đã lưu"
rỗng và đổi trang là mất hội thoại. Lý do ghi trong comment ("mở lại sẽ không còn cảnh báo") không đứng
vững: `grounded` **không được dùng ở đâu khi render** (chỉ có 3 chỗ gán, 0 chỗ đọc) — nên việc bỏ lưu
chẳng giữ được cảnh báo nào, chỉ làm mất dữ liệu của Sale.

**Lỗi 2 — Hai worker uvicorn ghi đè lịch sử của nhau (phía backend, đo được).**
`src/agents/copilot/history.py` chỉ có `threading.Lock` (khoá trong **một** tiến trình), nhưng
`deploy/ecosystem.config.cjs` chạy `uvicorn --workers 2`. Hai tiến trình cùng đọc–sửa–ghi một file JSON
→ mất lượt. Đo thật (3 tiến trình × 15 lượt, cùng một cuộc):

| Bản | Kết quả |
| :--- | :--- |
| Có `flock` (bản mới) | **90/90** message, cả 3 lần chạy |
| Chỉ `threading.Lock` (bản cũ) | **36/90**, **54/90**, **30/90** — và có tiến trình còn crash `FileNotFoundError` khi hai worker tranh nhau file `.tmp` (request 500 giữa lượt chat) |

**Lỗi 3 — Mở cuộc cũ bị 404 thì UI im lặng.** Nếu `logs/deploy-state`… nhầm, nếu `conversationId` nhớ
trong `localStorage` trỏ tới cuộc đã bị xoá (hoặc của nhân viên khác), query lỗi nhưng UI **không xử lý**:
khung chat trống trơn, id cũ vẫn nằm đó và lần vào trang sau lặp lại y hệt.

### 12.2 Đã sửa

| Việc | Chi tiết |
| :--- | :--- |
| Lưu **mọi** lượt | Quy tắc tách thành hàm thuần `turnToAppendPayload()` trong `frontend/packages/api-client/src/copilotHistory.ts` — có test khoá hành vi (`round5.test.ts`) |
| Khoá liên tiến trình | `history.py`: `_process_lock()` dùng `fcntl.flock` trên file `.lock` cạnh file dữ liệu, bọc **cả** đọc–sửa–ghi (kể cả `list_conversations`); máy không có `fcntl` (Windows) lùi về khoá luồng như cũ |
| 404 khi mở cuộc cũ | Xoá id đang nhớ + mở cuộc mới + báo "Cuộc hội thoại cũ không còn…"; lỗi mạng chỉ báo nhẹ và giữ id để thử lại |
| Khung lịch sử | **Mặc định ẨN**; nút "Lịch sử" chuyển sang **bên trái** cạnh tiêu đề (kèm số cuộc), bấm mới mở; chọn một cuộc trong danh sách thì khung vẫn mở |

### 12.3 Kiểm chứng (chạy thật)

| Lệnh / kịch bản | Kết quả |
| :--- | :--- |
| `.venv/bin/python -m pytest -q` | **536 passed** (đợt 7: 535; +1 test đa tiến trình) |
| `pytest tests/test_agents/test_copilot_history_concurrency.py` | pass — 3 tiến trình × 15 lượt, đủ **90/90** message |
| A/B có/không `flock` (script đo riêng) | có: 90/90 · 90/90 · 90/90 — không: 36/90 · 54/90 · 30/90 (kèm crash) |
| `cd frontend && npm test` | **39/39** (đợt 7: 38; +1 test chế độ dự phòng vẫn lưu) |
| `npx tsc -b apps/internal apps/customer` | exit 0 |
| `npm run lint` | 0 error, 124 warning (không tăng) |
| `npm run build -w @pricepolicy/internal` | OK; bundle chứa đủ 3 dấu hiệu mới (kiểm bằng `grep -rF` trong `dist/assets`) |
| `ruff check src/ tests/` | All checks passed |

**Chưa kiểm chứng:** hành vi UI trong trình duyệt thật — sandbox không có trình duyệt (tải Chromium bị chặn,
apt không tới được repo). Vì vậy phần "mặc định ẩn / bấm nút mới hiện" mới được xác nhận ở mức mã nguồn +
bundle + typecheck, chưa có ảnh chụp màn hình. Việc cần làm trên VM ở §12.4.

### 12.4 Trên VM cần làm gì (vì sao vẫn "không thấy lịch sử")

Bản đang chạy trên `demoday.work.gd` rất có thể vẫn là **bundle cũ** (lần deploy 08:46 đã bỏ qua build/reload
— xem §11.4). Sau khi đưa được các commit này lên remote mà VM dùng:

```bash
cd ~/vland
git pull origin develop     # lấy deploy.sh mới + các bản vá này
git up --force              # ép build lại frontend + reload backend
```

Kiểm tra nhanh trên VM (phải thấy giờ build mới):

```bash
ls -l --time-style=+%F_%T frontend/apps/internal/dist/assets/ | head -3
curl -s localhost:8000/api/v1/copilot/conversations   # 401 = endpoint có; 404 = còn chạy code cũ
```

Trên trình duyệt: **Ctrl+Shift+R** (xoá bundle cũ trong cache) rồi vào lại trang Sale — nút "Lịch sử"
nằm bên trái cạnh tiêu đề, khung lịch sử ẩn sẵn, bấm mới hiện.


---

## 13. Đợt 9 (2026-10-02) — Khai báo LLM: chặn điền nhầm user/password & nút Test kết nối ngay sau khi lưu

### 13.1 Lỗi 1 — trình duyệt tự điền tài khoản/mật khẩu vào `Base URL` và `API key`

Ảnh người dùng gửi: ô **Base URL** bị điền "sale", ô **API key** hiện dấu chấm tròn — đây là **tài khoản/mật
khẩu đã lưu trong trình duyệt**, không phải dữ liệu người dùng gõ.

**Nguyên nhân:** trong hộp thoại, ngay trước ô `API key` (`type="password"`) là các ô text. Chrome/Edge suy
luận "ô text + ô password = form đăng nhập" rồi tự điền. Bản cũ chỉ đặt `autoComplete="off"` cho ô khoá —
mà trình duyệt **bỏ qua `off` với ô password** (đây là hành vi có chủ đích của Chrome để không phá trình
quản lý mật khẩu).

**Đã sửa:**

| Việc | Chi tiết |
| :--- | :--- |
| Bọc cả lưới field trong `<form autoComplete="off">` | Chrome không còn coi cả hộp thoại là form đăng nhập; Enter trong ô nhập cũng lưu luôn (submit handler riêng) |
| Ô API key | `autoComplete="new-password"` (hiểu là khoá MỚI, không điền bản đã lưu và không hỏi "lưu mật khẩu?") + `name="llm-api-key"` |
| Ô Base URL | `type="url"` + `inputMode="url"` + `name="llm-base-url"` + `autoComplete="off"` (ô `type=url` không bị coi là username) |
| Các ô text khác (tên, provider, model, currency) | `autoComplete="off"` + `name` riêng |
| Trình quản lý mật khẩu bên thứ ba | `data-lpignore` (LastPass), `data-1p-ignore` (1Password), `data-bwignore` (Bitwarden), `data-form-type="other"` (Dashlane) |

### 13.2 Lỗi 2 — "lưu xong rồi, Test kết nối ở đâu?"

Thực tế **đã có** nút kiểm tra kết nối, nhưng chỉ là icon ⚡ nhỏ trong cột "Thao tác" của bảng — Admin vừa
điền form xong **không thấy** nó, vì hộp thoại tự đóng ngay sau khi lưu.

**Đã sửa — luồng mới đúng như mô tả:** điền → **lưu** → hộp thoại **giữ nguyên** → hiện dòng
"Đã lưu cấu hình — bấm **Test kết nối**…" và nút **Test kết nối**; bấm thì gọi backend (`POST
/admin/llm/providers/{id}/test`, backend gọi `/models` của nhà cung cấp thật), rồi hiện kết quả **ngay trong
hộp thoại**: xanh "Kết nối thành công · OK · 123 ms" hoặc vàng "Kết nối chưa dùng được" + lý do cụ thể
(HTTP 401, không gọi được, chưa có API key…). Lỗi mạng cũng hiện trong hộp thoại thay vì im lặng.

Kèm theo, ba chỗ phải chỉnh cho khớp vì hộp thoại không tự đóng nữa:

1. **Chống tạo trùng:** bấm "Khai báo" lần hai giờ là **cập nhật** đúng nhà cung cấp vừa tạo (trước đây
   `editing` vẫn null nên sẽ tạo thêm bản ghi trùng).
2. **Không giữ khoá thô** trong state sau khi lưu; để trống ở lần lưu sau = giữ khoá cũ (đúng ngữ nghĩa
   `update` của backend), placeholder hiện bản che vừa lưu.
3. **Sửa form sau khi lưu** thì kết quả test cũ bị bỏ (tránh hiểu nhầm "đã test" trong khi cấu hình trên
   form đã khác bản đã lưu).

### 13.3 Kiểm chứng (chạy thật)

| Lệnh / kịch bản | Kết quả |
| :--- | :--- |
| `npx tsc -b apps/internal` | exit 0 (bao gồm cả thuộc tính `data-1p-ignore` trong JSX) |
| `npm run lint` | 0 error, 124 warning (không tăng) |
| `npm run build -w @pricepolicy/internal` | OK |
| `grep -F` trong bundle `dist/assets` | có đủ: `new-password`, `1p-ignore`, `lpignore`, `bwignore`, `llm-base-url`, `llm-api-key`, "Test kết nối", "Đã lưu cấu hình" |
| `cd frontend && npm test` | **39/39** — bổ sung assertion: sau khi test, `last_test_status = OK`, `last_test_latency_ms > 0`, `last_tested_at` có giá trị **trong danh sách** (nếu không, bảng vẫn hiện "Chưa kiểm tra" dù vừa bấm Test) |
| `.venv/bin/python -m pytest -q` | **536 passed** |
| `ruff check src/ tests/` | All checks passed |

**Chưa kiểm chứng:** hành vi autofill thật của Chrome/Edge — phải thử bằng trình duyệt có lưu mật khẩu
(sandbox không có trình duyệt). Cách kiểm nhanh: mở hộp thoại khai báo, xác nhận 2 ô trống; nếu vẫn bị
điền, xoá mật khẩu đã lưu cho domain rồi thử lại và báo lại để thêm cách chặn khác (`readOnly` đến khi focus).


---

## 14. Đợt 10 (2026-10-02) — "Test kết nối" báo `HTTP 403` + trang Cloudflare, dù API vẫn chạy từ ứng dụng khác

### 14.1 Người dùng báo gì (nguyên văn)

> **Kết nối chưa dùng được · ERROR · 62.57 ms**
> Nhà cung cấp trả HTTP 403: `<!DOCTYPE html>…<title>Just a moment...</title>…`
>
> API của tôi đang hoạt động bình thường khi test gọi từ ứng dụng khác, nhưng trong mục test kết nối hiện tại thì đang gặp lỗi này.

### 14.2 Nguyên nhân gốc — lỗi ở phía mình, không phải cấu hình của Admin

Bản cũ của nút Test kết nối chỉ làm đúng một việc: `GET {base_url}/models` bằng `httpx` với tuỳ chọn mặc định.
Có hai vấn đề, và cả hai đều nằm ở phía mình:

1. **Thiếu `User-Agent` khai báo tử tế.** `httpx` mặc định gửi `User-Agent: python-httpx/<version>`. Nhà cung cấp
   nào đứng sau **Cloudflare bật chống bot** sẽ trả `403` kèm trang challenge `"Just a moment..."` cho client
   "trông giống bot". Ứng dụng khác của Admin chạy được vì nó gửi UA của chính nó (trình duyệt/SDK) → đúng như
   Admin nói: **cấu hình không sai, đường test của mình sai**.
2. **Chỉ thử `/models`.** Nhiều gateway OpenAI-compatible **không mở `/models`** nhưng vẫn chạy tốt
   `/chat/completions` — endpoint mà PricePolicy thật sự dùng khi gọi Copilot. Test một endpoint không dùng
   rồi kết luận "kết nối chưa dùng được" là kết luận sai.

Lỗi phụ: khi nhà cung cấp trả HTML, màn hình Admin nhận nguyên đoạn `<!DOCTYPE html>…` — vô nghĩa với người
đang cần biết phải sửa gì.

### 14.3 Đã sửa

Việc gọi mạng được tách sang `src/services/llm_probe.py` (`probe_llm_provider()` + `ProbeResult`) — không phụ
thuộc FastAPI/DB nên test được trực tiếp. Endpoint `POST /admin/llm-providers/{id}/test` chỉ còn gọi probe và
ghi `last_test_status` / `last_test_latency_ms` / `last_tested_at`.

| Trước | Sau |
| :--- | :--- |
| UA mặc định của httpx | `P096-VLandFuture-Healthcheck/1.0 (+https://demoday.work.gd)`, `Accept: application/json`, `follow_redirects=True`, timeout 8 s |
| Chỉ `GET /models` | `GET /models` → nếu không dùng được thì `POST /chat/completions` (`max_tokens: 1`, model theo cấu hình) — đúng đường app thật gọi |
| Không kiểm tra `base_url` | Nếu cả hai hỏng và Base URL chưa có `/vN` → thử thêm `{base_url}/v1/chat/completions`; nếu đường này sống thì trả lời thẳng **"API trả lời ở …/v1 nhưng KHÔNG trả lời ở Base URL hiện tại — sửa Base URL thành …/v1 rồi lưu lại"** (vẫn `ERROR` vì cấu hình đang sai, nhưng kèm đúng cách sửa) |
| `detail = f"… {resp.text[:160]}"` | Chẩn đoán tiếng Việt theo tình huống; HTML thô **không bao giờ** hiển thị |
| 200 + HTML bị coi là thành công | Cả hai đường phải trả **JSON** mới tính là thành công (một số server trả HTML trang chủ cho mọi đường dẫn) |

Chẩn đoán theo tình huống: Cloudflare (nói rõ 3 việc cần kiểm tra: Base URL phải là địa chỉ API thường có `/v1`;
nhà cung cấp có cho gọi từ IP máy chủ không; allowlist đường dẫn API trong Cloudflare) · HTML không phải
Cloudflare → "thường phải thêm `/v1`" · 401 → khoá bị từ chối · 403 → khoá thiếu quyền hoặc IP bị chặn ·
404 → không thấy endpoint, kiểm tra `/v1` · 429 → bị giới hạn tốc độ. `detail` gọn ≤ ~200 ký tự, gộp khoảng trắng.

### 14.4 Kiểm chứng (chạy thật)

`tests/test_services/test_llm_probe.py` dựng **server nhà cung cấp giả trong tiến trình** (`HTTPServer` ở cổng
trống, khai báo qua fixture `provider_server(scenario)` trong `tests/conftest.py`) đóng đúng các hành vi đã gặp:

| Kịch bản | Kỳ vọng — và đã đạt |
| :--- | :--- |
| Cloudflare chặn `/models`, `/chat/completions` chạy | **OK** qua `POST /chat/completions`; `detail` nói rõ vì sao `/models` không dùng được |
| Cloudflare chặn cả hai | `ERROR`, câu chẩn đoán có "Cloudflare"/"Just a moment"/`/v1`/`allowlist`, **không có** `<!DOCTYPE` hay `<html` |
| Server bình thường | OK qua `GET /models`, nêu số model |
| Server giả ghi lại `User-Agent` nhận được | đúng bằng `USER_AGENT` của mình (**không bao giờ** là `python-httpx`) |
| Base URL trỏ vào trang chủ (200 + HTML) | Không còn bị coi là thành công; gợi ý thiếu `/v1` |
| Base URL thiếu `/v1` nhưng API sống ở `/v1` | Chỉ đúng cách sửa, vẫn `ERROR` |
| 401 | Nói rõ khoá bị từ chối |
| Chưa có API key | `NOT_CONFIGURED` |

| Lệnh | Kết quả |
| :--- | :--- |
| `.venv/bin/python -m pytest -q` | **546 passed** (543 trước khi thêm ca "thiếu `/v1`" + 3 ca dùng lại fixture) |
| `pytest tests/test_api/test_llm_admin.py` | 9 passed — có ca endpoint thật gặp Cloudflare, và `last_test_*` được ghi vào danh sách |
| `ruff check src/ tests/` | All checks passed |

**Chưa kiểm chứng:** nhà cung cấp thật của Admin (sandbox không gọi ra được dịch vụ đó). Sửa này loại bỏ đúng
nguyên nhân đã thấy trong ảnh — UA mặc định bị Cloudflare chặn — và chuyển sang đúng endpoint ứng dụng dùng;
xác nhận cuối cùng phải bấm Test kết nối trên VM.

### 14.5 Trên VM cần làm gì

Đây là sửa **backend** (không đổi giao diện):

```bash
cd /opt/vin20k 2>/dev/null || cd ~/Vin20KBuildPhase
git pull origin develop && git up --force
```

Sau đó vào **Quản trị → Nhà cung cấp LLM**, mở nhà cung cấp, **Lưu thay đổi** (không cần nhập lại key), rồi bấm
**Test kết nối**. Kỳ vọng:

* API chạy được → xanh, ghi rõ đã kết nối qua đường nào (`GET /models` hay `POST /chat/completions`);
* Base URL còn thiếu `/v1` → đỏ nhưng kèm câu "sửa Base URL thành …/v1" — sửa xong bấm Test lại là xanh;
* Bị Cloudflare chặn thật (cả hai đường) → câu tiếng Việt nói rõ Cloudflare và 3 việc cần kiểm tra. Nếu gặp
  trường hợp này, gửi lại ảnh để đối chiếu: lúc đó mới cần nhà cung cấp allowlist đường dẫn API hoặc cho phép IP máy chủ.

### 14.6 Hỏi thêm (cùng đợt 10) — khoá API trong DB có được bảo vệ chưa? Nhiều khai báo thì cơ chế dự phòng còn chạy?

**1) Khoá API trong DB: đã mã hoá, nhưng khoá để mã hoá còn lấy từ ENV.**

* Cột `llm_providers.api_key_encrypted` lưu **Fernet** (`enc::` + ciphertext), không phải plaintext; mọi phản hồi API
  chỉ trả dạng che `sk-t…abcd`; PUT để trống `api_key` = giữ khoá cũ. Các hành vi này đã có test từ đợt 5 (§8.3).
* Khoá mã hoá lấy từ `LLM_SECRET_KEY` (hoặc `SECRET_KEY`) trong ENV; **trước đây chưa có trong `.env.example`** nên
  nhiều khả năng máy chủ đang chạy bằng khoá mặc định của mã nguồn (`vlandfuture-dev-secret-change-me`) — vẫn không
  lộ khoá trong file DB, nhưng ai đọc được mã nguồn là giải mã được. Vì vậy đợt này ghi rõ biến đó vào `.env.example`.
* Từ đợt này `src/services/llm_secrets.py` còn: cảnh báo khi **đang mã hoá bằng khoá mặc định**, giải mã được dữ liệu
  cũ (không làm mất nhà cung cấp khi Admin vừa đặt khoá mới) nhưng cảnh báo **phải nhập lại key** để mã hoá theo khoá
  riêng, và cảnh báo rõ khi khoá đổi sang giá trị khác hẳn khiến bản ghi không giải mã được (bản ghi đó bị bỏ khỏi
  chuỗi dự phòng — trước đây bị bỏ **im lặng**).
* **Bẫy vừa bịt**: hàm lấy khoá chỉ đọc `os.environ`, trong khi `pydantic-settings` nạp `.env` vào object Settings
  chứ **không ghi vào `os.environ`** → đặt `LLM_SECRET_KEY` trong `.env` của VM rồi khởi động lại vẫn âm thầm dùng
  khoá mặc định. Nay `_secret()` đi theo thứ tự biến môi trường thật → `.env` (qua `Settings.llm_secret_key`) →
  khoá mặc định, có test riêng (`tests/test_services/test_llm_secrets.py`) dựng `.env` thật rồi kiểm tra.

**2) Nhiều khai báo trong DB: cơ chế dự phòng chạy thật, đã kiểm chứng bằng lượt gọi thật (không chỉ đọc code).**

* Chuỗi được dựng theo `priority` tăng dần: bản ghi đầu là chính, các bản ghi còn lại là dự phòng (`is_fallback=True`);
  bản ghi `is_active = false` bị loại; DB có bản ghi **đang bật** thì ENV (`FALLBACK1_*`, `FALLBACK2_*`) không tham gia.
* Bằng chứng mới (`tests/test_api/test_llm_admin.py`):
  * `test_nhieu_khai_bao_db_thi_noi_thanh_chuoi_chinh_du_phong_theo_uu_tien` — tạo 4 bản ghi **lộn xộn** (20 → 10 → 30 → 5-tắt),
    chuỗi thật phải là `primary-model → fb1-model → fb2-model`, bản ghi đang tắt không có mặt.
  * `test_nha_cung_cap_chinh_chet_thi_tu_dong_chay_sang_nha_cung_cap_ke_tiep` — "chính" trỏ vào cổng chết, gọi thật
    `llm.ainvoke(...)` và nhận câu trả lời `pong` **từ nhà cung cấp dự phòng**: chuyển tiếp hoạt động end-to-end.
  * `test_doi_khoa_ma_hoa_khong_lam_mat_nha_cung_cap_nhung_phai_nhap_lai_key` — đổi `LLM_SECRET_KEY` không làm mất nhà
    cung cấp (không sập dịch vụ) nhưng có cảnh báo; nhập lại key thì mã hoá theo khoá mới.
* Đã kiểm tra thêm: khi có dự phòng, `bind_tools` vẫn được áp cho **cả** primary lẫn fallback (LangChain uỷ nhiệm
  `bind_tools` xuống từng runnable) → Copilot không mất khả năng gọi tool tra chính sách khi chạy bằng nhà cung cấp dự phòng.
* Cách nhìn thấy việc chuyển tiếp trên giao diện: tab **Chi phí & hiệu năng** nhóm theo `(provider, model_name)` kèm
  `calls` / `failed_calls`, và mỗi bản ghi usage có cờ `is_fallback` — nhà cung cấp lỗi hiện ra ngay ở đó.
* Khi **cả chuỗi** đều lỗi: Copilot không trả HTTP 500 mà rơi về chế độ offline kèm `degraded_reason` (đường đã có từ trước).

### 14.7 Hỏi tiếp (cùng đợt 10) — FallBack2 (`codecraftapi.com`) vẫn bị Cloudflare chặn: giờ làm gì?

**Bằng chứng thu được (không phải suy đoán):**

* Sandbox **không có Internet ra ngoài** (mọi `curl https://…` đều `http=000`, kể cả `example.com`) — nên không thể tự gọi nhà cung cấp để kiểm chứng.
* Bằng đường khác (khác IP, client khác), `https://codecraftapi.com/v1/models` **trả JSON bình thường**:
  `{"error":{"message":"Missing API key. Send it as a Bearer token or x-api-key header.","type":"authentication_error"}}`
  ⇒ **API sống, không hỏng, không chặn tất cả**; Cloudflare chỉ đang chặn client/máy chủ của mình. Đây đúng là
  chặn ở phía hạ tầng, không phải lỗi Base URL/API key của Admin.

**Đã sửa gì để lần sau không phải đoán:**

| Việc | Chi tiết |
| :--- | :--- |
| Header dùng chung cho probe **và** client thật | `src/services/llm_http.py`: hai chế độ `app` (mặc định, khai báo tên ứng dụng) và `browser` (thêm bộ header trình duyệt, vẫn giữ `X-Client-App` + đuôi `P096-VLandFuture`). `llm.py` truyền `default_headers` cho `ChatOpenAI` nên **test và chat đi cùng một kiểu header** — trước đây có thể lệch nhau (test xanh, chat đỏ) |
| Công tắc cho Admin | `LLM_HTTP_HEADERS=app|browser` trong `.env` (mặc định `app`, không đổi hành vi cũ) |
| Chẩn đoán khi bị Cloudflare | Probe **thử thêm chế độ header còn lại** và **tra IP công khai của máy chủ** (cache 10 phút, có thể điền sẵn `LLM_PUBLIC_IP`), rồi trả lời đúng câu hỏi: *đổi header là qua, hay bị chặn IP?* |
| Câu trả lời cho Admin (3 dòng) | (1) Khẳng định không phải lỗi Base URL/API key + **nói rõ Copilot cũng bị chặn**, không chỉ nút Test. (2) Kết quả chẩn đoán: *"gửi header kiểu trình duyệt thì QUA được ⇒ thêm `LLM_HTTP_HEADERS=browser` rồi `git up --force`"* hoặc *"đã thử cả hai kiểu header đều bị chặn ⇒ chặn theo IP"*. (3) Ba cách xử lý: nhờ nhà cung cấp allowlist **IP công khai của máy chủ** (in kèm IP), hỏi hostname API không qua Cloudflare (`api.<tên miền>`), hoặc trỏ Base URL qua proxy/relay ở mạng khác |
| Giao diện | Câu chẩn đoán nhiều dòng nên panel kết quả đổi sang `whitespace-pre-line` (trước đó dồn thành một khối, rất khó đọc) |

**Kiểm chứng (chạy thật trong sandbox):** `pytest` **556 passed**; `ruff` sạch; `tsc -b apps/internal` exit 0;
`npm run lint` 124 cảnh báo / 0 lỗi (không tăng); build OK, bundle có `whitespace-pre-line`; `npm test` **39/39**.
Test mới khoá lại đúng các hành vi vừa thêm:

* `test_client_that_gui_dung_bo_header_ma_test_ket_noi_bao_cao` — client thật gửi **đúng** UA theo chế độ (`app` → `P096-VLandFuture…`; `browser` → `Mozilla/5.0…`), bắt bằng server giả.
* `test_test_ket_noi_xanh_thi_chat_that_cung_chay_duoc` — Test kết nối báo OK thì `get_llm().ainvoke()` thật cũng trả lời được (nút Test không nói dối).
* `test_chan_theo_kieu_client_thi_bao_dung_cach_bat`, `test_bat_che_do_header_trinh_duyet_thi_test_xanh`,
  `test_chan_ca_hai_kieu_client_thi_phai_noi_dung_viec_can_lam` — ba nhánh của câu chẩn đoán.
* Server giả nay trả cùng một kiểu phản hồi cho mọi đường dẫn theo từng kịch bản (trước đây kịch bản "trang chủ"/"sai khoá" lại trả Cloudflare ở đường chat — không giống nhà cung cấp thật, và che mất chẩn đoán đúng).

**Chưa kiểm chứng — và cách biết:** ca của `codecraftapi.com` rơi vào nhánh nào (chỉ chặn theo kiểu client, hay chặn theo IP)
**chỉ máy chủ mới trả lời được**; sandbox không có Internet ra ngoài. Sau khi deploy, bấm **Test kết nối** một lần là
biết: nếu câu chẩn đoán chỉ việc bật `LLM_HTTP_HEADERS=browser` thì làm theo (một dòng `.env` + `git up --force` +
Test lại); nếu báo chặn cả hai kiểu thì phải nhờ nhà cung cấp allowlist IP (câu trả lời in kèm IP máy chủ).

**Ảnh hưởng hiện tại với Copilot:** `codecraftapi.com` là **FallBack2** — Copilot vẫn chạy bình thường qua nhà cung
cấp chính; nhà cung cấp này chỉ được gọi khi hai nhà cung cấp trước lỗi, nên không cần tắt vội.

### 14.8 Kết quả chẩn đoán trên VM (người dùng dán lại) — `codecraftapi.com` bị chặn ở tầng IP, không sửa được từ phía ứng dụng

**Người dùng nhận được (nguyên văn, rút gọn):**

> Cloudflare đang chặn MÁY CHỦ NÀY bằng trang challenge “Just a moment…” ở `https://codecraftapi.com/v1/chat/completions` (HTTP 403) — không phải lỗi Base URL hay API key. … **Chẩn đoán: đã thử cả hai kiểu header (ứng dụng và trình duyệt) đều bị chặn ⇒ nhiều khả năng chặn theo IP/dải IP máy chủ** … IP công khai của máy chủ **18.140.199.175** …

**Kết luận: chẩn đoán đã đúng, và đây là giới hạn thật — không có cách sửa nào ở phía mã ứng dụng.**

* Công tắc `LLM_HTTP_HEADERS=browser` **đã được thử tự động** ngay trong lượt test đó (đúng như thiết kế §14.7) và vẫn bị chặn ⇒ không phải chuyện header/UA.
* Máy chủ là `18.140.199.175` — IP **AWS (Singapore)**, thuộc dải datacenter mà Cloudflare/Bot Fight Mode đánh giá rủi ro cao. Vì vậy `Mozilla/5.0…` cũng không qua được.
* **Đã tự kiểm tra DNS (làm được từ sandbox, không cần Internet HTTP):** `codecraftapi.com` và `www.codecraftapi.com` đều phân giải về `104.21.15.95`, `172.67.162.24`, IPv6 `2606:4700:…` — **toàn bộ là IP Cloudflare**; các hostname khác (`api.`, `api2.`, `gateway.`, `gw.`, `v1.`, `llm.`, `openai.`, `relay.`, `direct.`, `origin.`, `edge.`, `proxy.`, `dash.`, `panel.`, `admin.`, `docs.`, `status.`, `cdn.`) **không tồn tại**; các tên miền khác (`codecraftapi.net/.io/.ai/.dev/.vn`) cũng không có bản ghi. ⇒ **Không có hostname thay thế nào để trỏ Base URL sang.**

**Đã bổ sung (đợt này):** câu chẩn đoán Cloudflare nay kèm **một dòng bằng chứng để gửi thẳng cho nhà cung cấp** —
`HTTP 403 · cf-mitigated=challenge · cf-ray=… · server=cloudflare · từ IP máy chủ … · lúc <ISO-8601>`. Bộ phận hỗ trợ
của nhà cung cấp luôn hỏi `cf-ray`; trước đây Admin phải tự đi tìm. `cf-ray`/`cf-mitigated`/`server` được lấy từ chính
phản hồi 403 bị chặn (không phải suy đoán), có test chốt lại.

**Việc cần làm (theo thứ tự thực tế):**

1. **Gửi nhà cung cấp** nội dung: máy chủ `18.140.199.175` (AWS Singapore) bị Cloudflare challenge khi gọi
   `POST /v1/chat/completions` với Bearer token; kèm dòng bằng chứng (cf-ray) trong câu chẩn đoán; đề nghị **allowlist IP**
   hoặc cấp **hostname/endpoint không qua Cloudflare**. Nếu họ dùng Cloudflare Access/Bot Management, họ có thể tạo rule
   cho phép theo IP — đây là việc **chỉ họ làm được**.
2. **Trong lúc chờ:** `codecraftapi.com` là FallBack2 nên **không ảnh hưởng Copilot** — hệ thống vẫn trả lời qua nhà cung cấp
   chính. Muốn sạch log thì tắt `is_active` của bản ghi đó (nút trong màn hình Nhà cung cấp LLM). Chi phí để giữ nguyên cũng
   rất thấp: Cloudflare trả 403 trong ~60 ms và **không tiêu token**, nên mỗi lượt phải chuyển tiếp chỉ chậm thêm ~0,06 giây.
3. **Nếu cần một tầng dự phòng thật:** thêm một nhà cung cấp **khác** chạy được từ máy chủ này (đo bằng chính nút Test kết nối)
   làm FallBack2, thay vì chờ nhà cung cấp cũ sửa.
4. **Không nên** trỏ Base URL qua proxy/relay công cộng để "lách" Cloudflare: khoá API sẽ đi qua bên thứ ba. Chỉ dùng relay
   khi **nhà cung cấp đồng ý** (ví dụ họ cấp endpoint riêng), hoặc relay do chính mình kiểm soát.

**Muốn hết hẳn phụ thuộc một IP:** dài hạn nên thêm tính năng "header bổ sung cho từng nhà cung cấp" (ví dụ service token
`CF-Access-Client-Id/Secret` nếu nhà cung cấp phát) — hiện **chưa làm được** vì cần thêm cột vào bảng `llm_providers` mà dự án
chưa có cơ chế migration cho DB đang chạy (ghi ở §10 mục 2). Đây là việc của một đợt sau, không phải bây giờ.

### 14.9 Hỏi tiếp — "ứng dụng trên Vercel dùng cùng nhà cung cấp thì KHÔNG bị chặn, vì sao?"

Câu này quan trọng vì nó **thu hẹp nguyên nhân**: cùng một nhà cung cấp, cùng API — vậy khác biệt nằm ở
**đường đi của request**, không phải ở tài khoản/khoá.

**Bốn khác biệt có thể có (xếp theo khả năng, kèm cách biết chắc):**

| # | Khác biệt | Vì sao nó làm Vercel qua được | Cách phân biệt |
| :--- | :--- | :--- | :--- |
| 1 | **Vercel gọi từ trình duyệt** (client-side, IP của người dùng) | IP dân dụng không nằm trong danh sách "datacenter" mà Bot Fight Mode chặn; trình duyệt thật **giải được** challenge JS và giữ cookie `cf_clearance` cho các lần sau | DevTools → tab Network của ứng dụng Vercel: nếu thấy request tới `codecraftapi.com` thì là gọi từ trình duyệt; nếu chỉ thấy tên miền của chính app thì là gọi từ server |
| 2 | **Khác dải IP ra Internet** | EC2 của mình là `18.140.199.175` (AWS **Singapore**); Vercel serverless thường ở AWS **us-east-1**/iad1 — cùng nhà cung cấp cloud nhưng khác dải, điểm rủi ro khác nhau | Chạy `curl` (bên dưới) **trên VM**: nếu bị 403 + HTML ⇒ chặn theo IP; chạy cùng lệnh đó ở một nơi khác để đối chiếu |
| 3 | **"Dấu vân tay" client** (TLS JA3/JA4 + HTTP/2) | Cloudflare chấm điểm cả *cách* client bắt tay TLS, không chỉ User-Agent. `httpx` (Python/OpenSSL) là vân tay bị gắn cờ rất phổ biến; SDK Node/undici của Vercel khác hẳn | Cùng phép thử `curl` ở trên: nếu `curl` (vân tay khác Python) **qua được** còn nút Test vẫn bị chặn ⇒ nguyên nhân là vân tay client, sửa được ở phía mã |
| 4 | **Endpoint/cách xác thực khác** | Ví dụ phía Vercel dùng `x-api-key` thay vì `Authorization: Bearer`; nếu nhà cung cấp có rule WAF theo header/path thì kết quả khác nhau | So DevTools/fetch code của ứng dụng Vercel xem gọi URL nào, header nào |

**Phép thử 1 phút, chạy trên máy chủ (không cần API key thật — 401 cũng đã chứng minh Cloudflare cho qua):**

```bash
curl -sS -o /tmp/cf.txt -w 'HTTP %{http_code}\n' -X POST https://codecraftapi.com/v1/chat/completions \
  -H 'Authorization: Bearer test-key' -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}],"max_tokens":1}'
head -c 200 /tmp/cf.txt; echo
```

* `HTTP 401` + JSON ⇒ Cloudflare **cho qua**; nguyên nhân là **dấu vân tay client (#3)** ⇒ sửa được ở phía mã
  (dùng client mang vân tay khác, ví dụ lớp impersonate kiểu trình duyệt) — cần một đợt riêng vì phải thêm phụ thuộc.
* `HTTP 403` + HTML `Just a moment` ⇒ **chặn theo IP (#2)** ⇒ đường sửa nằm ở hạ tầng (allowlist/relay).

**Phương án (chỉ để thảo luận — CHƯA triển khai):** một relay đặt ở hạ tầng không bị Cloudflare chặn
(ví dụ chính hạ tầng Vercel của bạn, nếu nó gọi nhà cung cấp **từ server**) sẽ là đường đi hợp lệ cho máy chủ.
Nguyên tắc nếu làm: ghim cứng host đích (không thành proxy mở), có token chặn lạm dụng, **không lưu khoá API**,
và luôn có đường quay lại Base URL gốc khi nhà cung cấp allowlist IP xong. Đây là **đề xuất**, sẽ chỉ được
triển khai khi có yêu cầu cụ thể.

**Cảnh báo bảo mật (nên kiểm tra ngay):** nếu ứng dụng Vercel đang gọi nhà cung cấp **từ trình duyệt**, khoá API
nằm trong mã phía client ⇒ **bất kỳ ai mở DevTools cũng lấy được khoá**, dùng hết hạn mức của bạn. Việc cần làm:
kiểm tra như ở bảng trên; nếu đúng thì **đổi khoá mới** và chuyển lời gọi về phía server (route/serverless của Vercel).

---

---

## 15. Đợt 13 (2026-10-02) — Sáu việc người dùng nêu trực tiếp: mất hội thoại khi đổi trang, bấm lịch sử không ra, F5 mới hiện, thiếu "Phiên chat mới", ô nhập bị che, nút rảnh tay (Micro)

### 15.1 Người dùng báo gì (nguyên văn, gộp ý)

1. "Khi đang chat với Agent… chuyển qua trang khác như báo giá rồi quay lại trang Trợ Lý, mọi đoạn chat trước biến mất."
2. "Lịch sử có lưu giữ đoạn chat, nhưng nhấn vào không ra."
3. "Nếu nhấn F5 thì đoạn lịch sử cũ mới load ra."
4. "Chưa có chức năng Phiên Chat mới."
5. Chat dài, kéo lên xem tin phía trên thì **ô nhập bị ẩn**: "làm đóng khung Khung chat luôn hiển thị vị trí ở dưới, không bị che khuất."
6. "Bổ sung nút rảnh tay (Micro)… nói và chuyển hóa thành văn bản… Nếu không phức tạp thì có thể triển khai luôn."

Sáu mục này là **yêu cầu cụ thể**, nên đợt này được triển khai (khác với câu hỏi tìm hiểu — xem nguyên tắc ở cuối tài liệu).

### 15.2 Nguyên nhân gốc — tìm được 4 lỗi thật, không chỉ 6 biểu hiện

| # | Biểu hiện | Nguyên nhân gốc trong mã |
|---|---|---|
| 1 | Đổi trang là mất hội thoại | `messages` là `useState` **cục bộ** trong `SalesWorkspacePage`; đổi trang ⇒ component unmount ⇒ mất sạch. Hội thoại chỉ nằm trong RAM. **Thêm một thủ phạm phụ chỉ lộ ra khi vá mục 1:** effect "Morning Briefing" gọi `setMessages([...])` trần trong effect deps rỗng ⇒ mỗi lần quay lại trang là **ghi đè** hội thoại vừa khôi phục bằng đúng 1 tin chào. |
| 2 | Bấm vào mục Lịch sử không ra gì | Hai lỗi cộng lại: (a) effect tải hội thoại bị **deps theo `conversationId`** nhưng nhánh `conversationId === null` vẫn `setMessages(greeting)`; (b) React Query có `staleTime: 15s` ⇒ cuộc vừa tạo/vừa xem nằm trong cache "còn tươi", bấm lại **không refetch** và không có gì để hiển thị. |
| 3 | F5 mới load ra | F5 làm mất cache RAM; lúc đó effect mount lại chạy đúng đường tải ⇒ hiện. Đây chính là mục 1–2 nhìn từ phía khác. |
| 4 | Chưa có Phiên chat mới | Đúng là chưa có. Cách duy nhất để "sang cuộc mới" là xoá cuộc đang mở — vừa mất dữ liệu vừa không rõ ràng. |
| 5 | Ô nhập bị che khi chat dài | `StaffLayout` dùng `flex min-h-screen` cho khung, nhưng `<main>` lại `h-screen`; dưới ngưỡng `lg` có thêm header di động `h-14` ⇒ **tài liệu cao hơn khung nhìn 56px**, ô nhập bị đẩy khỏi vùng thấy được thay vì bị "ghim" trong khung chat. Trong trang chat cũng thiếu chuỗi `min-h-0` nên vùng cuộn không co lại được. |
| 6 | Chưa có Micro | Window Speech Recognition (`vi-VN`) không cần backend, không cần API key ⇒ chi phí bằng 0, đúng điều kiện "nếu không phức tạp". |

### 15.3 Đã sửa

**Lưu hội thoại ra ngoài component (mục 1, 2, 3, 4)** — file mới
`frontend/packages/api-client/src/copilotChatState.ts`:

* Kho trạng thái phiên chat (`sessionStorage`, không phải RAM): `createCopilotChatStore({ storage?, initialConversationId? })`
  với `subscribe/getSnapshot/setConversationId/setItems/hydrate/assignConversationId/forget/cachedItems/reset`.
* Snapshot: `{ conversationId, items, pendingItems }`. Khoá lưu: `copilot.chatSession.v1` (nội dung) + `copilot.activeConversationId` (id đang mở).
* Ca khó đã xử lý — **id về muộn**: người dùng gửi tin đầu khi cuộc chưa có id, rồi chuyển trang trước khi backend trả id. Khi đó nội dung được **giữ tạm** (`pendingItems`); id về muộn được **ghi vào cache dưới id đó**, không "cướp" màn hình đang mở và **không mất nội dung**.
* `hydrate(id, items)` chỉ thay khung chat đang xem nếu `id === conversationId` (bấm mở cuộc cũ ⇒ hiện ngay; cache của cuộc khác thì lấy từ `cachedItems`).
* JSON hỏng ⇒ về phiên trống, không ném lỗi. Giới hạn 60 mục **chỉ áp cho bản lưu tạm** (`sessionStorage`) — khung chat đang xem không bị cắt, phiên dài xem được đủ.
* Hook: `useCopilotChatSession`, `useCopilotChatMessages`, `useCopilotChatConversationId` — thay trực tiếp `useState` cũ nên mọi chỗ đang đọc/ghi `messages` không phải sửa theo.

**Nối vào trang Trợ lý** — `frontend/apps/internal/src/features/sale/SalesWorkspacePage.tsx`:

* `messages`/`conversationId` nay đọc từ kho; effect tải hội thoại đặt khoá `${conversationId}#${reloadNonce}` và **không còn xoá khung chat khi `conversationId === null`**.
* `openConversation(id, { force })` ⇒ bấm lại đúng cuộc đang mở vẫn tải lại (đếm `reloadNonce`), gỡ đúng lỗi "bấm không ra" do cache tươi 15s.
* Xoá cuộc ⇒ gọi `copilotChatStore.forget(id)` (không để cache mồ côi).
* Nhịp ghi lượt đầu `assignConversationId` được đánh dấu vào `loadedConversationRef` — **thẻ/smart-card chỉ có ở client** không bị mất khi lượt chat được lưu lần đầu.
* Thêm `startNewChatSession()` + nút **"Phiên chat mới"** nằm cạnh nút "Lịch sử" (bấm khi đang trả lời thì từ chối và báo lý do, tránh mất phần đang stream). Nút luôn hiện, không phải chờ có cuộc cũ.
* Effect "Morning Briefing" nay chỉ chào khi **khung chat còn trống** (`setMessages(prev => prev.length > 0 ? prev : [greeting])`) — nếu không thì việc khôi phục hội thoại ở mục 1 sẽ bị chính nó ghi đè lại.

**Ghim ô nhập trong khung chat (mục 5)** — `frontend/apps/internal/src/components/layout/StaffLayout.tsx`:

* Khung gốc: `isWorkspace ? 'h-dvh overflow-hidden' : 'min-h-screen'` (chỉ trang workspace mới ghim theo chiều cao khung nhìn; các trang khác giữ nguyên hành vi cũ).
* `aside h-dvh`, `header shrink-0`, `main min-h-0 flex-1 overflow-hidden p-0` — phá đúng chuỗi `min-h-0` làm vùng cuộn không co được.
* Trong trang chat: `<section>` và vùng cuộn thêm `min-h-0`; thanh soạn tin `sticky bottom-0 z-10` ⇒ **luôn nằm dưới cùng khung chat**, không bị đẩy khỏi màn hình khi lịch sử dài.

**Nút rảnh tay — Micro (mục 6)** — `frontend/packages/ui/src/lib/speech.ts` (nối tiếp phần TTS đợt 6):

* `getSpeechRecognitionCtor()`, `isSpeechToTextSupported()`, `SPEECH_TO_TEXT_UNSUPPORTED_MESSAGE`;
* `createSpeechToText({ lang='vi-VN', continuous=true, interimResults=true, onPartial, onFinal, onStateChange, onError })` → `{ supported, start, stop, isListening }`.
* **Rảnh tay thật**: `continuous` + tự khởi động lại sau 250 ms khi trình duyệt tự `onend`, cho tới khi người dùng bấm dừng ⇒ nói một mạch không phải bấm lại từng câu.
* Chữ tạm hiện ngay trong ô nhập để Sale thấy máy nghe đúng; câu chốt được nối vào nội dung đang có, **không ghi đè** chữ đã gõ.
* Lỗi được dịch sang tiếng Việt thay vì im lặng: `not-allowed`/`service-not-allowed` (chưa cấp quyền micro), `audio-capture` (không thấy micro), `network`; `no-speech`/`aborted` thì bỏ qua (không làm phiền). Trình duyệt không hỗ trợ (Safari/Firefox) ⇒ nút báo rõ thay vì bấm không có gì xảy ra.
* Nút micro nằm trong thanh soạn tin: `aria-pressed`, đổi `Mic`/`MicOff`, nhấp nháy khi đang nghe, **bị khoá trong lúc Agent đang trả lời** để tránh trộn chữ vào câu trả lời.

### 15.4 Kiểm chứng (chạy thật trong sandbox)

* Bộ test mới cho hai thư viện (`vitest`, môi trường `node`):
  * `frontend/packages/api-client/src/copilotChatState.test.ts` — **10 ca**: sống qua unmount/remount, F5 (dựng lại từ sessionStorage), bấm lịch sử có cache, không ghi đè cuộc khác, phiên mới rỗng, id về muộn (giữ `pendingItems`), khoá id đang mở, JSON hỏng, phát tín hiệu cho listener.
  * `frontend/packages/ui/src/lib/speech.test.ts` — **6 ca**: trình duyệt không hỗ trợ, tự khởi động lại, `stop()` chặn khởi động lại, `not-allowed` ra tiếng Việt, tách chữ tạm/chữ chốt, `no-speech` im lặng.
* `cd frontend && npm test` ⇒ **api-client 10/10 · ui 6/6 · mock-server 39/39** (55 ca, 6 file).
* `npx tsc -b apps/internal` ⇒ 0 lỗi. `npm run lint` ⇒ **126 cảnh báo, 0 lỗi** (giảm 1 so với trước do `StaffLayout` hết cảnh báo `location` toàn cục).
* Backend: `556 passed` (không đổi — đợt này không đụng backend), `ruff check src/ tests/` sạch.
* `npm run build -w @pricepolicy/internal` chạy thật: bundle chứa `Phiên chat mới`, `Đang nghe`, `whitespace-pre-line`; CSS có `h-dvh` ⇒ xác nhận phần ghim ô nhập vào tới bản dựng, không chỉ ở mã nguồn.

### 15.5 Trên VM cần xác nhận (không có trình duyệt trong sandbox)

Kịch bản bấm tay, nên chạy sau khi deploy (Ctrl+Shift+R để bỏ bundle cũ):

1. Chat 2–3 lượt → sang *Báo giá* → quay lại *Trợ lý* ⇒ **hội thoại còn nguyên** (điểm 1).
2. Mở *Lịch sử* → bấm một cuộc cũ ⇒ **hiện ngay**, không cần F5 (điểm 2). Bấm lại chính cuộc đang mở ⇒ vẫn tải lại.
3. F5 ⇒ cuộc đang mở vẫn đó (điểm 3).
4. Bấm **Phiên chat mới** ⇒ khung chat trống, cuộc cũ vẫn nằm trong Lịch sử (điểm 4).
5. Chat dài (hoặc thu nhỏ cửa sổ) → cuộn lên đầu ⇒ **ô nhập vẫn nằm dưới cùng khung chat**, không bị che; header/nút không nhảy (điểm 5).
6. Bấm Micro (Chrome/Edge, trang HTTPS) → lần đầu hiện xin quyền micro → nói "Khách hỏi phí công chứng hợp đồng thuê nhà" ⇒ chữ hiện dần trong ô nhập, nói tiếp không phải bấm lại; bấm lần nữa để dừng (điểm 6). Từ chối quyền ⇒ phải thấy thông báo tiếng Việt, không im lặng.

### 15.6 Micro — nói thẳng về chi phí và giới hạn

* **Không tốn tiền, không cần backend, không cần API key**: dùng bộ nhận dạng có sẵn của trình duyệt. Vì vậy đợt này triển khai luôn theo đúng điều kiện người dùng nêu.
* **Đánh đổi đã biết, ghi rõ trong mã**: trên Chrome/Edge, đoạn ghi âm được gửi tới dịch vụ nhận dạng của Google để chuyển thành chữ (không phải xử lý tại máy). Nếu phòng pháp chế không cho phép dữ liệu khách hàng rời máy, cần phương án khác — **không phải việc đợt này**.
* **Chỉ chạy trên Chrome/Edge (và một phần Safari); Firefox không có** ⇒ nút báo "trình duyệt chưa hỗ trợ" và vẫn gõ tay bình thường.
* Bản này **chỉ một chiều: nói → chữ**. Chiều ngược lại (Agent đọc câu trả lời) đã có ở đợt 6 (TTS, có đường tự đọc khi được bật).
* Muốn chất lượng cao hơn nữa (thuật ngữ bảo hiểm, tên riêng, tự sửa câu) thì cần dịch vụ STT trả phí phía server — để **thảo luận**, chưa triển khai.

---

## 16. Đợt 14 (2026-10-02) — Tối ưu câu trả lời Agent: độ rõ ràng, văn phong, mỏ neo `[n]`, ghi chú nội bộ, cổng chất lượng

### 16.1 Người dùng yêu cầu gì

Đưa ví dụ thật để so sánh **câu trả lời hiện tại** (3 dòng "Lưu ý" xếp chồng) với **câu trả lời mong muốn**
(mỏ neo `[1]…[5]`, câu hỏi làm rõ đánh số, ghi chú kiểm duyệt gọn). Chốt phạm vi: *"tôi muốn nói về độ rõ
ràng và văn phong hợp lý khi trả lời, làm P0 đi"*, sau đó chốt toàn bộ thiết kế P1/P2/P3 và yêu cầu triển khai.

Phân tích đầy đủ (số liệu đo thật, trước/sau): `docs/team_report/agent_answer_optimization.md`.

### 16.2 P0 — dọn nhiễu & sửa văn phong (commit `2dd544f`)

| # | Sửa gì | Vì sao |
|---|---|---|
| 1 | `grounded` = có citation **hoặc** tool tra cứu chính sách/giỏ hàng chạy thành công | Câu "0 căn khớp" là **dữ liệu**, không phải "chưa đối chiếu" — trước đây bị dán nhãn sai |
| 2 | Verifier tha **số Sale tự nêu** trong câu hỏi (`echoed_claims`) | "2 tỷ" do Sale nhập, câu trả lời nhắc lại không phải bịa |
| 3 | Verifier tha **số/mã trong bối cảnh canonical** (`context_claims`) | "2,5 → 6,1 tỷ" là dải giá thật của giỏ, chỉ đến từ bối cảnh thay vì Observation |
| 4 | Critic chỉ nhắc "gắn mỏ neo" khi **có** citation để trỏ tới | Lượt lọc rỗng không có nguồn nào ⇒ lời nhắc không hành động được |
| 5 | Gộp mọi cảnh báo vào **một** trường; thêm luật văn phong cho LLM | Hết 3 dòng xếp chồng làm câu trả lời trông hỏng |

Đo trên đúng ví dụ: **3 dòng cảnh báo → 0**; `grounded` False→True; `verified` False→True; `critique.ok` False→True.

### 16.3 P1 — nội dung & nghiệp vụ (theo chốt của người dùng)

| Mã | Chốt | Cách làm |
|---|---|---|
| P1.1 | Lọc rỗng ⇒ gợi ý bước 1 (bỏ trần giá, **giữ số phòng ngủ**) + câu hỏi điều hướng; **không tự hạ phòng ngủ** | `inventory_funnel.render_empty_funnel()` trả phễu đầy đủ vào Observation: khoảng giá phân khúc, căn mềm nhất, chênh lệch, **hai hướng đi tiếp** |
| P1.2 | **Không** tính chi tiết ngay, chỉ đưa mốc tổng quan | Tool mới `danh_gia_von_tu_co`: tỷ lệ vốn tự có / giá trị HĐMB, mức tối thiểu theo phương án vay, thiếu/thừa bao nhiêu. KHÔNG trả bảng dòng tiền |
| P1.3 | Báo căn **mềm nhất** + mức thiếu hụt, không dội căn đắt nhất | `softest_unit_line()` — nêu mã căn, diện tích, dự án, giá, chênh so với ngân sách |
| P1.4 | Mặc định hiểu là **tổng giá**, luôn hỏi lại giả định vốn tự có | Luật trong prompt + `INTENT_ASSESS_FUNDS` cho câu hỏi về vốn tự có |
| P1.5 | **Mọi danh sách căn đều là bảng** (kể cả 1 căn), đúng 4 cột: Mã căn · Phòng ngủ · Diện tích · Giá niêm yết (trước thuế) | `inventory_funnel.units_table()` là đường duy nhất; `render_matches()` luôn trả bảng, không còn nhánh liệt kê dòng; `FormattedAiMessage` render bảng markdown động |
| P1.6 | Mốc thời gian dạng **watermark**, không đưa vào văn phong | `data_as_of` trong Observation → `final.payload.data_as_of` → UI hiển thị "Dữ liệu cập nhật: DD/MM/YYYY HH:mm" |
| P1.7 | Ưu tiên **Rõ ràng → Ngắn gọn → Đầy đủ**; phần chính 4–6 câu | Luật prompt (đổi thứ tự so với đề xuất ban đầu của tôi) |

**Điều chỉnh sau khi xem bản chạy (cùng ngày):** chốt P1.5 đổi từ *"<3 căn liệt kê dòng, ≥3 căn mới dùng bảng"* thành **"cứ có căn cần liệt kê là trình bày dạng bảng"**, và tên cột lấy đúng 4 cột người dùng chốt (*Mã căn · Phòng ngủ · Diện tích · Giá niêm yết (trước thuế)*) — bỏ cột Dự án để bảng không bị tràn ngang.

### 16.4 P2 — mỏ neo `[n]` & hiển thị

| Mã | Chốt | Cách làm |
|---|---|---|
| P2.1 | `[n]` **bấm mở được** nguồn (Trust Engine) | `anchors[]` trong payload → `FormattedAiMessage` render `[n]` thành chip bấm → mở modal căn cứ |
| P2.2 | **Không** gắn `[n]` cho số của Sale | Số có trong câu hỏi được in đậm + nhãn "(ngân sách anh/chị nhập)"; cùng một số chỉ gắn nhãn một lần |
| P2.3 | **Máy** tự chèn ở hậu xử lý, LLM không tự viết | Module mới `src/agents/copilot/anchors.py`: quét số → đối chiếu citation theo **giá trị số học** → chèn `[n]`; gỡ mỏ neo LLM tự gõ rồi đánh lại |
| P2.4 | Tách trường `internal_notes` khỏi nội dung | `reply` sạch (copy gửi khách nguyên văn); `internal_notes` + `anchors` + `data_as_of` lưu **cùng lượt** trong lịch sử |

### 16.5 P3 — kiểm soát chất lượng

| Mã | Chốt | Cách làm |
|---|---|---|
| P3.1 | Prompt giữ **metadata** giỏ hàng + nhãn cảnh báo + ép gọi tool khi cần số cụ thể | Bối cảnh ghi rõ "metadata của TOÀN GIỎ" và "MỌI con số chi tiết BẮT BUỘC từ kết quả tool" |
| P3.2 | **Cổng CI**: lọc 3PN thì mọi căn trả về phải là 3PN (lỗi cấm) | `segment_check` sinh ngay trong tool; `run_copilot_eval.py` in cổng và **exit 1** nếu vi phạm, bất kể `--fail-under` |
| P3.3 | Hallucination = 0%; không còn ghi chú rỗng/lạc hậu; thêm 2 kịch bản vàng | Thêm `expect_no_internal_notes`, chặn CI khi `hallucination_rate > 0`; thêm `EMPTY-01` (lọc rỗng) và `FUND-01` (tổng giá → đòn bẩy vốn tự có) → bộ vàng **34 câu** |

**K4 (nút hành động nhanh)** — `_default_suggestions` nay sinh chip theo ngữ cảnh, mang theo dữ liệu để
bấm là chạy ngay: *"Xem bảng tính vay chi tiết cho căn 3 ngủ (ngân sách 2 tỷ)"*, *"Gửi danh sách căn 3 ngủ
đang mở bán"*, *"Mở rộng sang căn 2PN+1 (ngân sách 2 tỷ)"*. Đã bổ sung từ khoá nhận diện để câu từ chip
được hiểu đúng (kèm chốt bảo vệ: câu có "dòng tiền / bảng tính vay / báo giá" vẫn đi đường tính chi tiết).

### 16.5b Bổ sung cùng ngày — hình thức câu trả lời & chống lộ tên nội bộ

Người dùng dán **câu trả lời thật** (chế độ LLM) và nêu hai lỗi: (1) hình thức chưa hợp lý — bảng bị
viết dính vào câu văn nên không xuống hàng, không thành cột, lại còn emoji mũi tên và `**đậm**` mở
nửa câu; (2) **`gia_toi_da_vnd = 0` lọt vào văn bản** — Sale không được thấy chuyện kỹ thuật, khách
càng không.

| Mã | Việc | Cách làm |
|---|---|---|
| P1.5b | Bảng phải nằm riêng dòng, mỗi hàng một dòng, có dòng trống trước/sau | Module mới `src/agents/copilot/reply_format.py::normalize_markdown()`: dò hàng phân cách để biết **số cột**, rồi cắt dòng theo đúng số cột — tách được cả bảng viết dính một dòng, kể cả trường hợp tiêu đề dính còn hàng phân cách ở dòng dưới. Áp ở cuối `_finalize`, sau khi chèn mỏ neo. Hàm **idempotent** |
| P1.5b | Bỏ emoji mũi tên, đậm rác, canh lại cột | Mũi tên đầu dòng → gạch đầu dòng; `** **` → khoảng trắng (không để hai chữ dính nhau); `**` trong ô bảng bị bỏ (bảng đã có kẻ ô); đậm lẻ (mở nửa câu) → bỏ hết `**` trên dòng đó thay vì để dấu sao rác hiện ra |
| P1.5b | Canh cột ở phía hiển thị | `frontend/packages/ui/src/lib/markdownTables.ts` + `FormattedAiMessage`: ô số (tiền, %, m²) **canh phải**, `tabular-nums`, không ngắt dòng giá; ô chữ canh trên. Lớp này còn **tách bảng dính cho dữ liệu cũ đã lưu** — câu trả lời cũ trong lịch sử cũng hiển thị đúng |
| P2.5 | Tên tool/tham số nội bộ không được xuất hiện | `reply_format.py::strip_internal_names()`: bỏ ngoặc chỉ chứa tham số (`(gia_toi_da_vnd = 0, …)`), bỏ `ten_tham_so = giá_trị`, đổi tên tool thành cách nói nghiệp vụ (`tinh_phuong_an_thanh_toan` → "phương án thanh toán chi tiết"), dọn mọi `snake_case` còn sót + giới từ lơ lửng. Có **ghi log** danh sách đã dọn để biết model rò rỉ gì mà chỉnh prompt, không im lặng che đi |
| — | Giảm từ gốc | `prompts.py` thêm luật hình thức (bảng trên dòng riêng, mỗi ý một dòng, không emoji mũi tên, `**` đúng cặp) và luật **cấm nhắc tên tool/trường nội bộ**, kể cả kể lể tham số đã truyền |

**Kiểm chứng đúng ví dụ người dùng gửi:** câu trả lời hỏng được đưa nguyên văn vào test
(`tests/test_agents/copilot/test_copilot_reply_format.py`, 14 ca) — sau khi qua lớp chuẩn hoá, bảng ra
đúng 5 dòng 4 cột, không còn dòng nào vừa chữ vừa ô bảng, `➡️` thành gạch đầu dòng, `gia_toi_da_vnd`
biến mất; test khẳng định thêm hàm **idempotent** (áp lại không đổi — dùng được cho dữ liệu cũ) và bảng
đã đúng định dạng thì **không bị sửa**. Một ca tích hợp chạy qua `_finalize` thật để chắc hai lớp này
nằm đúng chỗ trong đường đi của câu trả lời.

### 16.5c Bộ kịch bản Sale hỏi Copilot (deliverable theo yêu cầu người dùng)

Người dùng yêu cầu: *"Generate cho tôi bộ câu hỏi kịch bản thông dụng để sale hỏi copilot nhằm test luồng
hoạt động của Copilot tuân theo khả năng và thiết kế ban đầu hợp lệ, cũng để test nội dung trả ra có ổn
không."*

| Hạng mục | Nội dung |
|---|---|
| `eval/copilot/sale_scenarios.json` | **57 kịch bản / 12 nhóm việc của Sale**: tra cứu giỏ hàng, lọc rỗng & điều hướng, vốn tự có, phương án thanh toán & báo giá, chính sách (kèm hiệu lực theo ngày), soạn tin, kiểm F8, hồ sơ khách, nhiều ý một lượt, ngữ cảnh hội thoại, an toàn & không bịa, xã giao. Phủ đủ 7 tool. Mỗi câu có kỳ vọng máy kiểm được + ghi chú "kiểm điều gì" |
| Bộ chấm mở rộng | `run_copilot_eval.py` nay chấm thêm `must_not_contain`, `expect_table` (P1.5), `max_questions` (P1.7), và **vệ sinh hình thức** áp cho MỌI câu: không lộ `snake_case` nội bộ (P2.5), bảng không dính câu văn (P1.5b), không emoji mũi tên |
| Cổng mới | Cổng **nội dung/hình thức** chặn CI mặc định (vi phạm là exit 1); cờ `--strict` siết thêm `must_contain`; cờ `--questions` chạy bộ khác bộ vàng |
| Hai trạng thái mới | `known_gap` (lỗ hổng đã biết: vẫn chạy, vẫn báo cáo, không tính vào mẫu số) và `offline: skip` (câu cần LLM: bỏ qua khi chạy offline và **được liệt kê riêng** để không ai tưởng đã kiểm) |
| Cổng tự động trong CI | 4 test mới trong `tests/test_agents/copilot/test_copilot_eval.py`: phủ đủ nhóm/tool, chạy đạt cổng, báo cáo lỗ hổng + câu chỉ-LLM, và kiểm chính bộ chấm |
| Tài liệu cho Sale/QA | `docs/team_report/copilot_sale_scenarios.md`: cách chạy (offline · LLM trên VM · kiểm bằng mắt), bảng kịch bản theo nhóm, **phiếu chấm 6 điểm** cho người đọc, kết quả chạy thật, và danh sách việc cần xử lý |
| Báo cáo | `eval/results/sale_scenarios_report.json` |

**Kết quả chạy thật (offline):** 42/57 câu tính điểm (8 lỗ hổng đã biết, 7 câu chỉ-LLM) — gọi đúng tool
**100%**, citation **100%**, bịa **0.0%**, cổng phân khúc **ĐẠT**, cổng nội dung/hình thức **ĐẠT**.

**Lỗi thật phát hiện được nhờ bộ kịch bản này** (chi tiết + đề xuất ở §5 tài liệu kèm):

1. **[Nghiêm trọng]** Bộ chặn rò rỉ đầu ra nuốt mất kết luận kiểm F8 khi chính câu đang kiểm tra là phát
   ngôn bị cấm ("cam kết sinh lời 20%") — Sale không nhận được kết luận ở đúng ca quan trọng nhất. Bộ vàng
   chỉ kiểm "có gọi tool" nên lỗi lọt qua dưới dạng `missing_terms`.
2. **[Cao]** Thân bản nháp gửi khách trộn nhãn nội bộ (`Bản nháp (SUPPORTED)`, `F8: ALLOW_SEND`) ⇒ "Copy cho
   khách" mang mã kiểm duyệt tới khách — vi phạm chốt P2.4/K2.
3. **[Trung bình]** `POL-04` trong bộ vàng kỳ vọng phiên bản chính sách `V2.0` không tồn tại trong dữ liệu
   canonical ⇒ kỳ vọng không thể đạt, và `must_contain` hiện chưa nằm trong cổng CI (cờ `--strict` đã sẵn).
4. **[Thấp]** Lớp tất định chỉ hiểu 50/57 câu (7 câu cần LLM: bóc tên dự án, hỏi theo mã căn, thời hạn ưu
   đãi, đại từ "căn này"); chip "mở rộng phân khúc" giữ nguyên trần giá cũ nên lại ra kết quả rỗng.

### 16.5d Sửa hai lỗi nặng nhất do bộ kịch bản phát hiện + phân tích lỗi time-travel

**Lỗi 1 — kết luận kiểm duyệt F8 bị bộ chặn rò rỉ nuốt mất.** Kết luận buộc phải trích lại câu bị chặn
("cam kết sinh lời 20%"), mà luật cấm `ILLEGAL_COMMITMENT_VI` khớp chính phần trích dẫn ⇒ toàn bộ câu trả
lời bị thay bằng câu từ chối chung ⇒ **đúng ca quan trọng nhất, Sale không nhận được cảnh báo**.

*Cách sửa* (`reply_format.mask_review_text` + `graph._finalize`), tách đúng hai loại văn bản:
- `engine_texts` — câu chữ **do engine kiểm duyệt viết** (kết luận, lý do, mã luật): miễn theo kiểu trùng
  nguyên văn (≥ 12 ký tự). Engine viết thì hiển thị nguyên văn là đúng, và model không thể lợi dụng vì câu
  nó tự viết không trùng nguyên văn.
- `reviewed_texts` — **nội dung đang bị kiểm** (câu Sale nhờ kiểm, câu bị gắn cờ): **chỉ** miễn khi nằm
  trong ngoặc kép và khớp đúng văn bản đó (tức là đang được trích dẫn để chỉ chỗ sai).
- Test khoá **cả hai chiều**: cam kết trái luật do model tự viết (kể cả bọc ngoặc kép) và rò rỉ API key
  vẫn bị chặn như cũ; biến thể khó hơn (lời giải thích của engine cũng chứa cụm bị cấm) cũng không làm mất
  kết luận. Kèm theo: F8 khai báo `grounded: true` (đầu ra tất định) nên không còn ghi chú "chưa đối chiếu"
  gây nhiễu — nằm trong nhóm sửa của lỗi này.

**Lỗi 2 — bản nháp gửi khách trộn nhãn kiểm duyệt nội bộ** (`Bản nháp (SUPPORTED)`, `F8: ALLOW_SEND`) ⇒
bấm "Copy cho khách" là khách nhận luôn mã nội bộ, vi phạm chốt P2.4/K2.

*Cách sửa*: `soan_tin_tu_van` trả `summary` = **thân tin** (văn bản gửi khách) và `internal_notes` =
kết luận kiểm duyệt dạng **tiếng Việt**; `_finalize` gom `internal_notes` do tool khai báo vào banner nội
bộ. Bộ chấm có thêm tiêu chí `notes_contain` để kiểm **cả hai chiều**: thân tin CẤM chứa mã nội bộ, banner
nội bộ BẮT BUỘC có kết luận kiểm duyệt. Thêm `planner._compose_topic` bóc chủ đề Sale yêu cầu ("về chiết
khấu thanh toán sớm") để bản nháp nói đúng việc, và không nhét câu mệnh lệnh vào tin gửi khách.

**Kết quả:** hai câu chuyển từ nhãn "lỗ hổng đã biết" sang **tiêu chí kiểm thật** và đang ĐẠT; bộ kịch
bản còn 5 câu ghi nhận lỗ hổng (AT-03, AT-04, AT-05, CS-07, CS-08, RONG-04). `pytest` **633 passed**.

**Lỗi time-travel chính sách — phân tích để chốt (chưa sửa).** Ba vấn đề tách biệt:

| | Vấn đề | Bằng chứng |
|---|---|---|
| a | **Dữ liệu thiếu**: chỉ có `CSBH-ZEN-2026-V3.1` (01/08→31/12/2026) và `CSBH-SAPPHIRE-2026-V1.0` (01/01→31/12/2026). Ngày 15/07/2026 **không bản nào** của The Zen Park hiệu lực ⇒ kỳ vọng `V2.0` của `POL-04` không thể đạt | bảng `POLICIES_DATA` |
| b | **Code rơi về ứng viên đầu tiên**: `resolve_active_policy` khi không có bản nào phủ ngày vẫn trả về chính sách đầu tiên của dự án, câu trả lời vẫn ghi "đang hiệu lực tại <ngày>" | chạy thật CS-08: tiêu đề "(VLandFuture Sapphire)" nhưng nội dung trích `CSBH-ZEN-2026-V3.1` |
| c | **Tên dự án không được truyền xuống tool**: `_args_for(LOOKUP_POLICY)` chỉ truyền câu hỏi + ngày ⇒ tool trộn hai dự án | `planner._args_for` |

**Bàn giao:** người dùng chuyển việc #3 cho Gemini (2026-10-02) — bản giao chi tiết ở
`docs/team_report/handoff_policy_timetravel.md` (ba nguyên nhân kèm vị trí code, hành vi đúng, tiêu chí
nghiệm thu, cách kiểm chứng, ràng buộc kỹ thuật). Kịch bản `CS-08` mới được thêm để Gemini có ca
kiểm chạy được ngay cả ở chế độ offline.

Hệ quả nghiệp vụ: **Sale có thể trích sai văn bản chính sách cho giao dịch tháng 7**. Ba lựa chọn A (chỉ
sửa kỳ vọng), B (sửa code cho trung thực + bóc tên dự án — đề xuất làm trước), C (B + thêm dữ liệu lịch sử
`CSBH-ZEN-2026-V2.0` để demo đúng năng lực time-travel) được trình bày kèm đánh giá được/mất trong
`docs/team_report/copilot_sale_scenarios.md` §5.2, chờ người dùng chốt.

### 16.6 Bằng chứng chạy thật (sandbox)

- `pytest -q` → **633 passed** (572 → 633; thêm 5 file test: `test_copilot_anchors.py` 12 ca,
  `test_copilot_inventory_funnel.py` 15 ca, `test_copilot_reply_format.py` 14 ca,
  `test_copilot_f8_and_draft.py` 13 ca, +2 ca trong `test_copilot_answer_clarity.py`).
- `ruff check src/ tests/ scripts/` → sạch. `npm run lint` → **126 cảnh báo, 0 lỗi**.
- Frontend: `npm test` → api-client **14**, ui **12**, mock-server **39** (65 tổng); `tsc -b apps/internal` 0 lỗi;
  build nội bộ OK.
- `scripts/run_copilot_eval.py` (34 câu vàng): tool **100%** · citation **100%** · **bịa 0.0%** ·
  **cổng phân khúc ĐẠT**.
- Bộ kịch bản Sale (58 câu, 7 câu chỉ chạy ở chế độ LLM): 46/51 câu tính điểm — tool **100%** ·
  citation **100%** · bịa **0.0%** · cổng phân khúc **ĐẠT** · cổng nội dung/hình thức **ĐẠT**.
- Ví dụ chạy thật: câu "2 tỷ là vốn tự có thì có mua được căn 3 ngủ không?" → 3 mỏ neo
  (`31.8%`, `2.171.600.000 ₫`, `6.832.000.000 ₫`), nhãn ngân sách đúng, **không** còn ghi chú nội bộ.

### 16.7 Số liệu quan trọng (đo từ dữ liệu canonical, không suy đoán)

Giỏ đang mở bán có **4 căn**: ZEN-A-0803 (1PN, 2,5 tỷ) · ZEN-A-1205 (2PN, 4,2 tỷ) · SAP-01-2204 (2PN, 5,8 tỷ)
· ZEN-B-1502 (3PN, 6,1 tỷ). Phân khúc 3PN: **1 căn**; lọc 3PN ≤ 2 tỷ: **0 căn**.

Với **2 tỷ vốn tự có** cho ZEN-B-1502 (HĐMB 6,832 tỷ): tỷ lệ **29,3%**, mức tối thiểu theo phương án vay
**31,8% ≈ 2,1716 tỷ** ⇒ **thiếu 171,6 triệu**. Lưu ý: bản "câu trả lời mong muốn" trong ví dụ của người dùng
viết *"hoàn toàn khả thi"*, nhưng số liệu engine cho thấy **còn thiếu 171,6 triệu** — báo đúng số thiếu có
giá trị tư vấn cao hơn một câu khẳng định chung.

### 16.8 Còn lại (nói thẳng)

1. **Phần văn phong do LLM viết chưa đo được trong sandbox** (không có API key/egress): luật prompt P0.5/P1.7/K2
   mới chỉ kiểm được ở chế độ offline (ghép Observation). Cần một vòng chạy `--mode llm` hoặc bấm tay trên VM.
2. **UI chưa kiểm bằng trình duyệt** (sandbox không có Chromium): mỏ neo bấm được, nút "Copy cho khách",
   watermark thời gian, chip hành động — mới xác nhận ở mức mã nguồn + typecheck + build.
3. **Một số con số chưa có mỏ neo** dù đã có nguồn: mỏ neo trỏ tới **citation**; con số chỉ nằm trong
   Observation (không nằm trong citation) sẽ không được gắn `[n]` dù verifier coi là hợp lệ. Muốn phủ 100%
   thì cần sinh thêm citation cho từng dòng số liệu — nên làm cùng lúc với việc mở rộng `anchors`.
4. **Ghi chú nội bộ giờ sống cùng hội thoại** (đã lưu `internal_notes` trong bản ghi lượt), nhưng **mock server
   và backend đều đã đổi hợp đồng** — nếu VM còn chạy bundle cũ thì nên deploy cùng lượt để tránh lệch.
## 10. Còn lại (nói thẳng, không hứa quá)

1. **Học từ phản hồi mới ở mức "log + few-shot + màn hình theo dõi"**, chưa fine-tune/weight-tuning.
   Trang `/admin/copilot-quality` đã trả lời được "chất lượng đang lên hay xuống, kém ở đâu".
   Còn thiếu: **phân loại tag tự động** (hiện Sale gửi tag thô) và **tiêu chí gỡ** một "điều cần tránh"
   khỏi prompt khi nó đã được sửa — cả hai cần thêm dữ liệu thật mới đáng làm.
2. **Critic chưa gọi LLM sửa lời**: hiện critic *phát hiện + nhắc*, không tự viết lại. Đã có cờ `COPILOT_CRITIC=1` để bật một lượt sửa, nhưng **cố ý để mặc định TẮT** vì nhân đôi độ trễ. Từ đợt 5 đã có tab **Chi phí & hiệu năng** (§8.3) để đo cái giá đó trước khi bật — việc còn lại là chạy thử vài ngày rồi quyết định.
3. **Trôi hợp đồng mock vs backend (TD-4.1)** mới xử lý ở tầng type (`QuoteCreateOutcome`) và ở lớp benchmark/cổng ban hành (§6.2 — nay hai bên trả cùng shape); triệt để thì mock-server nên đổi sang **201 đồng bộ** cho khớp backend thật, và `POST /policies/publish` của backend thật nên trả `PolicyDocument` như type frontend đang khai.
4. **Audio TTS đang do trình duyệt tổng hợp**: nghe được ngay nhưng giọng tuỳ máy và không đo được chi phí.
   Bước kế tiếp là `POST /api/v1/tts/speak` + cache + ghi chi phí vào `llm_usage.jsonl` (hợp đồng đã chốt
   trong `tts_integration_plan.md` §7). Trước khi nối cần chốt: ngân sách/tháng, dữ liệu hội thoại có được
   gửi ra nhà cung cấp nước ngoài không, và có cần nhân bản giọng thương hiệu không (§6 tài liệu đó).
   Chưa làm: che PII trước khi đọc (SĐT/email khách) và bản tóm tắt để đọc cho câu trả lời dài.
5. **124 cảnh báo oxlint** còn lại: chủ yếu `no-unused-vars` ở `LeadInboxPage`, `PolicyListPage`… — dọn tiếp là việc cơ học, không rủi ro (đợt 5 không làm phát sinh cảnh báo mới).
6. **Cache tool hiện trong-một-lượt** (theo phiên chat). Cache xuyên lượt/TTL cần thêm khoá theo `transaction_date` + chính sách hiệu lực để không trả dữ liệu cũ — nên làm cùng lúc với dashboard chi phí.
7. **Eval mới chạy offline tất định** (không cần API key). Muốn đo chất lượng LLM thật thì chạy `python scripts/run_copilot_eval.py --mode llm` khi có `OPENAI_API_KEY`; bộ ngưỡng CI hiện bám chế độ offline để phù hợp môi trường không có key.
8. **Script deploy mới chưa chạy trên VM thật** (sandbox không SSH được vào `ip-172-31-4-117`): đã test end-to-end bằng
   repo fixture + pm2/health giả (§11.5). Việc cần làm: chạy 3 lệnh ở §11.6 trên VM, rồi deploy thử một commit nhỏ
   (đổi 1 file backend) để xác nhận log `pip=0 npm-ci=0 build=0` và thời gian ~10–20 giây. Đường nginx chỉ được
   kiểm chứng một phần (sandbox không có nginx/sudo) — nếu VM yêu cầu mật khẩu sudo, script in ra lệnh chạy tay.
9. **Kiểm chứng UI trong trình duyệt thật còn thiếu** (sandbox không có Chromium/Playwright): các thay đổi
   khung lịch sử (§12) mới xác nhận ở mức mã nguồn + bundle + typecheck. Cần một vòng chạy tay trên
   `demoday.work.gd` (Ctrl+Shift+R) để chốt: ẩn mặc định, bấm mới hiện, đổi trang rồi quay lại vẫn còn hội thoại,
   và mở lại được cuộc cũ trong danh sách.
10. **"Test kết nối" với nhà cung cấp LLM thật**: đã sửa đúng nguyên nhân (UA mặc định bị Cloudflare chặn + chỉ thử `/models`)
   và khoá lại bằng test với server giả (§14), nhưng **chưa gọi được nhà cung cấp thật của Admin từ sandbox**. Cần bấm
   Test kết nối trên VM xác nhận: nếu xanh là xong; nếu còn đỏ, câu chẩn đoán mới sẽ nói rõ phải kiểm tra gì.
11. **"Test kết nối" mới kiểm tra từng nhà cung cấp riêng lẻ**, chưa có nút mô phỏng cả chuỗi dự phòng
    (chủ động làm nhà cung cấp chính lỗi để xem có tự chuyển sang nhà cung cấp kế tiếp không). Cơ chế
    chuyển tiếp đã được chứng minh bằng test gọi thật (§14.6), nhưng một nút "Test cả chuỗi" trong màn hình
    quản trị sẽ giúp Admin tự tin trước khi sự cố thật xảy ra — nên làm cùng lúc với việc hiển thị số lần
    phải chuyển tiếp lên tab Chi phí & hiệu năng.

**Nguyên tắc làm việc (người dùng yêu cầu, ghi lại để không lặp lại):** câu hỏi của người dùng để **tìm hiểu vấn đề**
thì phần trả lời dừng ở **thảo luận – phản biện – đề xuất giải pháp**; **không tự triển khai** tính năng/code mới
cho tới khi có yêu cầu cụ thể. Bản relay Vercel viết ở lượt trước đã được **gỡ khỏi repo** theo yêu cầu này; ở đây
chỉ còn phần phân tích nguyên nhân và các phương án để thảo luận.
