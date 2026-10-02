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
