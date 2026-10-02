# CHANGELOG — Đợt nâng cấp 2026-10-02

Biên bản đầy đủ của đợt nâng cấp theo `docs/RASOAT_TONGTHE_2026-10-02.md`.
Code nằm ở vị trí chuẩn của repo; file này ghi **đã đổi cái gì, vì sao, và bằng chứng chạy thật**.

Thứ tự thực hiện: **A (Copilot P0)** → **B (eval)** → **C/D (UI P0–P1)** → **E (CI/type)** → **F (tài liệu)** → **P2 còn lại**.

---

## A. Copilot thông minh hơn — `src/agents/copilot/`

| File | Thay đổi | Vì sao |
| :--- | :--- | :--- |
| `planner.py` **(mới)** | `decompose(message, entities)` tách câu nhiều ý thành tối đa 3 bước có thứ tự nghiệp vụ (tra chính sách → tính tiền → soạn tin), `plan_summary()` cho UI | Trước đây câu hai ý bị xử lý tuyến tính trong 4 vòng → bỏ sót ý thứ hai |
| `memory.py` **(mới)** | `resolve_slots()` điền slot thiếu (`current_unit`, `lead_dossier_id`, `transaction_date`) từ lịch sử; `summarize_history()` tóm tắt hội thoại dài; `enrich_entity_with_slots()` | Sale nói thiếu ngữ cảnh → Copilot hỏi lại vô ích |
| `verifier.py` **(mới)** | Đối chiếu mọi con số trong câu trả lời với Observation (`_MONEY_RE`, `_to_float` xử lý định dạng VN `8,0 %` / `4.655.200.000`); trả `verified/unsupported_claims/checked_claims` | Chống ảo giác bằng máy, không chỉ bằng prompt |
| `graph.py` | `stream_copilot()` viết lại: phát `plan` trước vòng lặp; gọi planner/memory/verifier; guardrail short-circuit gắn `mode="guardrail"`; `_execute_tool()` retry 1 lần + backoff, Observation lỗi có `error_code` (không tiêu vốn 4 vòng); `_trim_tool_message()` cắt dài mà vẫn giữ JSON hợp lệ; **cache tool theo lượt** (`_tool_cache_key`, tham số đã chuẩn hoá thứ tự) + **ngân sách ngữ cảnh** (`MAX_TOTAL_OBSERVATION_CHARS`, báo cáo `context_budget`) | P0/P1/P2 §3.3 |
| `tools.py` | `tra_cuu_ho_so_khach_hang` lọc bằng SQL `WHERE`/`LIKE` + `LIMIT 5` thay vì kéo 50 dòng rồi lọc bằng Python | Tool duy nhất chưa scale |
| `intents.py`, `prompts.py`, `grounding.py` | Bổ sung nhánh ý định, prompt nhận `plan`/`history_summary`/ngữ cảnh chủ động, chuẩn hoá không dấu | Nền cho planner + memory |
| `src/agents/tools/guardrails.py` | Thêm mẫu prompt-injection; `scan_output_leakage` dùng trong `_finalize` | Bịt đường rò rỉ dữ liệu ở đầu ra |
| `src/api/endpoints/copilot.py`, `service.py` | DTO thêm `verified`, `verification`, `plan[]`, `slots{}`; luồng gộp + SSE giữ shape cũ | UI không vỡ khi backend thông minh hơn |

## B. Eval — đo được độ thông minh

- `eval/copilot/golden_questions.json`: **32 câu vàng**, 10 nhóm (policy, units, scenarios, compose, compliance, customer, smalltalk, refusal, multi_intent, memory), mỗi câu khai báo `any_tools|required_tools|expect_no_tools|expect_citation|expect_grounded|expect_refusal|must_contain`.
- `scripts/run_copilot_eval.py`: chạy offline (`_offline_llm_factory` — không cần API key), tính tool-selection accuracy / citation precision / hallucination rate / p95, ghi `eval/results/copilot_report.json`.
- `tests/test_agents/copilot/test_copilot_eval.py`: biến chỉ số thành **cổng CI** — tool ≥ 0.9, citation ≥ 0.9, hallucination ≤ 0.05, p95 < 2000 ms, câu từ chối phải dùng 0 tool, bộ câu hỏi ≥ 30 phủ đủ 6 tool/10 nhóm, mọi lượt trả lời `mode ∈ {react, offline_react, guardrail}`.

**Kết quả chạy thật** (`eval/results/copilot_report.json`): tool **1.00** · citation **1.00** · hallucination **0.00** · p95 **4 ms**.

Trong lúc làm eval phát hiện một lỗi thật: lượt bị guardrail chặn trả `mode = None` → đã gắn `mode: "guardrail"` ở `graph.py` và mở rộng union `CopilotMode` trong `contracts/copilot.ts` (2 chỗ) — nếu không, UI sẽ hiển thị lượt bị chặn như lượt lỗi.

## C. UI/UX P0 — `frontend/apps/internal/src/features/sale/SalesWorkspacePage.tsx`

| # | Trước | Sau |
| :-: | :--- | :--- |
| C1 | `handleConfirmQuoteAction` vẽ 4 bước bằng `setInterval` rồi in kết quả bịa ("Đề xuất PA-VAY…") | Gọi API thật: `api.catalog.units()` → `api.quotes.create()`; tiến trình phản ánh đúng vòng đời thật; thiếu mã căn/dự án thì **nói thẳng là thiếu**, không diễn; lỗi thì đánh dấu bước hỏng (`failed`) và báo lỗi thật |
| C2 | `customer_card` render bằng `dangerouslySetInnerHTML` + regex tự chế | `FormattedAiMessage` (React render, không còn đường XSS) — số lần xuất hiện `dangerouslySetInnerHTML` trong file: **0** |
| C3 | Modal căn cứ chỉ có 3 dòng tĩnh | Hiện thêm **Điều/khoản** + **hash tài liệu đầy đủ**, nút **Sao chép căn cứ** (kèm hash để đối soát) |
| C4 | Lỗi mạng → spinner treo | Banner `role="alert"` + nút **Thử lại** chạy lại đúng câu và đúng ngữ cảnh đã lỗi (`failedTurn` + `handleRetryFailedTurn`) |

## D. UI/UX P1

| # | Trước | Sau |
| :-: | :--- | :--- |
| D1 | Danh sách slash command hardcode, không render, không tìm kiếm | `packages/ui/src/components/common/SlashCommandPalette.tsx` + logic thuần `packages/ui/src/lib/slashCommands.ts`: lọc **không dấu** (NFD + `đ→d`, nhiều token AND), nhóm "gần đây" (localStorage `copilot.recentSlash`, tối đa 4), 8 lệnh (thêm `/gio-hang`), điều hướng ↑/↓/Enter/Esc, `role="listbox"`/`option` + `aria-activedescendant` |
| D2 | Không thấy ngữ cảnh gửi lên; luôn gửi `transactionDate: null` | `CopilotContextChips.tsx`: chip **căn / hồ sơ / ngày giao dịch** sửa và xoá được tại chỗ; `copilot.send()` gửi đúng `copilotUnit` + `copilotTxDate` (mặc định `2026-09-26`); căn tự đồng bộ từ ràng buộc hồ sơ đang chọn |
| D3 | `setTimeout(6000)` bịa nudge "Mr. Hùng đang xem Q-00092" | Nudge **từ dữ liệu thật**: báo giá `NEEDS_REVISION`/`REJECTED` → nhắc kèm lý do thật của quản lý; thêm nudge SLA (hồ sơ còn ≤ 10 phút tới hạn), quét mỗi phút, mỗi mốc hạn chỉ nhắc một lần |
| D4 | Nút "Hoàn tác (8s)" chỉ đổi state UI dù hồ sơ đã ở server | Thay bằng **Yêu cầu sửa** gọi thật `api.quotes.requestRevision()` (idempotency key + `ifMatchVersion`); `handleConfirmSubmitAction` cũng gọi thật `api.quotes.submit()` và chỉ hiện receipt khi server xác nhận; không có báo giá đủ điều kiện thì nói thẳng |
| D5 | Bốn tab `hoso/baogia/tinnhan/chinhsach` mỗi nơi một kiểu trạng thái | Dùng thống nhất `QueryState/EmptyState/ErrorState` (đủ 4 trạng thái loading/error/empty/data); tab hồ sơ chưa chọn khách thì có màn hình hướng dẫn thay vì panel trống |

`packages/ui/src/components/common/ReasoningTrace.tsx`: render thêm bước **`plan`** (danh sách bước + tool dự kiến) để kế hoạch của planner hiện lên đúng chỗ.

## E. CI + type

- `.github/workflows/ci.yml`: thêm job `frontend` (Node 22, `npm ci` → `tsc -p packages/tsconfig.json` → `tsc -b apps/internal apps/customer` → `oxlint` → `npm test`).
- `frontend/packages/tsconfig.json` **(mới)**: typecheck chung cho `api-client` · `ui` · `mock-server`.
- Sửa hết **8 lỗi type tồn đọng**:
  - `contracts/models.ts`: thêm `QuoteCreateOutcome` — backend thật trả **201 đồng bộ**, TD-4.1/mock trả **202 + `stream_url`**; client nhận cả hai hình dạng thay vì giả định một cái.
  - `contracts/copilot.ts`: thêm `'plan'` vào `CopilotStepType`, thêm `steps[]` cho event plan.
  - `client.ts`: `quoteCreate` nhận `QuoteCreatePayload | QuoteCreateRequest`, trả `QuoteCreateOutcome`.
  - `mock-server/src/server.ts`: chuyển `Buffer` → `BodyInit` tường minh (không đổi hành vi).
  - `mock-server/src/scenarios.test.ts`: 3 chỗ `stream_url` có thể `null` → khẳng định rõ hợp đồng mock là **phải** có `stream_url` (fail to, không im lặng).

## F. Tài liệu

- `README.md`: badge + số test **477 → 479**; thêm mục **chạy eval Copilot** kèm bảng ngưỡng CI/số thật.
- `docs/team_report/DEMO_RUNBOOK.md`: kỳ vọng "71 passed" (số cũ từ nhiều tháng) → 479.
- `upgrade/`: `README.md` (chỉ mục), `PLAN.md` (kế hoạch A–F), `CHANGELOG.md` (file này).

---

## Kiểm chứng cuối (chạy sau khi hết thay đổi)

| Lệnh | Kết quả |
| :--- | :--- |
| `.venv/bin/python -m pytest tests/ -q` | **479 passed**, 1 warning |
| `.venv/bin/python -m ruff check src/ tests/` | **All checks passed** |
| `scripts/run_copilot_eval.py` | tool 1.00 · citation 1.00 · hallucination 0.00 · p95 4 ms |
| `cd frontend && npx tsc -p packages/tsconfig.json` | **exit 0** (trước đó 8 lỗi) |
| `cd frontend && npx tsc -b apps/internal apps/customer` | **exit 0** |
| `cd frontend && npm test` | **22/22 passed** (2 file) |
| `cd frontend && npx oxlint` | **0 error**, 125 warning (trước: 151) |
| `cd frontend && npm run build` | build thành công (Vite) |
| Smoke logic palette (`filterCommands`) | 6/6 kịch bản gõ không dấu khớp đúng |

## Còn lại / chưa làm (nói thẳng, không hứa quá)

1. **`tinnhan` (soạn tin) chưa có trạng thái loading/error riêng** — tab này dùng state cục bộ (`draftContent`, `complianceResult`) tính tại chỗ nên không có query nào để mà bọc; muốn chuẩn hoá tiếp thì phải tách thành mutation gọi `kiem_tra_phat_ngon_f8` thật thay vì suy diễn trên client.
2. **Critic vòng 2 (§3.3 P2)** chưa làm: hiện `verifier` mới kiểm tra *số liệu có trong Observation không* (kiểm chứng dữ kiện), chưa phải *tự phản biện lập luận*. Muốn làm tử tế cần thêm một lượt LLM nữa → tăng độ trễ gấp đôi, nên để sau khi có dashboard chi phí.
3. **Học từ phản hồi (§3.3 P2)** chưa làm: cần endpoint `POST /copilot/feedback` + nút thumbs trên UI + kho log; chưa đủ dữ liệu để few-shot động có ý nghĩa.
4. **Trôi hợp đồng mock vs backend (TD-4.1)** đã *xử lý được ở tầng type* (`QuoteCreateOutcome`), nhưng logic UI vẫn phải rẽ nhánh theo hình dạng trả về; triệt để thì mock-server nên đổi sang 201 đồng bộ cho khớp backend.
5. **`oxlint` còn 125 warning** — đã giảm từ 151; 129 lượt là `no-unused-vars` rải ở các trang cũ (`LeadInboxPage`, `PolicyListPage`…), dọn tiếp là việc cơ học.
