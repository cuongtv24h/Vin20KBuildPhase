# TD-4.5 — ĐỀ XUẤT TÍNH NĂNG MỚI & TÍCH HỢP VÀO HỆ THỐNG HIỆN TẠI

**Dự án:** PricePolicy AI Agent — nền tảng bảo chứng định giá và quản trị chính sách bán hàng  
**Mã tài liệu:** TD-4.5  
**Phiên bản:** 1.0  
**Trạng thái:** Đề xuất cho Product & Engineering Review  
**Phạm vi:** Tích hợp Pre-Sales Agent, Financial Optimizer, Sales Handover Dossier và Evidence-Backed Message Composer & Compliance Gate vào nền tảng TD-4.1 đến TD-4.4  

---

## 1. Mục đích tài liệu

Tài liệu này mô tả các tính năng mới được đề xuất sau khi hoàn thiện TD-4.1, TD-4.2, TD-4.3, TD-4.4 và PRD MVP.

Mục tiêu là giúp đội phát triển hiểu rõ:

- tính năng nào nên triển khai trong MVP;
- tính năng nào mở rộng sau MVP;
- tính năng mới kết nối với module hiện tại ở đâu;
- dữ liệu, API, StateGraph và quyền hạn cần bổ sung;
- ranh giới giữa Pre-Sales Estimate và Official Quote;
- các nguyên tắc không được phá vỡ khi mở rộng hệ thống.

Tài liệu này **không thay thế** TD-4.1 đến TD-4.4. Đây là tài liệu tích hợp mở rộng, trong đó các thiết kế hiện tại tiếp tục là nguồn chuẩn cho:

- runtime và deployment;
- domain/data model;
- official quote StateGraph;
- REST/Event/Tool contracts;
- financial calculation.

---

## 2. Định hướng sản phẩm mới

### 2.1. Định vị đề xuất

> **PricePolicy AI là Pre-Sales Financial Copilot có căn cứ chính sách, giúp khách hàng tự khám phá phương án phù hợp, giúp Sale nhận lead đã được phân tích, và giúp doanh nghiệp kiểm soát các cam kết tư vấn bằng evidence có thể audit.**

### 2.2. Luồng giá trị mới

```text
Customer discovery
        ↓
Policy-backed recommendation
        ↓
Deterministic financial plan
        ↓
Sales handover dossier
        ↓
Official quote creation
        ↓
Manager approval
        ↓
Audit and PDF
```

### 2.3. Nguyên tắc tích hợp

1. **Không thay thế Official Quote Workflow.** Pre-Sales là luồng đầu vào mới.
2. **Không cho public Agent tự approve.** Approval vẫn thuộc Manager Workflow.
3. **Không dùng LLM để tính tiền.** Mọi số tiền lấy từ FCS deterministic calculator.
4. **Không dùng pre-sales result làm approval snapshot trực tiếp.** Official quote phải revalidate và recalculate.
5. **Không mutate quote version cũ.** Revision/exception làm thay đổi quyết định phải tạo version mới.
6. **Mọi claim quan trọng phải có evidence hoặc được đánh dấu unsupported.**
7. **Tách PII và consent khỏi policy/calculation artifact.**
8. **Agent-visible tools không có quyền ghi governance data.**

---

# 3. Danh sách tính năng mới

## 3.1. Feature F1 — Pre-Sales Discovery Agent

### Mục tiêu

Cho phép khách hàng tương tác với Agent trước khi gặp Sale để khai thác nhu cầu và các ràng buộc tài chính cần thiết.

### Giá trị

- giảm lead lạnh;
- giảm thời gian Sale phải hỏi lại thông tin cơ bản;
- tạo trải nghiệm tư vấn chủ động;
- thu thập input có cấu trúc cho Financial Optimizer.

### Thông tin có thể thu thập

- dự án/phân khu quan tâm;
- loại sản phẩm/căn hộ;
- mục đích mua: ở, đầu tư, cho thuê;
- ngân sách;
- vốn tự có;
- khả năng thanh toán hàng tháng;
- nhu cầu vay;
- thời điểm nhận nhà;
- thời gian dự kiến ra quyết định;
- phương thức liên hệ và consent.

### Không được thu thập hoặc suy luận quá mức

- số CMND/CCCD nếu chưa cần;
- thông tin tài khoản ngân hàng;
- thông tin sức khỏe;
- thông tin tài chính không liên quan;
- khả năng tín dụng được khẳng định khi chưa có ngân hàng thẩm định.

### Tích hợp với hệ thống hiện tại

```text
Customer UI
  → REST API
  → Pre-Sales StateGraph
  → Policy Retrieval
  → Financial Optimizer
  → Pre-Sales Plan
```

Tái sử dụng:

- policy registry của TD-4.2;
- retrieval/provenance của TD-4.3;
- FCS calculator;
- SSE event contract của TD-4.4;
- security guardrail.

Không sử dụng trực tiếp:

- official approval node;
- approval snapshot commit;
- server attestation;
- official PDF issuance.

---

## 3.2. Feature F2 — Customer Constraint Extraction

### Mục tiêu

Chuyển nội dung hội thoại tự nhiên thành input có kiểu dữ liệu rõ ràng.

### Ví dụ

Khách nói:

> “Tôi có khoảng 900 triệu, mỗi tháng có thể trả 20 triệu, muốn mua căn 2 phòng ngủ để ở trong năm nay.”

Hệ thống trích xuất:

```json
{
  "asset_type": "2BR",
  "purchase_purpose": "OWNER_OCCUPIED",
  "own_funds_vnd": 900000000,
  "monthly_capacity_vnd": 20000000,
  "target_move_in_period": "CURRENT_YEAR",
  "confidence": {
    "asset_type": 0.98,
    "own_funds_vnd": 0.94,
    "monthly_capacity_vnd": 0.91
  }
}
```

### Nguyên tắc

- giá trị do khách nói phải phân biệt với giá trị do hệ thống suy ra;
- nếu mơ hồ, Agent hỏi lại;
- không tự chuyển “khoảng 20 triệu” thành cam kết chính xác;
- mọi input dùng cho calculation phải được người dùng xác nhận hoặc đánh dấu là assumption.

### Component mới

```text
ConstraintExtractor
ConstraintValidator
AssumptionManager
```

### Tích hợp

```text
LLM extraction
→ Pydantic validation
→ user confirmation
→ FCS PricingInput
```

---

## 3.3. Feature F3 — Pre-Sales Financial Optimizer

### Mục tiêu

Từ nhu cầu và ràng buộc của khách, tạo 1–3 phương án tham khảo có thứ hạng rõ ràng.

### Nguyên tắc tính toán

LLM chỉ làm:

- hiểu nhu cầu;
- chọn policy candidates;
- tạo explanation.

Calculator deterministic làm:

- giá net;
- VAT;
- phí bảo trì/chi phí liên quan;
- tiền thanh toán từng đợt;
- số tiền cần chuẩn bị;
- dòng tiền;
- kiểm tra giới hạn.

### Các objective MVP

```text
MIN_NET_PRICE
MIN_INITIAL_CASH
MIN_MONTHLY_BURDEN
EARLY_HANDOVER
```

Mỗi session chỉ chọn một objective chính tại một thời điểm.

### Output

```json
{
  "plan_id": "PLAN-001",
  "plan_status": "REFERENCE_ONLY",
  "objective": "MIN_INITIAL_CASH",
  "rank": 1,
  "quote_context": {
    "project_id": "PROJECT-001",
    "asset_ref": "UNIT-A1204"
  },
  "calculation_artifact_ref": {
    "artifact_id": "CALC-001",
    "artifact_version": 1,
    "artifact_hash": "sha256:..."
  },
  "policy_refs": ["POL-2026-VLAND-01:v3"],
  "assumptions": [],
  "disclaimer_code": "PRE_SALES_REFERENCE_ONLY"
}
```

### Tích hợp với FCS

Không tạo calculator riêng cho Pre-Sales. Pre-Sales gọi cùng calculation service với Official Quote nhưng sử dụng:

```text
execution_context = PRE_SALES
```

Official Quote sử dụng:

```text
execution_context = OFFICIAL_QUOTE
```

Hai context có thể có khác biệt về:

- mức validation;
- dữ liệu bắt buộc;
- disclaimer;
- approval requirement;
- artifact lifecycle.

Kết quả calculation vẫn phải cùng chuẩn số học.

---

## 3.4. Feature F4 — Claim-Level Evidence Linking (Evidence-Backed Recommendation)

### Mục tiêu & Định vị Kiến trúc

F4 là cơ chế buộc **từng luận điểm riêng lẻ mà Agent đưa ra** phải có căn cứ cụ thể trong tài liệu chính sách hoặc artifact tính toán tài chính (`CalculationArtifact`).

Hệ thống không chỉ hiển thị trích dẫn chung chung ở cuối câu trả lời:
```text
Nguồn: Chính sách bán hàng 2026
```
mà phải giải trình chính xác:
> **"Luận điểm này dựa vào điều khoản nào, ở tài liệu nào, phiên bản nào, trang nào, đoạn nào và có được phép suy ra kết luận như vậy hay không?"**

---

### 3.4.1. Ba Cấp độ Trích dẫn (Citation Maturity Levels)

1. **Mức 1 — Citation chung (General Citation):**
   - Ví dụ: `Nguồn: Chính sách bán hàng 2026`.
   - Đánh giá: Quá rộng, không thể dùng cho mục đích kiểm toán (audit).
2. **Mức 2 — Citation theo trang/đoạn (Page/Section Citation):**
   - Ví dụ: `Nguồn: CSBH 2026 v3, Trang 12`.
   - Đánh giá: Khá hơn nhưng chưa xác định được từng vế câu trong luận điểm dựa vào điều khoản nào.
3. **Mức 3 — Claim-Level Evidence Linking (Chuẩn mực F4):**
   - Ví dụ: Luận điểm *"Chiết khấu thanh toán sớm 8%"* gắn với:
     - Document: `DOC-CSBH-2026-01` (Version `v3`, Hash `sha256:7d4c...`).
     - Trang: `12`, Section: `4.2`, Clause: `CLAUSE-4.2.1`.
     - Đoạn trích (Text Quote): *"Khách hàng thanh toán đủ ... được hưởng chiết khấu 8%..."*.
     - Hiệu lực thời gian: `01/09/2026 – 30/09/2026`.

---

### 3.4.2. Bốn Loại Luận điểm (4 Claim Archetypes)

Hệ thống phân định rạch ròi nguồn gốc của từng claim:

1. **Policy-backed Claim (Căn cứ văn bản chính sách):**
   - Ví dụ: *"Khách hàng được hưởng chiết khấu 8%"*.
   - Nguồn: Trích xuất trực tiếp từ `policy_clause` trong Supabase pgvector.
2. **Calculation-backed Claim (Căn cứ số học tất định):**
   - Ví dụ: *"Số tiền thanh toán đợt đầu là 675.000.000 VNĐ"*.
   - Nguồn: Trỏ trực tiếp vào trường dữ liệu `payment_schedule[0].amount_vnd` trong `CalculationArtifact` (FCS Python Engine).
3. **Derived Claim (Căn cứ đề xuất suy luận tổng hợp):**
   - Ví dụ: *"PA-NHANH phù hợp nhất với mục tiêu giảm gánh nặng ban đầu"*.
   - Nguồn: Kết quả của thuật toán tối ưu hóa đa mục tiêu kết hợp `CustomerConstraints` + `CalculationArtifact` + `RankingObjective`.
4. **User-provided Claim (Căn cứ thông tin khách hàng khai báo):**
   - Ví dụ: *"Khách hàng có 900 triệu vốn tự có"*.
   - Nguồn: Khách hàng nhập trong phiên chat pre-sales. Hệ thống dán nhãn `USER_DECLARED`, tuyệt đối không trình bày như một sự kiện đã được doanh nghiệp thẩm định.

---

### 3.4.3. Lược đồ Dữ liệu Chi tiết (Schemas)

#### 1. Source Coordinate (Tọa độ nguồn)
```json
{
  "document_id": "DOC-CSBH-2026-01",
  "document_version": "v3",
  "document_hash": "sha256:7d4c...",
  "page": 12,
  "section": "4.2",
  "clause_id": "CLAUSE-4.2.1",
  "paragraph_index": 3,
  "char_start": 184,
  "char_end": 329,
  "text_quote": "Khách hàng thanh toán đủ 95% trong vòng 15 ngày kể từ ngày ký HĐMB được hưởng mức chiết khấu 8,0% vào giá bán chưa VAT."
}
```

#### 2. Evidence Reference (Tham chiếu bằng chứng)
```json
{
  "evidence_id": "EVID-001",
  "evidence_type": "POLICY_CLAUSE",
  "source_coordinate": {
    "document_id": "DOC-CSBH-2026-01",
    "document_version": "v3",
    "document_hash": "sha256:7d4c...",
    "page": 12,
    "section": "4.2",
    "clause_id": "CLAUSE-4.2.1"
  },
  "support_relation": "DIRECTLY_SUPPORTS",
  "support_text": "Khách hàng thanh toán đủ 95% ... được hưởng chiết khấu 8,0%..."
}
```

#### 3. Evidence-Backed Claim (Cấu trúc luận điểm hoàn chỉnh)
```json
{
  "claim_id": "WHY-001",
  "claim_type": "POLICY_REASON",
  "text": "PA-NHANH được hưởng chiết khấu 8% khi đáp ứng điều kiện thanh toán sớm 95%.",
  "support_status": "SUPPORTED",
  "evidence_refs": ["EVID-001"],
  "calculation_refs": [
    {
      "artifact_id": "CALC-001",
      "artifact_version": 1,
      "field_path": "scenarios[0].discount_amount_vnd",
      "numeric_consistency_hash": "sha256:abc..."
    }
  ],
  "conditions": ["Khách hàng thanh toán đủ 95% trong 15 ngày"],
  "unsupported_fragments": []
}
```

---

### 3.4.4. Quy trình Xử lý 5 Bước (5-Step Processing Pipeline)

```text
[B1. Ingest Policy & Coordinates]
      │ (Giữ nguyên cấu trúc layout trang, bảng biểu, trích xuất clause_id & hash)
      ▼
[B2. Retrieve Candidate Evidence]
      │ (Lọc thời gian Time-Travel SQL trên Supabase pgvector; chỉ bốc chunks thực sự cần)
      ▼
[B3. Generate Structured Claims]
      │ (LLM sinh claim kèm candidate_evidence_ids; Server gán coordinate & hash thật)
      ▼
[B4. Validate Claim Integrity]
      │ (Kiểm tra: clause tồn tại? hash khớp? số tiền khớp FCS? có overclaim không?)
      ▼
[B5. Render UI with Interactive Anchors]
        (Hiển thị giải trình Why/Why-not có gắn chỉ số [1], [2]; click xem ngay tọa độ nguồn)
```

---

### 3.4.5. Xử lý Luận điểm Được Hỗ trợ Một Phần (Partially Supported Claims)

Khi phát hiện câu diễn giải của LLM hoặc Sale có vế vượt quá bằng chứng:
- **Câu gốc:** *"Khách hàng không phải trả gốc và lãi trong 24 tháng."*
- **Đối soát:**
  - *"Không phải trả gốc trong 24 tháng"* $
ightarrow$ Được hỗ trợ bởi Điều 7.1 (`SUPPORTED`).
  - *"Không phải trả lãi trong 24 tháng"* $
ightarrow$ Không có điều khoản hỗ trợ (`UNSUPPORTED`).
- **Phân loại:** `PARTIALLY_SUPPORTED`.
- **Hành động:** Validator tự động ép định dạng lại hoặc chặn xuất bản, yêu cầu diễn đạt chuẩn mực:
  > *"Khách hàng có thể được ân hạn nợ gốc tối đa 24 tháng nếu đáp ứng điều kiện chương trình (Điều 7.1). Nghĩa vụ lãi suất trong thời gian này cần được xác nhận cụ thể theo thông báo phê duyệt tín dụng của ngân hàng hợp tác."*

---

### 3.4.6. Ví dụ Thực tế Dữ liệu Why / Why-not

#### Hiển thị cho Người dùng:
```text
Vì sao đề xuất PA-NHANH?
1. Phương án áp dụng mức chiết khấu 8% nếu đáp ứng điều kiện thanh toán sớm. [1]
2. Phương án có số tiền thanh toán đợt đầu thấp hơn PA-CHUẨN theo mục tiêu MIN_INITIAL_CASH. [2]

Nguồn căn cứ:
[1] CSBH 2026 v3 · Điều 4.2.1 · Trang 12 (Doc SHA: 7d4c...)
[2] Bảng tính CALC-001 · payment_schedule[0].amount_vnd · Rank RANK-001

Vì sao loại trừ PA-CHUẨN?
1. PA-CHUẨN không áp dụng mức chiết khấu thanh toán sớm trong phiên bản chính sách hiện hành. [3]
2. PA-CHUẨN yêu cầu số tiền ban đầu cao hơn so với cùng căn hộ mục tiêu. [4]

Nguồn căn cứ:
[3] CSBH 2026 v3 · Điều 4.1.2 · Trang 11
[4] Bảng tính CALC-001 · scenario_comparison
```

---

## 3.5. Feature F5 — Pre-Sales Plan và Disclaimer

### Mục tiêu

Cho khách hàng xem kế hoạch dễ hiểu nhưng không nhầm với quote chính thức.

### UI bắt buộc hiển thị

```text
PRE-SALES ESTIMATE
NOT AN OFFICIAL QUOTE
```

### Không được hiển thị trong pre-sales

```text
APPROVED
MANAGER APPROVED
OFFICIAL PRICE GUARANTEE
SIGNED
```

### Bản kế hoạch có thể gồm

- thông tin nhu cầu đã khai báo;
- 1–3 phương án;
- giá trị và dòng tiền;
- assumption;
- policy evidence;
- cảnh báo điều kiện;
- disclaimer;
- nút yêu cầu Sale liên hệ.

### PDF

MVP có thể cho tải bản PDF tham khảo, nhưng phải dùng template riêng:

```text
pre_sales_reference.pdf
```

Không được dùng template PDF chính thức của approval workflow.

---

## 3.6. Feature F6 — Sales Handover Dossier

### Mục tiêu

Chuyển một session khách hàng thành hồ sơ có thể hành động cho Sale.

### Dossier gồm

- thông tin liên hệ được consent;
- nhu cầu;
- các input tài chính;
- assumptions;
- phương án đã xem/chọn;
- policy/evidence refs;
- transcript summary;
- lead temperature;
- next best action;
- thời điểm handoff;
- expiry.

### Lead temperature

MVP chỉ dùng heuristic minh bạch:

```text
HOT
WARM
COLD
UNQUALIFIED
```

Không dùng LLM tự tuyên bố xác suất mua chính xác.

### Ví dụ rule heuristic

```text
HOT:
- đã chọn phương án
- đồng ý để Sale liên hệ
- có budget hoặc own funds hợp lệ
- có thời gian ra quyết định ≤ 30 ngày

WARM:
- đã xem phương án
- chưa xác nhận liên hệ hoặc timeline chưa rõ

COLD:
- mới hỏi thông tin chung
- chưa cung cấp constraint tài chính
```

### Kênh handoff MVP

Ưu tiên:

1. Sales Dashboard;
2. Telegram Bot nội bộ nếu cần demo nhanh;
3. Email nội bộ tùy chọn.

Zalo production là hạng mục tích hợp riêng, không đưa vào dependency bắt buộc của MVP.

---

## 3.7. Feature F7 — Chuyển Pre-Sales thành Official Quote

### Mục tiêu

Cho phép Sale dùng dossier để khởi tạo quote chính thức nhưng vẫn bảo đảm revalidation.

### Luồng

```text
lead_dossier
→ create official quote
→ resolve active policy again
→ validate transaction context
→ recalculate
→ build explanation
→ safe decision gate
→ ready for manager review
```

### Bắt buộc

- tạo `quote_version = 1` mới;
- không mutate pre-sales plan;
- không kế thừa approval từ pre-sales;
- không dùng policy cũ nếu policy đã hết hiệu lực;
- nếu policy thay đổi, hiển thị difference cho Sale;
- lưu `source_pre_sales_session_id` để truy vết.

### API đề xuất

```http
POST /api/v1/leads/{dossier_id}/create-quote
```

Request:

```json
{
  "expected_dossier_version": 1,
  "selected_plan_id": "PLAN-001",
  "sales_adjustments": {
    "asset_ref": "UNIT-A1204"
  },
  "idempotency_key": "..."
}
```

---

## 3.8. Feature F8 — Evidence-Backed Message Composer & Compliance Gate

### Mục tiêu & Định vị Kiến trúc

F8 **không phải là một tính năng riêng biệt cạnh tranh với Message Generation** (sinh tin nhắn), mà được thiết kế thành một **Compliance Gate dùng chung** tích hợp trực tiếp bên trong một **Sales Message Composer duy nhất**:

```text
Tin nhắn do Agent đề xuất   ┐
Tin nhắn do Sale tự soạn    ├──> Claim Extraction ──> Policy/Quote Validation ──> Compliance Result
Tin nhắn được chỉnh sửa     ┘
```

> **Nguyên tắc cốt lõi:** *Agent có thể viết tin nhắn, nhưng không được mặc định rằng tin nhắn do chính Agent viết là đúng. Mọi nội dung trước khi gửi khách đều phải qua cùng một lớp kiểm tra tuân thủ bằng chứng.*
>
> - **Generator (Message Generation):** Đề xuất ngôn ngữ, giúp Sale soạn tin nhanh theo ngữ cảnh (phương án, giọng điệu, kênh).
> - **Verifier (Compliance Gate):** Bảo vệ nghiệp vụ, kiểm tra xem nội dung có vượt quá evidence, policy hoặc thẩm quyền của Sale hay không.

---

### 3.8.1. Giao diện Tích hợp: Sales Message Composer

Hệ thống không tách thành hai màn hình riêng ("soạn tin" và "kiểm tra"), mà tích hợp thành một giao diện làm việc duy nhất:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Người nhận: Anh Tuấn                                                   │
│ Context: QUOTE-001 · v1 · PA-NHANH · POL-2026-VLAND-01:v3              │
├────────────────────────────────────────────────────────────────────────┤
│ [✨ Tạo tin từ phương án] [Đổi giọng điệu: Thân thiện / Chuyên nghiệp] │
│                                                                        │
│ Chào anh Tuấn, theo phương án thanh toán sớm PA-NHANH, giá trị thanh   │
│ toán dự kiến của căn A-12.04 là 4,14 tỷ đồng theo chính sách đang áp   │
│ dụng cho hồ sơ này. Em gửi anh bảng tiến độ để tham khảo.              │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│ Trạng thái Tuân thủ: ✓ CÓ THỂ GỬI (SUPPORTED)                          │
│                                                                        │
│  ✓ Giá 4,14 tỷ — khớp 100% CALC-001 (FCS Engine)                       │
│  ✓ PA-NHANH — khớp Quote version v1                                    │
│  ✓ Chiết khấu thanh toán sớm — khớp CLAUSE-4.2 (Doc: CSBH_2026_V01)    │
│  ⚠ Điều kiện phê duyệt — cần giữ nguyên câu bảo lưu thẩm quyền          │
│                                                                        │
│ [Kiểm tra tuân thủ] [Sao chép] [Gửi khách hàng (Final Gate)]           │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 3.8.2. Ba Thời điểm Kiểm tra (Check Invariants)

Không chỉ kiểm tra khi Sale bấm nút, hệ thống kích hoạt xác thực ở 3 thời điểm:
1. **Ngay sau khi Agent tạo draft:** Tự động chạy compliance check trước khi hiển thị bản nháp cho Sale.
2. **Khi Sale chỉnh sửa nội dung:** Chạy kiểm tra debounce (sau 500–800ms khi Sale dừng gõ) hoặc khi rời focus ô nhập liệu; cache kết quả theo `message_hash`.
3. **Ngay trước khi gửi (Final Mandatory Gate):** Khi Sale bấm "Gửi", hệ thống băm SHA-256 nội dung cuối cùng, thực thi kiểm tra chốt chặn. Nếu chưa `PASS` hoặc chính sách đã thay đổi từ lần kiểm tra trước, lệnh gửi bị chặn lại.

---

### 3.8.3. Bốn Mức Đánh giá Tuân thủ (4-Tier Compliance Status)

Mọi claim trong tin nhắn được phân loại vào 4 mức định chuẩn:

| Trạng thái | Ý nghĩa nghiệp vụ | Hành động hệ thống |
| :--- | :--- | :--- |
| `SUPPORTED` | Claim có đầy đủ bằng chứng (Policy version, Clause ID, Source coordinate, Calculation ref). | Cho phép gửi trực tiếp. |
| `CONDITIONAL` | Claim đúng nhưng thiếu điều kiện hoặc cần diễn đạt thận trọng (ví dụ: cần giữ vế *"nếu được phê duyệt"*). | Cho phép gửi sau khi Sale giữ nguyên điều kiện bắt buộc. |
| `UNSUPPORTED` | Không tìm thấy bằng chứng trong chính sách hoặc nội dung vượt quá phạm vi evidence. | Đánh dấu đỏ; yêu cầu Sale sửa hoặc chuyển escalation. |
| `PROHIBITED` | Nội dung rủi ro cao bị cấm tuyệt đối: cam kết phê duyệt tín dụng, cam kết lợi nhuận, cam kết chắc chắn 100%, khẳng định thay ngân hàng/CĐT. | Khóa cứng nút Gửi (`BLOCKED`). Bắt buộc Manager override có ký số và lưu vết audit nếu là trường hợp đặc biệt. |

---

### 3.8.4. Hợp đồng Dữ liệu & Context Đầy đủ (API Contract)

Compliance Check không thể chạy độc lập nếu thiếu context hồ sơ. Request bắt buộc mang đầy đủ bối cảnh giao dịch:

**Endpoint:** `POST /api/v1/compliance/check-message`

**Request Payload:**
```json
{
  "message_text": "Anh/chị chắc chắn được vay 70% và không phải trả lãi trong 24 tháng đầu.",
  "context": {
    "quote_id": "QUOTE-001",
    "quote_version": 1,
    "selected_plan_id": "PA-NHANH",
    "lead_dossier_id": "DOSSIER-2026-0089",
    "policy_version": "POL-2026-VLAND-01:v3",
    "actor_id": "SALES-042",
    "actor_role": "SALES_EXECUTIVE",
    "channel": "ZALO_MESSAGE"
  }
}
```

**Response Payload:**
```json
{
  "overall_status": "BLOCKED",
  "message_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "claims": [
    {
      "claim_id": "CLAIM-001",
      "text": "chắc chắn được vay 70%",
      "status": "PROHIBITED",
      "reason_code": "CREDIT_APPROVAL_OVERCLAIM",
      "reason": "Chính sách và Agent không có thẩm quyền cam kết thay ngân hàng về việc phê duyệt tín dụng.",
      "evidence_refs": []
    },
    {
      "claim_id": "CLAIM-002",
      "text": "không phải trả lãi trong 24 tháng đầu",
      "status": "UNSUPPORTED",
      "reason_code": "INTEREST_WAIVER_NOT_SUPPORTED",
      "reason": "Chính sách active POL-2026-VLAND-01:v3 chỉ chứng minh hỗ trợ lãi suất 0% tối đa 18 tháng (Điều 7.1), không hỗ trợ 24 tháng.",
      "evidence_refs": []
    }
  ],
  "required_action": "REMOVE_OR_ESCALATE_TO_MANAGER"
}
```

---

### 3.8.5. Kiến trúc Nền tảng: Dịch vụ Dùng chung (Claim Compliance Service)

Không xây dựng F8 thành một module biệt lập, mà tích hợp vào **`Claim Compliance Service`** lõi phục vụ đồng thời 5 vị trí trong hệ thống:
1. **Pre-Sales Explanation Validator:** Xác thực claim giải trình cho khách hàng tự khám phá.
2. **Official Quote Explanation Validator:** Kiểm tra tính nhất quán giữa số liệu Math Engine và văn bản Why/Why-not.
3. **Sales Message Composer:** Kiểm tra tin nhắn Sale soạn gửi khách.
4. **PDF Content Validator:** Rà soát nội dung trước khi chuyển Outbox render PDF.
5. **Manager Approval Package Validator:** Bảo đảm không có luận điểm sai lệch khi trình duyệt Quản lý.

---

## 3.9. Feature F9 — Policy Structured Rule Extraction

### Mục tiêu

Nâng cấp policy ingestion từ chỉ lưu text/chunk sang lưu clause và rule có cấu trúc.

### Pipeline

```text
Upload document
→ Parse document
→ Chunk document
→ Extract clauses
→ Extract candidate rules
→ Attach source coordinates
→ Detect conflicts
→ Human validation
→ Publish policy version
```

### Rule không được tự động có hiệu lực

Các trạng thái:

```text
DRAFT
→ EXTRACTED
→ VALIDATION_REQUIRED
→ APPROVED_FOR_USE
→ ACTIVE
→ RETIRED
```

### Rule schema tối thiểu

```json
{
  "rule_id": "RULE-001",
  "policy_id": "POL-001",
  "policy_version": "v3",
  "scope": {
    "project_id": "PROJECT-001",
    "customer_segment": ["STANDARD"]
  },
  "conditions": [
    {
      "attribute": "payment_method",
      "operator": "EQUALS",
      "value": "EARLY"
    }
  ],
  "benefits": [
    {
      "type": "DISCOUNT_PERCENT",
      "value": "0.0800"
    }
  ],
  "exclusions": ["RULE-009"],
  "priority": 20,
  "source_refs": ["CLAUSE-4.2"],
  "validation_status": "VALIDATION_REQUIRED"
}
```

### MVP storage

Chưa cần Graph Database riêng. Có thể dùng:

```text
PostgreSQL normalized tables
+ JSONB attributes
+ policy_clause/policy_rule relations
+ deterministic conflict evaluator
```

---

# 4. Tích hợp với kiến trúc hiện tại

## 4.1. Tích hợp với TD-4.1 — Runtime Architecture

### Thành phần mới

```text
Customer Web UI
Pre-Sales API
Lead Handoff Service
Compliance Service
```

### Thành phần dùng lại

```text
PostgreSQL
Redis/ARQ
Qdrant/vector store
Object storage
SSE
LangGraph checkpoint
Transactional outbox
PDF worker
```

### Boundary mới

```text
Public Pre-Sales Boundary
        ≠
Official Quote Boundary
```

Public Pre-Sales không được gọi các side-effect node của Official Quote.

---

## 4.2. Tích hợp với TD-4.2 — Domain/Data Design

### Entity bổ sung

```text
pre_sales_session
pre_sales_message
customer_consent
customer_constraint
pre_sales_plan
lead_dossier
handoff_record
compliance_check
compliance_claim_result
```

### Quan hệ chính

```text
pre_sales_session 1 ── N pre_sales_message
pre_sales_session 1 ── N pre_sales_plan
pre_sales_session 1 ── 1 lead_dossier
lead_dossier 1 ── N handoff_record
lead_dossier 1 ── N quote
quote 1 ── N quote_version
quote_version 1 ── N calculation_artifact
quote_version 1 ── N evidence_artifact
```

### Immutable requirement

- raw customer message có retention riêng;
- extracted constraint là versioned artifact;
- pre-sales plan bất biến sau khi phát hành;
- official quote được tạo lại từ context đã xác nhận;
- compliance result phải gắn với message hash và policy version.

---

## 4.3. Tích hợp với TD-4.3 — StateGraph

### Graph Pre-Sales mới

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

### Interrupt points

- thiếu thông tin quan trọng;
- conflict chưa giải quyết;
- customer confirmation;
- consent trước handoff;
- policy ambiguity.

### Không có trong Pre-Sales Graph

```text
commit_approval_snapshot_audit
sign_server_attestation
issue_official_pdf
manager_approve
```

### Official Quote Graph

Giữ nguyên graph đã được chốt trong TD-4.3, chỉ bổ sung:

```text
source_pre_sales_session_id
source_dossier_id
```

vào workflow context nếu quote được tạo từ lead.

---

## 4.4. Tích hợp với TD-4.4 — API/Event/Tool

### API mới

```http
POST /api/v1/pre-sales/sessions
GET /api/v1/pre-sales/sessions/{session_id}
POST /api/v1/pre-sales/sessions/{session_id}/messages
GET /api/v1/pre-sales/sessions/{session_id}/events
POST /api/v1/pre-sales/sessions/{session_id}/handoff
GET /api/v1/leads/{dossier_id}
POST /api/v1/leads/{dossier_id}/create-quote
POST /api/v1/compliance/check-message
```

### Event mới

```text
PRE_SALES_SESSION_CREATED
CUSTOMER_CONSTRAINTS_EXTRACTED
CUSTOMER_CONSTRAINTS_CONFIRMED
PRE_SALES_PLAN_READY
CUSTOMER_HANDOFF_CONSENTED
LEAD_DOSSIER_CREATED
LEAD_HANDED_OFF
OFFICIAL_QUOTE_CREATED_FROM_LEAD
COMPLIANCE_CHECK_COMPLETED
COMPLIANCE_CLAIM_BLOCKED
```

### Tool mới hoặc tái sử dụng

Pre-Sales được phép dùng:

```text
retrieve_policy_by_date
calculate_cashflow_deterministic
validate_pricing_results
rank_scenarios_by_objective
generate_dual_explanation
```

Không được dùng trực tiếp:

```text
commit_approval_snapshot_audit
append_audit_event
create_pdf_outbox
sign_server_attestation
```

### Internal commands mới

```text
create_pre_sales_session
persist_customer_consent
create_lead_dossier
create_official_quote_from_dossier
run_message_compliance_check
```

Các command ghi dữ liệu phải có:

- idempotency;
- authorization;
- transaction boundary;
- audit requirement;
- retry semantics.

---

# 5. Bảo mật, quyền riêng tư và an toàn nghiệp vụ

## 5.1. Consent

Trước khi chuyển dữ liệu khách cho Sale, phải có:

```text
consent_type
consent_version
consented_at
consent_channel
purpose
expiry
```

Không được mặc định rằng khách nhập số điện thoại đồng nghĩa với đồng ý marketing.

## 5.2. PII

- mã hóa khi lưu nếu phù hợp;
- redaction trong log;
- RBAC theo vai trò và tenant/project;
- retention riêng cho raw chat;
- xóa hoặc anonymize khi hết hạn;
- không gửi toàn bộ transcript cho LLM nếu không cần.

## 5.3. Prompt injection

Guardrail cần đặt tại:

```text
customer input
uploaded document
retrieved chunk
tool argument
tool output
LLM output
manager feedback
approval boundary
```

Nội dung policy không được phép tự ghi đè system instruction hoặc workflow authorization.

## 5.4. Disclaimer và claim safety

Các từ sau phải được kiểm soát:

```text
chắc chắn
cam kết
đảm bảo
100%
không rủi ro
lợi nhuận cố định
được duyệt chắc chắn
```

Nếu không có evidence tương ứng, claim phải bị cảnh báo hoặc block.

---

# 6. Tích hợp kênh giao tiếp

## 6.1. MVP

Ưu tiên:

```text
Customer Web UI
Sales Dashboard
Telegram Bot nội bộ tùy chọn
Download/copy plan
```

## 6.2. Zalo

Không sử dụng unofficial personal API.

Production integration cần tách thành adapter riêng:

```text
Zalo OA Adapter
ZNS Adapter
Webhook Adapter
Template/Consent Manager
```

Phải xác minh policy, template approval, consent và giới hạn API theo tài liệu chính thức trước khi triển khai.

## 6.3. Thiết kế Channel Adapter

```text
NotificationService
├── WebNotificationAdapter
├── TelegramAdapter
├── EmailAdapter
└── ZaloOfficialAdapter
```

Business workflow không được phụ thuộc cứng vào một kênh duy nhất.

---

# 7. Tính mở rộng đa ngành

## 7.1. Phần dùng chung

```text
Tenant/Identity
Policy Registry
Document Ingestion
Provenance
Rule/Conflict Framework
Workflow
Audit/Event
Outbox
Tool Governance
```

## 7.2. Phần thuộc Domain Adapter

```text
Input schema
Calculator
Ranking objective
Tax/fee model
Approval authority
Output renderer
External integration
```

## 7.3. Real Estate Adapter trong MVP

```text
asset = apartment/unit
customer constraints = own funds/income/loan need
calculation = payment schedule/discount/VAT/fees
output = financial plan/PDF
```

## 7.4. Retail/Auto/Franchise

Chỉ xây extension point trong MVP, chưa triển khai production.

Ví dụ:

```text
Retail Adapter → headless deterministic rule API
Automotive Adapter → vehicle pricing/loan/option calculator
Franchise Adapter → SOP/contract compliance assistant
```

Không ép các adapter dùng chung một calculator hoặc một workflow approval.

---

# 8. Roadmap triển khai

## Phase 1 — MVP Core (Bao gồm đầy đủ F1 → F8)

Theo yêu cầu nghiệp vụ và định vị giá trị sản phẩm, **toàn bộ các tính năng từ F1 đến F8 (bao gồm đặc biệt F4 và F8) được tích hợp trực tiếp vào phạm vi MVP**:

- **F1 & F2 — Pre-Sales Discovery & Constraint Extraction:** Khách hàng tự tương tác khai phá nhu cầu, trích xuất ràng buộc tài chính (vốn tự có, trả hàng tháng) vào `CustomerConstraints` có kiểu dữ liệu chuẩn;
- **Chính sách & Tra cứu:** Truy vấn chính sách qua Supabase pgvector với bộ lọc thời gian Time-Travel SQL;
- **F3 & F5 — Deterministic Financial Optimizer & Pre-Sales Plan:** Gọi trực tiếp Python Math Engine (FCS) tính toán 1–3 kịch bản, hiển thị so sánh với watermark bảo lưu pháp lý `PRE-SALES ESTIMATE - NOT AN OFFICIAL QUOTE`;
- **F4 — Claim-Level Evidence Linking:** Tích hợp trực tiếp lớp truy vết chứng cứ đa tầng cho mọi luận điểm Why/Why-not: Tọa độ nguồn Document/Version/Clause/Page/Hash, đối soát số học tất định với FCS Engine, bóc tách luận điểm hỗ trợ một phần (`PARTIALLY_SUPPORTED`), hiển thị citation tương tác `[1]`, `[2]`;
- **F6 — Sales Handover Dossier:** Đóng gói hồ sơ khách hàng, phân loại mức độ nóng (Lead Temperature: `HOT`/`WARM`/`COLD`) theo rule minh bạch;
- **F7 — Create Official Quote from Lead:** Cho phép Sale khởi tạo báo giá chính thức từ hồ sơ bàn giao, bắt buộc Re-validation & Re-calculation qua `OfficialQuoteGraph`;
- **F8 — Evidence-Backed Message Composer & Compliance Gate:** Giao diện soạn thảo tin nhắn tập trung cho Sale, tích hợp 3 tầng chốt chặn (on-draft, debounce on-typing, final send gate), phân loại 4 mức tuân thủ (`SUPPORTED`, `CONDITIONAL`, `UNSUPPORTED`, `PROHIBITED`), khóa cứng các phát ngôn cam kết quá thẩm quyền hoặc sai lệch chính sách.

## Phase 2 — Policy Automation & Structured Rule Extraction

- **F9 — Policy Structured Rule Extraction:** Pipeline trích xuất văn bản PDF thành quy tắc dạng cấu trúc JSON kèm giao diện Human-in-the-Loop review cho Policy Admin;
- Giao diện ma trận xung đột chính sách (Policy Conflict Matrix UI);
- Tích hợp thông báo nội bộ qua Telegram Bot (Sales lead alerts);
- Mở rộng PDF citation viewer với tính năng highlight vùng văn bản chính sách trực tiếp trên tài liệu gốc.

## Phase 3 — Operationalization & Integrations

- CRM / ERP Lead handoff connectors;
- Bảng điều khiển phân tích chuyển đổi (Conversion & Policy Analytics Dashboard);
- Hiệu chuẩn thuật toán Lead Scoring;
- Quản lý chính sách lưu trữ (Retention Policy) và đồng thuận PII (Consent Management).

## Phase 4 — Policy Platform Expansion

- Mô phỏng chính sách bán hàng mới (Policy Draft Simulation & Margin Impact);
- Headless Business Rules API cho các hệ thống đối tác;
- Các Domain Adapters ngành mở rộng (Automotive, Retail, Franchise);
- Tích hợp Zalo Official Account (ZNS/OA) sản xuất.

---

# 9. Acceptance Criteria cho tính năng mới

## Pre-Sales

- [ ] Khách khởi tạo được session.
- [ ] Agent hỏi lại input không rõ.
- [ ] Input được lưu dưới dạng typed constraints.
- [ ] Khách xác nhận assumptions trước calculation.
- [ ] Hệ thống tạo tối đa 3 plan.
- [ ] Tất cả số tiền khớp canonical fixture/FCS.
- [ ] Plan có disclaimer và evidence.
- [ ] Plan không có trạng thái official approval.

## Handoff

- [ ] Consent được lưu trước khi handoff.
- [ ] Dossier có customer needs, financial inputs, plans và evidence.
- [ ] Dossier không chứa PII ngoài scope của Sale.
- [ ] Duplicate handoff không tạo nhiều side effect.
- [ ] Sale có thể tạo official quote từ dossier.
- [ ] Official quote revalidate và recalculate.

## Claim-Level Evidence Linking (F4)

- [ ] Mỗi luận điểm Why và Why-not bắt buộc mang định danh duy nhất `claim_id`.
- [ ] Claim bắt buộc phân loại rõ 1 trong 4 loại: `POLICY_REASON`, `CALCULATION_RESULT`, `DERIVED_RECOMMENDATION`, `USER_PROVIDED`.
- [ ] Phân loại chính xác 5 trạng thái kiểm định: `SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`, `REQUIRES_REVIEW`.
- [ ] Claim chính sách bắt buộc chứa: `policy_id`, `policy_version`, `clause_id`, `page`, `section`, `document_hash`.
- [ ] Claim số học bắt buộc gắn tham chiếu `CalculationArtifact` (`artifact_id`, `field_path`, `numeric_consistency_hash`).
- [ ] Validator phát hiện được tình trạng mở rộng suy luận vượt quá evidence (Overclaim Detection).
- [ ] Luận điểm chỉ được hỗ trợ một phần (`PARTIALLY_SUPPORTED`) bị tách vế và yêu cầu điều chỉnh câu chữ thận trọng.
- [ ] Người dùng có thể bấm vào chỉ số citation `[1]`, `[2]` trên giao diện để mở bảng tọa độ chứng cứ chi tiết.
- [ ] Văn bản chính sách hết hiệu lực tại ngày giao dịch không bao giờ được chấp nhận làm căn cứ hợp lệ (`Time-Travel Invariant`).
- [ ] Claim bị gắn nhãn `UNSUPPORTED` hoặc `CONTRADICTED` tuyệt đối không được hiển thị như một kết luận chắc chắn.
- [ ] Toàn bộ chuỗi bằng chứng (Evidence Chain) được lưu trữ bất biến (immutable) cùng với `quote_version` hoặc `pre_sales_plan`.
- [ ] Có bộ test kiểm thử phân biệt rõ giữa *"ân hạn nợ gốc"* và *"ân hạn cả gốc lẫn lãi"*.
- [ ] Có bộ test kiểm thử phát hiện số tiền trong văn bản giải thích sai lệch với kết quả tính của Python Math Engine.
- [ ] Có bộ test kiểm thử từ chối các trích dẫn thuộc phiên bản chính sách cũ đã bị thu hồi (`REVOKED`).
- [ ] Claim do người dùng khai báo (`USER_PROVIDED`) được gắn nhãn minh bạch `USER_DECLARED`, không trình bày như sự thật đã thẩm định.

## Evidence-Backed Message Composer & Compliance Gate (F8)

- [ ] Nội dung do Agent sinh ra (Generator) bắt buộc phải tự động chạy qua Validator trước khi hiển thị.
- [ ] Nội dung do Sale tự nhập hoặc chỉnh sửa đều được kiểm tra tuân thủ qua Claim Compliance Service.
- [ ] Mọi thay đổi ký tự sau lần kiểm tra trước đều đánh dấu trạng thái "Cần kiểm tra lại" (Stale Check).
- [ ] Thao tác gửi khách (Final Send) luôn tự động kích hoạt kiểm tra chốt chặn lần cuối với `message_hash`.
- [ ] Phân loại chính xác 4 mức trạng thái: `SUPPORTED`, `CONDITIONAL`, `UNSUPPORTED`, `PROHIBITED`.
- [ ] Mọi claim số tiền trong tin nhắn được đối soát 100% với `CalculationArtifact` của Python Math Engine.
- [ ] Claim rủi ro cao (cam kết tín dụng, cam kết lợi nhuận, từ ngữ tuyệt đối hóa) bị khóa cứng (`BLOCKED`).
- [ ] Kết quả kiểm tra được gắn chặt chẽ với `message_hash`, `quote_version` và `policy_version`.
- [ ] Nhật ký kiểm tra (Audit Trail) ghi nhận đầy đủ `actor_id`, `actor_role`, nội dung trước/sau sửa và kết quả tuân thủ.
- [ ] Không lưu trữ thông tin PII không cần thiết hoặc raw message vượt quá thời hạn quy định (Retention Policy).

## Policy Admin

- [ ] Document có source hash.
- [ ] Extracted rule có source coordinate.
- [ ] Rule chưa validate không được dùng để publish.
- [ ] Conflict được phát hiện và hiển thị.
- [ ] Policy version có effective period.

## Integration

- [ ] Pre-Sales Graph không gọi approval side effect.
- [ ] Official Quote Graph nhận được source dossier reference.
- [ ] SSE hỗ trợ event của pre-sales/handoff.
- [ ] Outbox xử lý notification retry.
- [ ] Audit ghi đúng actor, tenant, session/quote reference.

---

# 10. Các quyết định cần Product/Engineering chốt

1. Kênh đầu tiên cho Customer UI: web mobile hay landing page nhúng.
2. Kênh handoff MVP: dashboard, Telegram hay cả hai.
3. Dự án BĐS và policy corpus dùng cho MVP.
4. Các objective tài chính được bật ở phiên bản đầu.
5. Ngưỡng thông tin tối thiểu trước khi tính phương án.
6. Lead temperature dùng heuristic nào.
7. Mức độ hiển thị transcript cho Sale.
8. Retention của pre-sales session và raw transcript.
9. Disclaimer được Business/Legal phê duyệt.
10. Các claim bắt buộc phải block khi không có evidence.
11. Template PDF tham khảo và template PDF chính thức.
12. Có cho phép customer nhập số điện thoại ngay hay chỉ sau khi xem plan.
13. Dữ liệu nào được phép gửi tới LLM provider.
14. Ngưỡng chuyển từ pre-sales sang official quote.
15. Có cần CRM adapter trong MVP hay chỉ export/API.

---

# 11. Kết luận

Tính năng mới nên được tích hợp theo nguyên tắc:

```text
Mở rộng đầu vào và trải nghiệm khách hàng,
không phá vỡ lõi tính toán, approval, audit và versioning đã chốt.
```

MVP chính thức tích hợp trọn vẹn 5 cụm năng lực cốt lõi (F1 → F8):

```text
1. Pre-Sales Discovery Agent & Constraint Extraction (F1, F2)
2. Deterministic Financial Optimizer & Reference Plan (F3, F5)
3. Claim-Level Evidence Linking (F4)
4. Sales Handover Dossier & Official Quote Conversion (F6, F7)
5. Evidence-Backed Message Composer & Compliance Gate (F8)
```

Các tính năng mở rộng như Rule Extraction tự động (F9), Knowledge Graph, Retail POS, Voice, Zalo production và Multi-domain execution sẽ được xây theo adapter/extension ở các phase tiếp theo.

Mục tiêu cuối cùng của bản tích hợp là tạo ra một **Vertical Slice hoàn chỉnh và khép kín từ đầu phễu đến cuối phễu**:

```text
Khách hàng nhập nhu cầu
→ Agent khai phá & chuẩn hóa ràng buộc tài chính (F1, F2)
→ Tính toán các phương án tối ưu bằng Python Math Engine (F3, F5)
→ Gắn tọa độ bằng chứng & giải trình Why/Why-not chi tiết (F4)
→ Đóng gói hồ sơ bàn giao & phân loại nhiệt độ Lead (F6)
→ Sale khởi tạo báo giá chính thức, revalidate & recalculate (F7)
→ Quản lý phê duyệt và ký số Ed25519 (Manager Approval Gate)
→ Soạn tin nhắn gửi khách & vượt qua chốt chặn tuân thủ (F8)
→ Xuất PDF báo giá chính thức & lưu trữ Audit Snapshot bất biến
```

Nếu vertical slice này hoạt động ổn định, các module mở rộng sau đó có thể được phát triển mà không phải thay đổi nền tảng workflow và governance hiện tại.
