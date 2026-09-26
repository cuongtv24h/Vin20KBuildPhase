# KẾ HOẠCH THỰC THI CHI TIẾT DÀNH CHO TECHLEAD (TECHLEAD MASTER IMPLEMENTATION PLAN)
## DỰ ÁN: PRICEPOLICY AI AGENT – NỀN TẢNG BẢO CHỨNG ĐỊNH GIÁ & QUẢN TRỊ CHÍNH SÁCH BÁN HÀNG VLANDFUTURE

**Mã tài liệu:** TL-PLAN-DETAIL-01  
**Mã sản phẩm:** BDSVLandFuture-06  
**Vai trò sở hữu:** **TechLead / Principal System Architect & Agentic Orchestrator**  
**Tài liệu tham chiếu chuẩn:** 
- [mydoc/ImplementPlan.md](file:///d:/VinUni/P-096/mydoc/ImplementPlan.md) (Sprint Action Plan)
- [mydoc/Implement_plan_detail.md](file:///d:/VinUni/P-096/mydoc/Implement_plan_detail.md) (Detailed Implementation Plan)
- [mydoc/3.architecture-design.md](file:///d:/VinUni/P-096/mydoc/3.architecture-design.md) (Architecture Design v2.2)
- [mydoc/4.1-technical-architecture-runtime-deployment.md](file:///d:/VinUni/P-096/mydoc/4.1-technical-architecture-runtime-deployment.md) (Runtime & Topology v2.0)
- [mydoc/4.2-domain-data-financial-design.md](file:///d:/VinUni/P-096/mydoc/4.2-domain-data-financial-design.md) (Domain Data & Financial Design v2.2)
- [mydoc/4.3-agent-stategraph-workflow-design.md](file:///d:/VinUni/P-096/mydoc/4.3-agent-stategraph-workflow-design.md) (StateGraph & Workflow v2.2)
- [mydoc/4.4-api-event-tool-contracts.md](file:///d:/VinUni/P-096/mydoc/4.4-api-event-tool-contracts.md) (API, Event & Tool Contracts v2.2)
- [mydoc/baocaothhaydoi.mv](file:///d:/VinUni/P-096/mydoc/baocaothhaydoi.mv) (Living Changelog v2.2)

**Trạng thái:** **ACTIVE — BASELINE EXECUTION PLAN FOR TECHLEAD**  
**Thời gian áp dụng:** 10 Ngày Sprint MVP (Phân bổ 4 thành viên: TechLead + Dev 1 + Dev 2 + Dev 3)

---

## I. TỔNG QUAN VAI TRÒ & PHẠM VI SỞ HỮU (OWNERSHIP & BOUNDARIES)

### 1.1 Trách nhiệm Hạt nhân của TechLead (Core Mandates)
Trong mô hình phát triển song song của nhóm 4 thành viên, TechLead vừa là **Kiến trúc sư trưởng (System Architect)** giữ vững tính toàn vẹn hệ thống, vừa là **Kỹ sư lõi (Core Engineer)** trực tiếp xây dựng bộ máy điều phối StateGraph, các chốt chặn phê duyệt mật mã và khung tích hợp dữ liệu:
1. **Quản trị Kiến trúc & Hợp đồng (Architecture & Contract Freeze):** Đóng băng 29 Canonical REST Endpoints, 12 Agent-Visible Tools, các Pydantic Schemas v2, hệ thống Canonical Enums (6 Objectives, Statuses, Tiers) và Mock API Server nhằm unblock hoàn toàn 3 Developers từ Ngày 1.
2. **Xây dựng 2 Đồ thị Điều phối LangGraph StateGraph lõi:**
   - `C-09` — **Pre-Sales Advisory StateGraph:** 11 nodes, checkpoint namespace `PRE_SALES`, thread format `presales:{tenant_id}:{session_id}`, 3 điểm ngắt HITL, session TTL 1800s, xuất bản ước tính PDF có watermark tham khảo không ký số.
   - `C-01` — **Official Quote StateGraph:** 20 nodes, checkpoint namespace `DEFAULT`, thread format `quote:{tenant_id}:{quote_id}`, 3 điểm ngắt HITL, tái thẩm định dữ liệu từ Lead Dossier, điều phối Sidecar UDS, Safe Decision Gate, Revision Loop và Safe Abstention Gate.
3. **Thiết lập Chốt chặn Phê duyệt Mật mã & Quản trị (Cryptographic Approval & Governance):**
   - `C-05` — **HITL Review & Cryptographic Approval Gate:** Mô hình Sign-Before-Commit, ký số bất đối xứng Ed25519 qua KMS Server Attestation, cơ chế Atomic Commit-Discard, phân quyền Separation of Duties (SoD).
   - `C-07` — **Append-Only Audit Trail & Verification Engine:** Chuỗi băm liên hoàn chống chu trình (Anti-Cyclic Hash Chain), thuật toán kiểm định Genesis Verification, bảo đảm tính bất biến tuyệt đối.
4. **Quản lý Hạ tầng, Triển khai & Tích hợp (Runtime, Gateway & Outbox):**
   - API Gateway bảo mật: Idempotency Key Engine, Optimistic Concurrency Control (OCC ETag/If-Match), RBAC, Rate Limiting.
   - Giao thức Server-Sent Events (SSE) hỗ trợ replay sự kiện (`Last-Event-ID`).
   - Transactional Outbox Pattern & Background PDF Generation Worker.
   - Quản trị tích hợp toàn diện (End-to-End Integration, Failure Recovery Testing và Tổng duyệt Showcase Demo).

---

### 1.2 Danh mục Logic Components Trực tiếp Phụ trách
TechLead sở hữu trực tiếp 5/11 Logic Components và đồng sở hữu 2 components với các thành viên:

| Mã Component | Tên Logic Component | Vai trò TechLead | Cộng tác / Phối hợp |
| :--- | :--- | :--- | :--- |
| `C-01` | **Official Quote StateGraph Orchestrator** | **Chủ trì 100%** | Nhận Math từ Dev 2 (`C-06`), Evidence từ Dev 1 (`C-04`), UI từ Dev 3 (`C-08`) |
| `C-02` | **Time-Travel & Policy Snapshot Engine** | **Đồng chủ trì** | Hợp tác cùng Dev 1 (Dev 1 lo pgvector HNSW, TechLead lo transaction context & OCC) |
| `C-05` | **HITL Review & Cryptographic Approval Gate** | **Chủ trì 100%** | Kết nối KMS Server Signer Ed25519, Manager Approval Dashboard của Dev 3 (`C-08`) |
| `C-07` | **Append-Only Audit Trail & Verification Engine** | **Chủ trì 100%** | Cung cấp public verification API, Dev 1 phối hợp audit claim evidence |
| `C-09` | **Pre-Sales Advisory StateGraph Engine** | **Đồng chủ trì** | TechLead dựng StateGraph lõi + checkpointing, Dev 3 tích hợp Web Chat UI |

---

### 1.3 Bộ 3 Spikes Kỹ thuật Sở hữu Trực tiếp
TechLead trực tiếp giải quyết 3/6 Spikes kỹ thuật có độ rủi ro kiến trúc cao nhất:
- **Spike 2: LangGraph AsyncPostgresSaver Checkpointing, Interrupt & State Replay** (Đảm bảo đồ thị lưu trạng thái bền vững vào PostgreSQL 16, ngắt chờ người dùng và resume chuẩn xác qua `Command(resume=...)`).
- **Spike 3: Asymmetric Cryptographic Server Attestation (Ed25519) & Atomic Commit Discard** (Đảm bảo khóa riêng KMS an toàn, chữ ký số gắn chặt với snapshot, chống phát tán chữ ký mồ côi nếu DB crash).
- **Spike 4: Per-Quote Anti-Cyclic Hash Chain & Genesis Verification** (Đảm bảo log kiểm toán liên hoàn $H_i = \text{SHA256}(H_{i-1} \parallel \text{Payload}_i)$, ngăn chặn sửa lén lịch sử).

Đồng thời, TechLead giám sát và nghiệm thu 3 Spikes của đồng đội:
- **Spike 1** (Dev 2): Pricing Sidecar UDS Latency $< 5\text{ms}$ & Exact Match 15 Golden Cases.
- **Spike 5** (Dev 3): Pre-Sales Session Checkpointing, TTL 1800s & Web Mobile Interrupts.
- **Spike 6** (Dev 1): Sales Message Compliance Verification Gate & Final Send Enforcement (`POST /api/v1/messages/send`).

---

### 1.4 Ma trận Phân định Mã nguồn (Codebase Directory Layout)
Để bảo đảm 4 thành viên code song song mà không giẫm chân nhau, TechLead thiết lập và bảo vệ phân vùng thư mục:

```text
/backend/
├── contracts/               [CHỦ TRÌ: TechLead] Pydantic Schemas v2, Canonical Enums, DTOs, Error Catalog
├── orchestrator/            [CHỦ TRÌ: TechLead] LangGraph StateGraphs (Official & Pre-Sales), Checkpointing
├── governance/              [CHỦ TRÌ: TechLead] KMS Server Attestation, Anti-Cyclic Audit Trail, SoD Gate
├── gateway/                 [CHỦ TRÌ: TechLead] FastAPI Apps, Idempotency Engine, OCC, RBAC, SSE Router
├── services/
│   ├── rag/                 [PHỤ TRÁCH: Dev 1] Ingestion Pipeline, Time-Travel SQL, F9 Policy Rules
│   └── compliance/          [PHỤ TRÁCH: Dev 1] F4 Coordinate Parser, F8 Message Compliance Gate
├── pricing_sidecar/         [PHỤ TRÁCH: Dev 2] UDS Socket Server, Decimal Precision, FCS v2.6 Scenarios
└── workers/                 [CHỦ TRÌ: TechLead] Transactional Outbox Consumer (ARQ), Watermark PDF Engine
/frontend/                   [PHỤ TRÁCH: Dev 3] Next.js 14 App Router, Workspaces, SSE Client
/migrations/                 [CHỦ TRÌ: TechLead] PostgreSQL 16 + pgvector DDL Schemas & Triggers
/tests/
│   ├── benchmarks/          [PHỤ TRÁCH: Dev 2] 15 Golden Cases Test Suite
│   ├── integration/         [CHỦ TRÌ: TechLead] End-to-End StateGraph & API Gateway Tests
│   └── security/            [CHỦ TRÌ: TechLead] Failure Injection, Idempotency & Tamper Tests
```

---

### 1.5 10 Nguyên tắc Bất biến (Zero-Trust Architectural Invariants)
TechLead có nghĩa vụ thực thi nghiêm ngặt 10 nguyên tắc này trong mọi pull request:
1. **LLM không bao giờ tự tính số tiền:** Toàn bộ phép tính tài chính phải đi qua Sidecar UDS (`decimal.Decimal` 28 chữ số).
2. **Pre-Sales Plan không phải là Báo giá Chính thức:** Bản ước tính Pre-Sales chỉ mang tính tham khảo, bắt buộc đóng watermark chìm.
3. **Pre-Sales tuyệt đối cách ly khỏi KMS & Outbox:** Không gọi KMS Ed25519, không ghi vào `transactional_outbox`, không sinh mã QR cam kết.
4. **Official Quote bắt buộc Tái thẩm định & Tính toán lại:** Khi chuyển đổi từ Lead Dossier sang Báo giá chính thức, hệ thống phải chạy lại toàn bộ quy tắc chính sách tại thời điểm giao dịch thực.
5. **Dữ liệu Nghiệp vụ của Báo giá Cũ là Bất biến (Immutable):** Không UPDATE đè lên payload giá cũ; mọi điều chỉnh phải sinh `quote_version` mới.
6. **Mọi khẳng định tài chính (Claim) phải có Dẫn chứng (Evidence):** Khẳng định không có mỏ neo tọa độ điều khoản (`SourceCoordinate`) phải bị đánh dấu `UNSUPPORTED`.
7. **Chốt chặn Gửi tin Tuân thủ F8 thực thi tại Backend:** Giao diện không được tự ý gửi tin hoặc copy tự do nếu chưa có chữ ký băm kiểm định hợp lệ (`POST /api/v1/messages/send`).
8. **Công cụ hiển thị cho Agent (Agent Tools) là Read-Only:** Tuyệt đối cấm Agent-Visible Tools thực hiện thao tác ghi đè dữ liệu quản trị (governance data).
9. **Transactional Outbox là Nguồn Chân lý Bền vững:** Worker chỉ là Consumer có thể retry; lỗi worker không làm mất dữ liệu sự kiện.
10. **Nguyên tắc Phân quyền Phê duyệt Độc lập (Separation of Duties - SoD):** Sale tạo báo giá tuyệt đối không có quyền tự phê duyệt báo giá của chính mình.

---

## II. BẢN ĐỒ LỘ TRÌNH 6 PHASES THEO NGÀY (PHASE-BY-PHASE ROADMAP)

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        LỘ TRÌNH THỰC THI 10 NGÀY CỦA TECHLEAD (6 PHASES)                               │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ PHASE 0 (Ngày 1):     Contract Freeze, Khung Hạ tầng Docker, Mock API & Unblock 3 Devs (M0)           │
│ PHASE 1 (Ngày 2–3):   R&D 3 Spikes Kỹ thuật Lõi & Xây dựng StateGraph Skeleton (M1)                   │
│ PHASE 2 (Ngày 4–5):   Pre-Sales StateGraph, Checkpointing, Interrupts & Handoff Lead Dossier (M2)      │
│ PHASE 3 (Ngày 6–7):   Official Quote StateGraph, Tái thẩm định & Tích hợp Sidecar UDS (M3)             │
│ PHASE 4 (Ngày 8):     KMS Server Attestation Ed25519, Anti-Cyclic Audit Trail & Outbox Worker (M4)    │
│ PHASE 5 (Ngày 9–10):  Ghép nối End-to-End Toàn hệ thống, Failure Recovery & Tổng duyệt Demo (M5)       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## III. CHI TIẾT CÔNG VIỆC THỰC HIỆN THEO TỪNG PHASE

---

### PHASE 0 (NGÀY 1): CONTRACT FREEZE, KHUNG HẠ TẦNG & UNBLOCK TEAM (MILESTONE M0)

#### 1. Mục tiêu Kỹ thuật & Đầu ra (Deliverables)
- Khóa cứng toàn bộ Contract package dùng chung cho cả 4 thành viên.
- Khởi tạo Repository, Docker Compose profile MVP, PostgreSQL 16 DDL migration ban đầu.
- Vận hành Mock API Server trả về đầy đủ 29 REST Endpoints và SSE event envelope mẫu để Dev 1, Dev 2, Dev 3 code độc lập ngay lập tức mà không phải chờ đợi.

#### 2. Chi tiết Công việc Cụ thể của TechLead

##### Đầu việc TL-0.1: Chuẩn hóa & Đóng băng Danh mục Canonical Enums
- **Tập tin tạo:** `/backend/contracts/enums.py`
- **Nội dung triển khai:**
  - `PreSalesSessionStatus`: `ACTIVE`, `WAITING_FOR_CUSTOMER_INPUT`, `WAITING_FOR_CONSTRAINT_CONFIRMATION`, `WAITING_FOR_HANDOFF_CONSENT`, `HANDED_OFF`, `EXPIRED`, `ABANDONED`.
  - `LeadDossierStatus`: `NEW`, `ASSIGNED`, `CONTACTED`, `QUALIFIED`, `CONVERTED_TO_QUOTE`, `EXPIRED`, `DISQUALIFIED`.
  - `QuoteWorkflowStatus`: `DRAFT`, `NEEDS_INPUT`, `ANALYZING`, `EXCEPTION_INPUT`, `CALCULATING`, `CALCULATION_FAILED`, `READY_FOR_REVIEW`, `NEEDS_REVISION`, `ABSTAINED`, `BLOCKED`, `REJECTED`, `APPROVED`, `SUPERSEDED`, `REVOKED`.
  - `ApprovalStatus`: `NOT_REQUIRED`, `PENDING`, `ATTESTED`, `APPROVED`, `APPROVAL_FAILED`, `REJECTED`, `REVISION_REQUESTED`.
  - `PdfStatus`: `NOT_REQUESTED`, `PENDING`, `GENERATING`, `ISSUED`, `FAILED`, `RETRYING`, `MANUAL_INTERVENTION`.
  - `PolicyDecisionStatus`: `ELIGIBLE`, `NOT_ELIGIBLE`, `CONFLICT`, `AMBIGUOUS`, `EXPIRED`.
  - `PolicyRuleStatus`: `DRAFT`, `APPROVED_FOR_USE`, `ACTIVE`, `RETIRED`.
  - `ComplianceStatus`: `DRAFT`, `CHECKING`, `SUPPORTED`, `CONDITIONAL`, `UNSUPPORTED`, `PROHIBITED`, `EXPIRED`, `SUPERSEDED`.
  - `ComplianceTier`: `TIER_1_GREEN`, `TIER_2_YELLOW`, `TIER_3_RED`, `TIER_4_BLACK`.
  - `OptimizationObjective` (Chuẩn hóa đúng **6 Mục tiêu Tối ưu theo ADR-021**):
    * `MIN_NET_PRICE`
    * `MIN_INITIAL_CASH`
    * `MIN_MONTHLY_BURDEN`
    * `MIN_TOTAL_CASH_OUTFLOW`
    * `MAX_BENEFIT_VALUE`
    * `EARLY_HANDOVER`

##### Đầu việc TL-0.2: Chuẩn hóa Bộ Pydantic Schemas v2 & DTOs
- **Tập tin tạo:** `/backend/contracts/schemas.py`, `/backend/contracts/events.py`
- **Nội dung triển khai:**
  - Định nghĩa `CustomerConstraint`, `CalculationInput`, `CalculationResult`, `ScenarioDetail`.
  - Định nghĩa `EvidenceBackedClaim` và `SourceCoordinate` phục vụ F4 Claim-Level Traceability.
  - Định nghĩa `PreSalesPlanResponse`, `LeadDossierResponse`, `ConsentRequest`.
  - Định nghĩa `ComplianceCheckRequest`, `ComplianceCheckResponse`, `SendMessageRequest`.
  - Định nghĩa `OfficialQuoteCreateRequest`, `ApprovalRequest`, `RevisionRequest`.
  - Định nghĩa `SseEventEnvelope`:
    ```python
    class SseEventEnvelope(BaseModel):
        event_id: str
        event_seq: int
        event_type: str
        session_id: Optional[str] = None
        quote_id: Optional[str] = None
        quote_version: Optional[int] = None
        schema_version: str = "sse-event.v1"
        correlation_id: str
        occurred_at: datetime
        payload: Dict[str, Any]
    ```

##### Đầu việc TL-0.3: Chuẩn hóa Bảng Mã lỗi Hệ thống (Error Catalog)
- **Tập tin tạo:** `/backend/contracts/errors.py`
- **Nội dung triển khai:**
  - Đóng gói 13 mã lỗi chuẩn: `INPUT_VALIDATION_ERROR`, `MISSING_TRANSACTION_DATE`, `POLICY_NOT_FOUND`, `POLICY_EXPIRED`, `POLICY_CONFLICT_UNRESOLVED`, `FINANCIAL_SANITY_FAILED`, `STALE_QUOTE_VERSION`, `INVALID_STATE_TRANSITION`, `IDEMPOTENCY_PROCESSING`, `IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH`, `EXPLANATION_VALIDATION_FAILED`, `COMPLIANCE_SEND_BLOCKED`, `PDF_NOT_READY`.
  - Cấu trúc Error Envelope: `{"error_code": str, "message": str, "correlation_id": str, "details": dict}`.

##### Đầu việc TL-0.4: Triển khai Mock API Server & Khung OpenAPI 3.1
- **Tập tin tạo:** `/backend/mock_server/main.py`
- **Nội dung triển khai:**
  - Khởi chạy ứng dụng FastAPI độc lập mô phỏng trọn vẹn 29 Endpoints.
  - Trả dữ liệu JSON mock tĩnh nhưng đúng 100% schema và enum cho Happy Path và Error Paths.
  - Cung cấp endpoint xuất bản `/openapi.json` để Dev 3 tự động sinh TypeScript SDK client.

##### Đầu việc TL-0.5: Thiết lập Môi trường Triển khai MVP Docker Compose & Cơ sở Dữ liệu
- **Tập tin tạo:** `docker-compose.yml`, `/migrations/001_initial_schema.sql`, `.env.example`
- **Nội dung triển khai:**
  - Cấu hình dịch vụ Docker: `postgres` (PostgreSQL 16 + pgvector), `redis` (Cache & ARQ broker), `minio` (S3 emulator cho PDF & Artifacts), `mock-api`.
  - Tạo DDL khởi tạo các bảng: `projects`, `units`, `policy_documents`, `policy_rules` (kèm trigger test gate), `pre_sales_sessions`, `customer_consents`, `pre_sales_plans`, `lead_dossiers`, `quotes`, `quote_snapshots`, `quote_audit_events`, `transactional_outbox`, `compliance_checks`.

#### 3. Phụ thuộc & Lưu ý Phối hợp trong Phase 0
- **Phụ thuộc vào ai?** Không phụ thuộc ai. TechLead là người đi đầu (pioneer) mở đường cho cả dự án.
- **Ai đang chờ TechLead?**
  - **Dev 1:** Chờ Schema DDL và cấu trúc bảng `policy_documents`, `policy_rules`, `SourceCoordinate` để bắt đầu viết script nạp dữ liệu (Ingestion Pipeline).
  - **Dev 2:** Chờ `CalculationInput`, `CalculationResult`, `OptimizationObjective` và danh mục scenario chuẩn để dựng Math Engine.
  - **Dev 3:** Chờ Mock API Server và file `openapi.json` để dựng giao diện Next.js và component cards.
- **Rủi ro kỹ thuật & Dự phòng:**
  - *Rủi ro:* Schema thay đổi giữa chừng làm vỡ code của 3 Developers.
  - *Dự phòng:* Thực hiện "Contract Freeze" nghiêm ngặt cuối Ngày 1. Bất kỳ sự thay đổi schema nào sau Ngày 1 phải qua phiên họp khẩn cấp và cập nhật vào [mydoc/baocaothhaydoi.mv](file:///d:/VinUni/P-096/mydoc/baocaothhaydoi.mv).

#### 4. Tiêu chuẩn Nghiệm thu (DoD Phase 0)
- [ ] Chạy `docker compose up -d` khởi động thành công PostgreSQL 16 pgvector, Redis, MinIO và Mock Server.
- [ ] Truy cập `http://localhost:8000/docs` hiển thị đầy đủ 29 Endpoints không có lỗi validation.
- [ ] Lệnh `npm run codegen` bên phía Frontend sinh ra TypeScript types khớp 100% với Pydantic models.
- [ ] Toàn bộ 4 thành viên xác nhận ký duyệt biên bản Contract Freeze.

---

### PHASE 1 (NGÀY 2–3): R&D 3 SPIKES KỸ THUẬT LÕI & DỰNG KHUNG STATEGRAPH (MILESTONE M1)

#### 1. Mục tiêu Kỹ thuật & Đầu ra (Deliverables)
- Vượt qua 3 Spikes kỹ thuật rủi ro cao của TechLead (Spike 2: LangGraph Checkpointing, Spike 3: Ed25519 KMS Signer, Spike 4: Anti-Cyclic Hash Chain).
- Dựng xong khung sườn 2 StateGraphs (`PreSalesGraph` 11 nodes và `OfficialQuoteGraph` 20 nodes) với các state models Pydantic.
- Thiết lập API Gateway Middleware: Xử lý Idempotency Key, OCC ETag/If-Match và Correlation ID.

#### 2. Chi tiết Công việc Cụ thể của TechLead

##### Đầu việc TL-1.1: Thực thi Spike 2 — LangGraph AsyncPostgresSaver Checkpointing & Interrupts
- **Tập tin tạo:** `/backend/orchestrator/checkpointer.py`, `/tests/spikes/test_spike2_checkpointing.py`
- **Nội dung triển khai:**
  - Kết nối `AsyncPostgresSaver` vào PostgreSQL pool.
  - Cấu hình namespace cách ly: `PRE_SALES` (cho Pre-Sales sessions) và `DEFAULT` (cho Official Quotes).
  - Kiểm thử cơ chế `interrupt()` tại các điểm dừng và resume bằng `Command(resume=...)`.
  - Kiểm thử khả năng chịu lỗi: Kill process worker giữa chừng, khởi động lại và resume chính xác từ checkpoint cuối cùng trong DB mà không bị lặp node.

##### Đầu việc TL-1.2: Thực thi Spike 3 — Asymmetric Cryptographic KMS Attestation (Ed25519)
- **Tập tin tạo:** `/backend/governance/kms_signer.py`, `/tests/spikes/test_spike3_kms_attestation.py`
- **Nội dung triển khai:**
  - Sử dụng thư viện `cryptography.hazmat.primitives.asymmetric.ed25519`.
  - Xây dựng module ký số: Nhận snapshot hash SHA-256 của báo giá, tạo chữ ký số Ed25519 bằng private key được bảo vệ.
  - Xây dựng mô hình **Atomic Commit-Discard**: Quá trình ký diễn ra trong bộ nhớ; chỉ ghi nhận chữ ký vào cơ sở dữ liệu đồng thời với bản ghi `quote_audit_events` và `transactional_outbox` trong cùng 1 transaction ACID. Nếu database commit thất bại, chữ ký bị hủy bỏ ngay lập tức (không sinh orphan signature).
  - Cung cấp endpoint công khai `GET /api/v1/verification/public-key` và hàm verify chữ ký bằng public key.

##### Đầu việc TL-1.3: Thực thi Spike 4 — Per-Quote Anti-Cyclic Hash Chain & Genesis Verification
- **Tập tin tạo:** `/backend/governance/audit_chain.py`, `/tests/spikes/test_spike4_hash_chain.py`
- **Nội dung triển khai:**
  - Thuật toán băm liên hoàn: 
    * Bản ghi đầu tiên (Genesis Event): $H_0 = \text{SHA256}(\text{"GENESIS"} \parallel \text{quote\_id} \parallel \text{payload}_0)$.
    * Bản ghi thứ $i$: $H_i = \text{SHA256}(H_{i-1} \parallel \text{event\_type} \parallel \text{timestamp} \parallel \text{payload}_i)$.
  - Bảng `quote_audit_events` thiết lập ràng buộc khóa ngoại `prev_event_hash` trỏ về `event_hash` của sự kiện trước đó của cùng `quote_id`.
  - Xây dựng hàm `verify_audit_integrity(quote_id)` duyệt từ Genesis đến Leaf; nếu phát hiện bất kỳ sai lệch băm nào lập tức raise `TAMPER_DETECTED_ERROR`.

##### Đầu việc TL-1.4: Xây dựng Bộ khung StateGraph Skeletons (20 Nodes & 11 Nodes)
- **Tập tin tạo:** 
  - `/backend/orchestrator/pre_sales_graph.py` (StateGraph 11 nodes: PS-01 đến PS-11).
  - `/backend/orchestrator/official_quote_graph.py` (StateGraph 20 nodes: N-01 đến N-20).
- **Nội dung triển khai:**
  - Định nghĩa Pydantic State Schema: `PreSalesState` và `OfficialQuoteState` kế thừa từ `TypedDict`.
  - Khai báo tất cả các nodes và conditional edges; gắn mock logic vào từng node để đảm bảo đồ thị compile thành công (`graph.compile(checkpointer=checkpointer)`).
  - Định nghĩa các điểm ngắt `interrupt()` cho cả 2 đồ thị.

##### Đầu việc TL-1.5: Xây dựng Middleware API Gateway (Idempotency & OCC)
- **Tập tin tạo:** `/backend/gateway/middleware.py`
- **Nội dung triển khai:**
  - **Idempotency Engine:** Bắt header `Idempotency-Key`. Lưu hash của payload request vào Redis với TTL 86400s. Nếu phát hiện trùng key nhưng khác payload $\rightarrow$ Trả `409 Conflict` (`IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH`). Nếu đang xử lý dở dang $\rightarrow$ Trả `409 Conflict` (`IDEMPOTENCY_PROCESSING`).
  - **OCC Engine:** Bắt header `If-Match` chứa ETag (định dạng `W/"<quote_version>"`). Đối chiếu với version hiện tại trong database; nếu không khớp $\rightarrow$ Trả `412 Precondition Failed` (`STALE_QUOTE_VERSION`).

#### 3. Phụ thuộc & Lưu ý Phối hợp trong Phase 1
- **Phụ thuộc vào ai?**
  - Giám sát Dev 2 hoàn thành **Spike 1** (UDS sidecar socket server). Cần Dev 2 bàn giao đường dẫn socket `/var/run/pricing/engine.sock` và script test độ trễ $< 5\text{ms}$.
  - Giám sát Dev 1 chuẩn bị dữ liệu RAG (pgvector) để sẵn sàng cắm vào node `resolve_active_policy`.
- **Ai đang chờ TechLead?**
  - **Dev 3:** Chờ kết quả Spike 2 để biết chính xác format của `resume_token` và payload SSE khi gặp interrupt.
- **Rủi ro kỹ thuật & Dự phòng:**
  - *Rủi ro:* `AsyncPostgresSaver` của LangGraph bị nghẽn connection pool khi nhiều request đồng thời.
  - *Dự phòng:* Cấu hình connection pool riêng cho LangGraph checkpointer (`max_connections=20`, `timeout=10s`) tách biệt với pool của API Gateway.

#### 4. Tiêu chuẩn Nghiệm thu (DoD Phase 1)
- [ ] 3 bài test unit test của Spike 2, Spike 3, Spike 4 chạy Pass 100%.
- [ ] Biên bản nghiệm thu Spike 1 của Dev 2 đạt 15/15 Golden Cases với sai lệch $\Delta = 0$ VNĐ.
- [ ] Cả 2 StateGraph compile thành công mà không có chu trình chết hoặc node mồ côi.
- [ ] Test middleware Idempotency và OCC trả về đúng các mã HTTP status 409, 412 khi cố tình inject lỗi.

---

### PHASE 2 (NGÀY 4–5): PRE-SALES STATEGRAPH, CHECKPOINTING & HANDOFF LEAD (MILESTONE M2)

#### 1. Mục tiêu Kỹ thuật & Đầu ra (Deliverables)
- Hoàn thiện toàn bộ logic nghiệp vụ của `PreSalesGraph` (`C-09`): từ bóc tách nhu cầu tài chính $\rightarrow$ tra cứu chính sách $\rightarrow$ gọi Pricing Sidecar $\rightarrow$ sinh 3 kịch bản kèm watermark PDF.
- Hoàn thiện cổng đồng thuận điện tử (`C-10` Consent Gate) và tạo `LeadDossier` bàn giao sang Sales Dashboard.
- Nối luồng Server-Sent Events (SSE) thời gian thực truyền tiến trình suy luận của Agent về giao diện Web Mobile của Dev 3.

#### 2. Chi tiết Công việc Cụ thể của TechLead

##### Đầu việc TL-2.1: Lập trình Chi tiết 11 Nodes của `PreSalesGraph`
- **Tập tin hoàn thiện:** `/backend/orchestrator/pre_sales_graph.py`
- **Nội dung triển khai chi tiết từng node:**
  - `PS-01 (Init)`: Khởi tạo phiên, gán `session_id`, thread id `presales:{tenant_id}:{session_id}`, đặt TTL 1800s vào Redis.
  - `PS-02 (Input)`: Nhận tin nhắn chat của khách hàng.
  - `PS-03 (Extract)`: Gọi Agent Tool `extract_customer_constraints` bóc tách: ngân sách tự có, thu nhập hàng tháng, dự án quan tâm, loại căn, mục tiêu tối ưu.
  - `PS-04 (Validate)`: Kiểm tra tính hợp lệ số học của các ràng buộc; nếu thiếu thông tin cốt lõi $\rightarrow$ Rẽ nhánh về `interrupt(WAITING_FOR_CUSTOMER_INPUT)`.
  - `PS-05 (Resolve Policy)`: Gọi service RAG của Dev 1 (`retrieve_policy_by_date`) với `transaction_date` hiện tại, lấy danh sách điều khoản chính sách hiệu lực.
  - `PS-06 (Conflict Gate)`: Kiểm tra xung đột chính sách; nếu phát hiện xung đột cấm $\rightarrow$ Rẽ sang node `PS-11 (Safe Abstain)`.
  - `PS-07 (Calculate)`: Chuẩn hóa `PricingInput`, gửi qua Unix Domain Socket tới Sidecar của Dev 2 (`C-06`) để tính 3 kịch bản: `PA-CHUAN`, `PA-NHANH`, `PA-VAY`.
  - `PS-08 (Rank)`: Thực thi thuật toán xếp hạng tất định theo 1 trong 6 Canonical Objectives của khách.
  - `PS-09 (Build Plan)`: Tổng hợp 3 kịch bản, gắn các mỏ neo dẫn chứng F4 của Dev 1, tạo `PreSalesPlan` và lưu vào bảng `pre_sales_plans`.
  - `PS-10 (Await Consent)`: Kích hoạt `interrupt(WAITING_FOR_HANDOFF_CONSENT)`, gửi SSE event `PRE_SALES_PLAN_READY` về frontend, tạm dừng chờ khách bấm "Đồng ý chia sẻ thông tin".
  - `PS-11 (Safe Abstain)`: Đóng gói thông báo từ chối an toàn, giải thích rõ lý do chính sách và đề xuất kết nối chuyên viên tư vấn trực tiếp.

##### Đầu việc TL-2.2: Xây dựng Endpoint Sinh Bản ước tính Tham khảo PDF tức thời
- **Tập tin tạo:** `/backend/workers/watermark_pdf.py`, `/backend/gateway/routers/pre_sales.py`
- **Nội dung triển khai:**
  - Endpoint: `GET /api/v1/pre-sales/sessions/{session_id}/reference-plan.pdf`.
  - Sinh file PDF đồng bộ trong bộ nhớ (ReportLab / WeasyPrint, thời gian thực thi $< 1.5\text{s}$).
  - **Quy tắc bảo mật bắt buộc:** Bắt buộc vẽ watermark chìm góc 45 độ trên tất cả các trang:  
    `BẢN ƯỚC TÍNH THAM KHẢO TIỀN BÁN HÀNG - KHÔNG PHẢI BÁO GIÁ CHÍNH THỨC`.
  - Tuyệt đối không gọi KMS Server, không gắn chữ ký số, không ghi `outbox_events`. Trả trực tiếp binary stream về client.

##### Đầu việc TL-2.3: Xây dựng Dịch vụ Bàn giao Hồ sơ Khách hàng (`C-10` Lead Dossier & Handoff)
- **Tập tin tạo:** `/backend/services/handoff_service.py`, `/backend/gateway/routers/handoff.py`
- **Nội dung triển khai:**
  - Endpoint: `POST /api/v1/pre-sales/sessions/{session_id}/consent-and-handoff`.
  - Lưu bản ghi xác nhận đồng thuận vào bảng `customer_consents` (lưu IP, user-agent, timestamp, phạm vi đồng thuận PII).
  - Thu thập toàn bộ context hội thoại, đóng gói thành `lead_dossiers` với trạng thái `NEW`.
  - Tính toán nhiệt độ Lead (`lead_temperature`: `HOT` nếu ngân sách tự có $\ge 30\%$, `WARM` nếu $\ge 15\%$, `COLD` nếu thấp hơn).
  - Khởi động bộ đếm SLA 15 phút vào Redis (`lead:sla:{dossier_id}`).
  - Bắn SSE event `LEAD_DOSSIER_CREATED` sang màn hình Sales Dashboard của Dev 3.

##### Đầu việc TL-2.4: Triển khai SSE Streaming Bus & Event Replay Engine
- **Tập tin hoàn thiện:** `/backend/gateway/routers/sse.py`
- **Nội dung triển khai:**
  - Endpoint: `GET /api/v1/pre-sales/sessions/{session_id}/events` và `GET /api/v1/quotes/{quote_id}/events`.
  - Hỗ trợ header `Last-Event-ID`: Đọc Redis Stream để bù lại (replay) các sự kiện client bị rớt mạng trong vòng 300 giây.
  - Tách bạch rõ ràng giữa Event dữ liệu nghiệp vụ và Event Heartbeat định kỳ (`:keepalive` mỗi 15s) để giữ kết nối HTTP thông suốt.

#### 3. Phụ thuộc & Lưu ý Phối hợp trong Phase 2
- **Phụ thuộc vào ai?**
  - **Dev 1:** Cần module RAG `retrieve_policy_by_date` hoạt động chính xác theo ngày và trả về `SourceCoordinate`.
  - **Dev 2:** Cần Pricing Sidecar UDS lắng nghe ổn định tại `/var/run/pricing/engine.sock`.
  - **Dev 3:** Phối hợp kiểm thử luồng Resume từ giao diện chat Web Mobile khi khách bấm xác nhận consent.
- **Ai đang chờ TechLead?**
  - **Dev 3:** Chờ endpoint `/consent-and-handoff` và endpoint SSE `/events` để hoàn thành màn hình Chat và thông báo chuông Lead mới trên Sales Dashboard.
- **Rủi ro kỹ thuật & Dự phòng:**
  - *Rủi ro:* Khách hàng tắt trình duyệt giữa chừng khi đang ở trạng thái interrupt.
  - *Dự phòng:* Thiết lập cron worker quét các session quá 1800s không có tương tác $\rightarrow$ chuyển trạng thái sang `ABANDONED` và dọn dẹp checkpoint tạm.

#### 4. Tiêu chuẩn Nghiệm thu (DoD Phase 2)
- [ ] Chạy luồng thực tế trên Web Mobile: Khách chat $\rightarrow$ Agent trích xuất nhu cầu $\rightarrow$ Hiển thị bảng 3 phương án kèm watermark PDF.
- [ ] Bấm xác nhận đồng thuận $\rightarrow$ Tạo bản ghi `lead_dossiers` trên database và hiển thị tức thời trên Sales Dashboard của Dev 3 qua SSE.
- [ ] Tải file PDF tham khảo kiểm tra: Watermark hiển thị rõ nét, không có chữ ký số KMS.
- [ ] Giả lập ngắt kết nối mạng của client, kết nối lại với `Last-Event-ID` nhận đủ 100% các event bị mất.

---

### PHASE 3 (NGÀY 6–7): OFFICIAL QUOTE STATEGRAPH, TÁI THẨM ĐỊNH & TÍCH HỢP MATH ENGINE (MILESTONE M3)

#### 1. Mục tiêu Kỹ thuật & Đầu ra (Deliverables)
- Hoàn thiện toàn bộ logic nghiệp vụ của `OfficialQuoteGraph` (`C-01`): 20 nodes xử lý quy trình tạo Báo giá chính thức từ Lead Dossier.
- Thực thi nguyên tắc **Bắt buộc Tái thẩm định (Revalidation)** và **Tính toán lại (Recalculation)** tại thời điểm giao dịch thực.
- Xây dựng Vòng lặp Sửa đổi (Revision Loop) và Cổng Xử lý Ngoại lệ Chính sách (Exception Policy Handling).

#### 2. Chi tiết Công việc Cụ thể của TechLead

##### Đầu việc TL-3.1: Lập trình Chi tiết 20 Nodes của `OfficialQuoteGraph`
- **Tập tin hoàn thiện:** `/backend/orchestrator/official_quote_graph.py`
- **Nội dung triển khai chi tiết 20 nodes:**
  - `N-01 (Init Quote)`: Tiếp nhận `dossier_id`, sinh `quote_id`, tạo `quote_version = 1`, đặt trạng thái `DRAFT`.
  - `N-02 (Input Validation)`: Kiểm tra tính đầy đủ của thông tin pháp lý khách hàng, mã căn hộ, ngày lập báo giá.
  - `N-03 (Lock Context)`: Khóa cố định mã dự án, mã căn, bảng giá gốc (`listed_price_before_tax_vnd`).
  - `N-04 (Re-resolve Policy)`: **Bắt buộc gọi lại Time-Travel Policy Engine** với ngày giao dịch thực; so sánh hash chính sách với thời điểm Pre-Sales; nếu có thay đổi $\rightarrow$ Gắn cờ cảnh báo `POLICY_SUPERSEDED_WARNING`.
  - `N-05 (Detect Conflicts)`: Quét xung đột chính sách tầng 2 (áp dụng triệt để ma trận cấm cộng dồn quà tặng).
  - `N-06 (Exception Router)`: Kiểm tra nếu nhân viên kinh doanh có yêu cầu áp dụng chính sách ngoại lệ (giảm thêm, gia hạn ân hạn).
  - `N-07 (Exception Evaluation)`: Đánh giá thẩm quyền ngoại lệ; nếu vượt thẩm quyền Sale $\rightarrow$ Chuyển cờ yêu cầu phê duyệt Tổng Giám Đốc.
  - `N-08 (Sidecar Calculation)`: Đóng gói `PricingInput`, gửi qua UDS tới Math Engine Sidecar của Dev 2.
  - `N-09 (Sanity Validation)`: Thẩm định 6 nhóm sanity checks từ kết quả tính toán; nếu fail $\rightarrow$ Chuyển trạng thái `CALCULATION_FAILED`.
  - `N-10 (Ranking)`: Xếp hạng 3 kịch bản theo mục tiêu của hợp đồng chính thức.
  - `N-11 (Evidence Linking)`: Gọi module F4 của Dev 1 gắn tọa độ nguồn pháp lý (`SourceCoordinate`) cho từng dòng số liệu.
  - `N-12 (Why Explanation)`: Sinh lời giải thích khách quan lý do chọn kịch bản tối ưu nhất.
  - `N-13 (Why-Not Explanation)`: Sinh lời giải thích vì sao các kịch bản khác bị loại hoặc tốn dòng tiền hơn.
  - `N-14 (Explanation Validation)`: Kiểm tra tính trung thực của lời giải thích; cấm ảo giác số học; đảm bảo 100% số liệu khớp với kết quả Sidecar.
  - `N-15 (Assemble Package)`: Đóng gói toàn bộ hồ sơ báo giá (Approval Package) thành cấu trúc JSON bất biến.
  - `N-16 (Audit Hash Snapshot)`: Tính toán SHA-256 của toàn bộ hồ sơ, tạo bản ghi snapshot trong `quote_snapshots`.
  - `N-17 (HITL Gate)`: Kích hoạt `interrupt(WAITING_FOR_REVIEW)`, đưa báo giá vào trạng thái `READY_FOR_REVIEW`, chờ Quản lý mở Dashboard xem xét.
  - `N-18 (Revision Evaluation)`: Nếu Quản lý từ chối và yêu cầu sửa đổi $\rightarrow$ Nhận phản hồi, chuyển về `N-06` để tính lại.
  - `N-19 (Safe Abstention Gate)`: Nếu phát hiện vi phạm chính sách không thể giải quyết $\rightarrow$ Chuyển trạng thái `ABSTAINED`, dừng luồng an toàn.
  - `N-20 (Final Approval Ready)`: Xác thực hồ sơ hợp lệ, sẵn sàng chuyển tiếp sang khối Ký số Mật mã `C-05`.

##### Đầu việc TL-3.2: Xây dựng Cơ chế Chuyển đổi Báo giá Tức thời từ Lead Dossier
- **Tập tin tạo:** `/backend/gateway/routers/quotes.py`
- **Nội dung triển khai:**
  - Endpoint: `POST /api/v1/quotes/create-from-dossier`.
  - Kiểm tra trạng thái Lead Dossier (chỉ cho phép chuyển đổi nếu trạng thái là `NEW` hoặc `ASSIGNED`).
  - Cập nhật trạng thái dossier sang `CONVERTED_TO_QUOTE`.
  - Khởi tạo thread `quote:{tenant_id}:{quote_id}` và kích hoạt `OfficialQuoteGraph` chạy ngầm.
  - Trả về mã `201 Created` kèm `quote_id` và URL lắng nghe SSE.

##### Đầu việc TL-3.3: Lập trình Vòng lặp Sửa đổi (Revision Loop) & Quản lý Phiên bản (Version Control)
- **Nội dung triển khai:**
  - Khi Sale hoặc Quản lý yêu cầu điều chỉnh kịch bản thanh toán:
    * Báo giá hiện tại được đánh dấu `NEEDS_REVISION`.
    * Hệ thống tự động tăng `quote_version = quote_version + 1`.
    * Tạo một checkpoint mới, kế thừa thông tin khách hàng nhưng kích hoạt lại các node tính toán và thẩm định chính sách.
    * Đảm bảo bản ghi `quote_version` cũ không bị xóa hoặc sửa, phục vụ đối soát lịch sử.

#### 3. Phụ thuộc & Lưu ý Phối hợp trong Phase 3
- **Phụ thuộc vào ai?**
  - **Dev 1:** Cần module F4 Evidence Linking hoàn chỉnh để node `N-11` có thể gắn đúng số trang, số điều khoản vào hồ sơ báo giá.
  - **Dev 2:** Đảm bảo Sidecar xử lý trơn tru các trường hợp ngoại lệ chính sách (chiết khấu bổ sung).
  - **Dev 3:** Cung cấp thông tin người dùng đang thao tác để phục vụ kiểm tra phân quyền (SoD).
- **Ai đang chờ TechLead?**
  - **Dev 3:** Chờ endpoint `/quotes/create-from-dossier` và StateGraph chạy đến `READY_FOR_REVIEW` để hoàn thiện màn hình Manager Approval Dashboard.
- **Rủi ro kỹ thuật & Dự phòng:**
  - *Rủi ro:* Deadlock database khi hai luồng cùng cố gắng cập nhật `quote_version`.
  - *Dự phòng:* Áp dụng triệt để khóa lạc quan OCC (`If-Match: W/"<quote_version>"`); nếu xung đột, giao dịch thứ hai bị từ chối ngay với mã 412 và yêu cầu reload dữ liệu.

#### 4. Tiêu chuẩn Nghiệm thu (DoD Phase 3)
- [ ] Kích hoạt tạo báo giá từ Lead Dossier: Hệ thống tự động re-validate chính sách và tính toán lại thành công qua UDS Sidecar.
- [ ] Báo giá dừng chính xác tại điểm ngắt `WAITING_FOR_REVIEW`, không bị chạy vượt quyền sang trạng thái Approved.
- [ ] Thử nghiệm yêu cầu sửa đổi (Revision): Hệ thống sinh chính xác `quote_version = 2`, dữ liệu version 1 vẫn nguyên vẹn trong cơ sở dữ liệu.
- [ ] Giả lập xung đột chính sách: Hệ thống rẽ nhánh chính xác sang `ABSTAINED` và ghi nhận đầy đủ lý do từ chối.

---

### PHASE 4 (NGÀY 8): KMS ATTESTATION, ANTI-CYCLIC AUDIT TRAIL & OUTBOX WORKER (MILESTONE M4)

#### 1. Mục tiêu Kỹ thuật & Đầu ra (Deliverables)
- Triển khai hoàn chỉnh Chốt chặn Phê duyệt Ký số Mật mã `C-05` (KMS Server Attestation Ed25519) theo nguyên tắc Sign-Before-Commit.
- Thực thi quy tắc Phân quyền Độc lập (Separation of Duties - SoD).
- Vận hành Chuỗi Băm Liên hoàn Chống Chu trình `C-07` (Anti-Cyclic Hash Chain) và Transactional Outbox Worker (`ARQ`) phát hành Báo giá chính thức PDF có mã QR xác thực.

#### 2. Chi tiết Công việc Cụ thể của TechLead

##### Đầu việc TL-4.1: Triển khai Cổng Phê duyệt & Ký số Mật mã (`C-05` Sign-Before-Commit)
- **Tập tin tạo:** `/backend/governance/approval_service.py`, `/backend/gateway/routers/approvals.py`
- **Nội dung triển khai:**
  - Endpoint: `POST /api/v1/quotes/{quote_id}/approve`.
  - **Kiểm tra Phân quyền SoD (Separation of Duties Gate):**
    ```python
    if current_user.user_id == quote.created_by_user_id:
        raise HTTPException(
            status_code=403, 
            detail="SOD_VIOLATION: Creator cannot approve their own quote"
        )
    if "MANAGER" not in current_user.roles:
        raise HTTPException(status_code=403, detail="INSUFFICIENT_APPROVAL_ROLE")
    ```
  - **Thực thi Mô hình Sign-Before-Commit:**
    1. Lấy snapshot dữ liệu của báo giá từ bảng `quote_snapshots`.
    2. Băm nội dung snapshot: `snapshot_hash = SHA256(canonical_json(snapshot_payload))`.
    3. Gửi `snapshot_hash` tới module KMS Signer để sinh chữ ký số Ed25519 (`signature_bytes`).
    4. Mở một Database Transaction ACID duy nhất thực hiện đồng thời:
       - Cập nhật bảng `quotes`: `approval_status = 'APPROVED'`, `approved_by = current_user.id`, `signature = signature_base64`, `approved_at = NOW()`.
       - Ghi bản ghi vào `quote_audit_events`: Event `QUOTE_APPROVED` kèm băm liên hoàn $H_i$.
       - Ghi bản ghi vào `transactional_outbox`: Event `OFFICIAL_QUOTE_ISSUED` (payload chứa thông tin cần thiết để worker sinh PDF).
    5. Commit Transaction. Nếu commit lỗi $\rightarrow$ Rollback toàn bộ, chữ ký số trong RAM tự hủy.

##### Đầu việc TL-4.2: Tích hợp Chuỗi Băm Kiểm toán Liên hoàn (`C-07` Audit Hash Chain)
- **Nội dung triển khai:**
  - Mọi hành động làm thay đổi trạng thái của Báo giá (`CREATED`, `CALCULATED`, `REVISED`, `APPROVED`, `REJECTED`, `PDF_GENERATED`) đều phải gọi hàm:
    `audit_chain.append_event(quote_id, event_type, actor_id, payload)`.
  - Đảm bảo tính toàn vẹn liên kết: Sự kiện mới bắt buộc trỏ về hash của sự kiện trước.
  - Endpoint kiểm tra công khai: `GET /api/v1/quotes/{quote_id}/verify-audit` cho phép đối soát toàn bộ chuỗi băm từ Genesis đến hiện tại.

##### Đầu việc TL-4.3: Triển khai Transactional Outbox Background Worker & PDF Generator
- **Tập tin tạo:** `/backend/workers/outbox_worker.py`, `/backend/workers/official_pdf_generator.py`
- **Nội dung triển khai:**
  - Worker chạy nền bằng thư viện `ARQ` (kết nối Redis queue) định kỳ quét các bản ghi chưa xử lý (`status = 'PENDING'`) trong bảng `transactional_outbox`.
  - Đọc thông tin Báo giá đã được phê duyệt, lấy Chữ ký số Ed25519 và Snapshot Hash.
  - Sinh Mã QR Chữ ký số chứa đường link tra cứu công khai:  
    `https://verify.vlandfuture.vn/quote/{quote_id}?hash={snapshot_hash}&sig={signature}`.
  - Sinh file Báo giá chính thức PDF hoàn chỉnh: Bao gồm bảng chiết khấu chi tiết, dòng tiền từng đợt, điều khoản chính sách áp dụng, mỏ neo dẫn chứng F4, Chữ ký số và Mã QR xác thực.
  - Upload file PDF lên MinIO / S3; cập nhật bảng `quotes`: `pdf_status = 'ISSUED'`, `pdf_url = s3_url`.
  - Cập nhật trạng thái outbox sang `PROCESSED`. Hỗ trợ cơ chế tự động thử lại (Retry max 3 lần với Exponential Backoff).

##### Đầu việc TL-4.4: Hỗ trợ Dev 1 Hoàn thiện Chốt chặn Gửi tin F8 (`POST /api/v1/messages/send`)
- **Tập tin phối hợp:** `/backend/gateway/routers/messages.py`
- **Nội dung triển khai:**
  - TechLead hỗ trợ Dev 1 đóng chốt chặn cuối cùng ở backend:
  - Khi Sale bấm Gửi tin nhắn qua Zalo/SMS $\rightarrow$ Client gọi `POST /api/v1/messages/send` kèm `message_hash`.
  - Backend kiểm tra trong bảng `compliance_checks`: Nếu `message_hash` chưa từng được kiểm duyệt, hoặc có trạng thái là `UNSUPPORTED` hay `PROHIBITED` $\rightarrow$ Backend lập tức chặn đứng và trả về **`403 Forbidden`** (`COMPLIANCE_SEND_BLOCKED`).
  - Ghi log vi phạm bảo mật nếu phát hiện cố tình bypass frontend.

#### 3. Phụ thuộc & Lưu ý Phối hợp trong Phase 4
- **Phụ thuộc vào ai?**
  - **Dev 1:** Cần kết quả Spike 6 (Compliance Gate) của Dev 1 để tích hợp trơn tru với router gửi tin nhắn.
  - **Dev 3:** Cung cấp trải nghiệm người dùng mượt mà trên Manager Approval Dashboard khi bấm nút Ký số (hiển thị spinner, disable nút để tránh double-click).
- **Ai đang chờ TechLead?**
  - **Dev 3:** Chờ endpoint `/approve` và cơ chế sinh PDF có mã QR để hoàn thiện tính năng Preview Báo giá chính thức và kiểm tra mã QR trên điện thoại thật.
- **Rủi ro kỹ thuật & Dự phòng:**
  - *Rủi ro:* MinIO bị sập khiến worker không upload được file PDF dẫn đến outbox bị nghẽn.
  - *Dự phòng:* Thiết lập trạng thái `pdf_status = 'RETRYING'`; outbox worker có circuit breaker, tự động cảnh báo `MANUAL_INTERVENTION` nếu sau 3 lần retry không thành công mà không làm ảnh hưởng đến trạng thái `APPROVED` của báo giá.

#### 4. Tiêu chuẩn Nghiệm thu (DoD Phase 4)
- [ ] Thử nghiệm Sale tự duyệt báo giá của chính mình: Hệ thống chặn đứng và trả về `403 SOD_VIOLATION`.
- [ ] Quản lý thực hiện phê duyệt: Chữ ký số Ed25519 được sinh chuẩn xác, bảng outbox ghi nhận sự kiện ngay trong cùng 1 transaction.
- [ ] Worker chạy nền nhặt event, sinh PDF có mã QR thành công trong vòng $< 3$ giây; quét mã QR bằng điện thoại mở ra đúng trang xác thực toàn vẹn.
- [ ] Chạy hàm `verify_audit_integrity` trả về kết quả `VALID` 100%. Cố tình sửa 1 ký tự trong database $\rightarrow$ Hàm phát hiện ngay lập tức và báo `TAMPER_DETECTED`.

---

### PHASE 5 (NGÀY 9–10): GHÉP NỐI TOÀN HỆ THỐNG, FAILURE RECOVERY & TỔNG DUYỆT DEMO (MILESTONE M5)

#### 1. Mục tiêu Kỹ thuật & Đầu ra (Deliverables)
- Thông luồng tích hợp End-to-End toàn diện xuyên suốt 11 Logic Components (`C-01` $\rightarrow$ `C-11`).
- Thực thi Test Matrix 5 Kịch bản Lỗi Biên và Phục hồi (Failure Injection & Recovery Testing).
- Chuẩn hóa Script Demo Reset / Re-seed Database và diễn tập tổng thể phục vụ báo cáo / Hackathon Showcase.

#### 2. Chi tiết Công việc Cụ thể của TechLead

##### Đầu việc TL-5.1: Ghép nối & Kiểm thử Tích hợp Toàn diện (End-to-End Integration Test Harness)
- **Tập tin tạo:** `/tests/integration/test_full_funnel_e2e.py`
- **Nội dung kiểm thử tự động:**
  1. *Bước 1:* Khách hàng tạo phiên Pre-Sales, gửi tin nhắn nhu cầu.
  2. *Bước 2:* Hệ thống trích xuất ràng buộc, tra cứu chính sách, tính toán 3 kịch bản, trả về bản ước tính tham khảo có watermark PDF.
  3. *Bước 3:* Khách hàng gửi xác nhận đồng thuận (Electronic Consent) $\rightarrow$ Sinh Lead Dossier.
  4. *Bước 4:* Nhân viên kinh doanh nhận Lead, chuyển đổi thành Báo giá chính thức $\rightarrow$ Hệ thống re-validate chính sách và recalculate qua UDS Sidecar.
  5. *Bước 5:* Quản lý xem xét trên Approval Dashboard, kích hoạt ký số Ed25519 qua KMS Server $\rightarrow$ Outbox worker sinh PDF chính thức có mã QR.
  6. *Bước 6:* Nhân viên kinh doanh soạn tin nhắn gửi khách $\rightarrow$ Chốt chặn F8 kiểm duyệt và cho phép gửi nếu đạt chuẩn (`POST /messages/send`).

##### Đầu việc TL-5.2: Thực thi Bộ Kiểm thử Thất bại & Phục hồi (Failure Injection Runbook)
- **Tập tin tạo:** `/tests/security/test_failure_modes.py`
- **Nội dung kiểm định 5 kịch bản lỗi biên theo kiến trúc:**
  - **FAIL-01 (Sidecar UDS Crash):** Tắt tiến trình Sidecar giữa lúc StateGraph đang chạy $\rightarrow$ Hệ thống bắt timeout, chuyển sang trạng thái `CALCULATION_FAILED`, không làm crash FastAPI backend.
  - **FAIL-02 (Database Crash post-KMS Sign):** Giả lập DB bị ngắt kết nối ngay sau khi KMS sinh chữ ký $\rightarrow$ Cơ chế Atomic Commit-Discard hoạt động, không có chữ ký mồ côi nào lọt vào hệ thống.
  - **FAIL-03 (Policy Expired Mid-Flight):** Tạo Pre-Sales plan với chính sách còn hạn; cố tình chỉnh ngày hiệu lực của chính sách về quá khứ; chuyển đổi sang Official Quote $\rightarrow$ Hệ thống phát hiện ngay chính sách đã hết hạn (`POLICY_EXPIRED`) và từ chối phát hành báo giá.
  - **FAIL-04 (Stale Quote Version Concurrency):** Hai quản lý cùng mở màn hình duyệt và cùng bấm Approve/Revision $\rightarrow$ Người thứ nhất thành công, người thứ hai nhận lỗi `412 Precondition Failed` do OCC kiểm soát ETag.
  - **FAIL-05 (F8 Send Gate Bypass Attempt):** Dùng lệnh curl cố tình bắn request `POST /api/v1/messages/send` với nội dung cam kết sai lệch chưa qua kiểm duyệt $\rightarrow$ Backend chặn đứng với mã `403 Forbidden` (`COMPLIANCE_SEND_BLOCKED`).

##### Đầu việc TL-5.3: Chuẩn bị Script Reset Môi trường Demo & Runbook Diễn tập
- **Tập tin tạo:** `/scripts/demo_reset.sh`, `/scripts/seed_demo_data.py`, `DEMO_RUNBOOK.md`
- **Nội dung triển khai:**
  - Script một lệnh: `bash scripts/demo_reset.sh` tự động:
    * Dọn dẹp sạch sẽ dữ liệu phiên Pre-Sales, Báo giá và Audit log tạm thời.
    * Nạp lại nguyên vẹn bộ dữ liệu mẫu chuẩn (Dự án The Beverly, Bảng giá chuẩn, 3 Chính sách bán hàng hiệu lực tháng 09/2026).
    * Khởi động lại các container Docker về trạng thái đỉnh cao (pristine state).
  - Soạn tài liệu hướng dẫn diễn tập (Runbook) cho cả team, phân công rõ ai nói phần nào, click màn hình nào trong buổi trình diễn.

##### Đầu việc TL-5.4: Kiểm tra An toàn Toàn diện (Security & Performance Audit)
- Kiểm tra toàn bộ mã nguồn không có API key, Token hay Private Key bị hardcode.
- Kiểm tra Log hệ thống: Tuyệt đối không log thông tin định danh khách hàng (PII) như số CMND/CCCD, số điện thoại ở dạng clear-text.
- Đo đạc độ trễ toàn trình: Các endpoint tra cứu và tính toán phải phản hồi dưới 1.5 giây; Sidecar UDS tính toán dưới 5ms.

#### 3. Phụ thuộc & Lưu ý Phối hợp trong Phase 5
- **Phụ thuộc vào ai?** Toàn bộ 3 Developers phải hoàn thành merge mã nguồn vào nhánh `integration` trước đầu Ngày 9 để TechLead chạy bài test tổng duyệt.
- **Ai đang chờ TechLead?** Cả team chờ TechLead chốt kịch bản Demo và cung cấp lệnh reset database sạch sẽ.
- **Rủi ro kỹ thuật & Dự phòng:**
  - *Rủi ro:* Hệ thống demo gặp trục trặc mạng hoặc tải chậm trong lúc thuyết trình.
  - *Dự phòng:* Chuẩn bị sẵn profile Docker Compose chạy offline 100% trên Localhost của máy TechLead (không phụ thuộc vào internet bên ngoài).

#### 4. Tiêu chuẩn Nghiệm thu (DoD Phase 5)
- [ ] Toàn bộ 5 kịch bản Failure Modes (FAIL-01 $\rightarrow$ FAIL-05) được xử lý mượt mà, đúng mã lỗi, không phát sinh lỗi Unhandled Exception 500.
- [ ] Diễn tập kịch bản Demo mượt mà từ đầu đến cuối dưới 7 phút mà không gặp bất kỳ lỗi gián đoạn nào.
- [ ] Lệnh `bash scripts/demo_reset.sh` khôi phục hệ thống về trạng thái sạch chỉ trong vòng dưới 15 giây.
- [ ] Báo cáo nghiệm thu kỹ thuật xác nhận đạt trọn vẹn 11/11 Logic Components và vượt qua 6/6 Implementation Spikes.

---

## IV. HƯỚNG DẪN KỸ THUẬT CHI TIẾT 3 SPIKES DO TECHLEAD SỞ HỮU

---

### SPIKE 2: LANGGRAPH ASYNCPOSTGRESSAVER CHECKPOINTING & STATE REPLAY

#### 1. Mục tiêu Nghiên cứu & Thử nghiệm
Chứng minh khả năng lưu vết bền vững của LangGraph vào PostgreSQL 16 qua class `AsyncPostgresSaver`, cách ly hoàn toàn giữa 2 namespace `PRE_SALES` và `DEFAULT`, và xử lý mượt mà việc dừng/resume tại 3 điểm ngắt HITL.

#### 2. Kiến trúc Cài đặt & Code Mẫu Chuẩn

```python
# /backend/orchestrator/checkpointer.py
import psycopg
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

class CheckpointManager:
    def __init__(self, db_uri: str):
        self.db_uri = db_uri
        self.pool = AsyncConnectionPool(conninfo=db_uri, max_size=20, open=False)

    async def initialize(self):
        await self.pool.open()
        # Khởi tạo bảng checkpoint nếu chưa tồn tại
        async with self.pool.connection() as conn:
            checkpointer = AsyncPostgresSaver(conn)
            await checkpointer.setup()

    def get_checkpointer(self, conn) -> AsyncPostgresSaver:
        return AsyncPostgresSaver(conn)

    @staticmethod
    def build_thread_config(namespace: str, tenant_id: str, entity_id: str) -> dict:
        """
        Quy chuẩn định danh thread LangGraph:
        - Pre-Sales: namespace='PRE_SALES', thread_id='presales:{tenant_id}:{session_id}'
        - Official Quote: namespace='DEFAULT', thread_id='quote:{tenant_id}:{quote_id}'
        """
        thread_id = f"presales:{tenant_id}:{entity_id}" if namespace == "PRE_SALES" else f"quote:{tenant_id}:{entity_id}"
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": namespace
            }
        }
```

#### 3. Kịch bản Kiểm thử Nghiệm thu Spike 2
- **Test Case 2.1 (Interrupt Resume):** Cho `PreSalesGraph` chạy đến node `PS-10`, kích hoạt `interrupt("WAITING_FOR_HANDOFF_CONSENT")`. Đồ thị tạm dừng, checkpoint lưu vào PostgreSQL. Gọi `graph.ainvoke(Command(resume={"consent_granted": True}), config=config)` $\rightarrow$ Đồ thị tiếp tục chạy chính xác đến node `PS-11` và kết thúc thành công.
- **Test Case 2.2 (Process Crash Recovery):** Chạy StateGraph; khi đang tạm dừng tại interrupt, cố tình kill tiến trình Python worker. Khởi động lại tiến trình mới, đọc lại state từ thread_id $\rightarrow$ Lấy lại nguyên vẹn toàn bộ biến trạng thái `customer_constraints` và `scenarios` từ database.

---

### SPIKE 3: ASYMMETRIC CRYPTOGRAPHIC SERVER ATTESTATION (ED25519) & ATOMIC COMMIT-DISCARD

#### 1. Mục tiêu Nghiên cứu & Thử nghiệm
Đảm bảo tính xác thực pháp lý tối cao của Báo giá chính thức bằng Chữ ký số Ed25519 (chuẩn mã hóa bất đối xứng RFC 8032), triệt tiêu hoàn toàn rủi ro phát tán chữ ký số mồ côi nếu cơ sở dữ liệu gặp sự cố.

#### 2. Kiến trúc Cài đặt & Code Mẫu Chuẩn

```python
# /backend/governance/kms_signer.py
import json
import base64
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import hashes
import hashlib

class KMSServerSigner:
    def __init__(self, private_key_pem: bytes = None):
        # Trong môi trường MVP, sinh hoặc load private key Ed25519
        if private_key_pem:
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_pem)
        else:
            self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

    def get_public_key_base64(self) -> str:
        raw_bytes = self._public_key.public_bytes_raw()
        return base64.b64encode(raw_bytes).decode('utf-8')

    def calculate_snapshot_hash(self, snapshot_payload: dict) -> str:
        # Chuẩn hóa JSON dạng canonical để băm không bị lệch do khoảng trắng hoặc thứ tự key
        canonical_json = json.dumps(snapshot_payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def sign_snapshot_hash(self, snapshot_hash: str) -> str:
        """Ký số bất đối xứng Ed25519 trên chuỗi băm snapshot"""
        signature = self._private_key.sign(snapshot_hash.encode('utf-8'))
        return base64.b64encode(signature).decode('utf-8')

    def verify_signature(self, snapshot_hash: str, signature_base64: str) -> bool:
        try:
            signature_bytes = base64.b64decode(signature_base64)
            self._public_key.verify(signature_bytes, snapshot_hash.encode('utf-8'))
            return True
        except Exception:
            return False
```

#### 3. Quy trình Thực thi Nguyên tắc Atomic Commit-Discard
```python
# /backend/governance/approval_service.py
async def execute_atomic_approval(db_session, quote_id: str, approver_id: str, snapshot_data: dict, kms_signer: KMSServerSigner):
    # Bước 1: Tính toán băm và ký trong bộ nhớ (RAM)
    snapshot_hash = kms_signer.calculate_snapshot_hash(snapshot_data)
    signature_b64 = kms_signer.sign_snapshot_hash(snapshot_hash)

    # Bước 2: Bắt đầu giao dịch ACID nguyên tử duy nhất trên Database
    async with db_session.begin():
        # 1. Cập nhật trạng thái báo giá
        await db_session.execute(
            """
            UPDATE quotes 
            SET approval_status = 'APPROVED', 
                approved_by = :approver_id, 
                approved_at = NOW(),
                signature = :sig,
                snapshot_hash = :hash
            WHERE quote_id = :qid AND approval_status = 'READY_FOR_REVIEW'
            """,
            {"approver_id": approver_id, "sig": signature_b64, "hash": snapshot_hash, "qid": quote_id}
        )
        
        # 2. Ghi Audit Log liên hoàn
        await audit_chain.record_event_tx(db_session, quote_id, "QUOTE_APPROVED", approver_id, {"snapshot_hash": snapshot_hash})

        # 3. Ghi Transactional Outbox Event để worker sinh PDF
        await db_session.execute(
            """
            INSERT INTO transactional_outbox (event_id, aggregate_type, aggregate_id, event_type, payload, status)
            VALUES (gen_random_uuid(), 'QUOTE', :qid, 'OFFICIAL_QUOTE_ISSUED', :payload, 'PENDING')
            """,
            {"qid": quote_id, "payload": json.dumps({"quote_id": quote_id, "signature": signature_b64, "snapshot_hash": snapshot_hash})}
        )
        # NẾU CÓ BẤT KỲ LỖI NÀO XẢY RA Ở ĐÂY -> DB ROLLBACK -> SIGNATURE TRONG RAM TỰ HỦY -> KHÔNG CÓ CHỮ KÝ MỒ CÔI
```

---

### SPIKE 4: PER-QUOTE ANTI-CYCLIC HASH CHAIN & GENESIS VERIFICATION

#### 1. Mục tiêu Nghiên cứu & Thử nghiệm
Xây dựng một hệ thống nhật ký kiểm toán không thể chối bỏ (Tamper-Evident Append-Only Log) cho từng báo giá, trong đó mỗi sự kiện mới là một mắt xích liên kết toán học không thể phá vỡ với toàn bộ lịch sử trước đó.

#### 2. Kiến trúc Cài đặt & Thuật toán Băm

```python
# /backend/governance/audit_chain.py
import hashlib
import json
from datetime import datetime
from typing import List, Dict, Tuple

class AuditChainEngine:
    GENESIS_PREV_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    @staticmethod
    def compute_event_hash(prev_hash: str, quote_id: str, event_type: str, actor_id: str, occurred_at_iso: str, payload: dict) -> str:
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        seed_string = f"{prev_hash}|{quote_id}|{event_type}|{actor_id}|{occurred_at_iso}|{canonical_payload}"
        return hashlib.sha256(seed_string.encode('utf-8')).hexdigest()

    async def append_event(self, db_conn, quote_id: str, event_type: str, actor_id: str, payload: dict) -> str:
        # Lấy hash của sự kiện gần nhất của quote_id này (Row-level lock)
        cursor = await db_conn.execute(
            """
            SELECT event_hash, event_seq 
            FROM quote_audit_events 
            WHERE quote_id = %s 
            ORDER BY event_seq DESC 
            LIMIT 1 FOR UPDATE
            """,
            (quote_id,)
        )
        latest_event = await cursor.fetchone()

        if not latest_event:
            prev_hash = self.GENESIS_PREV_HASH
            new_seq = 1
        else:
            prev_hash = latest_event[0]
            new_seq = latest_event[1] + 1

        now_iso = datetime.utcnow().isoformat() + "Z"
        event_hash = self.compute_event_hash(prev_hash, quote_id, event_type, actor_id, now_iso, payload)

        await db_conn.execute(
            """
            INSERT INTO quote_audit_events (event_id, quote_id, event_seq, event_type, actor_id, occurred_at, prev_event_hash, event_hash, payload)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (quote_id, new_seq, event_type, actor_id, now_iso, prev_hash, event_hash, json.dumps(payload))
        )
        return event_hash

    async def verify_chain_integrity(self, db_conn, quote_id: str) -> Tuple[bool, str]:
        """Duyệt toàn bộ chuỗi từ Genesis đến Leaf để phát hiện can thiệp dữ liệu"""
        cursor = await db_conn.execute(
            """
            SELECT event_seq, event_type, actor_id, occurred_at, prev_event_hash, event_hash, payload 
            FROM quote_audit_events 
            WHERE quote_id = %s 
            ORDER BY event_seq ASC
            """,
            (quote_id,)
        )
        events = await cursor.fetchall()
        if not events:
            return True, "EMPTY_CHAIN"

        expected_prev_hash = self.GENESIS_PREV_HASH
        for row in events:
            seq, ev_type, actor, occurred_at, recorded_prev_hash, recorded_event_hash, payload_str = row
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
            occurred_at_iso = occurred_at.isoformat() + "Z" if isinstance(occurred_at, datetime) else str(occurred_at)

            # Kiểm tra mắt xích liên kết
            if recorded_prev_hash != expected_prev_hash:
                return False, f"BROKEN_LINK_AT_SEQ_{seq}: expected prev_hash {expected_prev_hash}, got {recorded_prev_hash}"

            # Tính lại băm và đối soát
            recalculated_hash = self.compute_event_hash(recorded_prev_hash, quote_id, ev_type, actor, occurred_at_iso, payload)
            if recalculated_hash != recorded_event_hash:
                return False, f"TAMPER_DETECTED_AT_SEQ_{seq}: data payload was modified!"

            expected_prev_hash = recorded_event_hash

        return True, "CHAIN_INTEGRITY_VERIFIED_100%"
```

---

## V. CỔNG KIỂM SOÁT HỢP ĐỒNG API, GATEWAY & BẢO MẬT

### 5.1 Danh mục 29 Canonical Endpoints & Phân định Trách nhiệm Backend của TechLead
TechLead trực tiếp lập trình Router và Gateway Middleware cho các endpoints cốt lõi, đồng thời cấu hình kết nối tới các dịch vụ của Dev 1, Dev 2, Dev 3:

| Nhóm Nghiệp vụ | Phương thức & URI Endpoint | Trách nhiệm Triển khai | Ghi chú Ràng buộc Kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Pre-Sales Advisory (`C-09`)** | `POST /api/v1/pre-sales/sessions` | **TechLead** | Tạo session mới, khởi tạo thread namespace `PRE_SALES` |
| | `POST /api/v1/pre-sales/sessions/{id}/messages` | **TechLead** | Đẩy tin nhắn vào LangGraph, resume interrupt |
| | `GET /api/v1/pre-sales/sessions/{id}/events` | **TechLead** | SSE Streaming tiến trình suy luận, hỗ trợ `Last-Event-ID` |
| | `POST /api/v1/pre-sales/sessions/{id}/confirm-constraints` | **TechLead** | Resume từ `WAITING_FOR_CONSTRAINT_CONFIRMATION` |
| | `POST /api/v1/pre-sales/sessions/{id}/consent-and-handoff` | **TechLead** | Lưu PII consent, tạo `LeadDossier`, resume consent interrupt |
| | `GET /api/v1/pre-sales/sessions/{id}/reference-plan.pdf` | **TechLead** | Sinh PDF đồng bộ $< 1.5\text{s}$, watermark chìm, cấm ký số |
| **Sales Dossier (`C-10`)** | `GET /api/v1/sales/leads` | TechLead (Gateway) | Trả danh sách lead, hỗ trợ lọc theo nhiệt độ Lead |
| | `GET /api/v1/sales/leads/{id}` | TechLead (Gateway) | Trả chi tiết dossier, mask thông tin PII theo role |
| **Official Quotes (`C-01`)** | `POST /api/v1/quotes/create-from-dossier` | **TechLead** | Chuyển đổi dossier thành quote v1, kích hoạt re-validation |
| | `GET /api/v1/quotes/{id}` | **TechLead** | Trả snapshot chi tiết của báo giá, header ETag |
| | `GET /api/v1/quotes/{id}/events` | **TechLead** | SSE Streaming tiến trình StateGraph báo giá chính thức |
| | `POST /api/v1/quotes/{id}/recalculate` | **TechLead** | Gọi Sidecar tính lại khi Sale thay đổi tham số |
| | `POST /api/v1/quotes/{id}/request-revision` | **TechLead** | Quản lý yêu cầu sửa, tăng `quote_version = quote_version + 1` |
| **Approval & KMS (`C-05`)** | `POST /api/v1/quotes/{id}/approve` | **TechLead** | Kiểm tra SoD, Sign-Before-Commit Ed25519, ghi outbox |
| | `POST /api/v1/quotes/{id}/reject` | **TechLead** | Quản lý từ chối báo giá, lưu lý do vào audit log |
| | `GET /api/v1/quotes/{id}/official.pdf` | **TechLead** | Tải PDF chính thức có chữ ký số và mã QR (nếu `ISSUED`) |
| **Verification & Audit (`C-07`)**| `GET /api/v1/quotes/{id}/verify-audit` | **TechLead** | Kiểm định tính toàn vẹn chuỗi băm Anti-Cyclic Genesis |
| | `GET /api/v1/verification/public-key` | **TechLead** | Xuất bản Ed25519 Public Key để khách hàng tự đối soát |
| **Compliance & F8 Gate (`C-11`)**| `POST /api/v1/compliance/check-message` | Phối hợp Dev 1 | Live-check nội dung tin nhắn, bóc tách claims, tính `message_hash` |
| | `POST /api/v1/messages/send` | **TechLead + Dev 1** | **Chốt chặn gửi tin backend: Chặn 403 nếu vi phạm** |
| **Policy Registry & F9 (`C-03`)**| `POST /api/v1/policies/ingest` | Phối hợp Dev 1 | Upload tài liệu chính sách, phân tích chunk và embedding |
| | `POST /api/v1/policies/rules/{id}/publish` | Phối hợp Dev 1 | Trigger test gate bắt buộc $100\%$ pass mới lên `ACTIVE` |

---

## VI. RUNBOOK KIỂM THỬ THẤT BẠI (FAILURE INJECTION & RECOVERY TESTING)

TechLead chịu trách nhiệm trực tiếp thiết lập và chạy bộ kiểm thử 5 kịch bản lỗi biên trước khi cho phép hệ thống bước vào giai đoạn demo:

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        MA TRẬN 5 KỊCH BẢN KIỂM THỬ THẤT BẠI (FAIL-01 -> FAIL-05)                       │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ FAIL-01: Sidecar UDS Socket Crash      --> FastAPI bắt Timeout, StateGraph chuyển CALCULATION_FAILED   │
│ FAIL-02: DB Crash sau khi KMS Sign     --> Atomic Discard, không sinh Orphan Signature trong DB        │
│ FAIL-03: Policy Expired Mid-Flight     --> Revalidation Gate phát hiện, từ chối tạo Official Quote     │
│ FAIL-04: Concurrency Race trên Quote   --> OCC bắt ETag/If-Match, người thứ hai nhận 412 Precondition  │
│ FAIL-05: Cố tình Bypass F8 Send Gate   --> Backend POST /messages/send trả 403 COMPLIANCE_BLOCKED      │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Chi tiết Thao tác Kỹ thuật cho từng Kịch bản Lỗi:

1. **FAIL-01 (Sidecar UDS Crash):**
   - *Cách kích hoạt:* Trong lúc StateGraph đang chạy ở node `N-08`, gửi lệnh `kill -9 $(pgrep -f pricing_sidecar)`.
   - *Hành vi kỳ vọng:* Client kết nối UDS nhận lỗi `ConnectionRefusedError` hoặc timeout sau 3.0 giây. Node `N-09` bắt exception, cập nhật trạng thái `CALCULATION_FAILED`, phát SSE event thông báo lỗi tới UI mà không làm sập ứng dụng FastAPI.

2. **FAIL-02 (DB Crash post-KMS Sign):**
   - *Cách kích hoạt:* Inject lỗi mô phỏng (Mock exception) ngay tại dòng lệnh chuẩn bị commit transaction của hàm `execute_atomic_approval`.
   - *Hành vi kỳ vọng:* Database tự động Rollback toàn bộ. Chữ ký số vừa sinh nằm trong biến cục bộ RAM bị giải phóng. Bảng `quotes` vẫn giữ nguyên trạng thái `READY_FOR_REVIEW`. Không có bất kỳ chữ ký mồ côi nào lưu lại trong cơ sở dữ liệu.

3. **FAIL-03 (Policy Expired Mid-Flight):**
   - *Cách kích hoạt:* Khách hàng hoàn tất Pre-Sales plan với chính sách có `effective_to = '2026-09-25'`. Dùng SQL sửa ngày hiện tại của hệ thống thành `'2026-09-26'`. Bấm tạo Báo giá chính thức từ Lead Dossier.
   - *Hành vi kỳ vọng:* Node `N-04 (Re-resolve Policy)` quét lại cơ sở dữ liệu và phát hiện chính sách đã hết hạn. Hệ thống rẽ nhánh sang `N-19 (Safe Abstention Gate)`, dừng xuất bản báo giá và hiển thị cảnh báo đỏ trên giao diện Sale: `CHÍNH SÁCH ĐÃ HẾT HIỆU LỰC, CẦN CHỌN CHÍNH SÁCH MỚI`.

4. **FAIL-04 (Concurrency Race trên Quote):**
   - *Cách kích hoạt:* Mở 2 tab trình duyệt cùng truy cập vào Báo giá `Q-100` (Version 1, ETag `W/"1"`). Tại Tab 1, bấm "Yêu cầu sửa đổi" (Revision). Ngay lập tức tại Tab 2, bấm "Phê duyệt" (Approve).
   - *Hành vi kỳ vọng:* Yêu cầu ở Tab 1 được xử lý trước, tăng version lên 2. Yêu cầu ở Tab 2 gửi kèm header `If-Match: W/"1"` sẽ bị Middleware Gateway từ chối lập tức với mã HTTP **`412 Precondition Failed`** (`STALE_QUOTE_VERSION`). Giao diện Tab 2 hiển thị thông báo yêu cầu tải lại dữ liệu mới nhất.

5. **FAIL-05 (Cố tình Bypass F8 Send Gate):**
   - *Cách kích hoạt:* Dùng Postman hoặc cURL gửi request trực tiếp tới `POST /api/v1/messages/send` với nội dung tin nhắn có chứa cam kết lãi suất $0\%$ trong 10 năm (chưa từng qua kiểm duyệt hoặc đã bị đánh dấu `PROHIBITED`).
   - *Hành vi kỳ vọng:* Backend băm nội dung tin nhắn thành `message_hash`, tra cứu trong bảng `compliance_checks`. Do không có bản ghi đạt chuẩn `SUPPORTED` tương ứng, Backend từ chối ngay lập tức với mã HTTP **`403 Forbidden`** và mã lỗi `COMPLIANCE_SEND_BLOCKED`.

---

## VII. QUY CHUẨN ĐIỀU HÀNH DAILY SYNC & GIẢI QUYẾT XUNG ĐỘT KỸ THUẬT

### 7.1 Cấu trúc Phiên Daily Sync 15 Phút (Mỗi đầu ngày)
TechLead chủ trì phiên họp ngắn 15 phút vào đúng 09:00 sáng mỗi ngày. Từng thành viên báo cáo đúng 4 nội dung trọng tâm trong tối đa 3 phút:
1. Hôm qua đã hoàn thành những đầu việc và test cases nào?
2. Hôm nay cam kết hoàn thành những đầu việc nào theo kế hoạch?
3. Đang gặp khó khăn hoặc bị block bởi contract / component nào?
4. Có đề xuất thay đổi nào liên quan đến schema, API hoặc state không?

### 7.2 Cơ chế Kích hoạt Báo động & Quyết định Kiến trúc Khẩn cấp (Escalation Triggers)
Bất kỳ thành viên nào phát hiện một trong các vấn đề sau **PHẢI DỪNG LẠI VÀ BÁO CÁO NGAY CHO TECHLEAD**:
- Sai lệch bất kỳ phép tính tiền tệ nào dù chỉ 1 VNĐ ($\Delta \neq 0$).
- Bất đồng bộ giữa Pydantic model và bảng dữ liệu database.
- Node StateGraph bị rơi vào vòng lặp vô tận (Infinite Loop) hoặc treo không nhả kết nối.
- Phát hiện lỗ hổng cho phép người dùng vượt qua kiểm tra bảo mật (Bypass HITL / SoD).

**Quyền quyết định tối cao của TechLead:**
- TechLead là người duy nhất có quyền phê duyệt thay đổi Pydantic schemas tại `/backend/contracts/`.
- Mọi quyết định thay đổi kiến trúc đều phải được TechLead ghi chép chính thức vào [mydoc/baocaothhaydoi.mv](file:///d:/VinUni/P-096/mydoc/baocaothhaydoi.mv) trước khi merge vào nhánh `integration`.

---

## VIII. BẢNG CHECKLIST TỔNG KẾT THEO NGÀY CỦA TECHLEAD (DAILY EXECUTION CHECKLIST)

```markdown
- [ ] NGÀY 1 (Phase 0):
  - [ ] Khóa danh mục Canonical Enums (6 Objectives, Statuses, Tiers).
  - [ ] Khóa bộ Pydantic Schemas v2 và Error Catalog 13 mã lỗi.
  - [ ] Chạy Mock API Server 29 endpoints và cung cấp file openapi.json cho Dev 3.
  - [ ] Khởi tạo Docker Compose MVP (PostgreSQL 16 pgvector, Redis, MinIO) và chạy migrations thành công.

- [ ] NGÀY 2–3 (Phase 1):
  - [ ] Hoàn thành Spike 2 (LangGraph Checkpointing & Interrupts) chạy pass test.
  - [ ] Hoàn thành Spike 3 (KMS Server Attestation Ed25519 & Atomic Commit-Discard) chạy pass test.
  - [ ] Hoàn thành Spike 4 (Per-Quote Anti-Cyclic Hash Chain & Genesis Verify) chạy pass test.
  - [ ] Hoàn thành StateGraph Skeletons (PreSalesGraph 11 nodes & OfficialQuoteGraph 20 nodes).
  - [ ] Cài đặt xong API Gateway Middleware (Idempotency Engine & OCC ETag/If-Match).
  - [ ] Nghiệm thu Spike 1 của Dev 2 đạt 100% 15 Golden Cases.

- [ ] NGÀY 4–5 (Phase 2):
  - [ ] Hoàn thiện 11 nodes của PreSalesGraph và nối với RAG (Dev 1) và Sidecar (Dev 2).
  - [ ] Hoàn thành endpoint sinh PDF ước tính tham khảo có watermark chìm (< 1.5s).
  - [ ] Hoàn thành Consent Gate và Handoff Service tạo Lead Dossier.
  - [ ] Hoàn thành Router SSE Streaming hỗ trợ replay sự kiện qua Last-Event-ID.

- [ ] NGÀY 6–7 (Phase 3):
  - [ ] Hoàn thiện 20 nodes của OfficialQuoteGraph, kích hoạt tái thẩm định và tính lại từ Dossier.
  - [ ] Hoàn thành Endpoint chuyển đổi Lead Dossier thành Báo giá v1.
  - [ ] Hoàn thành Vòng lặp Sửa đổi (Revision Loop) sinh version mới bất biến.
  - [ ] Tích hợp xong mỏ neo dẫn chứng F4 của Dev 1 vào hồ sơ báo giá.

- [ ] NGÀY 8 (Phase 4):
  - [ ] Hoàn thành Cổng Phê duyệt Ký số KMS Ed25519 có kiểm soát SoD.
  - [ ] Hoàn thành Chuỗi Băm Kiểm toán Liên hoàn Anti-Cyclic và API verify công khai.
  - [ ] Hoàn thành Transactional Outbox Background Worker (ARQ) phát hành PDF có mã QR.
  - [ ] Đóng chốt chặn gửi tin tuân thủ F8 tại Backend (POST /api/v1/messages/send chặn 403).

- [ ] NGÀY 9–10 (Phase 5):
  - [ ] Chạy bộ test tích hợp End-to-End toàn trình Pass 100%.
  - [ ] Chạy bộ test 5 kịch bản thất bại (FAIL-01 -> FAIL-05) xử lý an toàn.
  - [ ] Hoàn thành script reset demo (bash scripts/demo_reset.sh) khôi phục trong 15s.
  - [ ] Hoàn thành kiểm tra bảo mật (không rò rỉ secret, không rò rỉ PII trong log).
  - [ ] Diễn tập tổng duyệt Showcase Demo trơn tru cùng cả team.
```

---

*Tài liệu này được lập bởi TechLead và có hiệu lực thi hành ngay lập tức. Mọi thành viên trong nhóm kỹ thuật có trách nhiệm đối chiếu tiến độ hằng ngày theo đúng các mốc phụ thuộc và tiêu chuẩn nghiệm thu đã cam kết.*
