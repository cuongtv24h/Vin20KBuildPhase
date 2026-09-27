# KẾ HOẠCH HÀNH ĐỘNG HOÀN THIỆN & TÍCH HỢP TOÀN DIỆN MVP CORE
## DỰ ÁN: PRICEPOLICY AI AGENT (VLANDFUTURE) — BDSVLANDFUTURE-06
### VỊ TRÍ: DEV 2 — FINANCIAL MATH & CORE API ENGINEER (PHỐI HỢP CÙNG TECHLEAD, DEV 1, DEV 3)

- **Người lập kế hoạch:** Chung Văn Duy
- **Mã học viên (MSSV):** 02854
- **Vai trò phụ trách:** Dev 2 — Financial Math & Core API Engineer
- **Ngày lập kế hoạch:** 27/09/2026
- **Nhánh phát triển Git:** [`ChungVanDuy_02854`](https://github.com/AI20K-Build-Phase-Cohort-4/P-096/tree/ChungVanDuy_02854)
- **Tài liệu căn cứ kỹ thuật:**
  - [Báo cáo Thay đổi Kiến trúc v2 (baocaothaydoi.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/v2%2026-09/baocaothaydoi.md)
  - [Bản đồ Codebase Định vị Thực tế (CODEBASE_MAP.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/CODEBASE_MAP.md)
  - [Chỉ mục Codebase & Phân định Sở hữu (CodeBaseIndex.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/CodeBaseIndex.md)
  - [Kế hoạch Thực thi v2 Tổng thể (ImplementPlan.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/v2%2026-09/ImplementPlan.md)
  - [Chi tiết Kế hoạch Triển khai v2 (Implement_plan_detail.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/v2%2026-09/Implement_plan_detail.md)
  - [Đặc tả Kế toán Tài chính FCS v2.6 (0.2.financial-calculation-spec.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/v2%2026-09/0.2.financial-calculation-spec.md)
  - [Hợp đồng Giao diện API, Event & Tool Contracts TD-4.4 (4.4-api-event-tool-contracts.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/v2%2026-09/4.4-api-event-tool-contracts.md)
  - [Kế hoạch WBS Đã Nghiệm thu (2026-09-23_DEV2_FINANCIAL_MATH_WBS_PLAN.md)](file:///c:/Documents/Vin_Build_Phase/P-096/reports/plan/2026-09-23_DEV2_FINANCIAL_MATH_WBS_PLAN.md)
  - [Bản Tổng Hợp & Bàn Giao Kỹ Thuật (2026-09-25_DEV2_FINAL_WORK_SUMMARY_AND_HANDOVER.md)](file:///c:/Documents/Vin_Build_Phase/P-096/reports/plan/2026-09-25_DEV2_FINAL_WORK_SUMMARY_AND_HANDOVER.md)
  - [Báo Cáo Tiến Độ Chi Tiết Học Viên (ChungVanDuy_02854.md)](file:///c:/Documents/Vin_Build_Phase/P-096/reports/report/ChungVanDuy_02854.md)

---

## 1. TỔNG QUAN HIỆN TRẠNG KỸ THUẬT & ĐỐI SOÁT TIẾN ĐỘ

### 1.1. Hiện trạng Đạt được của Dev 2 (Nền móng Vững chắc Đã Nghiệm thu 100%)
Tính đến ngày 25/09/2026, Dev 2 đã hoàn thành trọn vẹn **27/27 tasks con thuộc 6 Task Lớn** trong kế hoạch WBS ban đầu:
- **Bộ kiểm thử toàn diện:** Đạt **318 / 318 tests passed 100%** (thời gian thực thi 5.82s). Linter `ruff` sạch sẽ 100%.
- **Tiêu chuẩn Kế toán Bất biến AC-FIN-01:** Khớp chính xác $\Delta = 0$ VNĐ tuyệt đối trên toàn bộ 15 test vectors Table 10 FCS v2.6.
- **Zero-Float Guard:** 100% logic số học sử dụng [`decimal.Decimal(28)`](file:///c:/Documents/Vin_Build_Phase/P-096/src/pricing_sidecar/arithmetic.py), làm tròn kế toán `ROUND_HALF_UP` về số nguyên VNĐ. Cơ chế [`AntiFloatBaseModel`](file:///c:/Documents/Vin_Build_Phase/P-096/src/pricing_sidecar/contracts.py) chặn đứng mọi giá trị `float`.
- **Cổng Kiểm duyệt Tài chính:** 6 Sanity Checks (`INV-FIN-01` → `INV-FIN-06`) với cấu trúc lỗi cấp trường HTTP 422 `FINANCIAL_SANITY_FAILED` (RFC 9457 / TD-4.4).
- **Chống Gian lận Dữ liệu:** Băm mật mã học SHA-256 trên Canonical JSON theo chuẩn RFC 8785 (JCS).
- **Hardened Sidecar Worker:** Lắng nghe UDS Linux (`0660`) và TCP Windows loopback (`127.0.0.1:8001`), timeout cứng 50ms, payload trần 1MB, kèm cơ chế auto-fallback in-memory.
- **SLA Hiệu năng Vượt trội (Spike 1):** In-process $P50 = 3.5$ms, Socket roundtrip $P50 = 6.1$ms (vượt xa ngân sách 50ms quy định trong TD-4.4).

### 1.2. Hiện trạng Toàn Đội ngũ Dự án P-096
- **Frontend Workspace (Dev 3 - C-08, C-10, C-11 UI):** Đã scaffold xong layout Next.js đa vai trò (Customer Pre-Sales, Sales Copilot, Manager Approval, Policy Admin) trên nhánh `BuiPhuongDuy_02684` và đã merge vào `origin/main` (PR #3). Hiện UI đang sử dụng dữ liệu Mock.
- **Orchestrator & Infrastructure (TechLead - C-01, C-05, C-07, C-09):** Đang giữ mã nguồn template FastAPI + LangGraph mẫu 2 node, cần chuyển đổi sang StateGraph 23 nodes chuẩn TD-4.3 và kích hoạt cơ sở dữ liệu PostgreSQL 16 + pgvector.
- **Knowledge & Compliance (Dev 1 - C-02, C-03, C-04, C-11):** Cần nạp dataset chuẩn tắc `dataset/` vào pgvector, hoàn thiện trích xuất điều khoản F9 và cổng kiểm duyệt phát ngôn F8.

---

## 2. KHOẢNG TRỐNG (GAP ANALYSIS) GIỮA CODEBASE HIỆN TẠI VÀ TEAM_DOCS V2

Bản cập nhật v2 (2026-09-26) mang lại các thay đổi kiến trúc lớn mà codebase hiện tại cần cập nhật và bù đắp:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             MA TRẬN KHOẢNG TRỐNG CẦN BÙ ĐẮP ĐỂ HOÀN THIỆN MVP                    │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. DEV 2 (Pricing Engine)     : • Cập nhật Enum 6 Canonical Objectives (ADR-021) thay vì 5 cũ.  │
│                                 • Bổ sung metric trích xuất MIN_MONTHLY_BURDEN & EARLY_HANDOVER. │
│                                 • Dựng tầng adapter src/services/pricing/ theo CODEBASE_MAP.     │
│                                 • Đóng gói Tool calculate_financial_plan cho StateGraph.        │
│                                 • Mở endpoint POST /api/v1/evaluation/benchmark-runs.          │
│ 2. TECHLEAD (Orchestrator)    : • Khóa thư mục hợp đồng chung src/contracts/.                    │
│                                 • Dựng StateGraph OfficialQuote (23 nodes) & PreSales (C-09).   │
│                                 • Triển khai Spikes 2, 3, 4 (Checkpointing, KMS Ed25519, Audit). │
│ 3. DEV 1 (AI & Compliance)    : • Ingestion dataset vào PostgreSQL 16 + pgvector (HNSW 1536 dims)│
│                                 • Claim Evidence Linker F4 & Policy Admin Pipeline F9.          │
│                                 • Compliance Gate F8 & chốt chặn POST /api/v1/messages/send.    │
│ 4. DEV 3 (Frontend & Client)  : • Kết nối Frontend Next.js với 7 API Routers thay vì Mock data. │
│                                 • Xử lý SSE Client Monotonic Reconnect (Last-Event-ID).          │
│                                 • Cài đặt Spike 5 (Pre-Sales Session TTL 1800s & Watermark PDF). │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. KẾ HOẠCH PHÂN RÃ CÔNG VIỆC WBS CHI TIẾT (WBS PHASE 7 — HOÀN THIỆN MVP)

Kế hoạch này phân định rõ các đầu việc trực tiếp của **Dev 2 (Trách nhiệm của bạn)** và các điểm phối hợp kỹ thuật với **TechLead, Dev 1, Dev 3** theo đúng phân vùng mã nguồn tại [CODEBASE_MAP.md](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/CODEBASE_MAP.md) và [CodeBaseIndex.md](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/CodeBaseIndex.md):

### 📌 TASK 7.1: Nâng Cấp Bộ 6 Mục Tiêu Tối Ưu Hóa Chuẩn Tắc (ADR-021)
*Trách nhiệm chính: Dev 2 | Tệp tác động: `src/pricing_sidecar/contracts.py`, `ranking.py`, `tests/`*

- [x] **Task 7.1.1 — Chuẩn hóa Enum `OptimizationObjective` trong `src/pricing_sidecar/contracts.py`:**
  - Đồng bộ chuẩn hóa 6 objectives:
    1. `MIN_NET_PRICE = "MIN_NET_PRICE"` (Giá Net trước thuế thấp nhất).
    2. `MIN_INITIAL_CASH = "MIN_INITIAL_CASH"` (Tiền mặt Đợt 1 thấp nhất — thay thế tên cũ `MIN_INITIAL_OUTFLOW`).
    3. `MIN_MONTHLY_BURDEN = "MIN_MONTHLY_BURDEN"` (**Mục tiêu mới**: Nghĩa vụ chi trả hàng tháng nhẹ nhất).
    4. `MIN_TOTAL_CASH_OUTFLOW = "MIN_TOTAL_CASH_OUTFLOW"` (Tổng tiền mặt đến khi nhận nhà thấp nhất — thay thế tên cũ `MIN_CASH_OUTFLOW_TO_HANDOVER`).
    5. `MAX_BENEFIT_VALUE = "MAX_BENEFIT_VALUE"` (Tổng giá trị quà tặng, voucher quy đổi cao nhất).
    6. `EARLY_HANDOVER = "EARLY_HANDOVER"` (**Mục tiêu mới**: Ưu tiên thời điểm nhận bàn giao nhà sớm nhất).
  - Cung cấp cơ chế Alias / Backward Compatibility:
    - `MIN_INITIAL_OUTFLOW = "MIN_INITIAL_CASH"`
    - `MIN_CASH_OUTFLOW_TO_HANDOVER = "MIN_TOTAL_CASH_OUTFLOW"`
    - `MIN_CONTRACT_PRICE = "MIN_NET_PRICE"` (fallback an toàn cho mã cũ).
  - Nghiệm thu: `contracts.py` chấp nhận cả 6 mã mới và alias cũ mà không làm gãy bất kỳ model Pydantic nào.

- [x] **Task 7.1.2 — Nâng cấp Thuật toán Xếp hạng & Bóc tách Metric tại `src/pricing_sidecar/ranking.py`:**
  - Cập nhật từ điển nhãn và tên chỉ số: `OBJECTIVE_LABELS` và `OBJECTIVE_METRIC_NAMES` bao phủ đủ 6 mục tiêu.
  - Hiện thực hàm tính metric cho `MIN_MONTHLY_BURDEN`:
    - Với `PA-VAY`: Ước tính số tiền trả nợ hàng tháng dựa trên dư nợ 70% ngân hàng và thời gian vay tối đa (ví dụ: gói vay 25 năm sau thời gian ân hạn).
    - Với `PA-CHUDONG`: Nghĩa vụ chia đều theo các tháng của tiến độ chuẩn.
    - Với `PA-NHANH`: Gán giá trị lớn nhất (do phải nộp 95% ngay Đợt 1, không tối ưu cho mục tiêu trả chậm hàng tháng).
  - Hiện thực hàm tính metric cho `EARLY_HANDOVER`:
    - Tìm mốc `is_handover == True` trong `cashflow_schedule`.
    - Trích xuất `days_from_deposit`: Số ngày bàn giao càng nhỏ thì điểm tối ưu càng cao.
  - Cập nhật hàm sinh diễn giải định lượng `_generate_quantitative_rationale`:
    - Tự động bổ sung lời giải thích tài chính rõ ràng bằng tiếng Việt cho 2 mục tiêu mới.
  - Nghiệm thu: Hàm `recommend_best_scenario` chạy mượt mà, phân loại chính xác kịch bản tối ưu cho cả 6 mục tiêu.

- [x] **Task 7.1.3 — Bổ sung Unit Tests & Kiểm chuẩn Hồi quy:**
  - Cập nhật `tests/test_pricing_sidecar/test_enums.py` kiểm tra đủ 6 objectives.
  - Cập nhật `tests/test_pricing_sidecar/test_ranking.py` bổ sung test cases cho `MIN_MONTHLY_BURDEN` (chọn `PA-VAY`) và `EARLY_HANDOVER` (chọn phương án có ngày bàn giao ngắn nhất).
  - Chạy toàn bộ test suite đảm bảo xanh 100% ($> 320$ tests passed).

---

### 📌 TASK 7.2: Xây Dựng Tầng Cầu Nối Dịch Vụ (Pricing Service Layer) theo CODEBASE_MAP
*Trách nhiệm chính: Dev 2 | Tệp tác động: `src/services/pricing/`, `src/agents/tools/pricing_engine.py`*

Theo cấu trúc phân vùng tại [CODEBASE_MAP.md §2](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/CODEBASE_MAP.md#L29) và [CodeBaseIndex.md §4.3](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/CodeBaseIndex.md#L213), thư mục `src/pricing_sidecar/` là tiến trình engine độc lập. Cần dựng các file cầu nối trong `src/services/pricing/` để StateGraph của TechLead tương tác:

- [ ] **Task 7.2.1 — Hiện thực `src/services/pricing/client.py`:**
  - Singleton / Lifecycle Manager quản lý thể hiện `PricingSidecarClient`.
  - Cấu hình thông minh qua biến môi trường (`src/config.py`):
    - Tự động ưu tiên UDS socket `/var/run/pricing/engine.sock` trên Linux.
    - Tự động chuyển TCP Loopback `127.0.0.1:8001` trên Windows.
    - Cờ `fallback_to_direct=True` kích hoạt dự phòng in-memory khi socket chưa bật.
  - Đóng gói hàm async `get_pricing_client() -> PricingSidecarClient`.

- [ ] **Task 7.2.2 — Hiện thực `src/services/pricing/validation.py` & `ranking.py`:**
  - `src/services/pricing/validation.py`: Cung cấp hàm `run_financial_sanity_gate(results) -> ValidationReport` cho Node N-11 của TechLead.
  - `src/services/pricing/ranking.py`: Cung cấp hàm `rank_and_recommend(results, objective) -> RecommendationResult` cho Node N-12 của TechLead.

- [ ] **Task 7.2.3 — Hiện thực `src/services/pricing/optimizer.py` (Pre-Sales Optimizer F3/F5):**
  - Hàm `generate_reference_plans(unit_context, constraints) -> list[ScenarioCalculationResult]`:
    - Nhận diện nhu cầu tài chính của khách hàng từ Pre-Sales Discovery (F1/F2).
    - Tạo input và gọi Pricing Engine mô phỏng 3 phương án tham khảo.
    - Lọc bỏ các phương án không khả thi (`infeasible`) theo hạn mức tài chính của khách.

- [ ] **Task 7.2.4 — Đóng gói LangGraph Tool `src/agents/tools/pricing_engine.py`:**
  - Định nghĩa `@tool("calculate_financial_plan")` chuẩn LangChain/LangGraph:
    - Input: `unit_id`, `listed_price_vnd`, `deposit_date`, `deposit_amount_vnd`, danh sách `applied_benefits`, `objective`.
    - Logic: Lấy client từ `get_pricing_client()`, thực thi `calculate_scenarios`, kiểm tra sanity, xếp hạng và trả về JSON payload kèm chữ ký `canonical_snapshot_hash`.
  - Nghiệm thu: StateGraph agent có thể bind và invoke tool độc lập mà không cần can thiệp logic nội bộ của sidecar.

- [ ] **Task 7.2.5 — Viết Test Suite cho Service Layer (`tests/test_services/test_pricing_services.py`):**
  - Kiểm thử khởi tạo client, cơ chế fallback, tool execution và wrapper functions.

---

### 📌 TASK 7.3: Tích Hợp Router Đánh Giá & Benchmark (`evaluation`) theo TD-4.4
*Trách nhiệm chính: Dev 2 | Tệp tác động: `src/api/endpoints/evaluation.py`, `src/api/routes.py`*

Theo hợp đồng giao diện [TD-4.4 §2.2](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/v2%2026-09/4.4-api-event-tool-contracts.md#L45), hệ thống cần cung cấp các REST API kiểm chuẩn:

- [ ] **Task 7.3.1 — Hiện thực Router `src/api/endpoints/evaluation.py`:**
  - `POST /api/v1/evaluation/benchmark-runs`:
    - Tiếp nhận yêu cầu kích hoạt kiểm chuẩn hệ thống.
    - Nạp tự động 15 Golden Test Cases từ `dataset/fixtures/golden_scenarios.json`.
    - Chạy toàn bộ 15 cases qua Pricing Engine, đối soát $\Delta = 0$ VNĐ từng trường số liệu kế toán.
    - Trả về mã HTTP 200 kèm báo cáo chi tiết: tổng số cases, số cases pass, độ trễ P50/P95, tỷ lệ khớp chính xác ($100.00\%$).
  - `GET /api/v1/evaluation/benchmark-runs/{run_id}`:
    - Trả về lịch sử kết quả của lần chạy benchmark tương ứng.
- [ ] **Task 7.3.2 — Đăng ký Router vào `src/api/routes.py`:**
  - Mount router `evaluation` vào prefix `/api/v1`.
  - Nghiệm thu: Endpoint phản hồi JSON chuẩn RFC 9457 khi test bằng `pytest` hoặc Swagger UI `/docs`.

---

### 📌 TASK 7.4: Phối Hợp Tích Hợp Toàn Trình E2E (Cross-Team Integration)
*Trách nhiệm: Dev 2 phối hợp cùng TechLead, Dev 1, Dev 3*

- [ ] **Task 7.4.1 — Đồng bộ Schema Khởi tạo với TechLead (`src/contracts/`):**
  - Chuyển giao các models chuẩn của Dev 2 sang `src/contracts/pricing.py` và `src/contracts/enums.py`.
  - Hỗ trợ TechLead cấu hình Node N-09, N-10A, N-10B, N-11, N-12 trong `OfficialQuoteStateGraph`.
- [ ] **Task 7.4.2 — Khớp Nối Giao diện Dữ liệu với Dev 1 (Policy RAG Extraction F9):**
  - Đối soát giữa dữ liệu `StructuredRule` do Dev 1 bóc tách từ PDF với cấu trúc `BenefitApplicationRule` của Dev 2 (đặc biệt là các loại chiết khấu tiền mặt `FIXED_CASH`, tỷ lệ `PERCENTAGE`, quà hiện vật `IN_KIND` có chứng thư `APPROVED`).
  - Đảm bảo 100% quy tắc trích xuất khi nạp vào sidecar đều hợp lệ và không gây lỗi validate.
- [ ] **Task 7.4.3 — Chuẩn hóa Dòng Tiền Hiển thị cho Dev 3 (Frontend Scenario Cards):**
  - Chuyển giao cấu trúc danh sách `cashflow_schedule` cho Dev 3 dựng bảng dòng tiền trên giao diện:
    - Cột đợt thanh toán, ngày đến hạn, nghĩa vụ vốn tự có, ngân hàng giải ngân, kinh phí bảo trì KPBT.
    - Cờ `is_handover` hiển thị nhãn `[BÀN GIAO CĂN HỘ]`.
    - Cờ `is_reconciliation` hiển thị nhãn `[QUYẾT TOÁN NHẬN SỔ HỒNG]`.
    - Hiển thị badge `[KHUYẾN NGHỊ TỐI ƯU]` và lời giải trình `quantitative_rationale` trên UI.

---

### 📌 TASK 7.5: Kiểm Chuẩn Tổng Thể, Đo Kiểm SLA & Chuẩn Bị Deliverables Demo Day
*Trách nhiệm: Dev 2 chủ trì phần số liệu kiểm chuẩn (Deliverable #10)*

- [ ] **Task 7.5.1 — Đo kiểm SLA Hiệu năng Toàn diện Hệ thống:**
  - Chạy lại bộ benchmark SLA trong `tests/benchmarks/test_pricing_latency_sla.py` ghi nhận số liệu chính thức:
    - Direct Engine $P50 \le 5$ms.
    - Validation Gate $P50 \le 1$ms.
    - Ranking Engine $P50 \le 1$ms.
    - Socket IPC Roundtrip $P50 \le 10$ms.
- [ ] **Task 7.5.2 — Đóng góp Báo cáo Đánh giá Nghiệm thu (Deliverable #10 — `eval/results/report.md`):**
  - Tổng hợp bảng số liệu 15 Golden Test Cases Table 10 FCS v2.6.
  - Trình bày bằng chứng kiểm nghiệm toán học $\Delta = 0$ VNĐ và kết quả kiểm thử Hypothesis 10 đặc tính bất biến.
- [ ] **Task 7.5.3 — Cập nhật Nhật ký Dự án (`WORKLOG.md` & `JOURNAL.md` — Deliverables #8, #9):**
  - Ghi nhận đầy đủ các mốc công việc hoàn thành của Dev 2 theo quy định của Ban Tổ chức.

---

## 4. LỘ TRÌNH THỰC HIỆN THEO NGÀY (SPRINT SCHEDULE & MILESTONES)

```text
┌──────────────┬─────────────────────────────────────────────────────────────────────────────┬───────────────────────────┐
│ THỜI GIAN    │ CÔNG VIỆC CỤ THỂ CỦA DEV 2                                                  │ CÔNG VIỆC PHỐI HỢP CẢ ĐỘI │
├──────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ NGÀY 1       │ • Hoàn thành Task 7.1: Nâng cấp 6 Objectives (ADR-021) trong contracts &     │ TechLead khóa thư mục     │
│ (27/09/2026) │   ranking.py. Cập nhật unit tests, bảo đảm xanh 100% (>320 tests pass).     │ src/contracts/.           │
├──────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ NGÀY 2       │ • Hoàn thành Task 7.2: Dựng tầng dịch vụ src/services/pricing/ (client,    │ TechLead dựng khung       │
│ (28/09/2026) │   validation, ranking, optimizer).                                          │ OfficialQuoteStateGraph.  │
│              │ • Đóng gói Tool calculate_financial_plan tại src/agents/tools/.             │ Dev 1 nạp pgvector RAG.   │
├──────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ NGÀY 3       │ • Hoàn thành Task 7.3: Dựng router POST /api/v1/evaluation/benchmark-runs. │ Dev 3 nối API Frontend    │
│ (29/09/2026) │ • Viết test suite cho Evaluation endpoint và Service layer.                 │ với Mock / Backend thật.  │
├──────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ NGÀY 4       │ • Task 7.4: Ghép nối StateGraph N-10B với Tool của Dev 2.                    │ Thông luồng Phân đoạn 1   │
│ (30/09/2026) │ • Khớp dữ liệu bảng dòng tiền cashflow_schedule với giao diện của Dev 3.    │ & Phân đoạn 2 (Pre-Sales).│
├──────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ NGÀY 5       │ • Chạy thử nghiệm E2E trọn vẹn 5 phân đoạn từ Khách Chat tới Quản lý duyệt.│ Thử nghiệm 15 kịch bản    │
│ (01/10/2026) │ • Kiểm tra chốt chặn Safe Abstention và các ngoại lệ số học.                │ thất bại FC-01 -> FC-15.  │
├──────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ NGÀY 6       │ • Task 7.5: Chạy đo kiểm SLA toàn diện và xuất báo cáo eval/results/report.md│ Diễn tập 5 kịch bản       │
│ (02/10/2026) │ • Hoàn tất cập nhật WORKLOG.md và JOURNAL.md.                               │ Demo Day Hackathon.       │
├──────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ NGÀY 7       │ • Freeze mã nguồn, tổng duyệt lần cuối, chuẩn bị sẵn sàng cho Demo Day.     │ Sẵn sàng bàn giao MVP!    │
│ (03/10/2026) │                                                                             │                           │
└──────────────┴─────────────────────────────────────────────────────────────────────────────┴───────────────────────────┘
```

---

## 5. MA TRẬN TRÁCH NHIỆM & RANH GIỚI BẢO VỆ CODEBASE (CODE OWNERSHIP)

Để bảo đảm tính toàn vẹn dữ liệu và tuân thủ nguyên tắc làm việc nhóm:

| Vùng Thư Mục Codebase | Thành viên Phụ trách Chính | Ranh giới & Quyền hạn của Dev 2 |
|:---|:---:|:---|
| `src/pricing_sidecar/` | **🟠 Chung Văn Duy (Dev 2)** | Toàn quyền kiểm soát, tối ưu hóa thuật toán và bảo trì test suite. |
| `src/services/pricing/` | **🟠 Chung Văn Duy (Dev 2)** | Toàn quyền thiết kế client adapter, validation và ranking wrapper. |
| `src/agents/tools/pricing_engine.py` | **🟠 Chung Văn Duy (Dev 2)** | Chủ trì thiết kế tool; TechLead review trước khi gắn vào graph. |
| `src/api/endpoints/evaluation.py` | **🟠 Chung Văn Duy (Dev 2)** | Chủ trì hiện thực router benchmark; TechLead mount vào routes. |
| `tests/test_pricing_sidecar/` & `tests/benchmarks/` | **🟠 Chung Văn Duy (Dev 2)** | Toàn quyền bổ sung bài test số học, SLA latency và test vectors. |
| `src/contracts/` | **🟣 Tạ Việt Cường (TechLead)** | Dev 2 đề xuất model số học; TechLead phê duyệt khóa chung. |
| `src/agents/official_quote/` & `pre_sales/` | **🟣 TechLead & 🔵 Dev 3** | Dev 2 cung cấp tool tính giá; không tự ý chỉnh sửa nodes logic. |
| `src/services/rag/`, `evidence/`, `compliance/` | **🟢 Trần Chí Ví (Dev 1)** | Dev 2 nhận đầu vào `BenefitApplicationRule`; Dev 1 phụ trách RAG. |
| `frontend/` | **🔵 Bùi Phương Đuy (Dev 3)** | Dev 2 cung cấp chuẩn dữ liệu số nguyên VNĐ; Dev 3 dựng UI. |

---

## 6. ĐIỀU KIỆN NGHIỆM THU HOÀN THÀNH TOÀN DIỆN (DEFINITION OF DONE - DOD)

Hạng mục công việc của Dev 2 và toàn bộ MVP Core chỉ được coi là hoàn tất khi thỏa mãn đầy đủ các tiêu chuẩn khắt khe sau:
1. **100% Tests Pass:** Bộ test suite toàn repo đạt trên 330 tests passed, không có bất kỳ failure hay error nào.
2. **Zero Linter Warning:** Linter `ruff check src/ tests/` đạt trạng thái `All checks passed!`.
3. **Chuẩn Kế toán Tuyệt đối:** Toàn bộ 15 Golden Cases đạt $\Delta = 0$ VNĐ, không làm tròn số lẻ hào/xu.
4. **Không Dùng Số Thực:** Không có bất kỳ kiểu `float` nào lọt vào calculation path (`assert_no_float` xác thực).
5. **Khóa Bất biến RFC 8785:** Mã băm `canonical_snapshot_hash` sinh ra tất định $100\%$ qua mọi lần chạy.
6. **SLA Độ trễ Đạt Chuẩn:** Tốc độ tính toán in-process $P50 \le 5$ms và socket IPC round-trip $P50 \le 10$ms.
7. **Tích hợp E2E Hoàn tất:** StateGraph gọi tool tính toán thành công, UI hiển thị đúng số tiền VNĐ và bảng dòng tiền.
8. **Hồ sơ Nghiệm thu Đầy đủ:** Đóng góp đầy đủ số liệu cho Báo cáo Đánh giá (Deliverable #10) và cập nhật nhật ký phát triển.

---
*Tài liệu Kế hoạch Hoàn thiện MVP Core — Lưu trữ tại `reports/plan/2026-09-27_DEV2_MVP_COMPLETION_PLAN.md`.*
