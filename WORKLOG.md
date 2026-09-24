# Worklog — Team PricePolicy P-096

> Ghi lại tất cả công việc đã làm theo ngày. Ai làm gì, kết quả gì.

---

## 2026-09-24

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Trần Chí Vĩ | Đóng băng Data Contracts PEC-RAG (`PolicyAtom`, `PolicyEdge`, `EvidenceBundle`, `AbstentionCertificate`, `EvidenceItem`) | ✅ Done | `src/models/pec_contracts.py` | 3h |
| Trần Chí Vĩ | Triển khai mock endpoint Pricing Service bắt buộc tiêu thụ verified EvidenceBundle | ✅ Done | `src/api/pricing_mock.py`, `src/main.py` | 2h |
| Trần Chí Vĩ | Tái cấu trúc thư mục RAG nội bộ tương ứng 5 sub-modules (compiler, retrieval, closure, verification, evaluation) | ✅ Done | `src/rag/` | 2h |
| Trần Chí Vĩ | Xây dựng bộ dữ liệu Golden Queries kiểm thử chuẩn hóa (T0_EXACT, T1_HYBRID, DUAL_POLARITY, ABSTENTION, TEMPORAL) | ✅ Done | `eval/golden_queries.json` | 1h |

**Tổng kết ngày:** Hoàn thành Day 1 PEC-RAG/TDEC MVP Alignment, đóng băng Data Contracts và sẵn sàng hạ tầng cho RAG Engine.

---

## 2026-09-23

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Trần Chí Vĩ | Thiết kế & triển khai Core Policy RAG Engine (Hierarchical Parser, Time-Travel Retriever, 3-Tier Mutual Exclusion Pruner, Cryptographic Evidence Binder) | ✅ Done | `src/rag/`, `src/models/rag_schemas.py` | 6h |
| Trần Chí Vĩ | Viết bộ Unit & Integration Test Suite cho toàn bộ các module RAG (12/12 tests passing) | ✅ Done | `tests/test_rag/` | 2h |
| Trần Chí Vĩ | Xây dựng Framework Đánh giá RAG Benchmark & tích hợp runner (Leakage 0.0%, Recall@k 100%, Integrity 100%, p95 < 6ms) | ✅ Done | `eval/rag/`, `eval/results/report.md`, `Makefile` | 3h |

**Tổng kết ngày:** Hoàn thành 100% nền tảng Core RAG Engine và Evaluation Framework chuẩn Enterprise cho PricePolicy P-096.

---

## 2026-09-15

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| DuyPhuong8804 | Setup repo (clone, kiểm tra cấu trúc project, tạo branch `docs`) | ✅ Done | Repo sẵn sàng để phát triển | - |

**Tổng kết ngày:** Hoàn thành setup repo ban đầu, bắt đầu cập nhật tài liệu.
