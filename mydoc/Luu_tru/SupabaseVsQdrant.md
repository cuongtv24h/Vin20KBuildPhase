# PHÂN TÍCH SO SÁNH & QUYẾT ĐỊNH KIẾN TRÚC: SUPABASE (POSTGRESQL + PGVECTOR) VS. DEDICATED QDRANT
## DỰ ÁN: PRICEPOLICY AI AGENT – TRỢ LÝ PHÂN TÍCH CHÍNH SÁCH BÁN HÀNG VLANDFUTURE
**Mã tài liệu:** ADR-SUPABASE-PGVECTOR-01  
**Trạng thái:** **APPROVED FOR IMPLEMENTATION & MVP BASELINE**  
**Hạng mục:** Kiến trúc Dữ liệu, Vector Database & Time-Travel RAG Pipeline  
**Tác giả:** Enterprise Solution Architect & Principal AI Systems Architect  
**Ngày phê duyệt:** 2026-09-20  

---

## 1. BỐI CẢNH & VẤN ĐỀ ĐẶT RA (CONTEXT & PROBLEM STATEMENT)

Trong kiến trúc ban đầu của dự án **PricePolicy AI Agent**, hệ thống phân tách hạ tầng dữ liệu thành 2 thành phần độc lập:
1. **PostgreSQL 16 (Multi-AZ):** Lưu trữ dữ liệu quan hệ, User RBAC, bảng giá căn hộ, hồ sơ Quote, Audit Hash Chain, Outbox Events và LangGraph Checkpoints (`AsyncPostgresSaver`).
2. **Qdrant Dedicated Cluster (Rust Engine v1.8+):** Chạy cụm riêng biệt 2 nodes (Raft consensus), mở cổng gRPC `6334` và REST `6333` nội bộ để lưu trữ và truy vấn vector tương đồng của các điều khoản chính sách.

Khi triển khai thực tế ở giai đoạn ban đầu (MVP / Implementation Spikes / Pilot), việc duy trì và vận hành một cụm Qdrant phân tán làm nảy sinh các vấn đề:
- **Overhead hạ tầng và DevOps:** Cần quản lý cấu hình, giám sát node, backup riêng cho Qdrant bên cạnh PostgreSQL.
- **Độ trễ mạng đa chặng (Network Hop) & Rủi ro lệch đồng bộ (Dual-Write / Sync Lag):** Quy trình truy xuất RAG phải chia làm 2 bước (Query Postgres lấy `valid_policy_ids` -> Gọi gRPC sang Qdrant với Payload Filter). Nếu cập nhật chính sách, việc đồng bộ giữa Postgres và Qdrant có nguy cơ trễ hoặc không đồng nhất.
- **Quy mô dữ liệu thực tế của miền bài toán:** Chính sách bán hàng của một dự án BĐS qua các đợt mở bán (v1, v2, v3) chỉ phân tách ra từ vài trăm đến vài nghìn vector chunks (thay vì hàng chục triệu vectors như e-commerce hay search engine tổng quát).

Do đó, đề xuất sử dụng **Supabase (Managed PostgreSQL tích hợp sẵn `pgvector`)** được đặt ra để tinh gọn hệ thống và tối ưu hóa chi phí vận hành ban đầu.

---

## 2. MA TRẬN SO SÁNH CHI TIẾT (COMPARATIVE MATRIX)

| Tiêu chí | Phương án Dedicated Qdrant | Phương án Supabase + pgvector | Đánh giá / Kết luận |
| :--- | :--- | :--- | :--- |
| **Quy mô dữ liệu (< 50,000 vectors)** | Quá mức cần thiết (Overkill) | Phù hợp tuyệt đối, hiệu năng cực cao | ✅ **Supabase tối ưu tài nguyên** |
| **Thời gian phản hồi truy vấn** | ~2 – 5ms | ~3 – 6ms (với HNSW Index) | ⚪ **Tương đương (đều < SLA 300ms)** |
| **Tính toàn vẹn dữ liệu (ACID)** | Tiềm ẩn rủi ro lệch đồng bộ giữa Postgres và Qdrant | **Đảm bảo ACID tuyệt đối** trong cùng một DB engine | ✅ **Supabase loại bỏ hoàn toàn Dual-Write** |
| **Truy vấn Time-Travel RAG** | Phức tạp (Gọi Postgres lấy ID $\rightarrow$ Đẩy vào Qdrant filter) | **1 câu lệnh SQL JOIN duy nhất** (lọc ngày và cosine search) | ✅ **Supabase đơn giản, dễ bảo trì** |
| **Hạ tầng DevOps & Deployment** | Cần Docker container/K8s pod riêng, monitor gRPC 6334 | Có sẵn trong Postgres, 1 Connection String duy nhất | ✅ **Supabase giảm 50% chi phí hạ tầng** |
| **Hỗ trợ LangGraph Checkpoint** | Không hỗ trợ (phải dùng Postgres riêng) | Hỗ trợ tự nhiên qua `AsyncPostgresSaver` | ✅ **Supabase đồng nhất lưu trữ State** |
| **Lưu trữ tệp PDF gốc & PDF xuất bản** | Cần cấu hình MinIO / AWS S3 riêng | Tích hợp sẵn Supabase Storage (S3-compatible) | ✅ **Supabase gom cụm tiện ích** |
| **Khả năng mở rộng (> 10M vectors)** | Rất mạnh nhờ sharding chuyên dụng | Cần mở rộng RAM lớn cho Postgres | ⚪ **Dành cho giai đoạn Scale-up tương lai** |

---

## 3. CÁC LUẬN ĐIỂM KỸ THUẬT QUYẾT ĐỊNH (CORE TECHNICAL ARGUMENTS)

### 3.1. Tính Tương đồng Quy mô & Hiệu năng của pgvector
- Hệ thống chính sách bán hàng VLandFuture mỗi đợt mở bán có khoảng 5–10 văn bản chính sách, phân rã tối đa 200–500 chunks ngữ nghĩa (Điều/Khoản). Tổng thể dự án qua 3 năm hiếm khi vượt quá **5.000 – 10.000 chunks**.
- Với kích thước này, toàn bộ vector index (`text-embedding-3-small`, 1536 chiều) được nạp hoàn toàn vào bộ nhớ đệm RAM (Buffer Pool) của PostgreSQL. Khi sử dụng chỉ mục **HNSW** (`vector_cosine_ops`), độ trễ tìm kiếm tương đồng chỉ mất **3–5ms**, hoàn toàn vượt trội so với SLA kỹ thuật đặt ra là **300ms**.

### 3.2. Hợp nhất Truy vấn Time-Travel RAG trong 1 câu SQL (Zero Sync Lag)
Thay vì quy trình phân mảnh:
$$\text{FastAPI} \xrightarrow{\text{SQL}} \text{PostgreSQL} \xrightarrow{\text{valid\_ids}} \text{FastAPI} \xrightarrow{\text{gRPC}} \text{Qdrant}$$
Supabase cho phép thực thi truy vấn hợp nhất nguyên tử:

```sql
-- TRUY VẤN TIME-TRAVEL VECTOR TRÊN SUPABASE (PGVECTOR)
SELECT 
    c.id AS chunk_id,
    c.policy_id,
    c.clause_id,
    c.clause_title,
    c.evidence_text,
    c.source_coordinates,
    c.exclusion_clauses,
    1 - (c.embedding <=> :query_embedding) AS similarity_score
FROM policy_chunks c
JOIN policy_documents p ON c.policy_id = p.id
WHERE p.project_id = :project_id
  AND p.status = 'ACTIVE'
  AND p.effective_from <= :transaction_date 
  AND :transaction_date <= p.effective_to
ORDER BY c.embedding <=> :query_embedding
LIMIT 5;
```
* **Lợi thế:** Khi `Policy Admin` vô hiệu hóa một văn bản (`status = 'REVOKED'`) hoặc chỉnh sửa ngày hiệu lực, kết quả RAG được cập nhật tức thì trong milli-giây mà không lo Vector DB chưa đồng bộ xong.

### 3.3. Hợp nhất Toàn diện Hạ tầng Bền vững (All-in-One Data Tier)
Supabase đóng vai trò nền tảng dữ liệu duy nhất cung cấp trọn vẹn các năng lực:
1. **Relational & Vector Data:** Bảng căn hộ, chính sách, vector embeddings nằm trong cùng một cơ sở dữ liệu.
2. **LangGraph Persistent State:** `AsyncPostgresSaver` lưu checkpoint đồ thị mượt mà.
3. **Audit Hash Chain & Outbox:** Khóa dòng bi quan `SELECT FOR UPDATE` trên bảng `quote_audit_events` và `outbox_events` hoạt động chính xác theo chuẩn ACID.
4. **Blob Storage:** Lưu trữ file PDF gốc có dấu mộc và file PDF báo giá xuất bản có mã QR qua Supabase Storage.

---

## 4. QUY CÁCH TRIỂN KHAI VỚI SUPABASE (IMPLEMENTATION SPECIFICATION)

### 4.1. Cấu hình Bảng & Chỉ mục pgvector
```sql
-- Kích hoạt extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Bảng lưu trữ chunks chính sách
CREATE TABLE IF NOT EXISTS policy_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id VARCHAR(64) NOT NULL REFERENCES policy_documents(id) ON DELETE CASCADE,
    clause_id VARCHAR(128) NOT NULL,
    clause_title TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    source_coordinates JSONB NOT NULL,
    exclusion_clauses TEXT[] DEFAULT '{}',
    embedding vector(1536) NOT NULL, -- OpenAI text-embedding-3-small
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('Asia/Ho_Chi_Minh', NOW())
);

-- Chỉ mục HNSW cho tìm kiếm Cosine Similarity cực nhanh
CREATE INDEX IF NOT EXISTS idx_policy_chunks_embedding_hnsw 
ON policy_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Chỉ mục hỗ trợ Time-Travel Filter
CREATE INDEX IF NOT EXISTS idx_policy_documents_time_travel 
ON policy_documents (project_id, status, effective_from, effective_to);
```

### 4.2. Bảo toàn Ranh giới Kiến trúc Tam phân (Invariants Guard)
Dù tích hợp vector search vào PostgreSQL, hệ thống **bảo lưu tuyệt đối các nguyên tắc bất biến**:
1. **AP-03 (Source of Truth):** Bản ghi file PDF gốc lưu trong Supabase Storage với mã băm SHA-256 là Source of Truth; bảng `policy_chunks` chỉ là Chỉ mục Tìm kiếm (Retrieval Index).
2. **AP-02 (Cognitive $\neq$ Math):** Kết quả RAG từ pgvector chỉ phục vụ cho việc đọc hiểu điều kiện; toàn bộ phép tính tài chính vẫn bắt buộc ủy thác cho **Python Deterministic Math Engine (`decimal.Decimal`)** trong Sidecar Container, tuyệt đối không dùng SQL/PLpgSQL để tự tính chiết khấu.
3. **INV-RT-02 (Verification Gate):** Mọi chunk trả về từ pgvector phải có `source_coordinates` và mã băm văn bản để đối soát tính hợp lệ trước khi đưa vào Agent StateGraph.

---

## 5. KẾT LUẬN & KẾ HOẠCH MỞ RỘNG (ROADMAP)

* **Giai đoạn Hiện tại (Phase 4 Spikes & Phase 5 MVP):**  
  Áp dụng **Supabase (PostgreSQL + pgvector)** làm tiêu chuẩn cơ sở dữ liệu và vector search chính thức. Giúp rút ngắn thời gian chuẩn bị môi trường, giảm chi phí kiểm thử tự động (CI/CD) và tập trung vào kiểm chuẩn số học 100% Exact Match.
* **Giai đoạn Tương lai (Scale-up Enterprise Nationwide):**  
  Nhờ có lớp trừu tượng `Policy Intelligence Subsystem (C-02)` và hợp đồng `retrieve_policy_by_date`, nếu trong tương lai quy mô dữ liệu vượt quá 5.000.000 vectors trên toàn quốc, hệ thống hoàn toàn có thể trích xuất phần vector engine sang cụm Qdrant/Pinecone chuyên dụng mà không làm thay đổi luồng StateGraph hay nghiệp vụ cốt lõi.
