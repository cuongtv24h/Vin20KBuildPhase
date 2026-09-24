# Báo Cáo Tiến Độ Dự Án — PricePolicy (P-096)

- **Thành viên:** Trần Chí Vĩ
- **Mã học viên (MSSV):** 02968
- **Vai trò / Phụ trách:** Core Policy RAG Engine & Retrieval Evaluation Framework
- **Ngày báo cáo:** 2026-09-24
- **Nhánh phát triển code:** [`TranChiVi_02968`](https://github.com/AI20K-Build-Phase-Cohort-4/P-096/tree/TranChiVi_02968)
- **Pull Request vào dev:** [PR #4](https://github.com/AI20K-Build-Phase-Cohort-4/P-096/pull/4)

---

## 1. Mục Tiêu Công Việc Đã Thực Hiện

Xây dựng toàn bộ hạ tầng **Policy RAG Engine & PEC-RAG/TDEC MVP Architecture Alignment** phục vụ hệ thống tư vấn lãi suất, phí và chính sách bán hàng của ngân hàng, giải quyết triệt để 3 bài toán nghiệp vụ cốt lõi:
1. **Truy xuất xuyên thời gian (Time-Travel Retrieval):** Ngăn chặn 100% rò rỉ chính sách tương lai hoặc áp dụng chính sách đã hết hạn vào ngày giao dịch của khách hàng.
2. **Khử xung đột chính sách 3 tầng (Mutual Exclusion Pruning & TDEC Closure):** Tự động phát hiện và loại trừ xung đột ưu đãi theo ma trận quyền hạn nghiệp vụ (Hard Exclusion, Conditional Exclusion, Ambiguous Conflict).
3. **Đóng băng Data Contracts & Ràng buộc mật mã học (PEC-RAG Evidence Bundle & Abstention Certificate):** Gắn chặt từng đoạn chính sách trích xuất với tọa độ chi tiết (`parent`, `page`, `section`, `table_coordinates`), chứng từ mật mã SHA-256 và buộc Pricing Service phải tiêu thụ duy nhất verified bundle.

---

## 2. Chi Tiết Các Hạng Mục Đã Hoàn Thành

### 2.1. Đóng Băng Data Contracts PEC-RAG (`src/models/pec_contracts.py`) — *2026-09-24*
- **`PolicyAtom`**: Định nghĩa nguyên tử chính sách với đầy đủ thuộc tính nguồn gốc (provenance): `atom_id`, `content`, `parent`, `page`, `section`, `table_coordinates`, `effective_from`, `effective_to`, `polarity`.
- **`PolicyEdge`**: Ma trận quan hệ chính sách và TDEC closure edges với thuộc tính thẩm quyền: `source_authority`, `reviewed_by`, `edge_version`, `source_atom_id`, `target_atom_id`, `relation_type`.
- **`EvidenceItem` & `EvidenceBundle`**: Đóng băng cấu trúc bằng chứng trích xuất bao gồm `items`, `evidence_bundle_id`, `sha256_digest`, `verified_status`.
- **`AbstentionCertificate`**: Giấy chứng nhận từ chối đưa ra kết luận (abstention) khi thiếu chính sách hoặc phát hiện xung đột không thể giải quyết.

### 2.2. Kiểm Soát Tuân Thủ API Pricing (`src/api/pricing_mock.py`) — *2026-09-24*
- Khởi tạo mock endpoint `POST /api/v1/pricing/quote` tích hợp vào FastAPI main app (`src/main.py`).
- Đảm bảo cơ chế bảo mật hợp đồng: Pricing Service CHỈ chấp nhận `EvidenceBundle` có `verified_status == VERIFIED` và mã băm SHA-256 hợp lệ.

### 2.3. Tái Cấu Trúc Thư Mục Nội Bộ RAG (`src/rag/`) — *2026-09-24*
- Phân tách cấu trúc module RAG tương ứng 5 task Dev 1 (D1-1 đến D1-5):
  - `src/rag/compiler/`: Policy Compiler tạo policy atoms và provenance.
  - `src/rag/retrieval/`: Hard temporal/scope filter + seed retrieval + cost route.
  - `src/rag/closure/`: Typed policy edges + TDEC closure.
  - `src/rag/verification/`: Evidence Verifier + EvidenceBundle / AbstentionCertificate.
  - `src/rag/evaluation/`: Consumer của verified EvidenceBundle.

### 2.4. Tập Dữ Liệu Kiểm Thử Chuẩn Golden Queries (`eval/golden_queries.json`) — *2026-09-24*
- Xây dựng 5 kịch bản kiểm thử chuẩn hóa: `T0_EXACT`, `T1_HYBRID`, `DUAL_POLARITY`, `ABSTENTION`, `TEMPORAL` phục vụ đánh giá tự động.

### 2.5. Pydantic Schemas & Data Contracts Ban Đầu (`src/models/rag_schemas.py`) — *2026-09-23*
- `EvidenceCoordinate`: Định danh tọa độ chính sách (file, Chương, Điều, Khoản, Điểm, `line_span`, `sha256_hash`).
- `AttributedPolicyEvidence`: Mô hình dữ liệu bằng chứng trích xuất phục vụ làm căn cứ tính phí/lãi suất.
- `TimeTravelFilter`: Cấu trúc bộ lọc temporal gồm ngày giao dịch `transaction_date`, hạng khách hàng `customer_tier`, mã dịch vụ `service_code`, kênh giao dịch `channel`.

### 2.6. Core RAG Engine (`src/rag/`) — *2026-09-23*
- **Hierarchical Ingestion Parser (`src/rag/ingestion/hierarchical_parser.py`):** Bóc tách tài liệu chính sách Markdown theo cấu trúc phân cấp Điều/Khoản/Điểm và mã băm SHA-256.
- **Metadata Enricher (`src/rag/ingestion/metadata_enricher.py`):** Trích xuất phạm vi ngày hiệu lực, hạng khách hàng và nhóm loại trừ.
- **Time-Travel Policy Retriever (`src/rag/retriever/time_travel_retriever.py`):** Lọc vector search kết hợp temporal filter.
- **Mutual Exclusion Pruner (`src/rag/retriever/pruner.py`):** Khử xung đột 3 tầng theo ma trận nghiệp vụ.
- **Evidence Binder (`src/rag/retriever/evidence_binder.py`):** Ràng buộc mật mã học trước khi bàn giao.
- **Policy RAG Service Facade (`src/rag/service.py`):** Điểm truy cập duy nhất tích hợp pipeline RAG.

### 2.7. Bộ Kiểm Thử Tự Động & Evaluation Benchmark Framework — *2026-09-23*
- `16/16 tests PASS` (12 tests RAG + 4 tests services).
- **Time-Travel Leakage:** `0.00%` (Đạt ✅)
- **Clause-Level Recall@k:** `100.00%` (Đạt ✅)
- **Conflict Completeness:** `100.00%` (Đạt ✅)
- **Cryptographic Integrity:** `100.00%` (Đạt ✅)
- **Retrieval Latency (p95):** `5.76 ms` (Đạt ✅)

---

## 3. Trạng Thái Hiện Tại & Kế Hoạch Tiếp Theo

- **Trạng thái:** ✅ Đã hoàn thành 100% đóng băng Data Contracts (Day 1) & Scaffolding PEC-RAG/TDEC MVP Architecture.
- **Pull Request:** Đã cập nhật và push lên nhánh [`TranChiVi_02968`](https://github.com/AI20K-Build-Phase-Cohort-4/P-096/tree/TranChiVi_02968), sẵn sàng cho công tác tích hợp tiếp theo.
- **Kế hoạch tiếp theo:**
  - Hoàn thiện logic trong các modules RAG (`compiler`, `retrieval`, `closure`, `verification`).
  - Phối hợp kết nối Verified EvidenceBundle vào Deterministic Pricing Engine.
