# KẾ HOẠCH PHÂN RÃ CÔNG VIỆC (WBS) & TIẾN ĐỘ THỰC THI CHI TIẾT
## VỊ TRÍ: DEV 2 — FINANCIAL MATH & CORE API ENGINEER
**Dự án:** PricePolicy AI Agent (VLand Future) — BDSVLandFuture-06  
**Ngày lập kế hoạch:** 23/09/2026 (2026-09-23)  
**Người phụ trách:** Dev 2 (Financial Math & Core API Engineer)  
**Trạng thái kế hoạch:** 🚀 SẴN SÀNG THỰC THI (READY FOR EXECUTION)  
**Tài liệu tham chiếu chuẩn:**
- [Đặc tả Tính toán Tài chính FCS v2.6 (0.2.financial-calculation-spec.md)](../../team_docs/0.2.financial-calculation-spec.md)
- [Kế hoạch Triển khai Chi tiết Nhóm (5.Implement_plan_detail.md)](../../team_docs/5.Implement_plan_detail.md)
- [Kiến trúc Runtime & Hardened Sidecar Worker TD-4.1 (4.1-technical-architecture-runtime-deployment.md)](../../team_docs/4.1-technical-architecture-runtime-deployment.md)
- [Hợp đồng Giao diện API, Event & Tool TD-4.4 (4.4-api-event-tool-contracts.md)](../../team_docs/4.4-api-event-tool-contracts.md)

---

## 1. MỤC TIÊU VÀ PHẠM VI TRÁCH NHIỆM

1. **Số học tất định 100%:** Tuyệt đối cấm sử dụng số thực dấu phẩy động (`float` / `double`) trong toàn bộ calculation path; sử dụng `decimal.Decimal` với precision tối thiểu 28 chữ số; làm tròn kế toán chuẩn Việt Nam `ROUND_HALF_UP` về số nguyên VNĐ ($\Delta = 0$ VNĐ).
2. **Hiện thực hóa 3 kịch bản FCS Canonical:** `PA-CHUDONG` (Tiến độ chuẩn), `PA-NHANH` (Thanh toán sớm 95%), `PA-VAY` (Hỗ trợ lãi suất), áp dụng Dual Discount Cap (tỷ lệ $\le 35\%$, tổng tiền $\le 40\%$) và mô hình chiết khấu cộng dồn Additive.
3. **Động cơ Lập lịch Dòng tiền Generic:** Lập lịch thanh toán từ chính sách động, kết chuyển cọc tại Đợt 1, phân bổ KPBT tại đợt bàn giao, và bù trừ triệt tiêu sai số đồng lẻ tại đợt quyết toán cuối (Reconciliation Gate), bảo đảm không sinh số dư âm.
4. **Chốt chặn Kiểm duyệt Tài chính (Validation Gate):** Kiểm tra 6 nhóm Sanity Checks, trả về cấu trúc lỗi cấp trường `field-level error envelope` với mã chuẩn `FINANCIAL_SANITY_FAILED`.
5. **Thuật toán Xếp hạng Tối ưu & Tie-Break Tất định:** Hỗ trợ 5 mục tiêu (`MIN_NET_PRICE`, `MIN_CONTRACT_PRICE`, `MIN_INITIAL_OUTFLOW`, `MIN_CASH_OUTFLOW_TO_HANDOVER`, `MAX_BENEFIT_VALUE`) kèm thứ tự giải quyết hòa tất định (`canonical_scenario_order`).
6. **Bảo chứng Dữ liệu RFC 8785:** Băm SHA-256 trên chuỗi Canonical JSON (JCS) để sinh `canonical_snapshot_hash` chống gian lận.
7. **Bộ Kiểm chuẩn Đáp án Vàng 15 Cases:** Nạp và đối soát 15 test vectors từ Table 10 FCS, bảo đảm đạt $\Delta = 0$ VNĐ tuyệt đối (AC-FIN-01) và kiểm định 10 đặc tính toán học (Hypothesis).
8. **Đóng gói Hardened UDS Sidecar Worker & 3 Agent Tools:** Đóng gói worker UDS `/var/run/pricing/engine.sock` (kèm fallback loopback TCP cho Windows dev) và xuất khẩu 3 Agent Tools chuẩn decorator `@tool` cho LangGraph Agent của TechLead.

---

## 2. CẤU TRÚC THƯ MỤC DỰ KIẾN (PLANNED DIRECTORY TREE)

```text
c:\Documents\Vin_Build_Phase\P-096\
├── src/
│   ├── pricing_sidecar/                   # [MỚI] Gói phần mềm lõi của Dev 2
│   │   ├── __init__.py
│   │   ├── arithmetic.py                  # Hàm làm tròn round_vnd, context precision Decimal(28)
│   │   ├── contracts.py                   # Pydantic v2 schemas: Input, Output, Rule, Enums
│   │   ├── engine.py                      # Động cơ tính 3 scenarios & cashflow generator
│   │   ├── validation.py                  # Financial Validation Gate (6 Sanity Checks)
│   │   ├── ranking.py                     # Ranking 5 Optimization Objectives & Canonical Tie-break
│   │   ├── canonical_hash.py              # Serializer RFC 8785 JCS & SHA-256 Hash generator
│   │   ├── server.py                      # UDS Hardened Server (hỗ trợ fallback loopback cho Windows)
│   │   └── client.py                      # Sidecar Client Adapter (UDS & In-Memory Direct Mode)
│   └── agents/
│       └── tools/
│           ├── __init__.py
│           └── financial_tools.py         # [MỚI] 3 Agent Tools tích hợp LangGraph cho TechLead
├── dataset/
│   └── fixtures/
│       └── golden_scenarios.json          # [CẬP NHẬT] Bổ sung đủ 15 golden cases chuẩn FCS Table 10
├── tests/
│   ├── benchmarks/                        # [MỚI] Bộ benchmark suite độc lập
│   │   ├── __init__.py
│   │   ├── test_golden_scenarios.py       # Chạy 15 Golden Vectors (Exact Delta = 0 VND)
│   │   ├── test_pricing_properties.py     # 10 Property-Based Tests (Hypothesis: 10,000 samples)
│   │   └── test_validation_gate.py        # Kiểm thử 6 Sanity Checks & Negative test cases
│   └── test_pricing_sidecar/              # [MỚI] Unit test cho các module nội bộ
│       ├── __init__.py
│       ├── test_engine.py                 # Test logic tính từng scenario, discount cap, VAT, KPBT
│       ├── test_ranking.py                # Test độ nhạy và thứ tự ưu tiên xếp hạng
│       ├── test_canonical_hash.py         # Test tính tất định của chuỗi byte RFC 8785
│       └── test_sidecar_ipc.py            # Test giao tiếp UDS / Local Socket IPC
├── reports/
│   └── plan/
│       └── 2026-09-23_DEV2_FINANCIAL_MATH_WBS_PLAN.md # [FILE NÀY] Bản kế hoạch phân rã công việc WBS
└── WORKLOG.md                             # [CẬP NHẬT] Ghi nhận tiến độ công việc hàng ngày
```

---

## 3. BẢNG TIẾN ĐỘ TỔNG QUAN (PROGRESS TRACKER)

| Mã Task | Tên Task Lớn | Số Task Nhỏ | Đã Hoàn Thành | Tiến Độ (%) | Trạng Thái |
|:---:|:---|:---:|:---:|:---:|:---:|
| **TASK 1** | Chuẩn hóa Dữ liệu Kiểm chuẩn & Hợp đồng Số học | 5 | 5 | 100% | ✅ Hoàn thành |
| **TASK 2** | Động cơ Tính toán 3 Phương án FCS & Lập Dòng tiền | 8 | 8 | 100% | ✅ Hoàn thành |
| **TASK 3** | Chốt chặn Kiểm duyệt Tài chính & Thuật toán Xếp hạng | 5 | 5 | 100% | ✅ Hoàn thành |
| **TASK 4** | Bộ Băm RFC 8785 & Golden Benchmark Suite (15 Cases) | 6 | 6 | 100% | ✅ Hoàn thành |
| **TASK 5** | Đóng gói Hardened UDS Sidecar Worker & Client Adapter | 5 | 0 | 0% | ⏳ Chưa làm |
| **TASK 6** | Tích hợp 3 Agent Tools cho LangGraph & Nghiệm thu | 3 | 0 | 0% | ⏳ Chưa làm |
| **TỔNG** | **6 Task Lớn** | **27 Task Nhỏ** | **24** | **88.9%** | **Đang thực thi** |

---

## 4. CHI TIẾT CÁC ĐẦU VIỆC & CHECK-LIST CẬP NHẬT TIẾN ĐỘ

### ══════════════════════════════════════════════════════════════════════════
### 🔵 TASK LỚN 1: Chuẩn hóa Dữ liệu Kiểm chuẩn & Hợp đồng Số học
*Mục tiêu: Xây dựng nền tảng Pydantic models, context số học Decimal(28) và nạp đủ 15 test vectors chuẩn Table 10 FCS.*
### ══════════════════════════════════════════════════════════════════════════

| Mã Task | Mô Tả Chi Tiết Đầu Việc | File Liên Quan | Trạng Thái | Check |
|:---:|:---|:---|:---:|:---:|
| **Task 1.1** | Mở rộng file `golden_scenarios.json` từ 2 cases lên đầy đủ 15 cases đối soát chuẩn (`TC-01` đến `TC-15`) trên căn hộ mẫu `A-12-05` (3.5 tỷ VNĐ, cọc 100M, VAT 10%, KPBT 2%). | `dataset/fixtures/golden_scenarios.json` | ✅ Hoàn thành | [x] |
| **Task 1.2** | Thiết lập module số học `arithmetic.py`: cấu hình `getcontext().prec = 28`, viết hàm làm tròn kế toán `round_vnd(ROUND_HALF_UP)`, thiết lập runtime guard cấm kiểu `float` trong calculation path. | `src/pricing_sidecar/arithmetic.py` | ✅ Hoàn thành | [x] |
| **Task 1.3** | Xây dựng toàn bộ Enums trong `contracts.py`: `ScenarioType`, `OptimizationObjective`, `BenefitCategory`, `BenefitType`, `CalculationBase`, `ValuationStatus`, `QuoteWorkflowStatus`. | `src/pricing_sidecar/contracts.py` | ✅ Hoàn thành | [x] |
| **Task 1.4** | Xây dựng Pydantic Input Models với validator nghiêm ngặt trong `contracts.py`: `InstallmentRule`, `PaymentScenarioConfig` (kiểm tra 8 invariants: tổng vốn = 1.0, duy nhất 1 handover, duy nhất 1 reconciliation,...), `BenefitApplicationRule`. | `src/pricing_sidecar/contracts.py` | ✅ Hoàn thành | [x] |
| **Task 1.5** | Xây dựng Pydantic Output Models trong `contracts.py`: `CashflowInstallmentOutput`, `ScenarioCalculationResult`, `ValidationReport`, `RecommendationResult`, `PricingCalculationOutput`. Đóng băng Milestone M0. | `src/pricing_sidecar/contracts.py` | ✅ Hoàn thành | [x] |

---

### ══════════════════════════════════════════════════════════════════════════
### 🔵 TASK LỚN 2: Động cơ Tính toán 3 Phương án FCS & Lập Dòng tiền
*Mục tiêu: Tính toán tất định 3 kịch bản canonical, chiết khấu cộng dồn Additive, Dual Cap và lập lịch dòng tiền generic.*
### ══════════════════════════════════════════════════════════════════════════

| Mã Task | Mô Tả Chi Tiết Đầu Việc | File Liên Quan | Trạng Thái | Check |
|:---:|:---|:---|:---:|:---:|
| **Task 2.1** | Triển khai Bước 1 & Bước 2 mô hình Additive Discount: Trừ tiền mặt cố định $\text{Base}_1 = P_{\text{listed}} - D_{\text{fixed}}$, tính tổng tỷ lệ chiết khấu cộng dồn $\text{Sum\_Rate} = \sum r_i$. | `src/pricing_sidecar/engine.py` | ✅ Hoàn thành | [x] |
| **Task 2.2** | Cưỡng chế cơ chế Dual Discount Cap: kiểm tra trần tỷ lệ $\text{Sum\_Rate} \le 35\%$ (`max_discount_rate`) và trần tổng tiền $D_{\text{total}} \le P_{\text{listed}} \times 40\%$ (`max_total_discount_cap_rate`). | `src/pricing_sidecar/engine.py` | ✅ Hoàn thành | [x] |
| **Task 2.3** | Triển khai Bước 3 & Bước 4: Tính thuế GTGT $A_{\text{vat}} = \text{round\_vnd}(P_{\text{net}} \times 10\%)$, phí $A_{\text{kpbt}} = \text{round\_vnd}(P_{\text{net}} \times 2\%)$ và tổng giá HĐMB $P_{\text{contract}} = P_{\text{net}} + A_{\text{vat}} + A_{\text{kpbt}}$. | `src/pricing_sidecar/engine.py` | ✅ Hoàn thành | [x] |
| **Task 2.4** | Hiện thực hàm tính 3 kịch bản: `PA-CHUDONG` (Tiến độ chuẩn), `PA-NHANH` (Thanh toán sớm 95%), `PA-VAY` (Hỗ trợ lãi suất ngân hàng). | `src/pricing_sidecar/engine.py` | ✅ Hoàn thành | [x] |
| **Task 2.5** | Xây dựng giải thuật Lập lịch Dòng tiền Generic (`generate_cashflow_schedule`): duyệt động theo `InstallmentRule`, tính ngày đến hạn từ `deposit_date`. | `src/pricing_sidecar/engine.py` | ✅ Hoàn thành | [x] |
| **Task 2.6** | Xử lý kết chuyển tiền cọc tại Đợt 1: `deposit_credited_vnd = min(deposit_paid, eq_amt)`, tính tiền nộp thêm thực tế `installment_additional_cash_due_vnd`. | `src/pricing_sidecar/engine.py` | ✅ Hoàn thành | [x] |
| **Task 2.7** | Xử lý phân bổ 100% kinh phí bảo trì KPBT tại đợt nhận bàn giao nhà (`is_handover`). | `src/pricing_sidecar/engine.py` | ✅ Hoàn thành | [x] |
| **Task 2.8** | Triển khai thuật toán bù triệt tiêu sai số lẻ tại đợt quyết toán cuối (`is_reconciliation`), kiểm tra chặn số dư âm, ném ngoại lệ `CASHFLOW_RESIDUAL_ERROR`. | `src/pricing_sidecar/engine.py` | ✅ Hoàn thành | [x] |

---

### ══════════════════════════════════════════════════════════════════════════
### 🔵 TASK LỚN 3: Chốt chặn Kiểm duyệt Tài chính & Thuật toán Xếp hạng
*Mục tiêu: Ngăn chặn 100% kết quả sai lệch bằng 6 Sanity Checks và xếp hạng tối ưu hóa bằng thuật toán tất định.*
### ══════════════════════════════════════════════════════════════════════════

| Mã Task | Mô Tả Chi Tiết Đầu Việc | File Liên Quan | Trạng Thái | Check |
|:---:|:---|:---|:---:|:---:|
| **Task 3.1** | Xây dựng `src/pricing_sidecar/validation.py` kiểm tra 6 nhóm Sanity Checks: (1) Giá Net $> 0$; (2) Dual cap; (3) VAT/KPBT khớp rate; (4) Cân bằng HĐ; (5) Dòng tiền khớp 100%; (6) Số tiền $\ge 0$ & ngày tăng đơn điệu. | `src/pricing_sidecar/validation.py` | ✅ Hoàn thành | [x] |
| **Task 3.2** | Định dạng cấu trúc lỗi chi tiết cấp trường (`field-level error envelope`) với mã lỗi chuẩn `FINANCIAL_SANITY_FAILED`. | `src/pricing_sidecar/validation.py` | ✅ Hoàn thành | [x] |
| **Task 3.3** | Xây dựng `src/pricing_sidecar/ranking.py` hiện thực 5 hàm mục tiêu: `MIN_NET_PRICE`, `MIN_CONTRACT_PRICE`, `MIN_INITIAL_OUTFLOW`, `MIN_CASH_OUTFLOW_TO_HANDOVER`, `MAX_BENEFIT_VALUE`. | `src/pricing_sidecar/ranking.py` | ✅ Hoàn thành | [x] |
| **Task 3.4** | Hiện thực cơ chế Tie-Break tất định dựa trên `canonical_scenario_order` (`STANDARD_PROGRESS: 1` $\rightarrow$ `EARLY_95: 2` $\rightarrow$ `BANK_LOAN_HTLS: 3`). | `src/pricing_sidecar/ranking.py` | ✅ Hoàn thành | [x] |
| **Task 3.5** | Xử lý loại trừ kịch bản không khả thi (`infeasible`) và kết xuất `RecommendationResult` kèm `quantitative_rationale`. | `src/pricing_sidecar/ranking.py` | ✅ Hoàn thành | [x] |

---

### ══════════════════════════════════════════════════════════════════════════
### 🔵 TASK LỚN 4: Bộ Băm RFC 8785 & Golden Benchmark Suite (15 Cases)
*Mục tiêu: Đạt tiêu chuẩn nghiệm thu AC-FIN-01 (Delta = 0 VND trên 15 vectors) và kiểm định 10 đặc tính toán học.*
### ══════════════════════════════════════════════════════════════════════════

| Mã Task | Mô Tả Chi Tiết Đầu Việc | File Liên Quan | Trạng Thái | Check |
|:---:|:---|:---|:---:|:---:|
| **Task 4.1** | Tạo `src/pricing_sidecar/canonical_hash.py`: hiện thực serializer chuẩn RFC 8785 Canonical JSON (JCS) sắp xếp key từ điển đệ quy, chuẩn hóa khoảng trắng. | `src/pricing_sidecar/canonical_hash.py` | ✅ Hoàn thành | [x] |
| **Task 4.2** | Tạo hàm sinh mã băm SHA-256 `canonical_snapshot_hash` trên payload JSON canonical, bảo đảm cùng input cho cùng một chuỗi hash 100%. | `src/pricing_sidecar/canonical_hash.py` | ✅ Hoàn thành | [x] |
| **Task 4.3** | Viết Test Runner `tests/benchmarks/test_golden_scenarios.py`: đọc `golden_scenarios.json`, chạy 15 cases đối soát tự động. | `tests/benchmarks/test_golden_scenarios.py` | ✅ Hoàn thành | [x] |
| **Task 4.4** | So khớp chính xác từng trường số tiền nguyên VNĐ ($\Delta = 0$ VNĐ tuyệt đối), kiểm tra đúng trạng thái nghiệp vụ (`ELIGIBLE`, `CONFLICT`, `AMBIGUOUS`, `BLOCKED`, `SAFE_ABSTAIN`). | `tests/benchmarks/test_golden_scenarios.py` | ✅ Hoàn thành | [x] |
| **Task 4.5** | Viết Negative Test Suite `tests/benchmarks/test_validation_gate.py`: đưa dữ liệu cố tình sai lệch để kiểm tra Validation Gate chặn đứng thành công. | `tests/benchmarks/test_validation_gate.py` | ✅ Hoàn thành | [x] |
| **Task 4.6** | Viết Property-Based Test `tests/benchmarks/test_pricing_properties.py` dùng `hypothesis`: kiểm chứng 10 đặc tính toán học (Reconciliation Completeness, Non-negativity, Monotonicity,...). | `tests/benchmarks/test_pricing_properties.py` | ✅ Hoàn thành | [x] |

---

### ══════════════════════════════════════════════════════════════════════════
### 🔵 TASK LỚN 5: Đóng gói Hardened UDS Sidecar Worker & Client Adapter
*Mục tiêu: Đóng gói tiến trình worker cô lập theo kiến trúc TD-4.1 và hỗ trợ song song môi trường Windows.*
### ══════════════════════════════════════════════════════════════════════════

| Mã Task | Mô Tả Chi Tiết Đầu Việc | File Liên Quan | Trạng Thái | Check |
|:---:|:---|:---|:---:|:---:|
| **Task 5.1** | Tạo `src/pricing_sidecar/server.py`: Lắng nghe trên Unix Domain Socket `/var/run/pricing/engine.sock` (quyền 0660 cho Linux). | `src/pricing_sidecar/server.py` | ✅ Hoàn thành | [x] |
| **Task 5.2** | Cấu hình chế độ Local TCP Loopback (`127.0.0.1:8001`) trong `server.py` để hỗ trợ chạy trực tiếp trên Windows dev environment. | `src/pricing_sidecar/server.py` | ✅ Hoàn thành | [x] |
| **Task 5.3** | Enforce timeout cứng (50ms), validate kích thước request và trả về lỗi định dạng RFC 9457 (`CALCULATOR_UNAVAILABLE`). | `src/pricing_sidecar/server.py` | ✅ Hoàn thành | [x] |
| **Task 5.4** | Tạo endpoint kiểm tra sức khỏe `health_check` (`PING` $\rightarrow$ `PONG`) và cơ chế Graceful Shutdown. | `src/pricing_sidecar/server.py` | ✅ Hoàn thành | [x] |
| **Task 5.5** | Tạo `src/pricing_sidecar/client.py`: Hỗ trợ Dual-mode (chế độ UDS IPC và chế độ Direct In-Memory cho fast test/fallback). | `src/pricing_sidecar/client.py` | ✅ Hoàn thành | [x] |

---

### ══════════════════════════════════════════════════════════════════════════
### 🔵 TASK LỚN 6: Chuẩn Hóa Tích Hợp Client API, Đo Kiểm SLA & Nghiệm Thu
*Mục tiêu: Chuẩn hóa Core Client Integration API cho Agent/Orchestrator theo TD-4.4 §4.1, đo kiểm SLA hiệu năng tính toán P95 và hoàn tất hồ sơ nghiệm thu bàn giao.*
### ══════════════════════════════════════════════════════════════════════════

| Mã Task | Mô Tả Chi Tiết Đầu Việc | File Liên Quan | Trạng Thái | Check |
|:---:|:---|:---|:---:|:---:|
| **Task 6.1** | Chuẩn hóa Core Client API trong `src/pricing_sidecar/client.py` phục vụ 3 thao tác cốt lõi của Agent theo TD-4.4 §4.1 (`calculate_scenarios`, `validate_pricing`, `rank_scenarios`), tuân thủ ranh giới Code Ownership. | `src/pricing_sidecar/client.py` | ✅ Hoàn thành | [x] |
| **Task 6.2** | Đo kiểm SLA hiệu năng tính toán (`tests/benchmarks/test_pricing_latency_sla.py`): In-process direct latency ($P50 \le 5$ms), Socket IPC round-trip ($P95 \le 25$ms) và kiểm thử đồng thời (concurrency). | `tests/benchmarks/test_pricing_latency_sla.py` | ✅ Hoàn thành | [x] |
| **Task 6.3** | Ghi nhận toàn bộ kết quả vào `WORKLOG.md` và hoàn tất báo cáo nghiệm thu tổng thể bàn giao cho TechLead. | `WORKLOG.md`, `reports/report/ChungVanDuy_02854.md` | ✅ Hoàn thành | [x] |

---

## 5. ĐIỀU KIỆN TIÊN QUYẾT & TIÊU CHUẨN HOÀN THÀNH (DEFINITION OF DONE)

Một đầu việc chỉ được đánh dấu hoàn thành `[x]` khi:
1. Đã vượt qua toàn bộ unit tests và benchmark tests liên quan.
2. Không có bất kỳ lỗi cú pháp (`ruff check`), không vi phạm kiểu dữ liệu `float`.
3. Có log/error handling rõ ràng, không phá vỡ schema contract của TechLead.
4. Được cập nhật trạng thái tương ứng vào file kế hoạch này và file `WORKLOG.md`.
