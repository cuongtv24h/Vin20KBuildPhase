# TÀI LIỆU HƯỚNG DẪN TÍCH HỢP KỸ THUẬT ĐỘNG CƠ ĐỊNH GIÁ TÀI CHÍNH
## (PRICING ENGINE SIDECAR INTEGRATION GUIDE & QUICKSTART)

- **Người biên soạn:** Chung Văn Duy (Dev 2 — Financial Math & Core API Engineer)
- **Mã học viên (MSSV):** 02854
- **Đối tượng thụ hưởng:** TechLead (Orchestrator / StateGraph Engineer) & Dev 1 (Policy RAG Engineer)
- **Ngày phát hành:** 25/09/2026
- **Tài liệu đặc tả đối soát:**
  - [Đặc tả Tính toán Tài chính FCS v2.6 (0.2.financial-calculation-spec.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/0.2.financial-calculation-spec.md)
  - [Kiến trúc Runtime & Hardened Sidecar Worker TD-4.1 (4.1-technical-architecture-runtime-deployment.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/4.1-technical-architecture-runtime-deployment.md)
  - [Hợp đồng Giao diện API, Event & Tool TD-4.4 (4.4-api-event-tool-contracts.md)](file:///c:/Documents/Vin_Build_Phase/P-096/team_docs/4.4-api-event-tool-contracts.md)
  - [Kế hoạch WBS Dev 2 (2026-09-23_DEV2_FINANCIAL_MATH_WBS_PLAN.md)](file:///c:/Documents/Vin_Build_Phase/P-096/reports/plan/2026-09-23_DEV2_FINANCIAL_MATH_WBS_PLAN.md)

---

## 1. TỔNG QUAN KIẾN TRÚC & NGUYÊN TẮC VẬN HÀNH

Động cơ Định giá Tài chính ([`src/pricing_sidecar/`](file:///c:/Documents/Vin_Build_Phase/P-096/src/pricing_sidecar/)) là thành phần phần mềm toán học thuần túy (Pure Deterministic Math Engine) được thiết kế cô lập hoàn toàn khỏi LLM. Động cơ chịu trách nhiệm tính toán chính xác 100% số tiền thực tế của giao dịch bất động sản, loại trừ mọi nguy cơ ảo giác (hallucination) và sai số dấu phẩy động.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                      MASTER ORCHESTRATOR / LANGGRAPH                    │
│   (TechLead StateGraph: analyze_node -> retrieve_node -> pricing_node)  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ calls via
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   PricingSidecarClient (Adapter Layer)                  │
│       (Auto Mode: IPC Socket on Linux/Windows | Direct In-Memory)       │
└───────────────────┬─────────────────────────────────┬───────────────────┘
                    │ [Mode IPC]                      │ [Mode DIRECT]
                    │ newline-delimited JSON          │ (In-Process Call)
                    ▼                                 │
┌───────────────────────────────────────┐             │
│        PricingSidecarServer           │             │
│  - Linux: /var/run/pricing/engine.sock│             │
│  - Windows: 127.0.0.1:8001 (TCP)      │             │
│  - Hard Timeout: 50ms (RFC 9457)      │             │
│  - Payload Guard: 1MB (Anti-DOS)      │             │
└───────────────────┬───────────────────┘             │
                    │ dispatches                      │
                    ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    DETERMINISTIC PRICING ENGINE CORE                    │
│  - Arithmetic: Decimal(28), ROUND_HALF_UP, VND Integer (Delta = 0)     │
│  - 3 Canonical Scenarios: PA-CHUDONG, PA-NHANH (95%), PA-VAY (HTLS)     │
│  - Dual Discount Cap: Rate <= 35%, Total Amount <= 40% Listed Price     │
│  - Cashflow Scheduler: Deposit Credit, 100% KPBT Handover, Residual Gate│
│  - Financial Validation Gate: 6 Sanity Checks (INV-FIN-01 .. 06)        │
│  - Ranking & Tie-Break: 5 Objectives & 3-Tier Canonical Tie-Break       │
│  - Cryptographic Attestation: RFC 8785 Canonical JSON & SHA-256 Hash    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. CHẾ ĐỘ HOẠT ĐỘNG KÉP (DUAL-MODE CLIENT)

Lớp Client Adapter [`PricingSidecarClient`](file:///c:/Documents/Vin_Build_Phase/P-096/src/pricing_sidecar/client.py) hỗ trợ 2 chế độ vận hành:

1. **`SidecarMode.IPC` (Chế độ Socket IPC - Chuẩn Production & Integration):**
   - Giao tiếp qua Unix Domain Socket (`/var/run/pricing/engine.sock`) trên Linux Production (K8s pod với quyền `0660`).
   - Tự động fallback sang Local TCP Loopback (`127.0.0.1:8001`) trên môi trường Windows Dev.
   - Ép timeout cứng 50ms và kiểm soát payload 1MB.
2. **`SidecarMode.DIRECT` (Chế độ In-Memory - Dành cho Unit Tests & Standalone Fast Run):**
   - Gọi trực tiếp hàm tính toán trong cùng tiến trình Python mà không mở kết nối socket.
   - Tốc độ siêu tốc ($P50 \approx 3.5\text{ms}$).
3. **Cơ chế Fallback Tự Động (`fallback_to_direct=True`):**
   - Nếu client được cấu hình chạy ở chế độ `IPC` nhưng máy chủ socket worker chưa được bật, client **tự động** chuyển sang tính toán trực tiếp in-memory và ghi warning log, **tuyệt đối không làm crash** chu trình chạy của LangGraph Agent.

---

## 3. CÁCH KHỞI TẠO & SỬ DỤNG CLIENT

### 3.1. Import các thực thể cần thiết
```python
from decimal import Decimal
from datetime import date

from src.pricing_sidecar import (
    PricingSidecarClient,
    SidecarMode,
    PricingCalculationInput,
    OptimizationObjective,
    create_pa_chudong_config,
    create_pa_nhanh_config,
    create_pa_vay_config,
    PricingSidecarError,
    FinancialSanityError,
)
```

### 3.2. Khởi tạo Client
```python
# Cách 1: Tự động (Khuyến nghị cho TechLead)
# Sẽ ưu tiên kết nối Socket IPC, nếu server chưa bật thì tự động tính in-memory
client = PricingSidecarClient(
    mode=SidecarMode.IPC,
    fallback_to_direct=True,
    timeout_seconds=0.050,  # 50ms theo TD-4.4 SLA
)

# Cách 2: Thuần In-Memory (Siêu nhanh cho unit test)
direct_client = PricingSidecarClient(mode=SidecarMode.DIRECT)
```

---

## 4. CHI TIẾT 3 TÁC VỤ ĐỊNH GIÁ CỐT LÕI (TD-4.4 §4.1)

### 4.1. Tác vụ 1: Tính toán 3 Phương án Canonical (`calculate_scenarios`)
Tương ứng với Agent Tool **`calculate_cashflow_deterministic`** (SLA 50ms, budget 50ms).

#### Ví dụ chuẩn bị dữ liệu đầu vào (`PricingCalculationInput`):
```python
deposit_amt = Decimal("100000000")  # 100 triệu VNĐ

calc_input = PricingCalculationInput(
    unit_code="VH-GRAND-PARK-S101",
    deposit_date=date(2026, 9, 1),
    contract_signing_date=date(2026, 9, 15),
    listed_price_vnd=Decimal("3500000000"),  # 3.5 tỷ VNĐ (Bắt buộc Decimal/int, CẤM float)
    deposit_amount_vnd=deposit_amt,
    tax_vat_rate=Decimal("0.1000"),          # 10.00%
    maintenance_fee_rate=Decimal("0.0200"),  # 2.00%
    max_discount_rate=Decimal("0.2000"),     # Trần tỷ lệ chính sách
    max_total_discount_cap_rate=Decimal("0.2500"),
    resolved_policy_snapshot_id="SNP-2026-VLF-01",
    source_policy_hash="e" * 64,             # SHA-256 chính sách nguồn
    approved_benefits=[],                    # Danh sách BenefitApplicationRule (nếu có)
    scenario_configs=[
        create_pa_chudong_config(deposit_amount_vnd=deposit_amt),
        create_pa_nhanh_config(deposit_amount_vnd=deposit_amt),
        create_pa_vay_config(deposit_amount_vnd=deposit_amt),
    ],
)
```

#### Thực thi tính toán:
```python
# Gọi bất đồng bộ (Async):
output = await client.calculate_scenarios(calc_input)

# Hoặc gọi đồng bộ (Sync) nếu ở ngữ cảnh blocking:
# output = client.calculate_scenarios_sync(calc_input)

# 1. Truy xuất 3 kịch bản canonical đã tính:
for scenario in output.scenario_results:
    print(f"Kịch bản: {scenario.scenario_type}")
    print(f"  Giá Net trước thuế: {scenario.net_price_before_vat_vnd:,} VNĐ")
    print(f"  Thuế VAT (10%):     {scenario.vat_amount_vnd:,} VNĐ")
    print(f"  Phí KPBT (2%):      {scenario.maintenance_fee_amount_vnd:,} VNĐ")
    print(f"  Tổng giá HĐMB:      {scenario.final_contract_price_vnd:,} VNĐ")
    print(f"  Tiền mặt nộp Đợt 1: {scenario.initial_cash_outflow_vnd:,} VNĐ")
    print(f"  Số đợt thanh toán:  {len(scenario.cashflow_schedule)} đợt")

# 2. Truy xuất kịch bản tối ưu nhất:
print(f"Khuyến nghị tốt nhất: {output.recommended_result.recommended_scenario}")
print(f"Giải trình định lượng: {output.recommended_result.quantitative_rationale}")

# 3. Chữ ký số SHA-256 RFC 8785 bất biến:
print(f"Mã băm bất biến: {output.canonical_snapshot_hash}")
```

---

### 4.2. Tác vụ 2: Kiểm duyệt Sanity Checks (`validate_pricing`)
Tương ứng với Agent Tool **`validate_pricing_results`** (SLA 20ms).

Trước khi chuyển sang bước phát sinh văn bản giải trình hoặc trình ký duyệt báo giá, Agent bắt buộc phải gọi xác thực chốt chặn 6 Sanity Checks:

```python
# calc_target có thể là danh sách scenario_results hoặc toàn bộ PricingCalculationOutput
val_report = await client.validate_pricing(output.scenario_results)

if not val_report.is_valid:
    print(f"Kiểm duyệt thất bại: {val_report.error_message}")
    for err in val_report.field_errors:
        print(f"  - Vi phạm: {err['invariant_id']} ({err['error_code']}): {err['message']}")
else:
    print("Toàn bộ 6 nhóm Sanity Checks hợp lệ 100%!")
```

---

### 4.3. Tác vụ 3: Xếp hạng theo Hàm Mục Tiêu Kinh Doanh (`rank_scenarios`)
Tương ứng với Agent Tool **`rank_scenarios_by_objective`** (SLA 20ms).

Hỗ trợ 5 hàm mục tiêu kinh doanh chính thức của PRD & FCS:
- `OptimizationObjective.MIN_NET_PRICE`: Khách muốn tổng giá Net rẻ nhất.
- `OptimizationObjective.MIN_CONTRACT_PRICE`: Khách muốn tổng tiền HĐMB (gồm VAT/KPBT) thấp nhất.
- `OptimizationObjective.MIN_INITIAL_OUTFLOW`: Khách có dòng tiền ban đầu hạn chế, tối ưu tiền nộp Đợt 1.
- `OptimizationObjective.MIN_CASH_OUTFLOW_TO_HANDOVER`: Khách muốn giảm gánh nặng tiền mặt đến khi nhận nhà.
- `OptimizationObjective.MAX_BENEFIT_VALUE`: Khách quan tâm nhất đến tổng trị giá ưu đãi/quà tặng nhận được.

```python
recommendation = await client.rank_scenarios(
    scenarios=output.scenario_results,
    objective=OptimizationObjective.MIN_INITIAL_OUTFLOW,
    infeasible_scenarios=["BANK_LOAN_HTLS"],  # Nếu khách không đủ điều kiện vay ngân hàng
)

print(f"Phương án xếp hạng 1: {recommendation.recommended_scenario}")
print(f"Giải trình số liệu: {recommendation.quantitative_rationale}")
print(f"Có áp dụng Tie-Break không: {recommendation.is_tie_break_applied}")
```

---

## 5. MẪU TÍCH HỢP VÀO LANGGRAPH STATEGRAPH (SNIPPET DÀNH CHO TECHLEAD)

Dưới đây là đoạn mã mẫu TechLead có thể sao chép trực tiếp vào `src/agents/nodes/pricing_node.py`:

```python
from typing import Any, Dict
from src.pricing_sidecar import (
    PricingSidecarClient,
    PricingCalculationInput,
    PricingSidecarError,
    FinancialSanityError,
    create_pa_chudong_config,
    create_pa_nhanh_config,
    create_pa_vay_config,
)

# Khởi tạo client dùng chung dạng Singleton
pricing_client = PricingSidecarClient(fallback_to_direct=True)

async def pricing_calculation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node trong LangGraph chịu trách nhiệm tính toán tài chính tất định."""
    try:
        # 1. Trích xuất thông tin căn hộ và chính sách từ State
        deposit_amt = state.get("deposit_amount_vnd", 100_000_000)
        
        calc_input = PricingCalculationInput(
            unit_code=state["unit_code"],
            deposit_date=state["deposit_date"],
            contract_signing_date=state["contract_signing_date"],
            listed_price_vnd=state["listed_price_vnd"],
            deposit_amount_vnd=deposit_amt,
            tax_vat_rate=state.get("tax_vat_rate", "0.1000"),
            maintenance_fee_rate=state.get("maintenance_fee_rate", "0.0200"),
            max_discount_rate=state.get("max_discount_rate", "0.2000"),
            max_total_discount_cap_rate=state.get("max_total_discount_cap_rate", "0.2500"),
            resolved_policy_snapshot_id=state["policy_snapshot_id"],
            source_policy_hash=state["policy_hash"],
            approved_benefits=state.get("approved_benefits", []),
            scenario_configs=[
                create_pa_chudong_config(deposit_amount_vnd=deposit_amt),
                create_pa_nhanh_config(deposit_amount_vnd=deposit_amt),
                create_pa_vay_config(deposit_amount_vnd=deposit_amt),
            ],
        )

        # 2. Gọi Động cơ Định giá Tính toán
        calc_output = await pricing_client.calculate_scenarios(calc_input)

        # 3. Cập nhật kết quả vào Agent State
        return {
            "pricing_output": calc_output.model_dump(mode="python"),
            "canonical_hash": calc_output.canonical_snapshot_hash,
            "recommended_scenario": calc_output.recommended_result.recommended_scenario,
            "calculation_status": "SUCCESS",
        }

    except FinancialSanityError as fe:
        # Chặn đứng khi phát hiện vi phạm nghiệp vụ tài chính (6 Sanity Checks)
        return {
            "calculation_status": "VALIDATION_FAILED",
            "error_details": fe.to_envelope(),
        }
    except PricingSidecarError as pe:
        # Lỗi truyền thông hoặc server quá tải / timeout 50ms
        return {
            "calculation_status": "CALCULATOR_UNAVAILABLE",
            "error_message": str(pe),
        }
    except Exception as ex:
        return {
            "calculation_status": "INTERNAL_ERROR",
            "error_message": str(ex),
        }
```

---

## 6. DANH MỤC MÃ LỖI RFC 9457 & CÁCH XỬ LÝ (ERROR HANDLING)

Khi gọi qua [`PricingSidecarClient`](file:///c:/Documents/Vin_Build_Phase/P-096/src/pricing_sidecar/client.py), các ngoại lệ được chuẩn hóa theo chuẩn RFC 9457 / TD-4.4 §3.1:

| Mã Lỗi (Error Code) | HTTP Status | Nguyên Nhân | Hành Động Xử Lý Trong Agent |
| :--- | :---: | :--- | :--- |
| `FINANCIAL_SANITY_FAILED` | **422** | Vi phạm 1 trong 6 Sanity Checks (Giá Net âm, sai lệch VAT/KPBT, dòng tiền lệch 1 đồng). | Ghi log khẩn cấp, dừng quy trình, chuyển state sang `ABSTAINED` / `SAFE_ABSTAIN`. |
| `CALCULATOR_UNAVAILABLE` | **503** | Tính toán vượt quá timeout cứng 50ms hoặc máy chủ socket mất kết nối (khi tắt fallback). | Thử lại sau 1 giây (Retryable). |
| `PAYLOAD_TOO_LARGE` | **413** | Kích thước gói tin request vượt quá 1MB. | Kiểm tra lại kích thước payload đầu vào (DOS guard). |
| `INVALID_REQUEST` | **400** | Cú pháp JSON lỗi hoặc thiếu trường bắt buộc của `PricingCalculationInput`. | Kiểm tra lại schema dữ liệu truyền vào. |

---

## 7. BA QUY TẮC AN TOÀN SỐ HỌC BẮT BUỘC (ZERO-FLOAT POLICY)

1. **Tuyệt đối cấm truyền số thực (`float`):**
   - ❌ **SAI:** `listed_price_vnd=3500000000.0`, `tax_vat_rate=0.1`
   - ✅ **ĐÚNG:** `listed_price_vnd=Decimal("3500000000")` hoặc `3500000000` (int)
   - ✅ **ĐÚNG:** `tax_vat_rate=Decimal("0.1000")` hoặc `"0.1000"` (str)
   - *Hệ thống sẽ lập tức ném ngoại lệ `TypeError: FLOAT_PROHIBITED` nếu phát hiện bất kỳ giá trị `float` nào!*
2. **Số tiền luôn làm tròn về số nguyên VNĐ ($\Delta = 0$ VNĐ):**
   - Động cơ đã tự động áp dụng `ROUND_HALF_UP` cho toàn bộ các bước tính thuế, phí, chiết khấu và dòng tiền. Caller chỉ cần nhận kết quả nguyên VNĐ.
3. **Mã băm SHA-256 RFC 8785 bất biến:**
   - Trường `output.canonical_snapshot_hash` là chuỗi 64 ký tự hex đại diện cho chữ ký số toàn vẹn của kết quả tính toán. Khi lưu database hoặc sinh PDF, TechLead phải dùng chuỗi băm này để chống gian lận.

---
*Bản tài liệu được kiểm định đồng bộ với mã nguồn và 318 unit/benchmark tests pass 100% của Dev 2.*
