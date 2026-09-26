# Worklog — Team PricePolicy P-096

> Ghi lại tất cả công việc đã làm theo ngày. Ai làm gì, kết quả gì theo chuẩn Deliverable #9 của Ban Tổ Chức AI20K.

---

## 2026-09-26

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Trần Chí Vĩ | Tái cấu trúc chuẩn hóa toàn diện theo `CODEBASE_MAP.md` và `CodeBaseIndex.md` của TechLead | ✅ Done | `src/services/rag/`, `src/services/evidence/`, `src/services/compliance/` | 4h |
| Trần Chí Vĩ | Hiện thực hóa Claim-Level Evidence Linker (C-04) và Coordinate Parser theo chuẩn N-14B | ✅ Done | `src/services/evidence/linker.py`, `coordinate_parser.py` | 2h |
| Trần Chí Vĩ | Xây dựng Message Compliance Gate (C-11 / F8) 3 checkpoint $\times$ 4 tier và quy chuẩn phát ngôn POL-08 | ✅ Done | `src/services/compliance/gate.py`, `rules.py` | 2h |
| Trần Chí Vĩ | Triển khai LangGraph Tool `search_policy` và Script nạp dữ liệu Markdown `scripts/seed_data.py` | ✅ Done | `src/agents/tools/policy_search.py`, `scripts/seed_data.py` | 1.5h |
| Trần Chí Vĩ | Nâng cấp toàn diện Test Suite đạt 32/32 bài test sạch không trùng lặp pass 100% trong 1.70s, format code chuẩn sạch `ruff` | ✅ Done | `tests/test_services/`, `tests/test_agents/`, `tests/` | 1.5h |
| Trần Chí Vĩ | Hoàn thiện tài liệu 10 Deliverables theo chuẩn Rubric 50/50 của Ban Tổ Chức AI20K | ✅ Done | `README.md`, `ARCHITECTURE.md`, `JOURNAL.md`, `eval/results/report.md` | 2h |

**Tổng kết ngày:** Hoàn thành xuất sắc đợt đại phẫu kiến trúc Zero-Breakage, đáp ứng 100% yêu cầu của TechLead Tạ Việt Cường và sẵn sàng cho buổi nghiệm thu Demo Day.

---

## 2026-09-25

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| Trần Chí Vĩ | Tối ưu hóa chuỗi kết nối cơ sở dữ liệu Supabase pgvector qua connection pooling AWS | ✅ Done | `src/config.py`, `src/db/session.py` | 2h |
| Trần Chí Vĩ | Khởi tạo extension `pgvector` và bảng `policy_nodes`, `policy_edges` trên Supabase cloud | ✅ Done | `src/db/init_db.py`, `src/db/models.py` | 2.5h |
| Trần Chí Vĩ | Mở rộng kịch bản test tích hợp phát hiện xung đột và từ chối an toàn khi thiếu footnote | ✅ Done | `tests/test_rag/test_tdec_and_bundle.py` | 2h |

**Tổng kết ngày:** Khởi tạo thành công cơ sở dữ liệu Supabase pgvector đám mây và kết nối thành công với lõi RAG.

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
| DuyPhuong8804 | Setup repo (clone, kiểm tra cấu trúc project, tạo branch `docs`) | ✅ Done | Repo sẵn sàng để phát triển | 2h |

**Tổng kết ngày:** Hoàn thành setup repo ban đầu, bắt đầu cập nhật tài liệu.
