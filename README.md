# PricePolicy AI Agent — Hệ Thống Trợ Lý AI Định Giá & Tư Vấn Chính Sách Bất Động Sản Doanh Nghiệp (P-096)

[![CI - Pytest](https://img.shields.io/badge/pytest-477%2F477%20passed-brightgreen.svg)](tests/)
[![Code Style - Ruff](https://img.shields.io/badge/code%20style-ruff%20clean-blue.svg)](ruff.toml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.14-blue.svg)](requirements.txt)
[![Architecture](https://img.shields.io/badge/architecture-PEC--RAG%20%7C%20TDEC-orange.svg)](ARCHITECTURE.md)
[![Database](https://img.shields.io/badge/pgvector-Supabase%20HNSW-green.svg)](src/db/)

> **Đồ án VinUni AI20K Build Phase — Team P-096**  
> Hệ thống Multi-Agent hỗ trợ tư vấn bán hàng, tính toán tài chính minh bạch và kiểm chứng pháp lý bất biến cho dự án bất động sản quy mô lớn (Vinhomes / Masterise).

---

## 1. Bài Toán & Bối Cảnh Thực Tế (Problem Statement)

Tại các chủ đầu tư bất động sản cao cấp, các văn bản chính sách bán hàng (`POL-01` đến `POL-10`) liên tục được cập nhật theo từng đợt mở bán, chương trình kích cầu hoặc nhóm đối tượng khách hàng:
1. **Ma trận chiết khấu phức tạp:** Khách hàng thanh toán sớm, vay ngân hàng hỗ trợ lãi suất 0%, quà tặng nội thất, ưu đãi cư dân... có mối quan hệ phụ thuộc (Prerequisite) hoặc loại trừ lẫn nhau (Mutual Exclusion).
2. **Rủi ro sai lệch tài chính & pháp lý:** Chuyên viên tư vấn (Sales) dễ tính toán sai lịch dòng tiền, áp dụng nhầm chính sách hết hiệu lực, hoặc tự ý phát ngôn hứa hẹn vượt thẩm quyền ("bao duyệt vay 100%", "cam kết sinh lời chắc chắn").
3. **Ảo giác AI (Hallucination):** Các mô hình LLM thông thường dễ tự bịa số liệu chiết khấu hoặc trích dẫn sai điều khoản pháp lý, gây rủi ro pháp lý nghiêm trọng cho chủ đầu tư.

---

## 2. Giải Pháp Toàn Diện (Our Solution)

PricePolicy P-096 triển khai kiến trúc **Enterprise AI Orchestrator kết hợp Sidecar Tính Toán Tất Định**:

* **PEC-RAG Core (C-02 & C-03):** Time-Travel Policy Retrieval lọc SQL cứng loại bỏ 100% rò rỉ thời gian, kết hợp Dual-Polarity (Truy xuất song song Cực Dương "Tại sao được" và Cực Âm "Tại sao không").
* **Evidence Verification & TDEC 1-Hop Closure (C-04):** Mở rộng đồ thị phụ thuộc 1-hop thu gom điều kiện tiên quyết và cặp quy tắc loại trừ. Gắn mỏ neo chứng cứ cấp câu với tọa độ SHA-256 chống giả mạo (Anti-Tamper), phát hành `EvidenceBundle` (Verified) hoặc `AbstentionCertificate` (Từ chối an toàn).
* **Compliance Gate (C-11 / F8):** Chốt chặn an toàn phát ngôn 3 Checkpoint (`ON_DRAFT`, `DEBOUNCE`, `FINAL_SEND`) $\times$ 4 Tier (`SUPPORTED`, `CONDITIONAL`, `UNSUPPORTED`, `PROHIBITED`) theo chuẩn POL-08.
* **High-Performance Vector DB:** Lưu trữ nhúng ngữ nghĩa trên PostgreSQL + `pgvector` với chỉ mục HNSW (`dims=1536`), độ trễ truy xuất < 2.5ms.

---

## 3. Sơ Đồ Kiến Trúc Hệ Thống (Architecture Overview)

```mermaid
graph TB
    subgraph Client["Lớp Giao Diện & Client"]
        User([Khách Hàng / Sales]) --> Frontend[React / Next.js Web UI]
    end

    subgraph API_GW["Lớp API Gateway & Routes (FastAPI)"]
        Frontend -->|HTTP / REST| API[FastAPI Endpoints<br/>/api/v1/chat, /pricing/calculate]
    end

    subgraph Agent_Orchestrator["Lớp Orchestrator (LangGraph StateGraph)"]
        API --> PreSales[Customer Pre-Sales Agent]
        PreSales --> OfficialQuote[Official Quote Agent]
    end

    subgraph Core_Services["Lớp Dịch Vụ Cốt Lõi (src/services/)"]
        PreSales -->|Query + Date| RAG[PEC-RAG Engine<br/>C-02 / C-03]
        RAG --> DualPol[Dual-Polarity Search<br/>Why vs Why-Not]
        DualPol --> TDEC[1-Hop TDEC Closure<br/>Footnotes & Exclusions]
        TDEC --> Verifier[Evidence Verifier & Linker<br/>C-04 / N-14B Invariant Checks]
        Verifier -->|Verified EvidenceBundle| PricingSidecar[Pricing Engine Sidecar<br/>6 Sanity Checks & Optimization]
        PricingSidecar --> Gate[Compliance Gate C-11<br/>POL-08 Speech Standards]
    end

    subgraph Storage["Lớp Lưu Trữ Bền Vững"]
        RAG --> PGVector[(PostgreSQL + pgvector<br/>Supabase HNSW)]
        PricingSidecar --> AuditLog[(Append-Only Audit Trail<br/>Hash Chain)]
    end

    Gate -->|Certified Quote Response| Frontend
```

---

## 4. Cấu Trúc Thư Mục Chuẩn Hóa (Codebase Map)

Tuân thủ tuyệt đối quy hoạch phân công kiến trúc [`CODEBASE_MAP.md`](file:///Users/mac/AITC/PROJECT/report/TeamDocs/CODEBASE_MAP.md):

```text
P-096/
├── src/
│   ├── services/
│   │   ├── rag/             # [C-02/C-03] Ingestion, Bi-Encoder, Cross-Encoder, Dual-Polarity, pgvector
│   │   ├── evidence/        # [C-04] Claim Evidence Linker, Coordinate Parser, TDEC Closure, Verifier
│   │   ├── compliance/      # [C-11] 3-Checkpoint Compliance Gate, POL-08 Speech Standards
│   │   └── llm.py           # LLM client với chuỗi fallback
│   ├── agents/
│   │   ├── tools/           # policy_search.py (LangGraph tool tra cứu chính sách)
│   │   ├── nodes/           # Các node xử lý hội thoại
│   │   ├── graph.py         # StateGraph orchestration
│   │   └── state.py         # State schema
│   ├── api/
│   │   ├── routes.py        # REST API endpoints
│   │   └── pricing_mock.py  # Consumer xác thực EvidenceBundle
│   ├── db/
│   │   ├── session.py       # Async SQLAlchemy session
│   │   ├── models.py        # Bảng policy_nodes, policy_edges
│   │   └── init_db.py       # Khởi tạo schema & pgvector HNSW
│   ├── models/              # Data contracts: pec_contracts.py, rag_schemas.py
│   ├── config.py            # Cấu hình Pydantic settings (.env)
│   └── main.py              # Điểm khởi chạy ứng dụng FastAPI
├── tests/                   # 455 test (pytest tests/ -q) — chạy ~10 s
│   ├── test_services/       # RAG, evidence, compliance, pricing sidecar, LLM
│   ├── test_agents/         # graph Pre-Sales/Official Quote, ReAct Copilot
│   ├── test_api/            # routers, hợp đồng endpoint, copilot, admin CP
│   └── test_pricing_sidecar/ # Enums, input/output contracts, arithmetic
├── scripts/
│   ├── seed_data.py         # [C-03] Nạp Markdown chính sách vào PostgreSQL pgvector
│   ├── run_eval.py          # [C-02] Đánh giá benchmark RAG tự động
│   └── setup_hooks.sh       # Cài đặt Git hooks đồng bộ AI logs
├── eval/                    # Dữ liệu đo lường, kịch bản benchmark & kết quả đánh giá
└── docs/                    # Sơ đồ kiến trúc & cẩm nang kỹ thuật
```

---

## 5. Hướng Dẫn Cài Đặt & Chạy Hệ Thống (Quickstart)

### Yêu cầu tiên quyết
- Python 3.11+
- PostgreSQL với extension `pgvector` (hoặc tài khoản Supabase)

### Bước 1: Khởi tạo môi trường ảo & cài đặt thư viện
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Bước 2: Cấu hình biến môi trường
Tạo file `.env` từ `.env.example`:
```bash
cp .env.example .env
```
Cập nhật chuỗi kết nối Database Supabase / PostgreSQL:
```env
DATABASE_URL=postgresql+asyncpg://postgres.xhaciuhasbaurovchlak:YOUR-PASSWORD@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres
OPENAI_API_KEY=your_api_key_here
```

### Bước 3: Khởi tạo bảng dữ liệu & Seed chính sách
```bash
# Khởi tạo extension pgvector và các bảng
python -m src.db.init_db

# Nạp dữ liệu 10 bộ chính sách bán hàng vào pgvector
python scripts/seed_data.py --dir ../report/Dataset/policies_md
```

### Bước 4: Chạy Backend Server
```bash
uvicorn src.main:app --reload --port 8000
```
- API Documentation (Swagger UI): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

---

## 6. Kiểm Thử & Đo Lường Chất Lượng (Quality & Eval)

### Chạy Toàn Bộ Test Suite (477 passed, ~11 s)
```bash
.venv/bin/pytest tests/ -q
```

### Chạy Test Frontend (22 test trên MSW, không cần backend)
```bash
cd frontend && npm test
```

### Kiểm Tra Chuẩn Code (Ruff Clean)
```bash
.venv/bin/ruff check src/ tests/ scripts/
```

### Chạy Benchmark Đánh Giá RAG
```bash
python scripts/run_eval.py
```
**Kết quả Benchmark mới nhất:**
- **Time-Travel Leakage:** `0.00%` (Không rò rỉ chính sách tương lai/quá hạn)
- **Clause-Level Recall@k:** `100.00%`
- **Conflict Completeness:** `100.00%`
- **Cryptographic Hash Integrity:** `100.00%`
- **Mean Retrieval Latency:** `4.78 ms`

### Chạy Eval Trợ Lý Copilot (32 câu vàng, offline)
```bash
.venv/bin/python scripts/run_copilot_eval.py
```
**Kết quả mới nhất** (`eval/results/copilot_report.json`):

| Chỉ số | Ngưỡng CI | Kết quả |
| :--- | :--- | :--- |
| Tool selection accuracy | ≥ 0.90 | **1.00** |
| Citation precision | ≥ 0.90 | **1.00** |
| Hallucination rate | ≤ 0.05 | **0.00** |
| p95 latency | < 2000 ms | **4 ms** |

---

## 7. Đội Ngũ Phát Triển (Team P-096)

| Thành viên | Vai trò | Phân công phụ trách chính |
| :--- | :--- | :--- |
| **Trần Chí Vĩ** | Core AI / RAG Engineer | **C-02, C-03, C-04, C-11:** PEC-RAG Core, TDEC Closure, Evidence Verifier, Compliance Gate, `scripts/seed_data.py`, `policy_search.py` |
| **Tạ Việt Cường** | TechLead / Backend | **C-01, C-05, C-07, C-09:** Data Contracts, Orchestrator Graph, Approval KMS, Hash-chain Audit Trail |
| **Văn Duy** | Pricing Sidecar Engineer | **C-06, Benchmark:** Pricing Engine Sidecar (Rust/Python), 6 Sanity Checks, Multi-Objective Ranking |
| **Phương Đuy** | Frontend / Fullstack | **C-08, C-10:** Frontend UI Next.js, Lead Dossier Handover, Compliance UI Feedback |
