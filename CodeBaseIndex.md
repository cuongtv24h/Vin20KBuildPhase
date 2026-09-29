# CodeBaseIndex — PricePolicy AI Agent

> **Chỉ mục chi tiết codebase**: cấu trúc tổng thể, mục đích từng file và phân định
> sở hữu theo thành viên. Cập nhật mỗi khi thêm/xóa/di chuyển file.
>
> **Dự án:** PricePolicy AI Agent (mã đề tài BDS020-06) — nền tảng bảo chứng định giá
> & quản trị chính sách bán hàng BĐS VLandFuture.
> **Cập nhật:** 2026-09-26 · **Trạng thái code:** Scaffold khung (contracts-first, chờ implement theo TD-4.x)

## Phân vai & ký hiệu sở hữu

| Ký hiệu | Thành viên | Vai trò | Components sở hữu |
|---|---|---|---|
| 🟣 | **Tạ Việt Cường** | TechLead | C-01, C-02 (co-owner), C-05, C-07, C-09 (co-owner), Hợp đồng API/Schema, Hạ tầng |
| 🟢 | **Trần Chí Ví** | DEV 1 — AI & Data | C-02 (co-owner), C-03 (F9), C-04 (F4), C-11 (F8) |
| 🟠 | **Văn Duy** | DEV 2 — Math & Core API | C-06 (Pricing Sidecar, FCS v2.6), Ranking/Validation Gate, Golden Benchmark |
| 🔵 | **Phương Đuy** | DEV 3 — Fullstack / UI | C-08, C-09 UI client (co-owner), C-10, C-11 UI |

Ký hiệu trạng thái: ⚙️ **Template** (code mẫu chạy được của AI20K, giữ/mút dần) ·
🏗️ **Scaffold** (khung + hợp đồng đã khóa, thân `NotImplementedError` chờ implement) ·
✅ **Hoàn chỉnh** (đã hoạt động thật).

> Quy ước: mọi file `__init__.py` chỉ chứa docstring mô tả khu vực + re-export —
> không liệt kê riêng trong bảng. **Sửa file ai thì người đó review** (chi tiết §5).

---

# 1. Cấu trúc tổng thể

```text
Vin20KBuildPhase/
│
├── 🟣 src/                        Backend FastAPI + LangGraph (toàn bộ Python backend)
│   ├── 🟣 contracts/              ★ Hợp đồng dùng chung: enums + DTO + error codes (KHÓA TRƯỚC)
│   ├── 🟣 agents/
│   │   ├── ⚙️ graph/state/nodes/  Code mẫu template (2 node analyze/respond) — sẽ thay bằng C-01
│   │   ├── 🟣 official_quote/     C-01: Official Quote StateGraph — 23 node N-01→N-20
│   │   ├── 🟣🔵 pre_sales/        C-09: Pre-Sales Advisory StateGraph — F1/F2/F3/F5/F6-F7
│   │   └── 🟢🟠🟣 tools/          Tool catalog: policy_search 🟢, pricing_engine 🟠, guardrails 🟣🟢
│   ├── 🟣 api/
│   │   ├── routes.py              Aggregator router (tiếp nhận 7 router con)
│   │   ├── deps.py                Idempotency-Key, RBAC, If-Match/ETag
│   │   └── endpoints/             7 router = 29 endpoint TD-4.4
│   ├── 🟢 services/rag/           C-02/C-03: ingestion → chunk → embed → time-travel retrieval → F9
│   ├── 🟢 services/evidence/      C-04: claim-level evidence linking + coordinate parser
│   ├── 🟢 services/compliance/    C-11/F8: compliance gate + POL-08 rules
│   ├── 🟠 services/pricing/       Cầu nối orchestrator↔sidecar: client UDS, 6 sanity checks, ranking
│   ├── 🟣 services/approval/      C-05: HITL SoD + Ed25519 KMS attestation
│   ├── 🟣 services/audit/         C-07: append-only hash chain + verifier
│   ├── 🟣🟢 services/snapshot/    C-02: policy snapshot freezer
│   ├── 🔵 services/dossier/       C-10: lead dossier service
│   ├── ⚙️ services/llm.py         LLM client + 2 fallback (template)
│   ├── 🟠 pricing_sidecar/        C-06: Math Engine tiến trình ĐỘC LẬP qua UDS (Decimal 28)
│   ├── 🟣 db/                     Session, models, repositories (quotes/audit/outbox), migrations
│   ├── 🟣 worker/                 Transactional Outbox consumer (PDF, SSE dispatch)
│   ├── ⚙️ main.py / config.py     App entry + Pydantic Settings (template)
│   └── ⚙️ models/schemas.py       ChatRequest/Response (template — thay bằng contracts)
│
├── 🔵 frontend/                   Next.js Multi-Role Workspace (C-08→C-11 UI) — Dev 3 init
│
├── tests/                         Mirror cấu trúc src/
│   ├── 🟣 test_contracts/         Khóa enum + models hợp đồng
│   ├── 🟣 test_agents/official_quote/  Khóa registry 23 node
│   ├── 🟣 test_api/               Khóa routing TD-4.4 + template API tests
│   ├── 🟣 test_services/          Smoke skeleton + template LLM tests
│   ├── 🟠 test_sidecar/           Khóa bất biến engine (Decimal 28, 9 đợt)
│   └── 🟠 benchmarks/             Golden scenarios kế toán Δ = 0 VNĐ
│
├── 🟢 scripts/seed_data.py        Nạp dataset mẫu (dry-run chạy được)
├── ⚙️ scripts/                    AI usage logging hooks + installer (template AI20K)
│
├── mydoc/                         Tài liệu thiết kế TD-* (nguồn chân lý kỹ thuật) + dataset/
├── docs/                          CODEBASE_MAP, architecture_diagram, guide (BTC), team_report
├── .github/workflows/ci.yml       🟣 CI: ruff + pytest
├── Dockerfile / docker-compose.yml / Makefile / requirements.txt / ruff.toml   🟣
└── JOURNAL.md / WORKLOG.md        Cả 4 thành viên ghi hằng ngày
```

---

# 2. Hạ tầng & cấu hình gốc (root)

| File | Mục đích | Owner | Trạng thái |
|---|---|---|---|
| `src/main.py` | Entry FastAPI: lifespan, CORS, mount `/api/v1`, `/health` | 🟣 TechLead | ⚙️ ✅ |
| `src/config.py` | Pydantic Settings: LLM, fallbacks, DB, vector store; mở rộng env TD-4.1 khi implement | 🟣 TechLead | ⚙️ ✅ |
| `src/models/schemas.py` | `ChatRequest`/`ChatResponse` của template — sẽ thay bằng `src/contracts/` | 🟣 TechLead | ⚙️ |
| `src/services/llm.py` | ChatOpenAI primary + 2 fallback chain | 🟣 TechLead | ⚙️ ✅ |
| `.github/workflows/ci.yml` | CI: `ruff check` + `pytest` trên push/PR | 🟣 TechLead | ⚙️ ✅ |
| `Dockerfile` | Multi-stage build backend | 🟣 TechLead | ⚙️ ✅ |
| `docker-compose.yml` | Chạy backend + healthcheck | 🟣 TechLead | ⚙️ ✅ |
| `Makefile` | `run/test/lint/format/check` + `seed-data`, `sidecar` | 🟣 TechLead | ✅ |
| `requirements.txt` | Deps: fastapi, langgraph, langchain-openai… (sqlalchemy/alembic/arq comment chờ bật) | 🟣 TechLead | ⚙️ ✅ |
| `ruff.toml` | Lint config: py311, line 120, E/F/I/N/W/UP | 🟣 TechLead | ⚙️ ✅ |
| `.env.example` | Biến môi trường mẫu (LLM, LangSmith, AI-log + nhóm biến TD-4.1: Supabase, Redis, socket sidecar, KMS) | 🟣 TechLead | ✅ |
| `JOURNAL.md` / `WORKLOG.md` | Deliverable #8/#9 — nhật ký phát triển | 👥 Cả 4 ghi, 🟣 tổng hợp | ✅ |

---

# 3. Hợp đồng dùng chung — `src/contracts/` 🟣

> **Nguyên tắc Contracts-First** (ngày 1 của ImplementPlan): Tạ Việt Cường khóa toàn bộ
> enum + DTO trước khi 4 người code song song. **Mọi thay đổi file này phải qua review
> TechLead + ghi `mydoc/baocaothaydoi.md`.** Các thành viên còn lại chỉ import, không sửa.

| File | Mục đích | Owner | Trạng thái |
|---|---|---|---|
| `enums.py` | 12 enum chuẩn hóa từ TD-4.3 (`QuoteWorkflowStatus`, `ApprovalStatus`, `PdfStatus`, `OptimizationObjective`, `ComplianceStatus`/`Tier`/`Trigger`, `SecurityEventType`, `PreSalesSessionStatus`, `LeadDossierStatus`…) — StrEnum, Triple Enum Isolation | 🟣 TechLead | 🏗️ ✅ test khóa |
| `common.py` | `TransactionContext` (đầu vào quote), `PolicyClauseEvaluation` (N-06, kèm evidence quote + chunk hash), `canonical_json_bytes` + `sha256_hex` (hash chuẩn cho N-19A/C-07) | 🟣 TechLead | 🏗️ ✅ |
| `errors.py` | `ErrorCode` + `DomainError` — mã lỗi chuẩn TD-4.4, tách khỏi trạng thái | 🟣 TechLead | 🏗️ ✅ |
| `quote.py` | DTO C-01: tên khóa (`QuoteCreateRequest`, `QuoteSnapshot`, `ConflictReport`, `ApprovalPackage`, `HumanReviewDecision`…) — định nghĩa khi implement | 🟣 TechLead | 🏗️ |
| `pricing.py` | Hợp đồng UDS orchestrator↔sidecar + `ScenarioCode` (PA-CHUDONG/NHANH/VAY) — **thiết kế cùng 🟠 Văn Duy** | 🟣 TechLead · 🟠 review | 🏗️ |
| `pre_sales.py` | DTO C-09: session, constraints, reference plan (watermark) — **Dev 3 tiêu thụ** | 🟣 TechLead · 🔵 review | 🏗️ |
| `dossier.py` | DTO C-10: lead dossier, assignment, convert-to-quote | 🟣 TechLead · 🔵 review | 🏗️ |
| `policy.py` | DTO C-02/C-03: policy document, chunk, snapshot, `StructuredRule` (F9) | 🟣 TechLead · 🟢 review | 🏗️ |
| `compliance.py` | DTO C-11/F8: `MessageVerdict`, `EvidenceAnchor`, `SendMessageCommand` | 🟣 TechLead · 🟢🔵 review | 🏗️ |
| `events.py` | Hợp đồng SSE: envelope monotonic + `Last-Event-ID` | 🟣 TechLead · 🔵 review | 🏗️ |

---

# 4. Chi tiết từng khu vực theo owner

## 4.1 🟣 Tạ Việt Cường — TechLead (Orchestrator, Governance, Hạ tầng)

### `src/agents/official_quote/` — C-01 Official Quote StateGraph (12 file)

| File | Mục đích |
|---|---|
| `state.py` | `OfficialQuoteState` (TypedDict) — trường khóa theo output N-01→N-20 |
| `graph.py` | Builder topology TD-4.3 + 3 interrupt boundary (N-08, N-16, N-18) — chờ dựng edges |
| `nodes/input_guards.py` | N-01 `validate_input` (thiếu ngày GD → `NEEDS_INPUT`), N-02 `security_guardrail_input` (prompt injection, SoD) |
| `nodes/context.py` | N-03 `load_transaction_context` — lookup căn hộ in-memory < 0.1ms từ `mydoc/dataset/canonical/units.json` |
| `nodes/policy_retrieval.py` | N-04 `retrieve_active_policies` (time-travel join), N-05 guardrail chống indirect injection |
| `nodes/evaluation.py` | N-06 thẩm định 5 trạng thái clause, N-07 phát hiện xung đột 3 cấp, N-08 Safe Abstention Gate |
| `nodes/pricing.py` | N-09 đóng gói input, N-10A tool guardrail, N-10B gọi sidecar 3 phương án, N-11 chạy 6 sanity checks |
| `nodes/ranking.py` | N-12 xếp hạng theo 6 mục tiêu + tie-break tất định |
| `nodes/explanation.py` | N-13 LLM giải trình Why/Why-not, N-14A quét rò rỉ output, N-14B kiểm chứng claim (5 điều kiện) |
| `nodes/approval.py` | N-15 gói hồ sơ HITL, N-16 interrupt chờ Quản lý, N-17 revision (version cũ `SUPERSEDED`), N-18 exception TGĐ, N-19A freeze hash, N-19B KMS ký Ed25519, N-20 commit 1 transaction |
| `nodes/__init__.py` | `NODE_REGISTRY` — khóa tên 23 node, test registry chống trôi |

### `src/services/approval/` — C-05 HITL & Ký số (3 file)

| File | Mục đích |
|---|---|
| `review.py` | Vòng đời approval intent; bất biến SoD (người tạo không tự duyệt) + chặn duyệt version stale |
| `signing.py` | Ed25519 (RFC 8032) qua KMS — private key không vào app process; `payload_fingerprint` chuẩn |

### `src/services/audit/` — C-07 Audit Trail (3 file)

| File | Mục đích |
|---|---|
| `chain.py` | Hash chain per-quote: `event_hash = SHA256(prev_hash ‖ canonical(event))`, append-only *(Spike 4 — 🟢 Trần Chí Ví hỗ trợ)* |
| `verifier.py` | Verify chuỗi: genesis đúng, anti-cyclic, hash khớp — phục vụ đối soát QR trên PDF |

### `src/services/snapshot/` — C-02 Policy Snapshot (2 file)

| File | Mục đích |
|---|---|
| `freezer.py` | Freeze snapshot chính sách tại thời điểm GD + resolve ngược theo hash *(co-owner 🟢 Trần Chí Ví)* |

### `src/api/` — API Gateway

| File | Mục đích |
|---|---|
| `routes.py` | Aggregator: include 7 router con vào `/api/v1` (giữ `/chat`, `/status` template) |
| `deps.py` | `get_idempotency_key` (chặn 400 khi thiếu — ✅ hoạt động), `get_current_principal` (RBAC/SoD, chờ), `get_if_match_etag` (412) |
| `endpoints/quotes.py` | 12 endpoint Quotes (POST create/approve/reject/revision/exception/pdf-retry, GET detail/evidence/audit/pdf) |
| `endpoints/quote_events.py` | SSE `GET /quotes/{id}/events` — monotonic Last-Event-ID |
| `endpoints/pre_sales.py` | 6 endpoint Pre-Sales sessions (co-design 🔵 Phương Đuy) |
| `endpoints/evaluation.py` | Benchmark-runs (nội dung 🟠 Văn Duy) + `/.well-known/jwks.json` công khai khóa Ed25519 |

### `src/db/` + `src/worker/` — Persistence & Outbox (9 file)

| File | Mục đích |
|---|---|
| `db/session.py` | Async engine (sqlalchemy + asyncpg — bật khi implement), chung pool với LangGraph checkpoint |
| `db/models.py` | Inventory bảng TD-4.2 (quotes, audit_events, outbox, policy_chunks pgvector…), Exclusion Constraint chống chồng lấn policy |
| `db/repositories/quotes.py` | `create_with_outbox` (quote + idempotency + outbox trong 1 transaction), `supersede_version` |
| `db/repositories/audit.py` | Repository append-only cho hash chain |
| `db/repositories/outbox.py` | Enqueue + poll pending events |
| `db/migrations/README.md` | Quy trình Alembic khi bật persistence |
| `worker/tasks.py` | `generate_quote_pdf` (chỉ version APPROVED), `dispatch_sse_events` |

### Tests nền tảng

| File | Mục đích |
|---|---|
| `tests/test_contracts/test_enums.py` | Khóa 12 enum: đủ 6 objectives, Triple Isolation, 4 tier |
| `tests/test_contracts/test_models.py` | `TransactionContext` từ chối giá trị lẻ; canonical json ổn định thứ tự key |
| `tests/test_agents/official_quote/test_nodes_registry.py` | Registry đúng 23 node N-01→N-20, mọi node async |
| `tests/test_api/test_endpoint_contracts.py` | Routing TD-4.4: thiếu Idempotency-Key → 400; chưa implement → 501 |
| `tests/test_services/test_component_skeletons.py` | Smoke các service skeleton + 6 sanity checks + fingerprint |

## 4.2 🟢 Trần Chí Ví — DEV 1 (AI & Data: RAG, Evidence, Compliance)

| File | Mục đích |
|---|---|
| `src/services/rag/ingestion.py` | **C-03**: pipeline nạp văn bản chính sách (`mydoc/dataset/policies_md/`) → parse → chunk → embed → upsert versioned |
| `src/services/rag/chunking.py` | Chunk giữ tọa độ (heading/bảng Markdown) + hash nguồn — đầu vào cho F4 |
| `src/services/rag/embeddings.py` | Embedding client pgvector — HNSW, 1536 dims |
| `src/services/rag/retrieval.py` | **C-02**: `TimeTravelPolicyRetriever` — semantic search + SQL filter ngày hiệu lực (co-owner 🟣) |
| `src/services/rag/rule_extraction.py` | **F9**: LLM trích `StructuredRule` + pre-publish regression test gate |
| `src/services/evidence/linker.py` | **C-04/F4**: gắn mỏ neo chứng cứ cấp câu, 5 kiểm chứng claim của N-14B |
| `src/services/evidence/coordinate_parser.py` | Chuẩn hóa tọa độ nguồn (doc_id, hash, page, section, quote) |
| `src/services/compliance/gate.py` | **C-11/F8**: Compliance Gate 3 checkpoint × 4 tier; `ON_FINAL_SEND` là chốt chặn bắt buộc |
| `src/services/compliance/rules.py` | Quy chuẩn phát ngôn từ POL-08: forbidden phrases + mỏ neo bắt buộc |
| `src/api/endpoints/compliance.py` | 2 endpoint F8: `POST /compliance/check-message` (live check) + `POST /messages/send` (cổng phát hành duy nhất) |
| `src/api/endpoints/policies.py` | 3 endpoint C-03/F9: extract-rules → rules/test (pre-publish gate) → publish (atomic + rollback) |
| `src/agents/tools/policy_search.py` | Tool `policy_time_travel_search` cho cả 2 StateGraph |
| `src/agents/tools/guardrails.py` | Scanner `scan_prompt_injection` / `scan_output_leakage` (khung allowlist do 🟣 dựng) |
| `scripts/seed_data.py` | Nạp dataset chuẩn tắc (canonical/policies_md/fixtures) vào DB + vector store — dry-run ✅ |

## 4.3 🟠 Văn Duy — DEV 2 (Math & Core API: Deterministic Engine, Benchmark)

| File | Mục đích |
|---|---|
| `src/pricing_sidecar/engine/calculator.py` | **C-06 lõi**: `DeterministicPricingEngine` — Decimal 28 chữ số, cấm float, mô phỏng 3 phương án FCS v2.6 *(Spike 1: < 5ms)* |
| `src/pricing_sidecar/engine/schedules.py` | Kế hoạch thanh toán: tiến độ chuẩn 9 đợt (POL-04), phương án nhanh 95%, cấn trừ cọc đợt 1 |
| `src/pricing_sidecar/engine/incentives.py` | Cơ chế ưu đãi + mutual exclusion (Hard/Conditional/Ambiguous) — không cộng dồn ưu đãi loại trừ |
| `src/pricing_sidecar/engine/reconciliation.py` | Dual Reconciliation — lệch 1 VNĐ → FAIL toàn lượt tính |
| `src/pricing_sidecar/server.py` | UDS server: stateless worker, không network |
| `src/pricing_sidecar/protocol.py` | Framing UDS (length-prefixed JSON) — chốt trong Spike 1, ghi `baocaothaydoi.md` |
| `src/pricing_sidecar/__main__.py` | `python -m src.pricing_sidecar` / `make sidecar` |
| `src/agents/tools/pricing_engine.py` | Tool `calculate_financial_plan` — LLM chỉ được tính tiền qua tool này, không tự cộng trừ |
| `src/services/pricing/client.py` | UDS client phía orchestrator (giao thức do Văn Duy định) |
| `src/services/pricing/validation.py` | 6 `SANITY_CHECKS` kế toán (khóa danh sách, N-11 thực thi) |
| `src/services/pricing/ranking.py` | Xếp hạng 6 mục tiêu + tie-break tất định (N-12) |
| `src/services/pricing/optimizer.py` | F3/F5: so sánh & tối ưu phương án tham khảo cho pre-sales |
| `tests/test_sidecar/test_engine.py` | Khóa bất biến: precision 28, 9 đợt, engine NotImplemented tới khi xong |
| `tests/benchmarks/test_golden_scenarios.py` | Golden benchmark Δ = 0 VNĐ trên fixtures thật (đang 2/15 cases — bổ sung trong Spike 1) |

## 4.4 🔵 Phương Đuy — DEV 3 (Fullstack / UI)

| File | Mục đích |
|---|---|
| `frontend/README.md` | Đặc tả 4 workspace cần dựng: Customer Chat (C-09), Sales Copilot + Composer (C-10/C-11), Manager Approval, Policy Admin; yêu cầu SSE `Last-Event-ID`, watermark, debounce 500ms |
| `frontend/` (sẽ init) | Next.js 14 + TypeScript + Tailwind — types sinh từ `src/contracts/` |
| `src/services/dossier/service.py` | **C-10**: vòng đời Lead Dossier (NEW→…→CONVERTED_TO_QUOTE), SLA countdown, 1-click convert |
| `src/api/endpoints/leads.py` | 2 endpoint Leads (list dossiers, convert-to-quote) |
| `src/agents/pre_sales/nodes/` | Co-owner 🟣: `discovery.py` (F1), `constraints.py` (F2 extract + confirm), `planning.py` (F3/F5 watermark), `handoff.py` (F6/F7 consent) |

---

# 5. Khu dùng chung & khu template

| Khu | Files | Ghi chú |
|---|---|---|
| ⚙️ Template AI20K | `src/agents/{graph,state}.py`, `nodes/example_node.py`, `tools/example_tool.py`, `src/models/schemas.py`, `tests/{conftest,test_routes,test_graph,test_llm}.py` | Code mẫu chạy được; giữ để CI xanh trong lúc scaffold — thay dần bằng C-01/C-09. Bảo trì: 🟣 |
| ⚙️ AI usage logging | `scripts/log_hook.py`, `log_manual.py`, `log_antigravity.py`, `submit_log.py`, `setup_hooks.sh/.ps1`, `setup.sh`, `_pyrun.*` + config `.claude/ .codex/ .cursor/ .gemini/ .agents/ .github/hooks/` | Của BTC template — **cả 4 thành viên cài hook ngày đầu, KHÔNG sửa nội dung** |
| 👥 Tài liệu đội | `mydoc/*` (TD-4.1→4.4, PRD, ImplementPlan, baocaothaydoi, dataset), `docs/team_report/*`, `ARCHITECTURE.md`, `docs/CODEBASE_MAP.md`, `docs/architecture_diagram.md` | Nguồn chân lý thiết kế; sửa kiến trúc phải ghi `mydoc/baocaothaydoi.md` |

---

# 6. Ma trận tổng hợp & luật chơi

| Thành viên | Component chính | Vùng code sở hữu (không ai đụng không xin) | Review bắt buộc bởi |
|---|---|---|---|
| 🟣 Tạ Việt Cường | C-01, C-05, C-07, C-09, hạ tầng | `src/contracts/`, `src/agents/official_quote/`, `src/services/{approval,audit,snapshot}/`, `src/api/`, `src/db/`, `src/worker/` | 🟢🟠 review code orchestrator |
| 🟢 Trần Chí Ví | C-02, C-03, C-04, C-11 | `src/services/{rag,evidence,compliance}/`, `src/agents/tools/policy_search.py`, `scripts/seed_data.py` | 🟣 |
| 🟠 Văn Duy | C-06, Benchmark | `src/pricing_sidecar/`, `src/services/pricing/`, `tests/{test_sidecar,benchmarks}/` | 🟣 |
| 🔵 Phương Đuy | C-08, C-09 UI, C-10, C-11 UI | `frontend/`, `src/services/dossier/`, `src/api/endpoints/leads.py`, co-own `src/agents/pre_sales/` | 🟣 |

**Co-ownership (từ ImplementPlan):**
- **C-02** Time-Travel & Snapshot: 🟣 Cường + 🟢 Chí Ví (retrieval & freezer cùng nguồn dữ liệu).
- **C-09** Pre-Sales: 🟣 Cường (StateGraph backend) + 🔵 Phương Đuy (web client + luồng hội thoại).
- **Spike 4** Hash Chain: 🟢 Chí Ví hỗ trợ 🟣 Cường.
- **Spike 1** UDS protocol: 🟠 Văn Duy chốt framing, 🟣 Cường phê duyệt trước khi 2 phía code.

**Luật chung:**
1. Thay đổi `src/contracts/` hoặc endpoint shape → review 🟣 + ghi `mydoc/baocaothaydoi.md`.
2. `make lint && make test` phải xanh trước mọi PR (CI chặn).
3. Node mới của C-01 phải đi qua `NODE_REGISTRY` + cập nhật test registry.
4. Xóa `NotImplementedError` chỉ khi có test thật thay thế.
5. Lấy dữ liệu mẫu: `make seed-data` · chạy sidecar: `make sidecar` · chạy backend: `make run`.

---

# 7. Tài liệu & tài sản phi code

## 7.1 `mydoc/` — Tài liệu thiết kế (nguồn chân lý kỹ thuật)

| Tài liệu | Nội dung | Owner bảo trì |
|---|---|---|
| `1.requirement-analysis.md` | PRD v2.3 — yêu cầu nghiệp vụ, F1→F9 | 👥 Đội (🟣 tổng hợp) |
| `2.product-discovery.md` | Product discovery & chiến lược | 👥 Đội (🟣 tổng hợp) |
| `3.architecture-design.md` | Kiến trúc tổng thể v2.2 | 🟣 Tạ Việt Cường |
| `0.1. data_generate.md` | Quy trình sinh dữ liệu mẫu | 🟢 Trần Chí Ví |
| `0.2.financial-calculation-spec.md` | **FCS v2.6** — đặc tả số học kế toán (bản chất công việc của Dev 2) | 🟠 Văn Duy |
| `4.1-technical-architecture-runtime-deployment.md` | TD-4.1: runtime, deployment topology, profiles | 🟣 Tạ Việt Cường |
| `4.2-domain-data-financial-design.md` | TD-4.2: schema DB, pgvector, ràng buộc thời gian | 🟣 + 🟢 + 🟠 (phần schema số học) |
| `4.3-agent-stategraph-workflow-design.md` | TD-4.3: 23 node N-01→N-20, enums, state models | 🟣 Tạ Việt Cường |
| `4.4-api-event-tool-contracts.md` | TD-4.4: 29 endpoints, SSE, tool contracts, bảng lỗi | 🟣 Tạ Việt Cường |
| `ImplementPlan.md` / `Implement_plan_detail.md` | Phân chia 4 thành viên, 11 components, 6 spikes, flowchart MVP | 🟣 Tạ Việt Cường |
| `CTV_ImplementPlanDetail.md` | Kế hoạch chi tiết vai trò TechLead (6 phase, 10 ngày) | 🟣 Tạ Việt Cường |
| `5.uiux-interaction-design.md` | TD-5: đặc tả tương tác UI/UX theo 4 đối tượng (vi-tương tác bám contract SSE/enum; bổ sung Composer F8, Dossier inbox, Policy Admin) | 🔵 Phương Đuy (implement) + 🟣 review |
| `5.1-sales-journey-ui.md` | TD-5.1: UI theo luồng đời thường của Sale — journey map 1 ngày, 7 interaction loops (Copilot < 60s, Revision tại chỗ, Copy-mode có audit), gap hợp đồng ADR-UX-03 | 🔵 Phương Đuy (implement) + 🟣 duyệt ADR |
| `5.2-agent-first-sales-workspace.md` | TD-5.2: mô hình "Agent là trung tâm" — Chat để chỉ huy/Panel để làm việc/Menu để duyệt; 5 mục rail, 8 pattern hội thoại, ranh giới an toàn agent | 🔵 Phương Đuy (implement) + 🟣 review |
| `frontend/prototype/sales_workspace.html` | Prototype tương tác SCR-S00 Agent-First Workspace (Rail + hội thoại Agent + Artifact Panel; demo 4 kịch bản TD-5.2) — xem: `make prototype` | 🔵 Phương Đuy |
| `frontend/prototype/sales_copilot.html` | Prototype tương tác SCR-S03 Sales Copilot (4 fixtures F8, live-check debounce 500ms, anchor popover, copy/send có audit) — `/sales_copilot.html` | 🔵 Phương Đuy |
| `phanbien.md` | Báo cáo phản biện vòng 2 — các khoảng trống cần xử lý | 🟣 Tạ Việt Cường |
| `baocaothaydoi.md` (+ `.mv`) | **CHANGELOG-ARCH** — bản ghi bắt buộc mọi thay đổi kiến trúc/contract | 🟣 Tạ Việt Cường (mọi thành viên ghi khi đổi) |
| `architecture-workflow-diagrams.html` | Sơ đồ kiến trúc + workflow dạng HTML | 🟣 Tạ Việt Cường |
| `Luu_tru/SupabaseVsQdrant.md`, `Luu_tru/UiUxRecommend.md`, `Luu_tru/new-features-integration-design.md` (TD-4.5) | Tài liệu lưu trữ — so sánh & đề xuất tích hợp F1→F8 mới | 🟢 + 🔵 tham khảo, 🟣 quyết |
| `dataset/` | Dữ liệu ground truth: `canonical/*.json` (40 căn, 10 policies, ma trận loại trừ), `policies_md/POL-01→10`, `fixtures/` (personas, golden cases, compliance messages), `showcase_documents/` | 🟢 Trần Chí Ví (data) + 🟠 Văn Duy (golden cases) |

## 7.2 `docs/` — Tài liệu repo

| File/Nhóm | Nội dung | Owner |
|---|---|---|
| `CODEBASE_MAP.md` | Bản đồ component → đường dẫn → owner (bản rút gọn của file này) | 🟣 Tạ Việt Cường |
| `architecture_diagram.md` | Deliverable #3 — architecture diagram | 🟣 Tạ Việt Cường |
| `team_report/Brief.md`, `1.requirement-analysis.md`, `2.product-discovery.md`, `Wireframe_UI_Flow.md`, `ui_mockup.html` | Bản nộp đội: brief, PRD, discovery, wireframe + mockup UI | 👥 Đội (wireframe: 🔵 Phương Đuy dẫn dắt) |
| `guide/` (10 chương + chuyên mục) | Technical Guidebook của BTC — **chỉ đọc, không sửa** (sửa phải qua team maintainer BTC) | ⚙️ BTC |

## 7.3 Deliverables Demo Day & governance

| Tài sản | Deliverable # | Owner |
|---|---|---|
| `JOURNAL.md` / `WORKLOG.md` | #8, #9 | 👥 Cả 4 ghi hằng ngày, 🟣 nhắc nhở |
| `eval/results/report.md` | #10 — evaluation evidence (metrics, RAGAS, golden benchmark) | 🟠 Văn Duy tổng hợp số liệu + 🟢 Chí Ví (RAGAS/compliance) |
| `presentation/` | #6 video demo, #7 pitch deck | 👥 Đội (🔵 Phương Đuy dựng slide) |
| `README_boilerplate.md` → `README.md` | #2 — README dự án | 🟣 Tạ Việt Cường |
| `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.agents/` rules + workflows | Governance template của BTC | ⚙️ BTC — không sửa |
| `.ai-log/` | AI usage logs (tự sinh từ hooks, gửi khi push) | ⚙️ Tự động |
