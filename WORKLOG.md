# Worklog — Team PricePolicy P-096

> Ghi lại tất cả công việc đã làm theo ngày. Ai làm gì, kết quả gì theo chuẩn Deliverable #9 của Ban Tổ Chức AI20K.

---

## 2026-09-28

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Trần Chí Vĩ | Chuẩn hóa Tool Catalog: Vá method `search_policy` (`policy_time_travel_search`) và xây dựng Security Scanners `guardrails.py` (N-02 / N-14A) | Done | `src/agents/tools/policy_search.py`, `src/agents/tools/guardrails.py`, `tests/test_agents/test_guardrails.py` | 2h |
| Trần Chí Vĩ | Triển khai 2 Router API C-11/F8 & C-03/F9: Compliance Gate (`/check-message`, `/messages/send`) và Quản trị Chính sách (`/extract-rules`, `/rules/test`, `/publish`) | Done | `src/api/endpoints/compliance.py`, `src/api/endpoints/policies.py`, `tests/test_api/test_compliance_policies_endpoints.py` | 2.5h |
| Trần Chí Vĩ | Tích hợp Router vào `src/main.py` và tối ưu `PolicyRAGService` với phương thức `retrieve()` hỗ trợ lọc thời gian | Done | `src/main.py`, `src/services/rag/service.py`, `src/services/evidence/verification/evidence_verifier.py` | 1h |
| Trần Chí Vĩ | Xây dựng bộ Test Tích Hợp End-to-End `test_e2e_ai_data_pipeline.py` chứng minh 5 kịch bản lõi PEC-RAG/TDEC/Compliance | Done | `tests/test_e2e_ai_data_pipeline.py` | 1.5h |
| Trần Chí Vĩ | Chạy toàn diện Ruff Lint & Pytest Suite đạt 50/50 tests PASS 100% trong 1.14s, code sạch chuẩn Zero-Breakage | Done | Toàn bộ codebase | 0.5h |

**Tổng kết ngày:** Hoàn tất 100% toàn bộ trách nhiệm của DEV 1 (AI & Data) theo đặc tả `CodeBaseIndex.md` và `PricePolicy_PEC-RAG_MVP_Alignment_Addendum_VI.md`, sẵn sàng bàn giao adapter sạch cho TechLead ghép nối StateGraph.

---

## 2026-09-26

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Trần Chí Vĩ | Tái cấu trúc chuẩn hóa toàn diện theo `CODEBASE_MAP.md` và `CodeBaseIndex.md` của TechLead | Done | `src/services/rag/`, `src/services/evidence/`, `src/services/compliance/` | 4h |
| Trần Chí Vĩ | Hiện thực hóa Claim-Level Evidence Linker (C-04) và Coordinate Parser theo chuẩn N-14B | Done | `src/services/evidence/linker.py`, `coordinate_parser.py` | 2h |
| Trần Chí Vĩ | Xây dựng Message Compliance Gate (C-11 / F8) 3 checkpoint $\times$ 4 tier và quy chuẩn phát ngôn POL-08 | Done | `src/services/compliance/gate.py`, `rules.py` | 2h |
| Trần Chí Vĩ | Triển khai LangGraph Tool `search_policy` và Script nạp dữ liệu Markdown `scripts/seed_data.py` | Done | `src/agents/tools/policy_search.py`, `scripts/seed_data.py` | 1.5h |
| Trần Chí Vĩ | Nâng cấp toàn diện Test Suite đạt 32/32 bài test sạch không trùng lặp pass 100% trong 1.70s, format code chuẩn sạch `ruff` | Done | `tests/test_services/`, `tests/test_agents/`, `tests/` | 1.5h |
| Trần Chí Vĩ | Hoàn thiện tài liệu 10 Deliverables theo chuẩn Rubric 50/50 của Ban Tổ Chức AI20K | Done | `README.md`, `ARCHITECTURE.md`, `JOURNAL.md`, `eval/results/report.md` | 2h |

**Tổng kết ngày:** Hoàn thành xuất sắc đợt đại phẫu kiến trúc Zero-Breakage, đáp ứng 100% yêu cầu của TechLead Tạ Việt Cường và sẵn sàng cho buổi nghiệm thu Demo Day.

---

## 2026-09-25

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Trần Chí Vĩ | Tối ưu hóa chuỗi kết nối cơ sở dữ liệu Supabase pgvector qua connection pooling AWS | Done | `src/config.py`, `src/db/session.py` | 2h |
| Trần Chí Vĩ | Khởi tạo extension `pgvector` và bảng `policy_nodes`, `policy_edges` trên Supabase cloud | Done | `src/db/init_db.py`, `src/db/models.py` | 2.5h |
| Trần Chí Vĩ | Mở rộng kịch bản test tích hợp phát hiện xung đột và từ chối an toàn khi thiếu footnote | Done | `tests/test_rag/test_tdec_and_bundle.py` | 2h |
| Chung Văn Duy | Task 4.1: Hiện thực Serializer RFC 8785 Canonical JSON (JCS) với sắp xếp UTF-16 code units đệ quy | Done | `src/pricing_sidecar/canonical_hash.py`, `tests/test_pricing_sidecar/test_canonical_hash.py` | 1.0h |
| Chung Văn Duy | Task 4.2: Hàm sinh mã băm SHA-256 canonical_snapshot_hash & factory PricingCalculationOutput | Done | `src/pricing_sidecar/canonical_hash.py`, `src/pricing_sidecar/__init__.py` | 0.8h |
| Chung Văn Duy | Task 4.3: Viết Test Runner tự động nạp dữ liệu kiểm chuẩn 17 cases | Done | `tests/benchmarks/test_golden_scenarios.py` | 0.8h |
| Chung Văn Duy | Task 4.4: So khớp chính xác số tiền nguyên VNĐ (AC-FIN-01 Delta = 0 VND) & kiểm soát ngoại lệ | Done | `tests/benchmarks/test_golden_scenarios.py` | 1.0h |
| Chung Văn Duy | Task 4.5: Negative Test Suite kiểm chứng Cổng kiểm duyệt 6 Sanity Checks | Done | `tests/benchmarks/test_validation_gate.py` | 1.0h |
| Chung Văn Duy | Task 4.6: Property-Based Tests dùng Hypothesis kiểm chứng 10 đặc tính toán học | Done | `tests/benchmarks/test_pricing_properties.py`, `src/pricing_sidecar/engine.py` | 1.2h |
| Chung Văn Duy | Task 5.1 & 5.2: Xây dựng Hardened Sidecar Worker Server (`PricingSidecarServer`) | Done | `src/pricing_sidecar/server.py`, `src/pricing_sidecar/__init__.py` | 1.0h |
| Chung Văn Duy | Task 5.3: Cưỡng chế timeout cứng 50ms, giới hạn kích thước request tối đa 1MB | Done | `src/pricing_sidecar/server.py`, `tests/test_pricing_sidecar/test_sidecar_ipc.py` | 0.8h |
| Chung Văn Duy | Task 5.4: Endpoint kiểm tra sức khỏe `health_check` và Graceful Shutdown | Done | `src/pricing_sidecar/server.py`, `tests/test_pricing_sidecar/test_sidecar_ipc.py` | 0.5h |
| Chung Văn Duy | Task 5.5: Xây dựng Client Adapter Dual-Mode (`PricingSidecarClient`) | Done | `src/pricing_sidecar/client.py`, `tests/test_pricing_sidecar/test_sidecar_ipc.py` | 1.0h |
| Chung Văn Duy | Task 6.1: Chuẩn hóa Core Client Integration API trong `src/pricing_sidecar/client.py` | Done | `src/pricing_sidecar/client.py`, `src/pricing_sidecar/__init__.py` | 0.8h |
| Chung Văn Duy | Task 6.2: Đo kiểm SLA hiệu năng tính toán: In-process direct latency ($P50 \le 5$ms) | Done | `tests/benchmarks/test_pricing_latency_sla.py` | 1.0h |
| Chung Văn Duy | Task 6.3: Hoàn tất báo cáo nghiệm thu tổng thể 27/27 tasks | Done | `reports/plan/2026-09-23_DEV2_FINANCIAL_MATH_WBS_PLAN.md` | 0.8h |

**Tổng kết ngày:** Khởi tạo thành công cơ sở dữ liệu Supabase pgvector đám mây và hoàn thành toàn diện 27/27 tasks của Dev 2 Financial Math.

---

## 2026-09-24

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Trần Chí Vĩ | Đóng băng Data Contracts PEC-RAG (`PolicyAtom`, `PolicyEdge`, `EvidenceBundle`, `AbstentionCertificate`, `EvidenceItem`) | Done | `src/models/pec_contracts.py` | 3h |
| Trần Chí Vĩ | Triển khai mock endpoint Pricing Service bắt buộc tiêu thụ verified EvidenceBundle | Done | `src/api/pricing_mock.py`, `src/main.py` | 2h |
| _(cập nhật 2026-10-07)_ | Endpoint mock `/api/v1/pricing` ở dòng trên ĐÃ GỠ khỏi runtime (commit `1aa356c`) vì sản phẩm online chạy dữ liệu thật; Pricing Sidecar C-06 (`src/pricing_sidecar/`) và cầu nối `src/pricing/` vẫn giữ nguyên | Removed | — | — |
| Trần Chí Vĩ | Tái cấu trúc thư mục RAG nội bộ tương ứng 5 sub-modules (compiler, retrieval, closure, verification, evaluation) | Done | `src/rag/` | 2h |
| Trần Chí Vĩ | Xây dựng bộ dữ liệu Golden Queries kiểm thử chuẩn hóa | Done | `eval/golden_queries.json` | 1h |
| Chung Văn Duy | Task 2.1: Triển khai Bước 1 & Bước 2 mô hình Additive Discount | Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` | 1.0h |
| Chung Văn Duy | Task 2.2: Cưỡng chế cơ chế Dual Discount Cap | Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` | 0.8h |
| Chung Văn Duy | Task 2.3: Triển khai Bước 3 & Bước 4 tính thuế VAT, phí KPBT và tổng giá HĐMB | Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` | 0.8h |
| Chung Văn Duy | Task 2.4: Hiện thực hàm tính 3 kịch bản canonical | Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` | 1.0h |
| Chung Văn Duy | Task 2.5: Xây dựng giải thuật Lập lịch Dòng tiền Generic | Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` | 1.0h |
| Chung Văn Duy | Task 2.6: Xử lý kết chuyển tiền cọc Đợt 1 và tính tiền nộp thêm thực tế | Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` | 0.5h |
| Chung Văn Duy | Task 2.7: Xử lý phân bổ 100% KPBT tại đợt nhận bàn giao nhà | Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` | 0.5h |
| Chung Văn Duy | Task 2.8: Triển khai bù triệt tiêu sai số lẻ và chặn số dư âm | Done | `src/pricing_sidecar/engine.py`, `tests/test_pricing_sidecar/test_engine.py` | 0.5h |
| Chung Văn Duy | Task 3.1: Xây dựng Cổng Kiểm duyệt Tài chính 6 Sanity Checks | Done | `src/pricing_sidecar/validation.py`, `tests/test_pricing_sidecar/test_validation.py` | 0.8h |
| Chung Văn Duy | Task 3.2: Cấu trúc lỗi cấp trường & ngoại lệ FINANCIAL_SANITY_FAILED | Done | `src/pricing_sidecar/validation.py`, `src/pricing_sidecar/__init__.py` | 0.8h |
| Chung Văn Duy | Task 3.3: Thuật toán Xếp hạng 5 Mục tiêu Kinh doanh | Done | `src/pricing_sidecar/ranking.py`, `tests/test_pricing_sidecar/test_ranking.py` | 0.8h |
| Chung Văn Duy | Task 3.4: Hiện thực Cơ chế Tie-Break 3 Tầng Tất định | Done | `src/pricing_sidecar/ranking.py`, `tests/test_pricing_sidecar/test_ranking.py` | 0.5h |
| Chung Văn Duy | Task 3.5: Lọc kịch bản không khả thi & kết xuất RecommendationResult | Done | `src/pricing_sidecar/ranking.py`, `src/pricing_sidecar/__init__.py` | 0.8h |

**Tổng kết ngày:** Hoàn thành Day 1 PEC-RAG/TDEC MVP Alignment, đóng băng Data Contracts và hoàn thành Task Lớn 2 & 3 của Financial Math.

---

## 2026-09-23

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Trần Chí Vĩ | Thiết kế & triển khai Core Policy RAG Engine | Done | `src/rag/`, `src/models/rag_schemas.py` | 6h |
| Trần Chí Vĩ | Viết bộ Unit & Integration Test Suite cho các module RAG | Done | `tests/test_rag/` | 2h |
| Trần Chí Vĩ | Xây dựng Framework Đánh giá RAG Benchmark & tích hợp runner | Done | `eval/rag/`, `eval/results/report.md`, `Makefile` | 3h |
| Chung Văn Duy | Lập kế hoạch WBS 6 Task Lớn / 27 Task Nhỏ | Done | `reports/plan/2026-09-23_DEV2_FINANCIAL_MATH_WBS_PLAN.md` | 1.0h |
| Chung Văn Duy | Task 1.1: Chuẩn hóa & mở rộng `golden_scenarios.json` đủ 17 cases | Done | `dataset/fixtures/golden_scenarios.json` | 1.0h |
| Chung Văn Duy | Task 1.2: Thiết lập module số học `arithmetic.py` | Done | `src/pricing_sidecar/arithmetic.py`, `tests/test_pricing_sidecar/test_arithmetic.py` | 1.0h |
| Chung Văn Duy | Task 1.3: Xây dựng toàn bộ Enums & ma trận nghiệp vụ | Done | `src/pricing_sidecar/contracts.py`, `tests/test_pricing_sidecar/test_enums.py` | 0.5h |
| Chung Văn Duy | Task 1.4: Xây dựng Pydantic Input Models & 8 Invariant Validators | Done | `src/pricing_sidecar/contracts.py`, `tests/test_pricing_sidecar/test_input_contracts.py` | 1.0h |
| Chung Văn Duy | Task 1.5: Xây dựng Pydantic Output Models, hoàn tất Milestone M0 Contract Freeze | Done | `src/pricing_sidecar/contracts.py`, `tests/test_pricing_sidecar/test_output_contracts.py` | 0.8h |

**Tổng kết ngày:** Hoàn thành 100% nền tảng Core RAG Engine và đóng băng Milestone M0 của Financial Math.

---

## 2026-09-15

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| DuyPhuong8804 | Setup repo (clone, kiểm tra cấu trúc project, tạo branch `docs`) | Done | Repo sẵn sàng để phát triển | 2h |

**Tổng kết ngày:** Hoàn thành setup repo ban đầu, bắt đầu cập nhật tài liệu.
