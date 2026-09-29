# BÁO CÁO NHẬT KÝ THAY ĐỔI KIẾN TRÚC & HỆ THỐNG
## DỰ ÁN: PRICEPOLICY AI AGENT – NỀN TẢNG BẢO CHỨNG ĐỊNH GIÁ & QUẢN TRỊ CHÍNH SÁCH BÁN HÀNG VLANDFUTURE

**Mã tài liệu:** CHANGELOG-ARCH-01  
**Mã sản phẩm:** BDSVLandFuture-06  
**Khối nghiệp vụ:** Kinh doanh Bất động sản VLandFuture  
**Ngày khởi tạo:** 2026-09-26  
**Lần cập nhật cuối:** 2026-09-26T18:30:00+07:00  
**Phiên bản hệ thống:** v2.8 (Controlled Implementation Baseline — Sales UI Handoff Spec Locked)  
**Tác giả / Quản trị viên:** Principal Enterprise Architect & Solution Architect Lead  
**Trạng thái tài liệu:** **LIVING DOCUMENT (TÀI LIỆU SỐNG ĐƯỢC DUY TRÌ & CẬP NHẬT LIÊN TỤC)**

---

## 1. MỤC ĐÍCH & NGUYÊN TẮC QUẢN TRỊ THAY ĐỔI (CHANGELOG GOVERNANCE)

### 1.1 Mục đích Tài liệu
Tài liệu này là **Nguồn Chân lý Duy nhất (Single Source of Truth - SoT)** lưu vết toàn bộ các thay đổi, tối ưu hóa, chuẩn hóa kiến trúc, thiết kế kỹ thuật, hợp đồng giao diện, cấu trúc dữ liệu và phân bổ công việc của toàn bộ hệ thống PricePolicy AI Agent.

Mọi thay đổi trong tương lai về:
- Kiến trúc tổng thể (Architecture Design)
- Môi trường & Hồ sơ Triển khai (Deployment Topology & Profiles)
- Cấu trúc Cơ sở Dữ liệu & Bảng Schema DDL (Domain Data & Financial Schemas)
- Đồ thị Máy trạng thái Agentic Orchestration (StateGraph & Decision Boundaries)
- Hợp đồng Giao diện REST API, Sự kiện SSE & Danh mục Công cụ (API, Event & Tool Contracts)
- Kế hoạch Triển khai & Phân bổ Nguồn lực (Implementation Plans & Spikes)

**BẮT BUỘC** phải được ghi chép có cấu trúc vào tệp này trước khi tiến hành cập nhật mã nguồn hoặc tạo pull request tích hợp.

### 1.2 Cấu trúc Chuẩn của một Bản ghi Thay đổi (Changelog Entry Schema)
Mỗi bản ghi cập nhật trong tương lai phải tuân thủ đúng định dạng:
```markdown
## [YYYY-MM-DD] - Phiên bản X.Y - <Tiêu đề Đợt Cập nhật>
- **Người thực hiện:** <Họ tên / Role>
- **Tài liệu tác động:** <Danh sách file kèm link>
- **Lý do thay đổi:** <Bối cảnh nghiệp vụ / Phản biện / Fix lỗi / Nâng cấp>
- **Chi tiết các thay đổi:**
  - Kiến trúc & Thành phần Logic (Components)
  - Mô hình Dữ liệu & Schema DDL
  - Đồ thị Trạng thái (StateGraph)
  - Hợp đồng API / Tool Contracts
  - Phân bổ Thực thi & Spikes
- **Quyết định Kiến trúc Mới (ADRs):** <Mã ADR và tóm tắt>
- **Tiêu chuẩn Nghiệm thu Bổ sung (New ACs):** <Mã AC>
```

---

## 2. NHẬT KÝ THAY ĐỔI LỊCH SỬ

---

### [2026-09-26] - Phiên bản 2.8 — Ban hành TD-5.3: Đặc tả Bàn giao UI Màn Sales (Handoff Spec cho Agent)

- **Người thực hiện:** TechLead (Tạ Việt Cường) + Dev 3 (Phương Đuy)
- **Tài liệu mới ban hành:** [mydoc/5.3-sales-ui-handoff-spec.md](5.3-sales-ui-handoff-spec.md)
- **Lý do cập nhật:** Hai prototype (SCR-S00 workspace + SCR-S03 copilot) đã được duyệt hướng; cần bản đặc tả chi tiết đến mức component + giá trị px/hex để agent AI / Dev 3 implement Next.js không phải suy đoán.
- **Chi tiết nội dung trọng yếu:** Layout geometry (rail 64px / chat flex / panel 380px, 3 breakpoints, container 1500px); design tokens trích trực tiếp từ prototype (màu, typography, radius, shadow, motion); đặc tả 7 component card trong stream (Briefing/Text/Confirm/Stepper/Receipt/Nudge/Clarify); 8 artifact type của panel; intent router + slash command; mapping endpoint/loading/empty/error từng component; responsive + a11y; acceptance checklist 10 mục + 7 anti-pattern từ chối nghiệm thu.
- **Quyết định Kiến trúc Mới (ADRs):** ADR-UX-05 — Màn Sales chỉ có 1 route `/sales`; các "quản lý khách hàng/báo giá" là view render trong Artifact Panel hoặc do agent render vào hội thoại, không phải route riêng; không dùng thư viện chat UI có sẵn (tự dựng theo spec).
- **Tiêu chuẩn Nghiệm thu Bổ sung (New ACs):** AC-UI-01 — acceptance checklist §10 pass 100% trước khi merge; AC-UI-02 — token màu/px dùng nguyên bản từ §3, không tự chế token mới.

---


### [2026-09-26] - Phiên bản 2.7 — Ban hành TD-5.2: Mô hình Tương tác "Agent là Trung tâm" cho Sales Workspace

- **Người thực hiện:** TechLead (Tạ Việt Cường) + Dev 3 (Phương Đuy)
- **Tài liệu mới ban hành:** [mydoc/5.2-agent-first-sales-workspace.md](5.2-agent-first-sales-workspace.md)
- **Lý do cập nhật:** Chốt quyết định kiến trúc UX cấp cao — màn hình chính của Sale là hội thoại với Agent Trợ lý (theo định hướng Product Owner), kết hợp menu hoạt động (Khách hàng, Báo giá, Tin nhắn, Chính sách) làm lưới an toàn.
- **Chi tiết nội dung trọng yếu:** Đối chiếu 3 mô hình (tool-first / agent-first tuyệt đối / hybrid) → chọn mô hình C "Chat để chỉ huy — Panel để làm việc — Menu để duyệt"; bố cục SCR-S00 (Rail 64px + Agent Conversation + Artifact Panel); 5 mục rail với bảng phân định khi nào dùng menu khi nào hỏi agent; 8 pattern hội thoại (Briefing mở ca, Slash command, Confirm card, Artifact rendering, Stepper, Receipt+Undo, Context chip, Proactive nudge); vòng đời lệnh "tạo báo giá" 2-lần-chạm; bảng ranh giới an toàn agent (đối ứng interrupt StateGraph TD-4.3).
- **Quyết định Kiến trúc Mới (ADRs):** ADR-UX-04 — Màn Sales chính là Agent Conversation; trang Home riêng bị bãi bỏ, thay bằng Briefing card do agent chủ động đăng vào đầu phiên (S01→SCR-S00). 7 vòng tương tác TD-5.1 giữ nguyên, chỉ đảo bố cục.
- **Tiêu chuẩn Nghiệm thu Bổ sung (New ACs):** AC-UX-03 — mọi side-effect từ chat phải qua Confirm card (2 lần chạm); AC-UX-04 — mọi kết quả có cấu trúc render thành đối tượng ở Artifact Panel, không đăng dạng text.

---


### [2026-09-26] - Phiên bản 2.6 — Ban hành TD-5.1: UI theo Luồng Nghiệp vụ Đời thường của Sales Executive

- **Người thực hiện:** TechLead (Tạ Việt Cường) + Dev 3 (Phương Đuy) — journey design workshop
- **Tài liệu mới ban hành:** [mydoc/5.1-sales-journey-ui.md](5.1-sales-journey-ui.md)
- **Lý do cập nhật:** TD-5 thiết kế theo màn hình; cần bổ sung góc nhìn journey-map theo ngày đời thực của Sale (70% tương tác trên mobile, Zalo là môi trường chính, khách hỏi giá giữa đường) để UI chạm đúng moment of truth.
- **Chi tiết nội dung trọng yếu:** 5 nguyên tắc vàng (A1 Answer-first-formalize-later, A2 Không nhập hai lần, A3 Zalo-là-nhà hệ thống-là-bộ-não, A4 Chặn-phải-có-lối-đi, A5 Trạng thái-tự-chạy-tới-người); journey map 1 ngày với 10 moment; 7 interaction loops (Sales Home, Dossier call-brief, Sales Copilot < 60s với Copy-mode có audit, Quote Builder prefill, Revision tại chỗ, Composer + PDF share, Meeting Mode & Pipeline tự sinh).
- **Quyết định Kiến trúc Mới (ADRs):** ADR-UX-03 (ĐỀ XUẤT — chờ phê duyệt) — bổ sung 4 hợp đồng API còn thiếu so với luồng đời thực: `GET /quotes?assignee=me`, `GET /policies/changes?since=`, `POST /quotes/{id}/versions/{version}/submit-for-review`, `GET /notifications`; kèm yêu cầu phi chức năng push/webhook mobile.
- **Tiêu chuẩn Nghiệm thu Bổ sung (New ACs):** AC-SALE-01 — trả lời khách qua Copilot < 60s (median); AC-SALE-02 — 100% tin nhắn kênh Copy vẫn có vết compliance check (ON_COPY logged).

---


### [2026-09-26] - Phiên bản 2.5 — Ban hành TD-5: Đặc tả Tương tác UI/UX theo Đối tượng

- **Người thực hiện:** TechLead (Tạ Việt Cường) — phối hợp định hướng Dev 3 (Phương Đuy)
- **Tài liệu mới ban hành:** [mydoc/5.uiux-interaction-design.md](5.uiux-interaction-design.md)
- **Tài liệu nền kế thừa:** `mydoc/Luu_tru/UiUxRecommend.md` (15 nguyên tắc Conversational Financial Workspace), `docs/team_report/Wireframe_UI_Flow.md` (SCR-02/04/05/06/07 + design tokens)
- **Lý do cập nhật:** Wireframe hiện có còn thiếu đặc tả tương tác cho Message Composer F8, Lead Dossier Inbox và toàn bộ workspace Policy Admin; các màn có sẵn chưa chỉ định vi-tương tác bám contract hệ thống (SSE event, enum trạng thái, debounce, checkpoint F8).
- **Chi tiết nội dung trọng yếu:** 7 nguyên tắc xuyên suốt (Trust-first, Boundary visualization, Latency honesty, Safe-abstention-≠-error…); vi-tương tác cụ thể cho 4 persona (Customer / Sales / Manager / Policy Admin); ma trận Màn hình ↔ Component ↔ Endpoint ↔ ưu tiên MVP (§5.1) làm checklist bàn giao Dev 3; bộ chỉ số UX nối `eval/`.
- **Quyết định Kiến trúc Mới (ADRs):** ADR-UX-01 — UI không tự quyết hành vi gửi tin: nút Gửi chỉ là gợi ý, chốt chặn luôn ở backend gate `ON_FINAL_SEND` (double-lock); ADR-UX-02 — không có thao tác xóa policy, chỉ supersede (đồng bộ bất biến append-only).
- **Tiêu chuẩn Nghiệm thu Bổ sung (New ACs):** AC-UX-01 — mọi màn hình P0 map 1-1 endpoint có thật trong TD-4.4; AC-UX-02 — mọi cờ rủi ro hiển thị icon + chữ, không phụ thuộc màu đơn thuần.

---


### [2026-09-26] - Phiên bản 2.4 — Chuẩn hóa Dependencies & Environment Variables theo Kiến trúc TD-4.1 (Codebase Baseline)

- **Người thực hiện:** TechLead (Tạ Việt Cường)
- **Tài liệu tác động:** `requirements.txt`, `.env.example`, `src/config.py`
- **Lý do thay đổi:** Scaffold codebase đã khóa phân vùng theo 11 components (xem `CodeBaseIndex.md`); cần chuẩn hóa danh sách phụ thuộc và biến môi trường bám kiến trúc đã chốt (Supabase PostgreSQL 16 + pgvector, Redis/ARQ outbox, UDS pricing sidecar, KMS Ed25519, SSE, PDF+QR) để 4 thành viên cài môi trường đồng nhất ngay từ Sprint 1.
- **Chi tiết các thay đổi:**
  - **Dependencies:** bật nhóm persistence (`sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pgvector`), outbox worker (`redis`, `arq`), SSE (`sse-starlette`), ký số (`pynacl` — dev-verify; production ký qua KMS), PDF+QR (`reportlab`, `qrcode`). Loại bỏ `chromadb` — vector store chính thức là Supabase pgvector theo TD-4.2.
  - **Environment:** tái cấu trúc `.env.example` theo nhóm component (DB, pgvector/embeddings 1536 dims, Redis, sidecar socket, KMS, object storage, pre-sales TTL); giữ nguyên nhóm AI-log grading và LangSmith của BTC.
  - **Config:** `src/config.py` bỏ `chroma_persist_dir`, bổ sung settings tương ứng biến môi trường mới (đều có default an toàn, không phá behavior hiện tại).
  - **Phạm vi code:** không thay đổi hợp đồng API/StateGraph/DD — chỉ tầng cấu hình & phụ thuộc.
- **Quyết định Kiến trúc Mới (ADRs):** ADR-IMP-01 — Python deps cho persistence/worker/PDF được khóa vào requirements.txt cơ sở; lib tuỳ chọn (multipart, pyjwt, boto3, psycopg2-binary) để dạng comment, bật khi implement đúng component.
- **Tiêu chuẩn Nghiệm thu Bổ sung (New ACs):** AC-ENV-01 — `pip install -r requirements.txt` trên Python 3.11 sạch, mọi import mới khả dụng; AC-ENV-02 — `ruff check src/ tests/` + toàn bộ pytest vẫn xanh sau thay đổi config.

---

### [2026-09-26] - Phiên bản 2.3 — Ban hành Kế hoạch Thực thi Chi tiết cho Vai trò TechLead (CTV_ImplementPlanDetail.md)

- **Người thực hiện:** TechLead / Principal System Architect & Agentic Orchestrator
- **Tài liệu mới ban hành:** [mydoc/CTV_ImplementPlanDetail.md](file:///d:/VinUni/P-096/mydoc/CTV_ImplementPlanDetail.md)
- **Tài liệu tham chiếu chuẩn:** [mydoc/ImplementPlan.md](file:///d:/VinUni/P-096/mydoc/ImplementPlan.md), [mydoc/Implement_plan_detail.md](file:///d:/VinUni/P-096/mydoc/Implement_plan_detail.md)
- **Lý do cập nhật:** Cụ thể hóa toàn bộ trách nhiệm, đầu việc, mã nguồn, thuật toán và lộ trình 6 phase cho riêng vai trò TechLead trong sprint 10 ngày của dự án.
- **Chi tiết các nội dung trọng yếu được thiết lập:**
  - **Phân định rõ 5/11 Components thuộc quyền TechLead:** `C-01` (Official Quote StateGraph), `C-02` (Time-Travel Context & OCC), `C-05` (HITL Review & KMS Attestation Ed25519), `C-07` (Anti-Cyclic Hash Chain Audit Trail), `C-09` (Pre-Sales Advisory StateGraph).
  - **Đặc tả kỹ thuật & Code mẫu 3 Spikes Kỹ thuật lõi:** Spike 2 (`AsyncPostgresSaver` Checkpointing & 3 Interrupts), Spike 3 (Ed25519 Sign-Before-Commit & Atomic Commit-Discard), Spike 4 (Anti-Cyclic Hash Chain $H_i$ & Genesis Verification).
  - **Lộ trình 6 Phase chi tiết theo từng ngày:** Phase 0 (Contract Freeze), Phase 1 (3 Spikes & StateGraph Skeleton), Phase 2 (Pre-Sales & Lead Handoff), Phase 3 (Official Quote & Recalculation), Phase 4 (KMS Signing & Outbox Worker), Phase 5 (Integration & 5 Failure Modes).
  - **Ma trận 29 Canonical Endpoints:** Xác định rõ các endpoint do TechLead trực tiếp lập trình (Pre-Sales, Quotes, Approval, Verification, SSE) và các endpoint phối hợp.
  - **Runbook Kiểm thử Thất bại:** Thiết lập chi tiết 5 kịch bản lỗi biên FAIL-01 đến FAIL-05 (Sidecar crash, DB crash post-KMS, Policy expired mid-flight, Concurrency race OCC, F8 send bypass).
  - **Quy chuẩn Vận hành Daily Sync 15 phút & Escalation Protocol:** 4 câu hỏi trọng tâm và quyền quyết định tối cao của TechLead đối với thay đổi kiến trúc và tiền tệ.

---

### [2026-09-26] - Phiên bản 2.2 — Tối ưu hóa Toàn diện sau Báo cáo Phản biện Vòng 2

- **Người thực hiện:** Principal Solution Architect & Lead AI Engineer
- **Tài liệu tham chiếu phản biện gốc:** [mydoc/phanbien.md](file:///d:/VinUni/P-096/mydoc/phanbien.md)
- **Danh sách 9 tài liệu được cập nhật & đồng bộ hóa 100%:**
  1. [mydoc/3.architecture-design.md](file:///d:/VinUni/P-096/mydoc/3.architecture-design.md) (Architecture Design v2.2)
  2. [mydoc/4.1-technical-architecture-runtime-deployment.md](file:///d:/VinUni/P-096/mydoc/4.1-technical-architecture-runtime-deployment.md) (Runtime & Deployment v2.0)
  3. [mydoc/4.2-domain-data-financial-design.md](file:///d:/VinUni/P-096/mydoc/4.2-domain-data-financial-design.md) (Domain Data & Financial Design v2.2)
  4. [mydoc/4.3-agent-stategraph-workflow-design.md](file:///d:/VinUni/P-096/mydoc/4.3-agent-stategraph-workflow-design.md) (Agent StateGraph & Workflow v2.2)
  5. [mydoc/4.4-api-event-tool-contracts.md](file:///d:/VinUni/P-096/mydoc/4.4-api-event-tool-contracts.md) (API, Event & Tool Contracts v2.2)
  6. [mydoc/1.requirement-analysis.md](file:///d:/VinUni/P-096/mydoc/1.requirement-analysis.md) (Enterprise PRD v2.4)
  7. [mydoc/2.product-discovery.md](file:///d:/VinUni/P-096/mydoc/2.product-discovery.md) (Product Discovery v2.1)
  8. [mydoc/Implement_plan_detail.md](file:///d:/VinUni/P-096/mydoc/Implement_plan_detail.md) (Implementation Plan Detail v1.1)
  9. [mydoc/Luu_tru/ImplementPlan.md](file:///d:/VinUni/P-096/mydoc/Luu_tru/ImplementPlan.md) (Team Sprint Action Plan v2.0)

---

#### 2.1 Bối cảnh & Mục tiêu Đợt Thay đổi
Báo cáo phản biện vòng 2 ([mydoc/phanbien.md](file:///d:/VinUni/P-096/mydoc/phanbien.md)) đã chỉ ra 10 điểm nghẽn (Blockers) và khoảng trống kiến trúc:
1. Vênh danh mục component giữa tài liệu 3 (8 components) và thực tế yêu cầu nghiệp vụ full-funnel (11 components).
2. Sơ đồ nghiệp vụ thiếu phân đoạn khám phá nhu cầu Pre-Sales và quy trình E2E kết nối bàn giao Lead.
3. Đồ thị máy trạng thái Pre-Sales chưa có đặc tả vòng đời kỹ thuật (TTL, thread namespace, resume token, interrupts).
4. Tính năng F8 thiếu hợp đồng gửi tin được kiểm soát ở backend (`POST /api/v1/messages/send`) và chưa làm rõ ngữ nghĩa clipboard.
5. Thiếu vòng đời trạng thái chi tiết cho kiểm duyệt thông điệp tuân thủ và ràng buộc băm toàn vẹn.
6. Bản ước tính tham khảo PDF chưa được phân tách rạch ròi với Báo giá chính thức Outbox.
7. Mập mờ hạ tầng triển khai giữa Kubernetes và Docker Compose / Linux VPS.
8. Vênh Nguồn Chân lý (SoT) của Vector Store giữa Qdrant và Supabase/pgvector.
9. Bất nhất danh mục Tiêu chí Tối ưu hóa (4 mục tiêu vs 5 mục tiêu vs 6 mục tiêu).
10. Thiếu đặc tả cho phân hệ F9 Policy Structured Rule Extraction, pre-publish test gate và rollback không phá hủy.

Toàn bộ 10 vấn đề trên đã được giải quyết dứt điểm và khóa chặt vào hệ thống tài liệu kỹ thuật.

---

#### 2.2 Chi tiết 10 Quyết định Thay đổi Hệ thống Trọng yếu

##### Thay đổi 1: Chuẩn hóa Danh mục 11 Logic Components (`C-01` đến `C-11`)
- **Nội dung:** Mở rộng từ 8 components cũ lên **11 Logic Components chuẩn hóa**, bổ sung:
  - `C-09`: **Pre-Sales Advisory StateGraph Engine** (Đồ thị tư vấn tiền bán hàng, lọc giỏ hàng, ước tính phương án tham khảo).
  - `C-10`: **Sales Lead Dossier & Handoff Service** (Quản lý hồ sơ bàn giao khách hàng có consent, đếm ngược SLA 15 phút, chuyển đổi báo giá 1 chạm).
  - `C-11`: **Sales Message Compliance Verification Gate** (Chốt chặn tuân thủ phát ngôn bán hàng F8, phân loại 4 tiers, bảo vệ chống rủi ro pháp lý/truyền thông).
- **Tài liệu tác động:** [3.architecture-design.md](file:///d:/VinUni/P-096/mydoc/3.architecture-design.md), [Implement_plan_detail.md](file:///d:/VinUni/P-096/mydoc/Implement_plan_detail.md), [Luu_tru/ImplementPlan.md](file:///d:/VinUni/P-096/mydoc/Luu_tru/ImplementPlan.md).

##### Thay đổi 2: Tái cấu trúc Luồng Nghiệp vụ E2E thành 5 Phân đoạn Tuần tự
- **Nội dung:** Thay thế sơ đồ luồng rời rạc bằng quy trình E2E 5 pha liên hoàn:
  1. *Phân đoạn 1:* Pre-Sales Discovery & Reference Plan Generation (Khách hàng tương tác Web, trích xuất ràng buộc tài chính).
  2. *Phân đoạn 2:* Electronic Consent & Sales Lead Dossier Handoff (Khách xác nhận chia sẻ thông tin, bàn giao sang Sales Dashboard).
  3. *Phân đoạn 3:* Official Quote StateGraph Execution & Recalculation (Sale kích hoạt tạo báo giá, thẩm định chính sách, Python Math Engine).
  4. *Phân đoạn 4:* Human-In-The-Loop Review & KMS Server Attestation (Quản lý thẩm định cờ rủi ro, ký số Ed25519, commit snapshot).
  5. *Phân đoạn 5:* Sales Message Compliance Gate & Enforced Dispatch (F8 kiểm tra tuân thủ trước khi gửi Zalo/SMS).
- **Tài liệu tác động:** [3.architecture-design.md](file:///d:/VinUni/P-096/mydoc/3.architecture-design.md), [4.3-agent-stategraph-workflow-design.md](file:///d:/VinUni/P-096/mydoc/4.3-agent-stategraph-workflow-design.md).

##### Thay đổi 3: Đặc tả Đồ thị Máy trạng thái Pre-Sales (`PreSalesGraph`) & 3 Điểm Ngắt HITL
- **Nội dung:**
  - Vận hành dưới Checkpoint Namespace độc lập `PRE_SALES`, thread id định dạng `presales:{tenant_id}:{session_id}`.
  - Session TTL = 1800 giây (30 phút không hoạt động $\rightarrow$ `EXPIRED`).
  - Thiết lập **3 điểm ngắt LangGraph `interrupt()`**:
    - `WAITING_FOR_CUSTOMER_INPUT`: Tạm dừng chờ khách hàng nhắn tin tiếp theo trong hội thoại.
    - `WAITING_FOR_CONSTRAINT_CONFIRMATION`: Hiển thị tóm tắt ràng buộc ngân sách, chờ khách bấm "Xác nhận đúng nhu cầu".
    - `WAITING_FOR_HANDOFF_CONSENT`: Hiển thị điều khoản bảo mật dữ liệu, chờ khách bấm "Đồng ý chia sẻ thông tin & kết nối Sale".
  - **Ranh giới kỹ thuật tối thượng:** Cấm gọi KMS Server Signer, cấm sinh chữ ký số, cấm chuyển trạng thái `APPROVED`, cấm ghi vào `transactional_outbox`.
- **Tài liệu tác động:** [4.3-agent-stategraph-workflow-design.md](file:///d:/VinUni/P-096/mydoc/4.3-agent-stategraph-workflow-design.md), [4.2-domain-data-financial-design.md](file:///d:/VinUni/P-096/mydoc/4.2-domain-data-financial-design.md).

##### Thay đổi 4: Thiết lập Hợp đồng Gửi tin Backend-Enforced (`POST /api/v1/messages/send`) & Ngữ nghĩa Clipboard
- **Nội dung:**
  - Không dựa vào frontend để tự kiểm tra; backend là rào chắn thực thi cuối cùng.
  - Endpoint `POST /api/v1/compliance/check-message`: Nhận tin nhắn, bóc tách claims, đối chiếu số tiền và điều khoản chính sách, trả về `compliance_status` và `message_hash`.
  - Endpoint `POST /api/v1/messages/send`: Bắt buộc truyền `message_hash`. Nếu trạng thái kiểm duyệt là `UNSUPPORTED` hoặc `PROHIBITED` $\rightarrow$ Backend trả mã **`403 Forbidden`** (`COMPLIANCE_SEND_BLOCKED`).
  - **Ngữ nghĩa Clipboard (Copy):** Nút Sao chép trên giao diện bị vô hiệu hóa cho đến khi `check-message` trả về `SUPPORTED` hoặc `CONDITIONAL`.
- **Tài liệu tác động:** [4.4-api-event-tool-contracts.md](file:///d:/VinUni/P-096/mydoc/4.4-api-event-tool-contracts.md), [4.3-agent-stategraph-workflow-design.md](file:///d:/VinUni/P-096/mydoc/4.3-agent-stategraph-workflow-design.md).

##### Thay đổi 5: Chuẩn hóa Vòng đời Tuân thủ Thông điệp (Compliance Status Lifecycle)
- **Nội dung:**
  - Định nghĩa `compliance_status_enum`: `DRAFT`, `CHECKING`, `SUPPORTED`, `CONDITIONAL`, `UNSUPPORTED`, `PROHIBITED`, `EXPIRED`, `SUPERSEDED`.
  - Phân hạng rủi ro `compliance_tier_enum`:
    - `TIER_1_GREEN`: Khớp 100% chứng cứ và số tiền, chính sách đang hiệu lực $\rightarrow$ Cho phép gửi ngay.
    - `TIER_2_YELLOW`: Đúng số tiền nhưng chính sách sắp hết hạn $\rightarrow$ Cảnh báo kèm disclaimer.
    - `TIER_3_RED`: Khẳng định không có dẫn chứng điều khoản hoặc sai lệch số tiền $\rightarrow$ Chặn gửi.
    - `TIER_4_BLACK`: Phát ngôn cam kết trái luật, hứa hẹn vượt thẩm quyền $\rightarrow$ Khóa gửi và ghi log vi phạm bảo mật.
  - Toàn bộ kết quả kiểm tra được băm SHA-256 (`message_hash`) và lưu vết kiểm toán bất biến.
- **Tài liệu tác động:** [4.2-domain-data-financial-design.md](file:///d:/VinUni/P-096/mydoc/4.2-domain-data-financial-design.md), [4.3-agent-stategraph-workflow-design.md](file:///d:/VinUni/P-096/mydoc/4.3-agent-stategraph-workflow-design.md).

##### Thay đổi 6: Tách biệt Bản ước tính Pre-Sales PDF và Báo giá Chính thức Outbox
- **Nội dung:**
  - **Báo giá Chính thức (Official Quote PDF):** Sinh bất đồng bộ qua Transactional Outbox Worker (`ARQ`), có Chữ ký số Ed25519 KMS, mã QR tra cứu tính toàn vẹn, lưu bản ghi vào `quote_snapshots` và `quote_audit_events`.
  - **Bản ước tính Tham khảo (Pre-Sales Estimate PDF):** Sinh đồng bộ tức thời (Synchronous on-demand $< 1.5\text{s}$) qua endpoint `GET /api/v1/pre-sales/sessions/{id}/reference-plan.pdf`. Bắt buộc chèn watermark chìm: `BẢN ƯỚC TÍNH THAM KHẢO TIỀN BÁN HÀNG - KHÔNG PHẢI BÁO GIÁ CHÍNH THỨC`. Tuyệt đối không có chữ ký số KMS và không ghi nhận cam kết doanh nghiệp.
- **Tài liệu tác động:** [3.architecture-design.md](file:///d:/VinUni/P-096/mydoc/3.architecture-design.md), [4.1-technical-architecture-runtime-deployment.md](file:///d:/VinUni/P-096/mydoc/4.1-technical-architecture-runtime-deployment.md), [4.4-api-event-tool-contracts.md](file:///d:/VinUni/P-096/mydoc/4.4-api-event-tool-contracts.md).

##### Thay đổi 7: Chuẩn hóa Mô hình Triển khai Hai Tầng (Two-Tier Deployment Profiles - ADR-023)
- **Nội dung:** Xóa bỏ hoàn toàn sự mập mờ giữa Kubernetes và VPS/Docker Compose:
  - **Tier 1 — MVP Demo & Hackathon Profile:** Chạy gọn trên một máy chủ Linux VPS (8 vCPU, 16GB RAM) hoặc cụm Docker Compose: Nginx Reverse Proxy (SSL termination, rate limiting), FastAPI Backend (`api-backend`), Math Engine Sidecar chạy local UDS socket (`/var/run/pricing/engine.sock`), PostgreSQL 16 + pgvector, Redis In-Memory, ARQ Worker, MinIO Object Storage.
  - **Tier 2 — Enterprise Scale Profile:** Mở rộng thành cụm AWS EKS / Kubernetes Pods, Amazon RDS Multi-AZ PostgreSQL, AWS KMS HSM, Amazon S3, Qdrant Vector Cluster.
- **Tài liệu tác động:** [3.architecture-design.md](file:///d:/VinUni/P-096/mydoc/3.architecture-design.md), [4.1-technical-architecture-runtime-deployment.md](file:///d:/VinUni/P-096/mydoc/4.1-technical-architecture-runtime-deployment.md).

##### Thay đổi 8: Khóa Chặt PostgreSQL 16 + pgvector làm Nguồn Chân lý Duy nhất cho MVP
- **Nội dung:**
  - Trong giai đoạn MVP, loại bỏ sự phân mảnh giữa Supabase, pgvector và Qdrant.
  - Sử dụng **PostgreSQL 16 với pgvector extension (HNSW index, khoảng cách cosine, vector 1536 chiều)** làm Single Source of Truth duy nhất lưu trữ đồng thời dữ liệu quan hệ, snapshot kiểm toán và vector embeddings chính sách bán hàng.
  - Đảm bảo tính nhất quán giao dịch ACID giữa bảng chính sách và các vector chunks tương ứng.
- **Tài liệu tác động:** [3.architecture-design.md](file:///d:/VinUni/P-096/mydoc/3.architecture-design.md), [4.1-technical-architecture-runtime-deployment.md](file:///d:/VinUni/P-096/mydoc/4.1-technical-architecture-runtime-deployment.md), [4.2-domain-data-financial-design.md](file:///d:/VinUni/P-096/mydoc/4.2-domain-data-financial-design.md).

##### Thay đổi 9: Chuẩn hóa Bộ 6 Mục tiêu Tối ưu hóa (Canonical 6-Objective Enum - ADR-021)
- **Nội dung:** Đồng bộ hóa toàn bộ các tài liệu (từ PRD, Product Discovery, Architecture đến Code Schemas) sang đúng danh mục 6 mục tiêu chuẩn tắc:
  1. `MIN_NET_PRICE`: Giá mua Net trước thuế thấp nhất (ưu tiên chiết khấu thanh toán sớm).
  2. `MIN_INITIAL_CASH`: Số tiền mặt thanh toán ban đầu Đợt 1 thấp nhất (ưu tiên đòn bẩy vay HTLS hoặc giãn tiến độ).
  3. `MIN_MONTHLY_BURDEN`: Nghĩa vụ chi trả hàng tháng nhẹ nhất (ưu tiên thời gian vay dài, ân hạn nợ gốc).
  4. `MIN_TOTAL_CASH_OUTFLOW`: Tổng dòng tiền mặt tự chi trả đến khi nhận nhà thấp nhất.
  5. `MAX_BENEFIT_VALUE`: Tổng giá trị quà tặng, voucher, nội thất quy đổi lớn nhất.
  6. `EARLY_HANDOVER`: Ưu tiên căn hộ có tiến độ bàn giao sớm nhất để vào ở hoặc cho thuê.
- **Tài liệu tác động:** Đồng bộ trên cả 9 tài liệu kỹ thuật và kế hoạch triển khai.

##### Thay đổi 10: Thiết lập Vòng đời Quy tắc Chính sách F9 & Rollback Không Phá hủy (ADR-022)
- **Nội dung:**
  - Thêm `policy_rule_status_enum`: `DRAFT`, `APPROVED_FOR_USE`, `ACTIVE`, `RETIRED`.
  - Bảng `policy_rules` quản lý các quy tắc chiết khấu dưới dạng JSON logic có cấu trúc.
  - Trigger `trg_check_rule_publish`: Ngăn chặn kích hoạt trạng thái `ACTIVE` nếu bộ kiểm thử hồi quy chưa đạt tỷ lệ đạt chuẩn $100\%$ (`regression_test_pass_rate == 1.0`).
  - **ADR-022 (Non-Destructive Rollback):** Khi phát hiện lỗi trong vận hành, hệ thống chuyển rule mới sang `RETIRED` và kích hoạt lại rule phiên bản cũ trước đó; bảo toàn nguyên vẹn toàn bộ dữ liệu lịch sử và snapshot cũ.
- **Tài liệu tác động:** [3.architecture-design.md](file:///d:/VinUni/P-096/mydoc/3.architecture-design.md), [4.2-domain-data-financial-design.md](file:///d:/VinUni/P-096/mydoc/4.2-domain-data-financial-design.md), [4.4-api-event-tool-contracts.md](file:///d:/VinUni/P-096/mydoc/4.4-api-event-tool-contracts.md).

---

#### 2.3 Mở rộng Danh mục Hợp đồng API & Công cụ (Catalog Expansion)
- **REST Endpoints:** Mở rộng từ 16 lên **29 Canonical Endpoints** bao phủ:
  - 7 Command APIs & 6 Query/SSE APIs Báo giá chính thức (C-01).
  - 6 Pre-Sales Advisory Chat & Streaming APIs (C-09).
  - 2 Sales Lead Dossier & Conversion APIs (C-10).
  - 2 Sales Message Compliance & Send Gate APIs (C-11).
  - 3 Policy Admin Pipeline APIs (C-03 / F9).
  - 3 Benchmark & Public Key Verification APIs.
- **Agent-Visible Tools:** Mở rộng từ 7 lên **12 Tools chuẩn hóa** (bổ sung `extract_customer_constraints`, `match_inventory_catalog`, `create_lead_dossier`, `verify_claim_level_evidence`, `check_message_compliance`).
- **Lộ trình Spikes Kỹ thuật:** Mở rộng từ 4 lên **6 Implementation Spikes** tại Workstream 4.1 và Implement Plan (thêm Spike 5 về Pre-Sales Checkpointing và Spike 6 về Compliance Gate Enforcement).

---

## 3. MA TRẬN TRUY VẾT YÊU CẦU & BẢO ĐẢM TÍNH TOÀN VẸN (TRACEABILITY MATRIX)

| Tiêu chí Kiểm định Kiến trúc | Trạng thái Trước 2026-09-26 | Trạng thái Sau Cập nhật 2026-09-26 | Mức độ Tuân thủ |
| :--- | :---: | :---: | :---: |
| Phân định 11 Logic Components C-01..C-11 | Bị thiếu C-09, C-10, C-11 | Đầy đủ 11 components có sơ đồ khối & phân vai | **100% Hoàn hảo** |
| Luồng Sequence E2E Full-Funnel | Bị đứt đoạn ở đầu phễu | Chuỗi 5 phân đoạn từ Pre-Sales tới Message Send | **100% Hoàn hảo** |
| StateGraph Pre-Sales Isolation & Interrupts | Chưa có thiết kế | Hoàn chỉnh với 3 interrupts, TTL 1800s, namespace PRE_SALES | **100% Hoàn hảo** |
| Cổng Tuân thủ Thông điệp Backend Gate F8 | Chỉ có lý thuyết | Hợp đồng POST /messages/send enforced ở backend | **100% Hoàn hảo** |
| Vòng đời Trạng thái Compliance F8 | Chưa rõ ràng | 8 trạng thái, 4 tiers, hash binding SHA-256 | **100% Hoàn hảo** |
| Phân biệt Pre-Sales PDF vs Official PDF | Nhập nhằng outbox | Tách biệt On-Demand Watermark vs KMS Signed Outbox | **100% Hoàn hảo** |
| Topology Triển khai Thực tế | Vênh K8s vs Docker | Chuẩn hóa Two-Tier Profiles (MVP VPS vs Scale K8s) | **100% Hoàn hảo** |
| Vector Store SoT | Vênh Supabase vs Qdrant | Khóa PostgreSQL 16 + pgvector duy nhất cho MVP | **100% Hoàn hảo** |
| Canonical Optimization Objectives | Bất nhất 4/5/6 | Khóa 6 mục tiêu chuẩn tắc trên toàn bộ 9 tài liệu | **100% Hoàn hảo** |
| Policy Rule Extraction & Test Gate F9 | Chưa có cơ chế | Bảng policy_rules, trigger 100% pass, ADR-022 Rollback | **100% Hoàn hảo** |
| Phân công Công việc & Lộ trình Spikes | Chưa gắn Spikes | Phân chia 4 vai trò gắn với 11 components & 6 Spikes | **100% Hoàn hảo** |

---

## 4. HƯỚNG DẪN CẬP NHẬT CHO CÁC THAY ĐỔI TƯƠNG LAI

Khi có bất kỳ thay đổi nào tiếp theo trong quá trình triển khai hoặc kiểm thử mã nguồn thực tế:
1. Thêm một mục mới vào phần **2. NHẬT KÝ THAY ĐỔI LỊCH SỬ** ở đầu danh sách (theo thứ tự thời gian giảm dần).
2. Nêu rõ ngày thay đổi, phiên bản cập nhật, người phụ trách và tài liệu liên quan.
3. Tóm tắt nguyên nhân và phân tích tác động (Impact Analysis) đến các tầng: Dữ liệu (DDL), Logic điều phối (StateGraph), Hợp đồng (API/Tool Contracts) và UI.
4. Cập nhật lại Ma trận Truy vết tại Mục 3 nếu có bổ sung hoặc thay đổi phạm vi nghiệp vụ.
