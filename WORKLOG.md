# Worklog — Team [Tên Team]

> Ghi lại tất cả công việc đã làm theo ngày. Ai làm gì, kết quả gì.

---

## 2026-09-15

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| DuyPhuong8804 | Setup repo (clone, kiểm tra cấu trúc project, tạo branch `docs`) | ✅ Done | Repo sẵn sàng để phát triển | - |

**Tổng kết ngày:** Hoàn thành setup repo ban đầu, bắt đầu cập nhật tài liệu.

---

## 2026-09-23

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Dev 2 (ChungVanDuy) | Lập kế hoạch WBS 6 Task Lớn / 27 Task Nhỏ | ✅ Done | `reports/plan/2026-09-23_DEV2_FINANCIAL_MATH_WBS_PLAN.md` | 1.0h |
| Dev 2 (ChungVanDuy) | Task 1.1: Chuẩn hóa & mở rộng `golden_scenarios.json` đủ 17 cases (15 Golden Cases FCS Table 10) | ✅ Done | `dataset/fixtures/golden_scenarios.json` (17 cases pass 100% invariants) | 1.0h |
| Dev 2 (ChungVanDuy) | Task 1.2: Thiết lập module số học `arithmetic.py` (Decimal 28, round_vnd, Anti-Float Guard) | ✅ Done | `src/pricing_sidecar/arithmetic.py`, `tests/test_pricing_sidecar/test_arithmetic.py` (21/21 tests pass, ruff clean) | 1.0h |
| Dev 2 (ChungVanDuy) | Task 1.3: Xây dựng toàn bộ Enums & ma trận nghiệp vụ trong `contracts.py` | ✅ Done | `src/pricing_sidecar/contracts.py`, `tests/test_pricing_sidecar/test_enums.py` (14/14 tests pass, ruff clean) | 0.5h |
| Dev 2 (ChungVanDuy) | Task 1.4: Xây dựng Pydantic Input Models & 8 Invariant Validators | ✅ Done | `src/pricing_sidecar/contracts.py`, `tests/test_pricing_sidecar/test_input_contracts.py` (32/32 tests pass, ruff clean) | 1.0h |
| Dev 2 (ChungVanDuy) | Task 1.5: Xây dựng Pydantic Output Models, hoàn tất Milestone M0 Contract Freeze | ✅ Done | `src/pricing_sidecar/contracts.py`, `tests/test_pricing_sidecar/test_output_contracts.py` (18/18 tests pass, ruff clean) | 0.8h |

**Tổng kết ngày:** Hoàn thành xuất sắc 100% Task Lớn 1 (5/5 tasks con), đóng băng thành công Milestone M0 (Contract Freeze) bao gồm toàn bộ Hợp đồng Dữ liệu Đầu vào & Đầu ra theo FCS v2.6. Tổng cộng 85/85 unit tests pass 100% (0.17s) và ruff linter đạt chuẩn sạch.

---

## 2026-09-24

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Dev 2 (ChungVanDuy) | Task 2.1: Triển khai Bước 1 & Bước 2 mô hình Additive Discount | ✅ Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` (27/27 tests pass, ruff clean, nâng tổng tests lên 112/112) | 1.0h |
| Dev 2 (ChungVanDuy) | Task 2.2: Cưỡng chế cơ chế Dual Discount Cap (trần tỷ lệ 35% & trần tổng tiền 40%) | ✅ Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` (40/40 tests pass, ruff clean, nâng tổng tests lên 125/125) | 0.8h |
| Dev 2 (ChungVanDuy) | Task 2.3: Triển khai Bước 3 & Bước 4 tính thuế VAT, phí KPBT và tổng giá HĐMB | ✅ Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` (54/54 tests pass, ruff clean, nâng tổng tests lên 139/139) | 0.8h |
| Dev 2 (ChungVanDuy) | Task 2.4: Hiện thực hàm tính 3 kịch bản canonical (PA-CHUDONG, PA-NHANH, PA-VAY) và hàm điều phối canonical | ✅ Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` (67/67 tests pass, ruff clean, nâng tổng tests sidecar lên 152/152, toàn repo lên 161/161) | 1.0h |
| Dev 2 (ChungVanDuy) | Task 2.5: Xây dựng giải thuật Lập lịch Dòng tiền Generic (`generate_cashflow_schedule`) | ✅ Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` (74/74 tests pass, ruff clean, nâng tổng tests sidecar lên 159/159, toàn repo lên 168/168) | 1.0h |
| Dev 2 (ChungVanDuy) | Task 2.6: Xử lý kết chuyển tiền cọc Đợt 1 và tính tiền nộp thêm thực tế | ✅ Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` (Suite TestInstallmentDepositCredit 5/5 tests pass) | 0.5h |
| Dev 2 (ChungVanDuy) | Task 2.7: Xử lý phân bổ 100% KPBT tại đợt nhận bàn giao nhà (is_handover) | ✅ Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` (Suite TestHandoverMaintenanceFeeAllocation 5/5 tests pass) | 0.5h |
| Dev 2 (ChungVanDuy) | Task 2.8: Triển khai bù triệt tiêu sai số lẻ và chặn số dư âm CashflowResidualError | ✅ Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` (Suite TestReconciliationResidualGate 5/5 tests pass, nâng tổng tests sidecar lên 174/174, toàn repo lên 183/183) | 0.5h |
| Dev 2 (ChungVanDuy) | Task 3.1: Xây dựng Cổng Kiểm duyệt Tài chính 6 Sanity Checks | ✅ Done | `src/pricing_sidecar/validation.py`, `tests/test_pricing_sidecar/test_validation.py` (6 nhóm Sanity Checks, positive & negative tests pass) | 0.8h |
| Dev 2 (ChungVanDuy) | Task 3.2: Cấu trúc lỗi cấp trường (field-level envelope) & ngoại lệ FINANCIAL_SANITY_FAILED | ✅ Done | `src/pricing_sidecar/validation.py`, `src/pricing_sidecar/__init__.py` (25/25 tests pass, nâng tổng tests sidecar lên 199/199, toàn repo lên 208/208) | 0.8h |
| Dev 2 (ChungVanDuy) | Task 3.3: Thuật toán Xếp hạng 5 Mục tiêu Kinh doanh (MIN_NET, MIN_CONTRACT, MIN_INITIAL, MIN_HANDOVER, MAX_BENEFIT) | ✅ Done | `src/pricing_sidecar/ranking.py`, `tests/test_pricing_sidecar/test_ranking.py` (Xếp hạng tất định 100% số nguyên VNĐ) | 0.8h |
| Dev 2 (ChungVanDuy) | Task 3.4: Hiện thực Cơ chế Tie-Break 3 Tầng Tất định (Contract Price & Canonical Order) | ✅ Done | `src/pricing_sidecar/ranking.py`, `tests/test_pricing_sidecar/test_ranking.py` (TIEBREAK-CONTRACT-PRICE-v1, TIEBREAK-CANONICAL-ORDER-v1) | 0.5h |
| Dev 2 (ChungVanDuy) | Task 3.5: Lọc kịch bản không khả thi (infeasible) & kết xuất RecommendationResult kèm quantitative_rationale | ✅ Done | `src/pricing_sidecar/ranking.py`, `src/pricing_sidecar/__init__.py` (17/17 tests pass, nâng tổng tests sidecar lên 216/216, toàn repo lên 225/225) | 0.8h |

**Tổng kết ngày:** Hoàn thành xuất sắc 100% Task Lớn 2 (Tasks 2.1 - 2.8) và 100% Task Lớn 3 (Tasks 3.1 - 3.5): hiện thực hóa trọn vẹn Động cơ Định giá Tài chính 4 bước, Lập lịch dòng tiền Generic, Cổng kiểm duyệt 6 Sanity Checks, Thuật toán Xếp hạng 5 mục tiêu, Cơ chế Tie-Break tất định 3 tầng và Kết xuất Khuyến nghị kịch bản tối ưu kèm giải trình định lượng theo chuẩn FCS v2.6 & TD-4.4. Toàn bộ 225/225 tests đạt tỷ lệ pass 100% (2.40s) và linter ruff đạt chuẩn sạch tuyệt đối.

---

## 2026-09-25

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Dev 2 (ChungVanDuy) | Task 4.1: Hiện thực Serializer RFC 8785 Canonical JSON (JCS) với sắp xếp UTF-16 code units đệ quy | ✅ Done | `src/pricing_sidecar/canonical_hash.py`, `tests/test_pricing_sidecar/test_canonical_hash.py` (Chuẩn hóa đệ quy không float, minification, UTF-8 bytes) | 1.0h |
| Dev 2 (ChungVanDuy) | Task 4.2: Hàm sinh mã băm SHA-256 canonical_snapshot_hash & factory PricingCalculationOutput | ✅ Done | `src/pricing_sidecar/canonical_hash.py`, `src/pricing_sidecar/__init__.py` (23/23 tests pass, nâng tổng tests sidecar lên 239/239, toàn repo lên 248/248, ruff clean) | 0.8h |

**Tổng kết ngày:** Hoàn thành xuất sắc Task 4.1 và Task 4.2: hiện thực hóa trọn vẹn Serializer RFC 8785 Canonical JSON (JCS) sắp xếp key theo chuẩn UTF-16 code units đệ quy, chuẩn hóa khoảng trắng, bảo toàn Anti-Float Guard, tích hợp bộ sinh mã băm SHA-256 `canonical_snapshot_hash` 64 hex characters cho payload snapshot FCS v2.6 §8 và kiểm chứng tính toàn vẹn mật mã học. Toàn bộ 248/248 tests toàn repo pass 100% (2.36s) và linter ruff đạt chuẩn sạch tuyệt đối.

---

## [YYYY-MM-DD]

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| [Tên] | [mô tả task] | ✅ Done | [link/kết quả] | 2h |
| [Tên] | [mô tả task] | 🔄 WIP | [mô tả tiến độ] | 1.5h |
| [Tên] | [mô tả task] | ❌ Blocked | [lý do block] | - |

**Tổng kết ngày:** [1-2 câu về tiến độ chung]

---

## [YYYY-MM-DD]

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| | | | | |

**Tổng kết ngày:**

---

<!-- Format: copy block trên cho mỗi ngày làm việc -->
