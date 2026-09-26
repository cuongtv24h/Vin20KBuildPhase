# Đánh giá mức độ tích hợp các tính năng mới

## Kết luận ngắn

Sau khi đối chiếu:

- `TD-4.5 — New Features & Integration Design`;
- `3.architecture-design.md`;
- `4.1-technical-architecture-runtime-deployment.md`;

có thể kết luận:

> **Các tính năng mới đã được tích hợp đúng ở tầng ý tưởng, component và nguyên tắc an toàn; tuy nhiên chưa hoàn toàn đầy đủ ở tầng business sequence, state lifecycle, API contract, persistence và executable acceptance test.**

Mức đánh giá:

| Nhóm | Đánh giá |
|---|---|
| Pre-Sales Agent | **Đã tích hợp đúng hướng** |
| Financial Optimizer | **Đã tích hợp tốt** |
| Claim-Level Evidence F4 | **Đã được tích hợp khá đầy đủ** |
| Sales Message Compliance F8 | **Đã có kiến trúc nhưng thiếu final-send flow** |
| Sales Handover Dossier | **Đã có entity/flow, thiếu lifecycle chi tiết** |
| Policy Structured Rule Extraction | **Đã có khung, thiếu contract và publish workflow chi tiết** |
| Public Pre-Sales vs Official Quote | **Phân tách đúng** |
| Business workflow end-to-end | **Chưa cập nhật đầy đủ trong architecture document** |
| Runtime | **Có một số mâu thuẫn triển khai cần xử lý** |
| Production readiness | **Chưa đạt nếu chưa có executable evidence** |

---

# 1. Những phần đã tích hợp đúng

## 1.1. Đã tạo boundary giữa Pre-Sales và Official Quote

Đây là phần quan trọng nhất và hiện đã được thể hiện tốt.

Trong TD-4.5:

```text
Public Pre-Sales Boundary
        ≠
Official Quote Boundary
```

Trong TD-4.1:

```text
INV-RT-09 — Pre-Sales Safety Boundary & Watermark Protection
```

đã quy định:

- Pre-Sales không gọi KMS;
- không tạo `APPROVED`;
- không phát hành PDF chính thức;
- plan phải có watermark;
- chuyển sang Official Quote phải revalidate/recalculate.

Trong architecture document cũng đã có:

```text
ADR-020 — Strict Isolation of Public Pre-Sales vs. Internal Official Quote Lifecycles
```

### Đánh giá

> **Đạt tốt ở tầng kiến trúc và governance.**

Đây là nền tảng đúng để tránh việc chatbot công khai tự tạo cam kết thương mại.

---

## 1.2. F4 đã được tích hợp vào runtime và architecture

F4 không còn chỉ nằm trong tài liệu tính năng mới mà đã được đưa vào `TD-4.1`:

```text
INV-RT-10 — Claim-Level Evidence Coordinate Traceability
```

và architecture:

```text
ADR-018 — Claim-Level Evidence Linking as Universal Provenance Backbone
```

Đã có các thành phần quan trọng:

- `SourceCoordinate`;
- document ID;
- version;
- SHA-256;
- page;
- section;
- clause ID;
- calculation artifact;
- `PARTIALLY_SUPPORTED`;
- các archetype claim;
- áp dụng cho Pre-Sales, Official Quote và Sales Message.

### Đánh giá

> **Đạt tốt về nguyên tắc và traceability model.**

### Còn thiếu

Cần kiểm tra `TD-4.4` đã thực sự đổi output của:

```text
generate_dual_explanation
```

từ dạng text tự do sang structured claims hay chưa.

Nếu tool vẫn trả:

```json
{
  "why": "...",
  "why_not": "..."
}
```

thì F4 mới chỉ được mô tả ở architecture, chưa được triển khai đầy đủ ở API contract.

---

## 1.3. F8 đã có vị trí kiến trúc rõ ràng

`TD-4.1` đã bổ sung:

```text
compliance-verifier-worker
```

và:

```text
INV-RT-11 — Zero-Trust Message Compliance Gate
```

Architecture document cũng có:

```text
ADR-019 — Integrated Sales Message Composer & Zero-Trust Compliance Gate
```

Đã thể hiện đúng các nguyên tắc:

- Agent sinh cũng phải kiểm tra;
- Sale tự soạn cũng phải kiểm tra;
- có 3 thời điểm kiểm tra;
- có 4 mức kết quả;
- final send phải bị backend chặn nếu vi phạm.

### Đánh giá

> **Đúng về thiết kế.**

Tuy nhiên, phần business flow/API hiện chưa đầy đủ để chứng minh F8 chạy thực tế. Phần này cần bổ sung như bên dưới.

---

## 1.4. Financial Optimizer đã tái sử dụng đúng FCS

TD-4.5 quy định:

```text
execution_context = PRE_SALES
execution_context = OFFICIAL_QUOTE
```

nhưng dùng chung deterministic calculation service.

Điều này phù hợp với architecture hiện tại:

- LLM không tính tiền;
- Python pricing engine làm calculation;
- ranking deterministic;
- FCS golden vectors;
- financial validation gate.

### Đánh giá

> **Đạt tốt. Không nên tạo calculator riêng cho Pre-Sales.**

Cần tiếp tục giữ nguyên nguyên tắc:

```text
Pre-Sales chỉ khác về mức validation, disclaimer và lifecycle.
Không khác về công thức tài chính.
```

---

## 1.5. Handover Dossier đã được nhận diện trong architecture

Architecture đã có:

```text
C-10 Handover
create_lead_dossier
```

và TD-4.5 đã mô tả:

- consent;
- nhu cầu;
- financial inputs;
- assumptions;
- plan;
- policy/evidence refs;
- lead temperature;
- next best action;
- expiry.

### Đánh giá

> **Đã có đúng domain concept.**

Nhưng hiện vẫn thiếu:

- lifecycle rõ ràng;
- quyền truy cập;
- cơ chế claim/assignment cho Sale;
- deduplication;
- SLA;
- trạng thái Sale đã tiếp nhận hay chưa;
- liên kết dossier với CRM nếu có.

---

# 2. Các điểm chưa tích hợp đầy đủ

## Blocker 1 — Business workflow trong architecture chưa phản ánh Pre-Sales

Phần `Business Sequence` của architecture hiện vẫn bắt đầu bằng:

```text
Sale tiếp nhận bối cảnh giao dịch
→ nhập mã căn
→ xác định ngày giao dịch
→ lập báo giá
```

Trong khi tính năng mới yêu cầu thêm luồng:

```text
Khách hàng tự khởi tạo Pre-Sales Session
→ Agent discovery
→ tạo plan tham khảo
→ consent
→ handoff
→ Sale tạo Official Quote
```

Hiện TD-4.5 mô tả luồng này, nhưng architecture document chưa cập nhật business sequence tương ứng.

### Cần bổ sung vào architecture

```text
[BƯỚC 0A: KHÁCH HÀNG TỰ KHỞI TẠO PHIÊN TƯ VẤN]
- Khách truy cập web/QR.
- Chọn mục tiêu.
- Xác nhận consent phù hợp.

[BƯỚC 0B: DISCOVERY & PLAN THAM KHẢO]
- Agent hỏi nhu cầu.
- Chuẩn hóa financial constraints.
- Tính 1–3 phương án tham khảo.
- Hiển thị disclaimer/evidence.

[BƯỚC 0C: CUSTOMER HANDOFF CONSENT]
- Khách yêu cầu chuyên viên liên hệ.
- Hệ thống tạo Lead Dossier.

[BƯỚC 1: SALE TIẾP NHẬN DOSSIER]
- Sale kiểm tra thông tin.
- Sale tạo Official Quote.
- Official Quote revalidate/recalculate toàn trình.
```

Nếu không bổ sung, đội phát triển có thể chỉ triển khai Pre-Sales như một màn hình phụ mà không hiểu đây là một business entry point mới.

---

## Blocker 2 — StateGraph Pre-Sales chưa đủ lifecycle kỹ thuật

TD-4.5 đã có graph:

```text
START
→ initialize_pre_sales_session
→ collect_customer_input
→ extract_constraints
→ validate_constraints
→ ...
→ await_handoff_consent
→ build_lead_dossier
→ handoff_to_sales
→ END
```

Đúng hướng nhưng còn thiếu đặc tả:

- thread ID của Pre-Sales;
- checkpoint namespace;
- TTL session;
- resume token;
- session expiry;
- anonymous/public user;
- reconnect SSE;
- consent interrupt;
- user abandon/resume;
- rate limit;
- session replay protection.

### Cần bổ sung

```text
thread_id = presales:{tenant_id}:{session_id}
checkpoint_namespace = PRE_SALES
session_ttl = configurable
```

Các interrupt cần được định nghĩa rõ:

```text
WAITING_FOR_CUSTOMER_INPUT
WAITING_FOR_CONSTRAINT_CONFIRMATION
WAITING_FOR_HANDOFF_CONSENT
```

Nếu khách quay lại sau khi đóng trình duyệt, hệ thống cần biết:

```text
resume session
restart expired session
or create new session
```

---

## Blocker 3 — F8 chưa có API gửi tin thực tế

TD-4.5 mới có:

```http
POST /api/v1/compliance/check-message
```

Nhưng F8 yêu cầu:

```text
final send gate
```

Nếu chỉ có endpoint kiểm tra mà không có endpoint gửi, backend không thể bảo đảm Sale không gửi nội dung chưa được kiểm tra.

### Cần bổ sung một trong hai mô hình

## Mô hình A — Backend-controlled send

```http
POST /api/v1/messages/send
```

Request:

```json
{
  "recipient_ref": "CUSTOMER-001",
  "channel": "INTERNAL_PREVIEW",
  "message_text": "...",
  "quote_id": "QUOTE-001",
  "quote_version": 1,
  "compliance_check_id": "CHECK-001"
}
```

Backend phải:

```text
hash final message
→ kiểm tra policy/quote version còn hiệu lực
→ chạy final compliance check
→ chỉ gửi nếu pass
```

## Mô hình B — MVP chỉ cho copy

Nếu MVP chưa gửi tự động:

```text
[Copy message]
```

thì không nên gọi là `final send gate`.

Nên gọi:

```text
Pre-send compliance check
```

và ghi rõ:

```text
Hệ thống không kiểm soát nội dung sau khi Sale copy ra ngoài.
```

### Khuyến nghị

Với MVP, dùng:

```text
Generate
→ Check
→ Copy
```

nhưng thiết kế API sẵn cho:

```text
Send via approved channel
```

Không nên tích hợp Zalo cá nhân.

---

## Blocker 4 — Message Compliance chưa có state/lifecycle

F8 cần có trạng thái của một lần kiểm tra:

```text
DRAFT
CHECKING
SUPPORTED
CONDITIONAL
UNSUPPORTED
PROHIBITED
EXPIRED
SUPERSEDED
```

Khi Sale sửa message, kết quả cũ không còn hợp lệ.

Cần có:

```text
message_hash
checked_at
quote_version
policy_version
actor_id
check_result
```

Nếu:

```text
message_hash thay đổi
quote_version thay đổi
policy_version thay đổi
```

thì phải chạy check lại.

---

## Blocker 5 — Pre-Sales PDF chưa khớp runtime outbox

TD-4.5 có nói:

```text
pre_sales_reference.pdf
```

và `TD-4.1` quy định Pre-Sales không dùng outbox để phát hành PDF chính thức.

Điều này không mâu thuẫn, nhưng cần phân biệt rõ:

```text
Official Quote PDF
→ approval commit
→ outbox
→ PDF worker
→ PDF_ISSUED
```

với:

```text
Pre-Sales Reference Plan
→ không phải official artifact
→ có thể render on-demand
→ watermark bắt buộc
→ không tạo approval/audit event chính thức
```

### Cần chốt một trong hai

#### Cách 1 — Render on-demand

Phù hợp MVP:

```text
GET /pre-sales/sessions/{id}/reference-plan.pdf
```

Không lưu lâu hoặc lưu object có retention ngắn.

#### Cách 2 — Async reference artifact

Nếu dùng worker, phải có event riêng:

```text
PRE_SALES_REFERENCE_PDF_REQUESTED
```

Không được dùng:

```text
QUOTE_APPROVED
PDF_ISSUANCE_OUTBOX
```

---

# 3. Các điểm cần sửa trong tài liệu kiến trúc

## 3.1. Architecture component list chưa đồng bộ

Architecture mô tả:

```text
8 thành phần logic: C-01 đến C-08
```

nhưng trong Tool Map lại dùng:

```text
C-09 Pre-Sales
C-10 Handover
C-11 Compliance
```

Đây là mâu thuẫn tài liệu.

### Có hai cách sửa

#### Cách A — Mở rộng thành 11 components

Bổ sung:

```text
C-09 Pre-Sales Experience & Workflow
C-10 Lead Handoff Service
C-11 Claim Compliance Service
```

Đây là cách rõ ràng hơn.

#### Cách B — Gộp vào components cũ

- Pre-Sales vào C-01/C-03;
- Handover vào C-06;
- Compliance vào C-05/C-07.

Nhưng cách này khó đọc và không phản ánh đúng boundary runtime.

### Khuyến nghị

> Chuyển architecture từ 8 components thành 11 components logic.

---

## 3.2. Traceability matrix chưa phản ánh đầy đủ tính năng mới

Architecture đã có capability cũ, nhưng cần thêm các dòng:

| Business Goal | Capability | Component |
|---|---|---|
| Tăng chất lượng lead | Pre-Sales Discovery | C-09 |
| Rút ngắn thời gian Sale xử lý lead | Sales Handover Dossier | C-10 |
| Giảm cam kết sai | Message Compliance Gate | C-11 |
| Tăng minh bạch tư vấn | Claim-Level Evidence | C-05/C-11 |
| Phân biệt estimate và official quote | Lifecycle Isolation | C-09/C-06 |
| Bảo vệ consent/PII | Customer Consent Management | C-09/C-10 |

Nếu không cập nhật, những tính năng mới sẽ giống “phần thêm ngoài lề” thay vì năng lực chính thức của sản phẩm.

---

## 3.3. Domain model còn thiếu Lead và Customer Session

Architecture hiện có:

```text
TransactionContext
CustomerProfileRef
CommercialQuote
```

Nhưng để hỗ trợ Pre-Sales cần bổ sung rõ:

```text
PreSalesSession
PreSalesMessage
CustomerConstraint
CustomerConsent
PreSalesPlan
LeadDossier
HandoffRecord
ComplianceCheck
```

Đặc biệt cần tách:

```text
CustomerProfileRef
```

khỏi:

```text
CustomerConsent
```

Vì có thông tin khách hàng không đồng nghĩa với consent cho chuyển dữ liệu hoặc marketing.

---

# 4. Vấn đề runtime/deployment cần chốt

## 4.1. Kubernetes vs Dedicated Linux VPS/Docker Compose

Trong các ràng buộc trước đây, hạ tầng mục tiêu là:

```text
Dedicated Linux VPS
Docker Compose
```

Nhưng `TD-4.1` hiện mô tả:

```text
Kubernetes Pod
Multi-AZ
RDS
Cloud Load Balancer
Managed Redis Cluster
```

Đây là mâu thuẫn triển khai đáng kể.

### Cần chọn rõ

#### MVP/VPS

```text
Docker Compose
FastAPI
PostgreSQL
Redis
Qdrant hoặc pgvector
ARQ worker
Nginx
Object storage
```

#### Production scale-up

```text
Kubernetes
Managed PostgreSQL
Managed Redis
Cloud KMS
Multi-AZ
```

Không nên dùng Kubernetes security context làm baseline bắt buộc nếu MVP thực sự chạy Docker Compose.

### Khuyến nghị

Đổi tên các phần trong TD-4.1 thành:

```text
MVP Deployment Profile — Docker Compose/VPS
Scale Deployment Profile — Kubernetes/Managed Services
```

---

## 4.2. pgvector/Qdrant chưa hoàn toàn thống nhất

TD-4.5 đề xuất:

```text
Qdrant/vector store
```

nhưng architecture và TD-4.1 chốt:

```text
Supabase PostgreSQL + pgvector
```

Cần chọn một source of truth cho MVP.

### Khuyến nghị

Với MVP:

```text
PostgreSQL + pgvector
```

là đủ nếu:

- corpus chưa lớn;
- có metadata filter;
- cần transaction/provenance chung;
- muốn giảm số service trên VPS.

Qdrant có thể để ở roadmap nếu:

- corpus lớn;
- retrieval traffic cao;
- cần vector service độc lập.

Không nên để đội phát triển hiểu rằng phải triển khai cả PostgreSQL pgvector và Qdrant ngay từ MVP.

---

# 5. Financial Optimizer cần bổ sung contract

TD-4.5 đã nêu các objective:

```text
MIN_NET_PRICE
MIN_INITIAL_CASH
MIN_MONTHLY_BURDEN
EARLY_HANDOVER
```

Nhưng architecture hiện có một số mục tiêu khác như:

```text
MAX_BENEFIT_VALUE
MIN_TOTAL_CASH_OUTFLOW
```

Cần canonicalize enum.

### Đề xuất

Tạo một enum duy nhất:

```text
OptimizationObjective:
- MIN_NET_PRICE
- MIN_INITIAL_CASH
- MIN_MONTHLY_BURDEN
- MIN_TOTAL_CASH_OUTFLOW
- MAX_BENEFIT_VALUE
- EARLY_HANDOVER
```

Mỗi objective phải có:

- definition;
- time horizon;
- input required;
- ranking formula;
- tie-break;
- expected output;
- golden test case.

Không nên để Product, FCS, architecture và API dùng các tên objective khác nhau.

---

# 6. Policy Structured Rule Extraction

Phần này đã có pipeline tốt:

```text
Upload
→ Parse
→ Extract
→ Source Coordinates
→ Conflict
→ Human Validation
→ Publish
```

Nhưng cần bổ sung rõ:

## Rule lifecycle

```text
DRAFT
EXTRACTED
VALIDATION_REQUIRED
APPROVED_FOR_USE
ACTIVE
RETIRED
REJECTED
```

## Policy publish invariant

```text
Chỉ rule ở APPROVED_FOR_USE mới được dùng cho Official Quote.
```

## Rollback

Nếu rule publish sai:

```text
không sửa trực tiếp rule cũ;
tạo version mới hoặc RETIRED;
ghi policy change event.
```

## Test trước publish

Mỗi policy mới nên có:

```text
representative test cases
expected eligibility
expected conflict
expected calculation impact
```

Phần này chưa được mô tả đủ trong TD-4.5.

---

# 7. Luồng nghiệp vụ hoàn chỉnh nên là

## 7.1. Luồng khách hàng

```text
Customer opens pre-sales UI
→ creates session
→ accepts privacy notice
→ answers guided questions
→ confirms extracted constraints
→ system retrieves active policy
→ system detects conflict
→ safe decision gate
→ calculator creates scenarios
→ claim/evidence validation
→ customer views reference plan
→ customer requests Sale contact
→ consent recorded
→ dossier created
```

## 7.2. Luồng Sale

```text
Sale receives dossier
→ reviews customer context
→ reviews assumptions
→ selects plan
→ creates Official Quote
→ system revalidates policy
→ system recalculates
→ system builds approval package
→ Sale writes or generates customer message
→ compliance check
→ copy/send only if allowed
→ submit quote to Manager
```

## 7.3. Luồng Manager

```text
Manager opens approval package
→ reviews evidence
→ reviews risk flags
→ reviews message compliance if applicable
→ approve/reject/revision/exception
→ approval intent
→ server attestation
→ commit snapshot/audit/outbox
→ PDF worker
→ official PDF issued
```

## 7.4. Luồng Policy Admin

```text
Admin uploads document
→ ingestion
→ clause/rule extraction
→ source coordinate validation
→ conflict detection
→ test cases
→ human validation
→ publish active policy version
```

Đây là luồng nên đưa vào architecture document thay cho chỉ mô tả Official Quote workflow.

---

# 8. Verdict theo từng tính năng

| Tính năng | Đã tích hợp? | Mức độ | Việc cần bổ sung |
|---|---|---|---|
| F1 Pre-Sales Discovery | Có | **Đúng hướng** | Business sequence, session lifecycle, public API security |
| F2 Constraint Extraction | Có | **Khá đầy đủ** | Confirmation/assumption persistence |
| F3 Financial Optimizer | Có | **Đạt** | Canonical objective enum và golden tests |
| F4 Claim Evidence | Có | **Tốt** | Đồng bộ output TD-4.4 và ingestion coordinates |
| F5 Reference Plan | Có | **Đạt** | PDF/reference artifact semantics |
| F6 Handover Dossier | Có | **Khá đầy đủ** | Assignment, lifecycle, dedupe, SLA |
| F7 Official Quote Conversion | Có | **Tốt** | Transaction/API/OCC/error contract |
| F8 Message Compliance | Có | **Chưa hoàn toàn** | Final send endpoint/gate, message lifecycle |
| F9 Rule Extraction | Có | **Đúng hướng** | Publish test, rollback, schema/migration |
| Multi-domain extension | Có | **Chỉ ở extension level** | Không nên coi là MVP runtime |
| Zalo/Telegram | Có | **Phù hợp** | Giữ Zalo production ngoài MVP |

---

# 9. Các thay đổi bắt buộc đề xuất cho TD-4.5 v1.1

## Bổ sung mục “Business Flow Integration”

Gồm bốn flow:

```text
Customer Pre-Sales
Sales Handoff
Official Quote
Policy Administration
```

## Bổ sung mục “State and Lifecycle”

Cho:

```text
PreSalesSessionStatus
PreSalesPlanStatus
LeadDossierStatus
ComplianceCheckStatus
PolicyRuleStatus
```

## Bổ sung mục “Final Message Send Contract”

Tối thiểu:

```http
POST /api/v1/messages/send
```

hoặc ghi rõ MVP chỉ hỗ trợ `copy/export`, chưa có server-controlled send.

## Bổ sung “Component Catalog v2”

Đồng bộ:

```text
C-01 → C-11
```

không để architecture ghi 8 component nhưng tool map dùng C-09/C-10/C-11.

## Bổ sung “Deployment Profiles”

```text
MVP: Docker Compose/VPS
Scale: Kubernetes/Managed Services
```

## Bổ sung “Canonical Objective Contract”

Dùng một enum thống nhất cho FCS, API, UI và tests.

## Bổ sung “Policy Publish Test Gate”

Không publish extracted rule nếu chưa pass validation và representative test cases.

---

# Kết luận cuối

Các tính năng mới **đã được tích hợp đúng về mặt kiến trúc tổng thể**. Đặc biệt các phần sau đã khá chắc:

```text
Pre-Sales boundary
Deterministic Financial Optimizer
F4 evidence traceability
F8 zero-trust compliance concept
Lead dossier
Official Quote revalidation
```

Tuy nhiên, chưa thể nói là **đủ và hoàn toàn nhất quán trong tài liệu và luồng nghiệp vụ**, vì còn các khoảng trống chính:

1. Business workflow chưa cập nhật đầy đủ luồng Customer Pre-Sales.
2. Pre-Sales StateGraph thiếu session/checkpoint/TTL/resume semantics.
3. F8 chưa có final send API hoặc phải xác nhận MVP chỉ copy/export.
4. Component catalog đang lệch giữa C-01–C-08 và C-09–C-11.
5. Domain model chưa mô tả đủ lifecycle cho lead/session/compliance.
6. Pre-Sales reference PDF chưa tách contract đầy đủ khỏi Official PDF.
7. `Docker Compose/VPS` và `Kubernetes/Cloud` đang cùng xuất hiện như baseline.
8. `pgvector` và `Qdrant` chưa được chốt rõ vai trò MVP.
9. Optimization objectives chưa có một enum canonical duy nhất.
10. Policy rule extraction chưa có publish test và rollback semantics.

## Verdict đề xuất

> **NEW FEATURES ARCHITECTURALLY INTEGRATED**  
> **BUSINESS FLOW INTEGRATION PARTIALLY COMPLETE**  
> **CONDITIONAL FOR IMPLEMENTATION SPIKE**  
> **PENDING TD-4.5 v1.1 CONTRACT/LIFECYCLE ALIGNMENT**

Nói ngắn gọn:

> **Ý tưởng và ranh giới kiến trúc đã đúng; việc cần làm tiếp theo là đóng các contract, lifecycle và business-flow gap trước khi đội phát triển bắt đầu triển khai toàn bộ MVP.**