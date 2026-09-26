# IMPLEMENTATION PLAN DETAIL
## PRICEPOLICY AI AGENT — MVP PRE-SALES FINANCIAL COPILOT

**Tên file:** `Implement_plan_detail.md`  
**Phiên bản:** 1.0  
**Trạng thái:** Kế hoạch triển khai chi tiết cho Product/Engineering Team  
**Phạm vi:** MVP gồm Customer Pre-Sales, Financial Optimizer, Sales Handover, Official Quote, F4 Claim Evidence, F8 Compliance Gate và Manager Approval  
**Team:** 1 TechLead + 3 Developers  

---

# 1. Mục tiêu triển khai

Mục tiêu của giai đoạn này là hoàn thiện một **vertical slice có thể demo và kiểm thử đầu cuối**:

```text
Customer nhập nhu cầu
→ Pre-Sales Agent hỏi và xác nhận constraint
→ Policy Time-Travel Retrieval
→ Financial Calculator deterministic
→ 1–3 phương án tham khảo
→ Evidence/Disclaimer
→ Customer consent
→ Sales Handover Dossier
→ Sale tạo Official Quote
→ F4/F8 validation
→ Manager Approval
→ Audit/PDF status
```

## 1.1. Các nguyên tắc không được phá vỡ

1. LLM không được tự tính toán số tiền.
2. Pre-Sales Plan không phải Official Quote.
3. Pre-Sales không được gọi KMS, approval hoặc Official PDF outbox.
4. Official Quote phải revalidate và recalculate sau khi được tạo từ dossier.
5. Quote version cũ immutable về business payload.
6. Exception/revision làm thay đổi quyết định phải tạo version mới.
7. Mọi claim Why/Why-not phải có evidence hoặc trạng thái unsupported.
8. Mọi tin nhắn Sale gửi khách phải qua F8 final gate nếu hệ thống có chức năng gửi.
9. Agent-visible tools không được ghi governance data.
10. Outbox là durable source of truth; worker chỉ là consumer có thể retry.

---

# 2. Cấu trúc team, Trách nhiệm Component & Implementation Spikes

Hệ thống phân bổ 11 Logic Components (`C-01` đến `C-11`) và 6 Implementation Spikes theo ma trận sở hữu:

## 2.1. TechLead
Chịu trách nhiệm chính:
- **Kiến trúc & Tích hợp:** Tổng thể hệ thống, API Gateway, Transaction Boundaries, Idempotency/OCC, Security Boundary.
- **Components Trực tiếp:**
  - `C-01`: Official Quote StateGraph Orchestrator (LangGraph).
  - `C-02`: Time-Travel & Policy Snapshot Engine (co-owner với Dev 1).
  - `C-05`: HITL Review & Cryptographic Approval Gate (KMS Server Attestation Ed25519).
  - `C-07`: Append-Only Audit Trail & Verification Engine (Anti-Cyclic Hash Chain).
  - `C-09`: Pre-Sales Advisory StateGraph Engine (co-owner với Dev 3).
- **Spikes Sở hữu:**
  - `Spike 2`: LangGraph AsyncPostgresSaver Checkpointing, Interrupt & State Replay.
  - `Spike 3`: Asymmetric Cryptographic Server Attestation (Ed25519) & Atomic Commit Discard.
  - `Spike 4`: Per-Quote Anti-Cyclic Hash Chain & Genesis Verification (co-owner với Dev 1).

## 2.2. Dev 1 — AI & Data Engineer
Chịu trách nhiệm chính:
- **Tầng Dữ liệu & Tri thức Ngữ nghĩa:** Ingestion pipeline, Supabase pgvector HNSW index, Hybrid Time-travel SQL filtering.
- **Components Trực tiếp:**
  - `C-03`: Policy Registry & Ingestion Pipeline (bao gồm F9 Structured Rule Extraction & Pre-Publish Test Gate).
  - `C-04`: Claim-Level Evidence Linking & Coordinate Parser (F4 Coordinate Traceability).
  - `C-11`: Sales Message Compliance Verification Gate (F8 Compliance Gate, 3 checkpoints, 4 tiers).
- **Spikes Sở hữu:**
  - `Spike 4`: Per-Quote Anti-Cyclic Hash Chain & Audit Trail Verification (hỗ trợ TechLead).
  - `Spike 6`: Sales Message Compliance Verification Gate & Final Send Enforcement (`POST /api/v1/messages/send`).

## 2.3. Dev 2 — Financial Math & Core API Engineer
Chịu trách nhiệm chính:
- **Tầng Tính toán Tài chính Kế toán:** Pricing Engine Sidecar, FCS v2.6 math implementation, Decimal floating-point accuracy, Golden Benchmark.
- **Components Trực tiếp:**
  - `C-06`: Deterministic Financial Pricing Engine (Unix Domain Socket sidecar, FCS v2.6, 6 Sanity Checks).
  - Golden Benchmark Test Suite (15 Golden Cases, Exact Match 100% $\Delta = 0$ VNĐ).
  - Financial Validation Gate & Ranking Engine theo 6 Mục tiêu Tối ưu chuẩn hóa.
- **Spikes Sở hữu:**
  - `Spike 1`: Financial Calculation Precision & In-Memory Worker Latency ($< 5\text{ms}$ qua UDS).

## 2.4. Dev 3 — Frontend / UI Engineer
Chịu trách nhiệm chính:
- **Tầng Giao diện & Tương tác Thời gian thực:** Next.js Multi-Role Workspaces, SSE Client Reconnect, Responsive UI.
- **Components Trực tiếp:**
  - `C-08`: Next.js Multi-Role Workspace UI (Customer Chat, Sales Copilot, Manager Approval, Policy Admin).
  - `C-09`: Web Mobile Pre-Sales Chat Client (Customer discovery, constraint confirmation, watermark PDF).
  - `C-10`: Sales Lead Dossier Management UI (Handoff dashboard, SLA countdown, 1-click quote conversion).
  - `C-11`: Sales Message Composer UI & Live Compliance Feedback (Debounce check, flag indicators, blocked send button).
- **Spikes Sở hữu:**
  - `Spike 5`: Pre-Sales Session Checkpointing, TTL & Interrupts (hợp tác với TechLead).

---

# 3. Nguyên tắc làm việc song song

## 3.1. Mock Contracts First

Trong ngày đầu, TechLead phải công bố:

```text
OpenAPI draft (29 Canonical REST Endpoints)
Pydantic request/response models (bao gồm 6 Canonical Optimization Objectives)
SSE event envelope (Tách biệt transport heartbeat)
Calculation input/output schema (FCS v2.6)
EvidenceBackedClaim & SourceCoordinate schema (F4)
ComplianceCheckResponse schema (F8)
Pre-Sales Session & Lead Dossier schema (C-09, C-10)
```

Dev 1, Dev 2 và Dev 3 không tự tạo schema cạnh tranh.

## 3.2. Quy tắc code ownership

| Khu vực | Owner | Người review bắt buộc | Components Phụ trách |
|---|---|---|---|
| `/backend/contracts/` | TechLead | Tất cả | All Schemas & DTOs |
| `/backend/orchestrator/` | TechLead | Dev 1, Dev 2 | C-01, C-05, C-07, C-09 |
| `/backend/services/rag/` | Dev 1 | TechLead | C-02, C-03 (F9) |
| `/backend/services/compliance/` | Dev 1 | TechLead, Dev 3 | C-04 (F4), C-11 (F8) |
| `/backend/pricing_sidecar/` | Dev 2 | TechLead | C-06 (FCS v2.6) |
| `/tests/benchmarks/` | Dev 2 | TechLead | Golden Benchmarks |
| `/frontend/` | Dev 3 | TechLead | C-08, C-09, C-10, C-11 |
| `/demo-data/` | Dev 1 + Dev 2 | TechLead | Fixtures & Seeds |
| `/migrations/` | TechLead | Dev 1, Dev 2 | PostgreSQL 16 DDL |

## 3.3. Quy tắc branch

```text
main                 protected/release branch
integration          branch tích hợp hằng ngày
feature/techlead-*   TechLead
feature/rag-*        Dev 1
feature/pricing-*    Dev 2
feature/frontend-*   Dev 3
```

Mỗi pull request phải có:

- mô tả thay đổi;
- test đã chạy;
- schema/API impact;
- migration impact;
- screenshot nếu thay đổi UI;
- known limitations.

---

# 4. Milestone tổng thể & Tích hợp 6 Spikes

| Milestone | Mục tiêu | Kết quả bắt buộc | Liên kết Spike |
|---|---|---|---|
| **M0 — Contract & Architecture Freeze** | Thống nhất 29 REST endpoints, Pydantic schemas, 6 Objectives, fixture skeleton | OpenAPI render pass, Mock Server active, DB migrations ready | Khởi tạo Spike 1, 2, 4 skeletons |
| **M1 — Independent Component Spikes** | Hoàn thành và chứng minh độc lập từng module kỹ thuật rủi ro cao | FCS v2.6 math pass, Supabase HNSW retrieval pass, UI mock screens pass | **Spike 1** (Math latency $< 5\text{ms}$), **Spike 2** (LangGraph Checkpoint), **Spike 5** (Pre-Sales TTL) |
| **M2 — Pre-Sales & First Integration** | Kết nối End-to-End luồng tiền bán hàng và bàn giao Lead | Customer chat $\rightarrow$ constraints $\rightarrow$ watermark PDF $\rightarrow$ Lead Dossier | **Spike 5** (Pre-Sales Interrupts & Handoff Gate) |
| **M3 — Official Quote & Financial Engine** | Chuyển đổi Lead thành Báo giá chính thức, revalidation & recalculation | LangGraph 20 nodes pass, 6 Sanity checks pass, F4 Claim coordinates verified | **Spike 1** (UDS sidecar integration), **Spike 2** (Quote Revision/Exception replay) |
| **M4 — Governance, Compliance & Security** | Hoàn tất rào chắn tuân thủ thông điệp và bảo chứng phê duyệt mật mã | F8 Send Gate enforced, KMS Server Attestation Ed25519, Anti-Cyclic hash audit pass | **Spike 3** (Ed25519 Atomic Commit Discard), **Spike 4** (Hash Chain Genesis Verify), **Spike 6** (Compliance Gate) |
| **M5 — Controlled Demo & Production Readiness** | Tổng duyệt toàn diện kịch bản demo và kiểm thử chịu tải / lỗi biên | 5 Failure paths handled (FAIL-01..05), Golden benchmark 100% exact match | Nghiệm thu toàn bộ 6 Spikes & Full-Funnel Demo |

---

# 5. PHASE 0 — Chuẩn bị và Contract Freeze

## 5.1. TechLead — Công bố contract package

### Đầu việc lớn

Tạo contract package dùng chung cho toàn team.

### Task chi tiết

#### TL-0.1 — Chuẩn hóa domain enum

Định nghĩa và đóng băng toàn bộ các Canonical Enums:

```text
PreSalesSessionStatus: ACTIVE, WAITING_FOR_CUSTOMER_INPUT, WAITING_FOR_CONSTRAINT_CONFIRMATION, WAITING_FOR_HANDOFF_CONSENT, HANDED_OFF, EXPIRED, ABANDONED
LeadDossierStatus: NEW, ASSIGNED, CONTACTED, QUALIFIED, CONVERTED_TO_QUOTE, EXPIRED, DISQUALIFIED
QuoteWorkflowStatus: DRAFT, NEEDS_INPUT, ANALYZING, EXCEPTION_INPUT, CALCULATING, CALCULATION_FAILED, READY_FOR_REVIEW, NEEDS_REVISION, ABSTAINED, BLOCKED, REJECTED, APPROVED, SUPERSEDED, REVOKED
ApprovalStatus: NOT_REQUIRED, PENDING, ATTESTED, APPROVED, APPROVAL_FAILED, REJECTED, REVISION_REQUESTED
PdfStatus: NOT_REQUESTED, PENDING, GENERATING, ISSUED, FAILED, RETRYING, MANUAL_INTERVENTION
PolicyDecisionStatus: ELIGIBLE, NOT_ELIGIBLE, CONFLICT, AMBIGUOUS, EXPIRED
ComplianceStatus: DRAFT, CHECKING, SUPPORTED, CONDITIONAL, UNSUPPORTED, PROHIBITED, EXPIRED, SUPERSEDED
ComplianceTier: TIER_1_GREEN, TIER_2_YELLOW, TIER_3_RED, TIER_4_BLACK
OptimizationObjective (Canonical 6 Objectives):
  - MIN_NET_PRICE
  - MIN_INITIAL_CASH
  - MIN_MONTHLY_BURDEN
  - MIN_TOTAL_CASH_OUTFLOW
  - MAX_BENEFIT_VALUE
  - EARLY_HANDOVER
```

Không gộp:
- Quote status
- Approval status
- PDF status
- Compliance status

#### TL-0.2 — Chuẩn hóa Pydantic models

Tạo models cho:

```text
CustomerConstraint
CalculationInput
CalculationResult
Scenario
EvidenceBackedClaim
SourceCoordinate
PreSalesPlan
LeadDossier
ComplianceCheckRequest
ComplianceCheckResponse
SseEventEnvelope
OfficialQuoteCreateRequest
```

#### TL-0.3 — Chuẩn hóa Error Catalog

Tối thiểu:

```text
INPUT_VALIDATION_ERROR
MISSING_TRANSACTION_DATE
POLICY_NOT_FOUND
POLICY_EXPIRED
POLICY_CONFLICT_UNRESOLVED
FINANCIAL_SANITY_FAILED
STALE_QUOTE_VERSION
INVALID_STATE_TRANSITION
IDEMPOTENCY_PROCESSING
IDEMPOTENCY_KEY_REUSE_PAYLOAD_MISMATCH
EXPLANATION_VALIDATION_FAILED
COMPLIANCE_BLOCKED
PDF_NOT_READY
```

#### TL-0.4 — Công bố Mock Server

Mock Server phải mô phỏng:

- create Pre-Sales Session;
- customer message;
- plan ready;
- handoff dossier;
- calculation result;
- evidence result;
- compliance result;
- SSE events;
- quote status.

### Định hướng triển khai

- Tất cả request/response có schema version.
- ID dùng dạng deterministic trong demo hoặc UUID trong runtime.
- Tiền dùng integer VND.
- Timestamp dùng ISO 8601 UTC.
- Mọi artifact reference có version/hash.

### Checklist hoàn thành

- [ ] Models import được trong backend/frontend contract generation.
- [ ] OpenAPI render thành công.
- [ ] Mock Server trả đúng schema.
- [ ] Có example happy path và error path.
- [ ] Enum không trùng nghĩa.
- [ ] `quote_version`, `policy_version`, `artifact_hash` xuất hiện đúng nơi.
- [ ] Team review và ký xác nhận contract freeze.

---

## 5.2. TechLead — Repository, CI và local environment

### Task chi tiết

- tạo Docker Compose profile cho local MVP;
- tạo `.env.example`;
- tạo migration runner;
- tạo lint/typecheck/test command;
- tạo seed command;
- tạo health endpoint;
- tạo OpenAPI export;
- tạo test database profile.

### Checklist

- [ ] Một developer mới có thể chạy hệ thống theo README.
- [ ] `docker compose up` khởi động được service cần thiết.
- [ ] Migration chạy idempotently.
- [ ] Seed data chạy lặp không tạo duplicate.
- [ ] CI chạy lint, typecheck, unit test.
- [ ] Secret không commit vào repository.

---

# 6. PHASE 1 — DEV 1: AI & DATA ENGINEER

## 6.1. D1-1 — Chuẩn bị và nạp dữ liệu demo

### Đầu việc lớn

Xây dựng pipeline nạp dữ liệu từ `mydoc/dataset` vào PostgreSQL/pgvector và object storage.

### Task chi tiết

1. Kiểm kê file:
   - PDF;
   - DOCX;
   - XLSX;
   - CSV;
   - golden fixture.
2. Tạo manifest dữ liệu:

```json
{
  "document_id": "DOC-001",
  "filename": "early-payment-v3.pdf",
  "document_hash": "sha256:...",
  "policy_id": "POL-001",
  "policy_version": "v3",
  "effective_from": "2026-09-01",
  "effective_to": "2026-09-30",
  "status": "ACTIVE"
}
```

3. Parse text và bảng.
4. Bảo toàn page, section, clause, table/row coordinate.
5. Chunk theo heading/clause, không chunk tùy tiện theo số ký tự.
6. Tạo embeddings.
7. Insert policy registry, clauses, chunks và embeddings.
8. Validate số document/chunk/embedding.

### Định hướng

- Source document là source of truth.
- pgvector chỉ là retrieval index.
- Không ingest document không có hash hoặc effective period trong official corpus.
- Các document demo có thể synthetic nhưng phải ghi rõ `synthetic=true`.

### Checklist

- [ ] Mọi document có SHA-256.
- [ ] Mọi clause có policy/version/page/section.
- [ ] Chunk không mất tiêu đề bảng.
- [ ] Embedding dimension đúng 1536 nếu contract đã chốt.
- [ ] Policy hết hạn vẫn lưu nhưng không được trả về active query.
- [ ] Có report document/chunk count.
- [ ] Re-run ingestion không tạo duplicate.

---

## 6.2. D1-2 — Time-Travel Policy Retrieval

### Đầu việc lớn

Xây `retrieve_policy_by_date` kết hợp semantic retrieval và filter nghiệp vụ.

### Task chi tiết

1. Nhận input:

```json
{
  "query": "chiết khấu thanh toán sớm cho căn 2BR",
  "project_id": "PROJECT-001",
  "transaction_date": "2026-09-16",
  "unit_type": "2BR",
  "customer_segment": "STANDARD",
  "channel": "DIRECT"
}
```

2. Pre-filter theo:

```text
project
policy status
valid_from/valid_to
unit_type
customer segment
channel
```

3. Chạy semantic retrieval.
4. Chạy keyword/full-text retrieval nếu có.
5. Merge candidate.
6. Rerank.
7. Resolve clause and source coordinates.
8. Loại policy stale/expired.
9. Trả evidence set có ranking và support metadata.

### Định hướng

Không để vector similarity quyết định hiệu lực policy. Effective-date validation phải là SQL/business rule bắt buộc.

### Checklist

- [ ] Query đúng policy active.
- [ ] Policy hết hạn không xuất hiện trong final evidence.
- [ ] Policy cùng nội dung nhưng khác version được phân biệt.
- [ ] Filter project/segment/channel hoạt động.
- [ ] Kết quả chứa clause/page/hash.
- [ ] Có test policy replacement.
- [ ] Có test không tìm thấy active policy.
- [ ] Có benchmark Recall@k trên golden retrieval cases.

---

## 6.3. D1-3 — Structured Policy Rule và Conflict Input

### Đầu việc lớn

Chuyển clause đã xác minh thành rule có cấu trúc cho conflict evaluator.

### Task chi tiết

- tạo candidate rule từ policy clause;
- lưu điều kiện, benefit, exclusion, priority;
- gắn `source_refs`;
- trạng thái `VALIDATION_REQUIRED`;
- hỗ trợ `STACKABLE`, `MUTUALLY_EXCLUSIVE`, `REPLACES`;
- tạo fixture conflict.

### Định hướng

LLM chỉ tạo candidate extraction. Rule chỉ được dùng trong Official Quote khi:

```text
validation_status = APPROVED_FOR_USE
```

### Checklist

- [ ] Rule có source clause.
- [ ] Rule có policy version.
- [ ] Rule chưa validate không lọt vào active retrieval.
- [ ] Conflict relation có test.
- [ ] Replacement relation có test.
- [ ] Scope rule test pass.

---

## 6.4. D1-4 — Claim-Level Evidence Linking F4

### Đầu việc lớn

Xây dựng claim parser/verifier cho Why/Why-not, Pre-Sales và Compliance.

### Task chi tiết

1. Nhận output claim có cấu trúc.
2. Phân loại archetype:

```text
POLICY_REASON
CALCULATION_RESULT
DERIVED_RECOMMENDATION
USER_PROVIDED
```

3. Resolve evidence refs từ trusted registry.
4. Gắn `SourceCoordinate`:

```text
Document ID
Document Version
Document Hash
Page
Section
Clause ID
```

5. Gắn `CalculationArtifact` field path cho claim số học.
6. Phát hiện partial support.
7. Phát hiện unsupported/contradicted.
8. Trả result cho UI và approval package.

### Định hướng

LLM không được tự điền page/hash/clause tùy ý. Server phải resolve từ evidence registry.

### Checklist

- [ ] Claim policy có policy/version/clause/page/hash.
- [ ] Claim số tiền có calculation field path.
- [ ] Claim “không trả gốc” không bị biến thành “không trả gốc và lãi”.
- [ ] Partial support được tách thành unsupported fragment.
- [ ] Claim không có evidence bị đánh dấu.
- [ ] Có fixture Why/Why-not.
- [ ] Có tampering test document hash.
- [ ] Có test stale policy version.

---

## 6.5. D1-5 — Compliance Gate F8

### Đầu việc lớn

Xây `Claim Compliance Service` dùng chung cho Agent-generated và Sale-authored message.

### Task chi tiết

1. Nhận message và quote/policy context.
2. Bóc tách claim rủi ro:
   - giá;
   - discount;
   - lãi suất;
   - ân hạn;
   - thời hạn;
   - quà tặng;
   - cam kết lợi nhuận;
   - cam kết phê duyệt tín dụng.
3. Validate từng claim.
4. Trả 4 mức:

```text
SUPPORTED
CONDITIONAL
UNSUPPORTED
PROHIBITED
```

5. Tạo `message_hash`.
6. Gắn `quote_version`/`policy_version`.
7. Hỗ trợ các mode:

```text
ON_DRAFT
DEBOUNCE
FINAL_SEND
```

8. Tạo response cho Composer.

### Định hướng

- Check on-draft có thể nhanh và nhẹ.
- Debounce không gọi LLM mỗi phím; dùng 500ms hoặc local rule pre-check.
- Final send phải chạy server-side, không tin trạng thái từ browser.
- Nếu MVP chỉ copy, phải ghi rõ đây là pre-send check, không phải send gate.

### Checklist

- [ ] Agent-generated message cũng bị kiểm tra.
- [ ] Sale-edited message bị kiểm tra lại.
- [ ] Message hash thay đổi thì kết quả cũ mất hiệu lực.
- [ ] Quote version thay đổi thì check lại.
- [ ] Claim “chắc chắn vay 70%” bị block.
- [ ] Claim “ân hạn nợ gốc” được phân biệt với “miễn cả gốc và lãi”.
- [ ] Có test `SUPPORTED`, `CONDITIONAL`, `UNSUPPORTED`, `PROHIBITED`.
- [ ] Có API contract cho final send hoặc xác nhận MVP chỉ copy/export.

---

# 7. PHASE 1 — DEV 2: FINANCIAL MATH & CORE API

## 7.1. D2-1 — Pricing Engine Sidecar

### Đầu việc lớn

Xây pricing engine độc lập, không phụ thuộc LLM, giao tiếp qua UDS.

### Task chi tiết

- tạo input/output schema;
- cấu hình `decimal.Decimal` precision 28;
- cấm float trong calculation path;
- triển khai UDS server;
- hard timeout;
- validate request size;
- trả error envelope nội bộ;
- health/readiness check;
- graceful shutdown.

### Định hướng

Pricing worker:

- không mở network socket;
- không truy cập internet;
- không đọc policy trực tiếp;
- chỉ nhận normalized `PricingInput`;
- không chứa business prompt;
- không tự quyết định eligibility.

### Checklist

- [ ] Worker chạy non-root/read-only nếu profile hỗ trợ.
- [ ] UDS permission đúng.
- [ ] Không có float trong source calculation.
- [ ] Invalid input bị từ chối.
- [ ] Timeout được kiểm tra.
- [ ] Cùng input cho cùng output/hash.
- [ ] Có health check.

---

## 7.2. D2-2 — Ba phương án FCS

### Đầu việc lớn

Triển khai các scenario theo FCS canonical contract.

### Task chi tiết

1. `PA-CHUAN`/`PA-CHUDONG` theo tên canonical đã được TechLead chốt.
2. `PA-NHANH` thanh toán sớm 95%.
3. `PA-VAY` hỗ trợ lãi suất.
4. Tính:
   - listed price before tax;
   - discount;
   - net price;
   - VAT;
   - KPBT;
   - total contract price;
   - payment schedule;
   - cash outflow;
   - benefit value.
5. Nhận policy-derived parameters thay vì hardcode.

### Định hướng

Không dùng tên scenario khác nhau giữa FCS, UI, API và fixture. TechLead phải chốt một enum canonical trước khi code.

### Checklist

- [ ] Tất cả field dùng tên chuẩn `_vnd`.
- [ ] Không hardcode `listed_price_vat`.
- [ ] Policy snapshot truyền đúng vào calculator.
- [ ] Tổng các đợt thanh toán khớp contract.
- [ ] Không có giá trị âm.
- [ ] VAT/KPBT đúng policy context.
- [ ] Output có calculation hash.

---

## 7.3. D2-3 — Financial Validation Gate

### Sáu nhóm sanity check

1. Không có số tiền âm.
2. Tổng dòng tiền khớp tổng contract price theo FCS.
3. Giá net không vượt price boundary.
4. VAT/KPBT khớp rate snapshot.
5. Tỷ lệ các đợt thanh toán hợp lệ.
6. Discount/benefit không vượt policy bounds.

### Định hướng

Validation result phải có field-level error:

```json
{
  "valid": false,
  "errors": [
    {
      "code": "PAYMENT_SCHEDULE_SUM_MISMATCH",
      "field": "payment_schedule",
      "expected_vnd": 4500000000,
      "actual_vnd": 4499999999
    }
  ]
}
```

### Checklist

- [ ] Mỗi sanity check có unit test.
- [ ] Có negative test.
- [ ] Không để LLM bypass validation.
- [ ] `CALCULATION_FAILED` chuyển đúng workflow state.
- [ ] Validation result có calculation artifact ref.

---

## 7.4. D2-4 — Ranking và Objective

### Đầu việc lớn

Xây ranking deterministic cho 1–3 scenario.

### Task chi tiết

- chốt `OptimizationObjective` enum;
- tạo comparison key;
- tie-break deterministic;
- xử lý infeasible scenario;
- tạo ranking metadata;
- không dùng score mơ hồ nếu không cần.

### Checklist

- [ ] Cùng input cho cùng ranking.
- [ ] Objective được lưu trong artifact.
- [ ] Tie-break rule ID được trả về.
- [ ] Scenario infeasible không thể đứng hạng 1.
- [ ] Golden ranking tests pass.

---

## 7.5. D2-5 — Golden Benchmark Suite

### Đầu việc lớn

Chạy 15 golden cases từ `golden_scenarios.json`.

### Task chi tiết

- tạo test runner;
- compare exact integer VND;
- compare calculation hash;
- compare eligibility/status;
- compare scenario ranking;
- xuất report JSON/HTML;
- thêm property-based test sau khi golden suite ổn định.

### Checklist

- [ ] 15/15 cases pass.
- [ ] Delta mỗi field bằng 0 VND khi yêu cầu exact.
- [ ] Có report commit artifact.
- [ ] Fail case hiển thị input/expected/actual.
- [ ] CI chạy benchmark trước merge.
- [ ] Thay đổi công thức làm test fail rõ ràng.

---

# 8. PHASE 1 — DEV 3: FRONTEND/UI & SSE

## 8.1. D3-1 — Customer Pre-Sales UI

### Đầu việc lớn

Xây giao diện guided conversation, không dùng chat box trống đơn thuần.

### Task chi tiết

- welcome screen với quick actions;
- guided question chips;
- input số tiền có format VND;
- hiển thị extracted constraints;
- cho khách confirm/edit assumptions;
- loading state theo business step;
- scenario cards;
- watermark `PRE-SALES ESTIMATE — NOT AN OFFICIAL QUOTE`;
- evidence popover;
- disclaimer;
- CTA handoff.

### Định hướng UX

Không hiển thị technical reasoning. Hiển thị:

```text
Đã hiểu nhu cầu
Đang kiểm tra chính sách
Đang tính phương án
Đã kiểm tra điều kiện
```

### Checklist

- [ ] Mobile responsive.
- [ ] Không hiển thị nhãn Approved trong Pre-Sales.
- [ ] Assumption được nhìn thấy và sửa được.
- [ ] Plan có disclaimer.
- [ ] Evidence mở được từ claim.
- [ ] Empty/loading/error/abstain state đầy đủ.
- [ ] Session refresh không làm mất context nếu còn hạn.
- [ ] Handoff yêu cầu consent rõ ràng.

---

## 8.2. D3-2 — Sales Dashboard và Lead Dossier

### Đầu việc lớn

Xây workspace cho Sale xử lý dossier và tạo Official Quote.

### Task chi tiết

- danh sách lead;
- lead detail;
- nhu cầu và financial inputs;
- assumptions;
- plan comparison;
- evidence panel;
- transcript summary/redaction;
- lead temperature;
- nút `Create Official Quote`;
- hiển thị policy changed khi revalidation khác pre-sales;
- trạng thái handoff/assignment.

### Checklist

- [ ] Sale chỉ xem dossier trong scope.
- [ ] PII được mask theo role.
- [ ] Có source session/dossier ref.
- [ ] Có cảnh báo nếu plan đã hết hạn.
- [ ] Create quote không kế thừa approval.
- [ ] UI hiển thị revalidation/recalculation đang chạy.
- [ ] Error stale dossier/version hiển thị rõ.

---

## 8.3. D3-3 — Sales Message Composer F8

### Đầu việc lớn

Tích hợp generator và verifier thành một composer.

### Task chi tiết

- chọn quote/plan context;
- nút tạo tin nhắn đề xuất;
- ô chỉnh sửa tự do;
- debounce check 500ms;
- claim highlights;
- màu xanh/vàng/đỏ;
- hiển thị evidence;
- hiển thị suggested rewrite;
- khóa send/copy tùy compliance policy;
- final check trước action.

### Định hướng

Không dùng màu đỏ chỉ cho lỗi chính tả. Màu đỏ dành cho claim nghiệp vụ nguy hiểm.

### Checklist

- [ ] Tin do Agent sinh cũng được check.
- [ ] Tin Sale sửa bị check lại.
- [ ] Claim được highlight theo span nếu có.
- [ ] Evidence panel mở đúng clause.
- [ ] Message hash thay đổi sau chỉnh sửa.
- [ ] Quote/policy context hiển thị.
- [ ] Nút gửi bị khóa khi `PROHIBITED`.
- [ ] Nếu MVP chỉ copy, UI không tuyên bố đã gửi.

---

## 8.4. D3-4 — Manager Approval Dashboard

### Đầu việc lớn

Xây màn hình review approval package.

### Task chi tiết

- quote/version header;
- policy snapshot;
- 3 scenarios;
- risk flags;
- F4 claims/evidence;
- compliance result;
- SoD status;
- exception record;
- OCC version/ETag;
- approve/reject/revision;
- PDF status;
- audit timeline.

### Checklist

- [ ] Không hiển thị nút approve nếu state không hợp lệ.
- [ ] Hiển thị stale version.
- [ ] Re-auth không log ra browser console/server log.
- [ ] Approve cần confirmation.
- [ ] Revision yêu cầu reason.
- [ ] Exception hiển thị scope/authority hash.
- [ ] PDF chỉ hiển thị issued sau worker success.

---

## 8.5. D3-5 — SSE Client

### Đầu việc lớn

Xây SSE client với replay/reconnect.

### Task chi tiết

- parse `SseEventEnvelope`;
- lưu `Last-Event-ID`;
- tự reconnect với backoff;
- deduplicate event ID;
- fallback REST khi replay window expired;
- mapping event sang UI state;
- heartbeat handling;
- hiển thị connection status.

### Checklist

- [ ] Reconnect không tạo duplicate UI event.
- [ ] Event sequence tăng đúng.
- [ ] `Last-Event-ID` gửi lại đúng.
- [ ] Xử lý `410 RESYNC_FULL_STATE`.
- [ ] Heartbeat không hiển thị như business event.
- [ ] SSE session bị unauthorized thì đóng đúng.
- [ ] UI vẫn hiển thị state cuối khi SSE mất.

---

# 9. TECHLEAD — ORCHESTRATION & INTEGRATION TASKS

## 9.1. TL-1 — Pre-Sales StateGraph

### Graph

```text
START
→ initialize_pre_sales_session
→ collect_customer_input
→ extract_constraints
→ validate_constraints
→ security_guardrail_input
→ resolve_active_policy
→ retrieve_policy_evidence
→ security_guardrail_content
→ evaluate_policy_clauses
→ detect_conflicts
→ safe_decision_gate
→ build_pricing_input
→ calculate_scenarios
→ validate_calculation
→ rank_scenarios
→ generate_explanation
→ validate_explanation
→ build_reference_plan
→ present_plan
→ await_handoff_consent
→ build_lead_dossier
→ handoff_to_sales
→ END
```

### Task chi tiết

- thread ID/namespace;
- checkpoint persistence;
- interrupt/resume;
- session TTL;
- retry node;
- safe abstention;
- event emission;
- artifact references;
- no governance side effects.

### Checklist

- [ ] Customer input interrupt resume được.
- [ ] Consent interrupt resume được.
- [ ] Worker crash vẫn resume được.
- [ ] Pre-Sales không gọi approval/KMS/PDF official.
- [ ] State có session/version/artifact refs.
- [ ] Conflict đi đúng abstain/clarification.
- [ ] Session expired có trạng thái rõ.

---

## 9.2. TL-2 — Official Quote Conversion

### Luồng

```text
Lead Dossier
→ Create Quote v1
→ Resolve active policy again
→ Validate transaction context
→ Recalculate
→ Validate explanation
→ Safe decision gate
→ Ready for review
```

### Task chi tiết

- idempotent create quote;
- source dossier/session ref;
- OCC;
- transaction context snapshot;
- detect policy changed;
- re-run calculation;
- create approval package;
- emit SSE events.

### Checklist

- [ ] Official quote có version mới.
- [ ] Không copy approval từ pre-sales.
- [ ] Policy active được re-resolve.
- [ ] Calculation chạy lại.
- [ ] Dossier stale bị xử lý rõ.
- [ ] Duplicate command không tạo quote duplicate.
- [ ] Quote có source dossier ref.

---

## 9.3. TL-3 — API Gateway, Idempotency và OCC

### Task chi tiết

- implement request authentication;
- RBAC/data scope;
- `X-Correlation-ID`;
- `Idempotency-Key`;
- payload fingerprint;
- ETag/If-Match;
- error envelope;
- rate limit public Pre-Sales;
- CORS/CSRF strategy;
- request size limit.

### Checklist

- [ ] Same key/same payload replay đúng.
- [ ] Same key/different payload trả 409.
- [ ] Stale If-Match trả đúng status.
- [ ] Public API không truy cập internal audit.
- [ ] Sale không tự approve quote của mình.
- [ ] PII không rò trong error details.
- [ ] Rate limiting hoạt động.

---

## 9.4. TL-4 — Official Approval/PDF Integration

### Task chi tiết

- approval intent;
- re-auth;
- sign-before-commit;
- snapshot/audit/outbox transaction;
- PDF status separation;
- outbox retry;
- recovery reconciliation;
- QR verification.

### Checklist

- [ ] DB crash sau KMS không công bố orphan signature.
- [ ] Retry cùng idempotency key không ký lại.
- [ ] Audit chain không cyclic.
- [ ] PDF worker duplicate-safe.
- [ ] Upload-success/DB-failure recovery pass.
- [ ] PDF chưa issued không trả download thành công.

---

## 9.5. TL-5 — Integration Tests và Demo Orchestration

### Task chi tiết

- tạo integration test harness;
- tạo seeded tenant/project;
- nối Mock Server → real service từng bước;
- viết demo seed/reset;
- tạo trace ID cho demo;
- tạo failure injection flags;
- chuẩn bị runbook.

### Checklist

- [ ] Demo reset được về trạng thái sạch.
- [ ] Happy path chạy từ customer đến manager.
- [ ] Conflict path chạy đúng.
- [ ] Compliance path chạy đúng.
- [ ] Abstention path chạy đúng.
- [ ] Revision path tạo version mới.
- [ ] Có log/trace cho từng bước.

---

# 10. Hợp đồng giao tiếp giữa các thành viên

## 10.1. Pricing API nội bộ

```json
{
  "schema_version": "pricing-input.v1",
  "execution_context": "PRE_SALES",
  "quote_id": null,
  "quote_version": null,
  "asset": {
    "unit_code": "A-12.04",
    "listed_price_before_tax_vnd": 4500000000
  },
  "policy_snapshot_ref": {
    "policy_id": "POL-001",
    "policy_version": "v3",
    "snapshot_hash": "sha256:..."
  },
  "customer_constraints": {
    "own_funds_vnd": 900000000,
    "monthly_capacity_vnd": 20000000
  },
  "objective": "MIN_INITIAL_CASH"
}
```

## 10.2. Evidence claim contract

```json
{
  "claim_id": "WHY-001",
  "claim_type": "POLICY_REASON",
  "text": "...",
  "support_status": "SUPPORTED",
  "source_coordinates": [
    {
      "document_id": "DOC-001",
      "document_version": "v3",
      "document_hash": "sha256:...",
      "page": 12,
      "section": "4.2",
      "clause_id": "CLAUSE-4.2.1"
    }
  ],
  "calculation_refs": []
}
```

## 10.3. SSE event contract

```json
{
  "event_id": "SES-001:v1:000004",
  "event_seq": 4,
  "event_type": "PRE_SALES_PLAN_READY",
  "session_id": "SES-001",
  "quote_id": null,
  "quote_version": null,
  "schema_version": "sse-event.v1",
  "correlation_id": "trace-001",
  "occurred_at": "2026-09-22T09:00:00Z",
  "payload": {
    "plan_id": "PLAN-001"
  }
}
```

## 10.4. Compliance response contract

```json
{
  "check_id": "CHECK-001",
  "message_hash": "sha256:...",
  "mode": "FINAL_SEND",
  "overall_status": "CONDITIONAL",
  "quote_id": "QUOTE-001",
  "quote_version": 1,
  "policy_version_refs": ["POL-001:v3"],
  "claims": [],
  "required_action": "KEEP_REQUIRED_CONDITION"
}
```

---

# 11. Ma trận phụ thuộc và thứ tự triển khai

| Task | Phụ thuộc | Có thể làm song song? |
|---|---|---|
| Contract models | Không | Làm đầu tiên |
| Seed/ingestion | Policy schema | Có sau contract |
| Pricing engine | Pricing schema/FCS | Có song song Dev 1 |
| Customer UI | Mock API/SSE schema | Có song song |
| Retrieval | Policy schema/embedding config | Có song song |
| F4 verifier | Retrieval/evidence schema | Sau evidence schema |
| F8 verifier | Claim schema/policy retrieval | Sau F4 nền tảng |
| Pre-Sales graph | Các service contracts | Sau mock contract |
| Sales Dashboard | Dossier schema | Có thể dùng mock |
| Official quote conversion | Graph + pricing + retrieval | Sau M1 |
| Manager approval | Existing approval contract | Có thể tích hợp sau official quote |
| Final send gate | F8 + channel contract | Sau compliance API |

---

# 12. Kế hoạch theo ngày/sprint

## Ngày 1 — Contract và skeleton

### TechLead

- freeze schemas;
- tạo repo structure;
- mock server;
- local compose;
- event/error contract.

### Dev 1

- inventory dataset;
- manifest schema;
- ingestion skeleton;
- evidence/source coordinate model.

### Dev 2

- pricing input/output model;
- UDS sidecar skeleton;
- first golden fixture.

### Dev 3

- Next.js shell;
- customer/sales/manager route;
- mock API client;
- design tokens/components.

### Exit criteria

- [ ] Tất cả service build được.
- [ ] Mock end-to-end chạy được.
- [ ] Không còn schema TBD cho integration points.

## Ngày 2–3 — Independent modules

- Dev 1: ingestion, retrieval, F4 base.
- Dev 2: three scenarios, validation, benchmark.
- Dev 3: customer UI, scenario cards, evidence popover.
- TechLead: StateGraph skeleton, API gateway, checkpoint.

### Exit criteria

- [ ] Retrieval test pass.
- [ ] Calculator golden cases pass.
- [ ] UI chạy với mock.
- [ ] Graph có checkpoint.

## Ngày 4–5 — Pre-Sales integration

- nối constraint extraction;
- nối retrieval;
- nối pricing;
- hiển thị plan;
- consent/handoff;
- dossier persistence;
- SSE event.

### Exit criteria

- [ ] Customer happy path chạy thật.
- [ ] Plan có disclaimer/evidence.
- [ ] Handoff tạo dossier.
- [ ] SSE reconnect pass.

## Ngày 6–7 — Official Quote và Sales Dashboard

- create quote from dossier;
- revalidation/recalculation;
- Sales Dashboard;
- official quote status;
- F4 claims.

### Exit criteria

- [ ] Dossier → quote chạy được.
- [ ] Policy change được phát hiện.
- [ ] Quote version/reference đúng.

## Ngày 8 — F8 và Manager Approval

- Message Composer;
- compliance check;
- approval package;
- manager dashboard;
- revision/exception cơ bản.

### Exit criteria

- [ ] Agent-generated message được check.
- [ ] Sale-edited message được check.
- [ ] Prohibited claim bị khóa.
- [ ] Manager approve/revision hoạt động.

## Ngày 9 — Failure/recovery/integration

- idempotency;
- stale version;
- worker crash;
- outbox retry;
- PDF status;
- policy expired/conflict;
- evidence tampering.

## Ngày 10 — Demo hardening

- seed/reset;
- performance smoke test;
- UI polish;
- runbook;
- evidence report;
- rehearsal.

---

# 13. Definition of Done chung

Một task chỉ được coi là hoàn thành khi:

- [ ] Code đã merge qua integration branch.
- [ ] Có unit test hoặc integration test phù hợp.
- [ ] Không phá schema contract.
- [ ] Có logging/correlation ID.
- [ ] Có xử lý error path.
- [ ] Có cập nhật README/API example nếu cần.
- [ ] Có checklist của task được đánh dấu.
- [ ] TechLead review nếu liên quan security, money, state hoặc persistence.
- [ ] Không dùng dữ liệu hardcode ngoài fixture được phê duyệt.
- [ ] Không có secret/PII thật trong code hoặc dataset.

---

# 14. Test matrix bắt buộc trước demo

## Happy path

- [ ] Customer nhập đủ thông tin.
- [ ] Policy active được tìm thấy.
- [ ] Ba scenario tính đúng.
- [ ] Plan hiển thị evidence.
- [ ] Handoff tạo dossier.
- [ ] Sale tạo official quote.
- [ ] Manager approve.

## Difficult cases

- [ ] Thiếu transaction date.
- [ ] Thiếu monthly capacity.
- [ ] Policy expired.
- [ ] Policy conflict.
- [ ] Non-stackable benefit.
- [ ] Ngân sách không khả thi.
- [ ] Claim partially supported.
- [ ] Sale claim prohibited.
- [ ] Policy thay đổi giữa Pre-Sales và Official Quote.
- [ ] Stale quote version.
- [ ] Duplicate idempotency key.
- [ ] Worker crash.
- [ ] SSE reconnect.
- [ ] Revision tạo version mới.
- [ ] Exception cần Manager.

## Security

- [ ] Prompt injection từ customer input.
- [ ] Prompt injection trong document.
- [ ] Unauthorized dossier access.
- [ ] SoD violation.
- [ ] Final send bypass attempt.
- [ ] PII xuất hiện trong log.
- [ ] Governance command bị gọi từ Agent tool.

---

# 15. Daily sync format — 15 phút

Mỗi thành viên báo cáo đúng bốn mục:

1. Hôm qua đã hoàn thành gì?
2. Hôm nay sẽ hoàn thành gì?
3. Đang bị block bởi contract/service nào?
4. Có thay đổi schema, state hoặc API nào không?

Không dùng daily sync để review code chi tiết.

## Escalation rule

Phải báo TechLead ngay khi thay đổi liên quan đến:

```text
money field
policy version
workflow state
approval permission
PII
event schema
idempotency
OCC
```

---

# 16. Release gate cho MVP demo

MVP chỉ được chuyển sang demo khi:

- [ ] 15 golden financial cases pass.
- [ ] Retrieval active-date cases pass.
- [ ] F4 claim/evidence cases pass.
- [ ] F8 four-tier cases pass.
- [ ] Customer → dossier → quote flow pass.
- [ ] Official quote revalidation pass.
- [ ] Manager approval/OCC/SoD pass.
- [ ] SSE reconnect pass.
- [ ] Outbox/retry smoke test pass.
- [ ] UI có loading/error/abstention state.
- [ ] Không có official claim từ Pre-Sales Plan.
- [ ] Demo dataset không chứa PII thật.
- [ ] Có runbook reset/demo.
- [ ] Có danh sách known limitations.

---

# 17. Kết luận

Kế hoạch này phân tách rõ bốn vùng trách nhiệm:

```text
TechLead
→ contracts, orchestration, governance, integration

Dev 1
→ policy intelligence, evidence, compliance

Dev 2
→ deterministic money, validation, benchmarks

Dev 3
→ customer/sales/manager experience, SSE
```

Mỗi thành viên có thể code song song sau khi `Contract Freeze` hoàn tất. Các điểm giao tiếp quan trọng đều được chuẩn hóa trước:

```text
Pydantic schema
Pricing payload
Evidence claim
Compliance response
SSE event
Error envelope
```

Mục tiêu không phải hoàn thiện mọi tính năng enterprise trong một lần, mà là tạo một vertical slice đáng tin cậy:

```text
Customer Pre-Sales
→ Evidence-backed Financial Plan
→ Sales Handover
→ Official Quote
→ Compliance Check
→ Manager Approval
```

Nếu vertical slice này pass toàn bộ checklist và test matrix, đội có thể tiếp tục mở rộng sang CRM, Zalo Official API, policy simulation và domain adapter mà không phải phá vỡ lõi tính toán, workflow hoặc governance hiện tại.
