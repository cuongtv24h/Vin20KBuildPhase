# CODEBASE MAP — PricePolicy AI Agent (P-096)

> Bản đồ điều hướng toàn bộ repository cho người/dev mới tiếp cận code.
> **Phương pháp:** dựng bằng đọc trực tiếp mã nguồn (static reading) trên commit `af77de6`
> (branch `arena/d9871366-vin20kbuildphase`), không chạy test/benchmark. Mọi số liệu
> "kết quả test/độ trễ" trong README/docs là **tài liệu khai báo**, chưa được xác minh lại
> trong phiên này. Số liệu trong tài liệu này (dòng code, số endpoint, số bảng…) thì đã đếm thật.
>
> **Đối tượng đọc:** thành viên mới, người review, hoặc bất kỳ ai cần trả lời câu hỏi
> "tính năng X nằm ở file nào / luồng dữ liệu đi qua đâu".

---

## 0. TL;DR

- Đây là **nền tảng tư vấn bán hàng & báo giá đa tác tử (multi-agent)** cho bất động sản
  (Vinhomes / Masterise-style), phủ **full-funnel**: khám phá nhu cầu → hồ sơ khách → báo giá
  chính thức → phê duyệt → PDF ký số.
- **Backend Python (FastAPI)** là nơi chứa toàn bộ nghiệp vụ; `src/` có 272 file / ~47.300 dòng.
  **Frontend TypeScript** (npm workspaces) có 165 file / ~30.700 dòng, gồm 2 app (customer, internal)
  + 3 package dùng chung.
- Trục kỹ thuật chính:
  1. **Deterministic math** — toàn bộ số tiền tính bằng `Decimal` trong **pricing sidecar (C-06)**,
     không dùng LLM để tính tiền.
  2. **Evidence-first** — mọi khẳng định về chính sách phải gắn evidence bundle có nguồn
     (PEC-RAG + time-travel retrieval + abstention).
  3. **Governance** — HITL gates, SoD (separation of duties), bất biến (immutable snapshot),
     ký Ed25519 trước commit, audit hash-chain, outbox giao dịch.
- **Không có CI chạy trên branch này** (workflow chỉ trigger `main`/`develop`), và sandbox hiện
  **không cài dependencies** → muốn chạy test phải cài `requirements.txt` / `npm ci` trước.

---

## 1. Số liệu nhanh (đếm trực tiếp từ repo)

| Hạng mục | Số lượng |
|---|---|
| File được git track | 582 |
| Python | 276 file · ~49.439 dòng |
| TypeScript/TSX | 167 file · ~31.134 dòng |
| API routers (sub-router) | 15 (+ base router + pricing mock) |
| Route operation (`@router.*`) | 92 (+2 base `/chat`,`/status` +1 pricing mock +1 `/health`) |
| Bảng ORM (`__tablename__`) | 24 |
| ErrorCode trong `src/contracts/errors.py` | 23 |
| Tool của Copilot | 8 |
| Node Pre-sales graph | 11 |
| Node Official-quote graph | 23 |
| Test files | 74 |
| Hàm `def test_` | 745 |
| Endpoint defs phía frontend (`endpoints.ts`) | 75 |

> Lệch tài liệu: README ghi "498/498 pytest" và `docs/RASOAT_TONGTHE_2026-10-02.md` ghi 455 —
> số thực tế đếm được là **745 hàm test / 74 file**. Xem §11.

---

## 2. Sơ đồ luồng tổng quan

```
                    ┌──────────────────────────────────────────────────────────┐
                    │                     NGƯỜI DÙNG                            │
                    │  Customer (app :5173)      Sales/Manager/Admin (:5174)    │
                    └───────────────┬──────────────────────────┬───────────────┘
                                    │ REST + SSE               │ REST + SSE
                                    ▼                          ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│  FastAPI  src/main.py  (CorrelationIdMiddleware → CORS → DomainError handler)  │
│  routers: src/api/routes.py (aggregator) + src/api/pricing_mock.py             │
│           15 sub-router trong src/api/endpoints/*                              │
└───────┬───────────────┬────────────────┬───────────────┬───────────────┬──────┘
        │               │                │               │               │
        ▼               ▼                ▼               ▼               ▼
 ┌────────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────┐  ┌────────────┐
 │ Copilot    │  │ Pre-sales  │  │ Official     │  │ Pricing   │  │ Governance │
 │ ReAct      │  │ graph      │  │ Quote graph  │  │ sidecar   │  │ services   │
 │ src/agents │  │ 11 node    │  │ 23 node      │  │ C-06 UDS  │  │ approval/  │
 │ /copilot   │  │ 3 HITL     │  │ 3 HITL + SoD │  │ Decimal28 │  │ audit/snap │
 └─────┬──────┘  └─────┬──────┘  └──────┬───────┘  └─────┬─────┘  └─────┬──────┘
       │               │                │                │              │
       ▼               ▼                ▼                ▼              ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │  SERVICES LAYER  src/services/*                                               │
 │  rag (PEC-RAG + time-travel) · evidence · compliance · dossier · llm · tts    │
 └───────────────────────────────┬───────────────────────────────────────────────┘
                                 │ SQLAlchemy async
                                 ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │  PERSISTENCE  src/db (24 bảng ORM, repositories)                              │
 │  Dev: SQLite ./data/app.db   ·   Prod: Supabase Postgres16 + pgvector HNSW    │
 │  LangGraph checkpoint: AsyncPostgresSaver (src/orchestrator/checkpointer.py)  │
 └───────────────────────────────┬───────────────────────────────────────────────┘
                                 │ transactional outbox
                                 ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │  WORKER  src/worker/tasks.py (outbox batch) · watermark_pdf.py (reportlab+QR) │
 └───────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Cây thư mục (có chú thích)

```
Vin20KBuildPhase/
├── src/                        # Toàn bộ backend Python
│   ├── main.py                 # FastAPI app, middleware, lifespan bootstrap (145 dòng)
│   ├── config.py               # pydantic-settings Settings (114 dòng)
│   ├── api/
│   │   ├── routes.py           # Master aggregator mount 15 sub-router
│   │   ├── deps.py             # Principal, idempotency, OCC, SoD helpers
│   │   ├── pricing_mock.py     # /api/v1/pricing mock (demo không cần sidecar)
│   │   └── endpoints/          # 15 file router nghiệp vụ
│   ├── agents/
│   │   ├── copilot/            # ReAct agent + planner/verifier/critic/anchors/history…
│   │   ├── pre_sales/          # graph 11 node (discovery/constraints/planning/handoff)
│   │   ├── official_quote/     # graph 23 node (guard→retrieve→price→rank→approve)
│   │   ├── tools/              # langchain tools: guardrails, policy_search, pricing_engine
│   │   ├── graph.py            # ⚠️ template lỗi thời (import node không tồn tại)
│   │   ├── state.py
│   │   └── nodes/              # ⚠️ rỗng/không dùng
│   ├── contracts/              # enums, errors (23 ErrorCode), events (SSE), units, common
│   ├── db/
│   │   ├── models.py           # 24 bảng SQLAlchemy (623 dòng)
│   │   ├── session.py          # async engine/session factory
│   │   ├── init_db.py          # tạo schema + pgvector HNSW + btree + FTS (Postgres-only)
│   │   └── repositories/       # quote_repository, audit_repository, outbox_repository
│   ├── models/                 # Pydantic schemas + PEC contracts + rag_schemas
│   ├── orchestrator/checkpointer.py   # CheckpointManager (AsyncPostgresSaver, shared pool)
│   ├── pricing_sidecar/        # C-06: engine, contracts, validation, server, ranking, hash
│   ├── services/
│   │   ├── rag/                # ingestion → compiler → retrieval → retriever → service
│   │   ├── evidence/           # linker, verifier, closure/tdec, abstention, coordinate_parser
│   │   ├── compliance/         # gate (3 mode × 4 tier) + rules (POL-08)
│   │   ├── approval/           # review (atomic approval) + signing (Ed25519)
│   │   ├── audit/              # chain (hash-chain) + verifier
│   │   ├── snapshot/           # freezer (immutable snapshot)
│   │   ├── dossier/            # hồ sơ khách hàng
│   │   ├── pricing/            # bridge sidecar↔in-process: client, optimizer, ranking, eval
│   │   ├── llm*.py / tts*.py   # provider registry, probe, usage, secrets, TTS
│   │   └── …
│   └── worker/                 # tasks (outbox batch) + watermark_pdf (PDF + QR)
├── tests/                      # 77 file · 721 test function
│   ├── test_pricing_sidecar/   # nặng nhất (~252 test)
│   ├── test_agents/copilot/    # ~170 test
│   ├── test_api/               # ~117 test
│   ├── benchmarks/ integration/ security/
│   └── conftest.py             # SQLite in-memory override + grounding isolation
├── eval/                       # rag/ (integrity, performance, retrieval, temporal), copilot/, results/
├── frontend/                   # npm workspaces
│   ├── apps/customer/          # :5173 — public + /tu-van
│   ├── apps/internal/          # :5174 — login, /sale/*, /manager/*, /admin/*, /admin_cp
│   └── packages/{api-client,ui,mock-server}/
├── scripts/                    # seed_data, seed_canonical_inventory, run_eval, run_copilot_eval, verify_schema…
├── deploy/                     # nginx conf, pm2 ecosystem, deploy/rollback/install-git-up
├── docs/                       # guide 10 chương, team_report, RASOAT, arch diagram, UI mockup
├── dataset/fixtures/golden_scenarios.json
├── upgrade/                    # PLAN.md, CHANGELOG.md
├── requirements.txt · Dockerfile · docker-compose.yml · Makefile · run.py · ruff.toml
└── .github/workflows/ci.yml    # 3 job: python, deploy-scripts, frontend
```

---

## 4. Backend theo tầng

### 4.1 Entry point & bootstrap — `src/main.py`

| Thành phần | Vai trò |
|---|---|
| `CorrelationIdMiddleware` | Đọc `X-Correlation-ID`/`X-Request-ID` hoặc sinh `trace-<uuid12>`; gắn ContextVar + trả header về client (M-02). |
| CORS | `settings.cors_origins` (default `*`), expose `Idempotent-Replayed`, `X-Action`, `X-Correlation-ID`, `Content-Disposition`. |
| `domain_error_exception_handler` | Bắt `DomainError` → JSON `{"detail": <envelope>}` với HTTP status từ lỗi. |
| `lifespan` | ① dựng `CheckpointManager` + `AsyncPostgresSaver` nếu `USE_POSTGRES_CHECKPOINTER=true`, ngược lại `MemorySaver` (cảnh báo nếu `APP_ENV=production`); ② tạo `app.state.pre_sales_runner`; ③ `_bootstrap_database()` (`Base.metadata.create_all`, idempotent); ④ `refresh_provider_cache()` nạp LLM provider từ DB. |
| Mount | `src.api.routes.router` + `src.api.pricing_mock.router` tại `/api/v1/pricing`. |
| Health | `GET /health` và `GET /api/v1/health`. |

### 4.2 Cấu hình — `src/config.py`

`Settings` (pydantic-settings, tiền tố ENV trực tiếp):

- **App**: `app_name`, `app_env` (`development`), `cors_origins` (`*`), `database_url` (default `sqlite:///./data/app.db`).
- **Checkpoint**: `checkpoint_db_uri`, `use_postgres_checkpointer`.
- **LLM**: `llm_secret_key` (alias `LLM_SECRET_KEY`/`SECRET_KEY`), `llm_http_headers` (`app`|`browser`),
  `primary_llm_*`, `fallback1_*`, `fallback2_*` (provider/model/base_url/api_key/temperature).
- **RAG local**: `embedding_model = sentence-transformers/all-MiniLM-L6-v2` (**384 dim**), cross-encoder reranker.
- **Pricing**: `pricing_sidecar_socket` (`./data/pricing.sock`), `pricing_sidecar_host/port` (`28001`),
  `pricing_use_mock`, `pricing_fallback_to_direct` (**default true** → demo chạy engine in-process).

### 4.3 API layer

`src/api/routes.py` mount 15 sub-router; 6 router được thêm prefix `/api/v1` tại aggregator
(`llm_admin`, `tts_admin`, `tts_speak`, `settings`, `copilot`, `policies`).

| Router | Prefix | #op | Nội dung chính |
|---|---|---:|---|
| `admin_cp.py` | `/api/v1/admin` | 6 | setup-status/setup, CRUD users (⚠️ MD5 password — xem §11) |
| `catalog.py` | `/api/v1` | 8 | auth login/logout/reauth, `/public/projects`, `/units` |
| `compliance.py` | `/api/v1` | 2 | kiểm tra compliance, gate F8 |
| `copilot.py` | `/copilot` | 11 | chat, stream SSE, history, feedback, commands, quality |
| `evaluation.py` | — | 6 | eval endpoints |
| `leads.py` | `/api/v1/leads` | 11 | CRUD lead + dossier + `convert-to-quote` |
| `llm_admin.py` | `/admin/llm` | 7 | provider CRUD, test/probe, usage |
| `policies.py` | `/policies` | 3 | policy list/detail + F9 rule extraction |
| `pre_sales.py` | `/api/v1/pre-sales` | 6 | session CRUD, resume HITL, handoff |
| `quote_events.py` | `/api/v1/quotes` | 1 | SSE stream sự kiện quote |
| `quotes.py` | `/api/v1/quotes` | 14 | create/list/get/calculate/submit-review/approve/reject/revision/exception/audit-trail/pdf/… |
| `settings.py` | `/settings` | 3 | runtime settings |
| `tts_admin.py` | `/admin/tts` | 5 | provider + voice admin |
| `tts_speak.py` | `/tts` | 2 | speak/stream |
| `pricing_mock.py` | `/api/v1/pricing` | 1 | mock engine (VERIFIED-bundle gate) |

**Helper quan trọng** — `src/api/deps.py`: `Principal` (từ token/header, map role), lưu idempotency
in-memory (`_IDEMPOTENCY_STORE`) trả **409** khi payload mismatch + header `Idempotent-Replayed`,
`verify_occ` trả **412** khi `If-Match` lệch `ETag`, kiểm SoD trả **403**.

### 4.4 Contracts — `src/contracts/`

- `enums.py`: **Triple Enum Isolation** — `QuoteWorkflowStatus` (14 giá trị),
  `ApprovalStatus` (7), `PdfStatus` (7); `OptimizationObjective` (6 + alias legacy,
  ví dụ `MIN_INITIAL_OUTFLOW → MIN_INITIAL_CASH`).
- `errors.py`: 23 `ErrorCode` + `DomainError` (giữ `correlation_id` qua ContextVar) + `to_envelope()`.
- `events.py`: envelope SSE `sse-event.v1`, `{quote_id}:v{quote_version}:{event_seq:06d}` (monotonic).
- `units.py`, `common.py`: kiểu dùng chung.
- `src/models/pec_contracts.py`: `PolicyAtomType`, `PolicyEdgeType`
  (`REQUIRES/EXCLUDES/SUPERSEDES/HAS_FOOTNOTE…`), `EvidenceDecisionStatus` (`VERIFIED|ABSTAINED`),
  `RetrievalRoute` (`T0|T1|T2`).

### 4.5 Persistence — `src/db/`

**24 bảng ORM** (`models.py`, 623 dòng):

| Nhóm | Bảng |
|---|---|
| Policy / RAG | `policies`, `policy_atoms`, `policy_edges`, `policy_documents`, `policy_chunks`, `policy_rules`, `evidence_bundles`, `abstention_certificates` |
| Catalog | `projects`, `units` (có `area_m2`, `view`) |
| Pre-sales | `pre_sales_sessions`, `customer_consents`, `pre_sales_plans`, `lead_dossiers` |
| Quote | `quotes`, `quote_snapshots`, `quote_audit_events`, `transactional_outbox` |
| Compliance | `compliance_checks` |
| Admin | `users` (role), `tts_settings`, `tts_feedback`, `tts_providers`, `llm_providers` |

- `session.py`: async engine + `async_sessionmaker` (`expire_on_commit=False`); dev dùng `aiosqlite`.
- `init_db.py`: tạo schema rồi thêm **pgvector HNSW** (`m=16`, `ef_construction=64`), btree temporal,
  GIN full-text — **chỉ chạy trên Postgres** (SQLite sẽ bỏ qua/lỗi nếu gọi trực tiếp).
- `repositories/`: `quote_repository` (supersede `{quote_id}-V{n}`), `audit_repository` (append-only),
  `outbox_repository` (retry 3 → `FAILED`).

### 4.6 Services — `src/services/`

**RAG (C-02/C-03/C-04)** — `rag/`
`ingestion/` (hierarchical_parser → metadata_enricher → pipeline) · `compiler/` (atomizer, provenance)
· `retrieval/` (bi_encoder, temporal_scope_filter, dual_polarity, hybrid_fusion RRF k=60, reranker)
· `retriever/` (time_travel_retriever, pruner TIER_1_HARD/TIER_2_REDUCE_BENEFIT/TIER_3_SAFE_ABSTAIN,
evidence_binder) · `vector_store/pgvector_manager` · `evaluation/domain_metrics`.
Entry: **`rag/service.py`** (`PolicyRAGService`: `load_from_db`, `retrieve`,
`compile_and_retrieve_bundle` — TDEC hops=1, cap 25, chỉ `APPROVED_FOR_USE`).
`rag/facade.py` là bản cũ trùng chức năng — **không dùng**, xem §11.

**Evidence** — `evidence/`: `linker.py` (5 invariant → `VERIFIED/CONDITIONAL/REJECTED/UNLINKED`,
`bundle_id = EB-{sha256[:12]}`), `verification/evidence_verifier.py`, `verification/abstention.py`,
`closure/tdec.py` (1-hop closure <2 ms theo docs), `coordinate_parser.py`.

**Compliance F8** — `compliance/gate.py`: 3 chế độ (`ON_DRAFT`/`DEBOUNCE`/`FINAL_SEND`) × 4 tier
→ `ALLOW_SEND`/`WARN_*`/`BLOCK`; `rules.py` = POL-08 (4 mẫu cấm). `enforce_send()` băm sha256
chống sửa + mask số điện thoại; cổng `/messages/send` → **403 `COMPLIANCE_SEND_BLOCKED`**.

**Governance**
- `approval/review.py`: `execute_atomic_approval` — whitelist trạng thái `DRAFT/CALCULATING/READY_FOR_REVIEW/NEEDS_REVISION`,
  kiểm SoD, ghi audit + outbox `OFFICIAL_QUOTE_ISSUED` **trong cùng transaction của caller**.
- `approval/signing.py`: `KMSServerSigner` Ed25519 (RFC 8032); thứ tự khóa: tham số → `KMS_ED25519_SEED`
  → khóa ephemeral sinh trong process (⚠️ kèm cảnh báo, không dùng cho prod).
- `audit/chain.py`: `H = SHA256(prev | quote | event_type | actor | iso_ts | canonical_payload)`,
  genesis 64 ký tự `"0"`, retry `begin_nested` ×3; `audit/verifier.py` kiểm lại chuỗi.
- `snapshot/freezer.py`: chặn trùng → `IMMUTABLE_SNAPSHOT_VIOLATION`; verify hash → `TAMPER_DETECTED`.

**Pricing bridge (C-06 phía backend)** — `pricing/`: `client.py` (dual-mode sidecar→in-process),
`adapters.py` (translate `PricingInput`; `contract_date = deposit + 7 ngày`, deposit cố định 100M),
`optimizer.py`, `ranking.py`, `validation.py` (6 sanity check), `evaluation.py`.

**Khác**: `dossier/service.py` (hồ sơ khách), `llm_providers.py` + `llm_http.py` + `llm_secrets.py`
(Fernet `enc::`, **DB-first, ENV sau**), `llm_probe.py`, `llm_usage.py`/`llm_usage_callback.py`
(JSONL `data/llm_usage.jsonl`), `tts_*` (registry/provider/probe/speak).

### 4.7 Agents — `src/agents/`

| Subsystem | File chính | Đặc điểm |
|---|---|---|
| **Copilot** | `copilot/graph.py` (964) | ReAct có kiểm soát: `MAX_ITERATIONS=4`, `MAX_TOOL_CALLS_PER_TURN=4`, retry tool lỗi 1 lần; trần observation 1400 ký/tool message (`TIGHT=700` khi cạn budget), tổng `MAX_TOTAL_OBSERVATION_CHARS=6000`; mỗi tool tự clip 1800 (`tools.py`). |
| | `copilot/tools.py` (1132) | 8 tool tiếng Việt: `tra_cuu_chinh_sach`, `tra_cuu_gio_hang`, `tinh_phuong_an_thanh_toan`, `danh_gia_von_tu_co`, `kiem_tra_phat_ngon_f8`, `tra_cuu_ho_so_khach_hang`, `soan_tin_tu_van`, `soan_ho_so_de_xuat` (+ helper chung `_call_pricing_engine`); contract observation: `summary`/`citations`/`data_as_of`/`segment_check`/`bedroom_histogram`. |
| | `planner.py` / `verifier.py` / `critic.py` | Planner: thứ tự 10→60 + `split_clauses` `MAX_PLAN_STEPS=3`. Verifier: mọi số tiền/% phải xuất hiện trong Observation. Critic: `MONEY_WITHOUT_ANCHOR`/`OVER_PROMISE`/`OFFER_WITHOUT_CONDITION`. |
| | `anchors.py` | Chèn `[n]` do máy sinh (không để LLM tự bịa nguồn). |
| | `history.py` / `feedback.py` / `memory.py` / `commands.py` / `grounding.py` / `intents.py` / `reply_format.py` | Lịch sử (`data/copilot_conversations.json`, flock), feedback (`eval/results/copilot_feedback.jsonl`), slot phiên, slash commands, grounding, chuẩn hoá markdown. |
| **Pre-sales** | `pre_sales/graph.py` (300) + 4 node | 11 node, **3 HITL interrupt gate** + self-loop chống deadlock, TTL 1800s, filter injection, build plan + watermark. |
| **Official quote** | `official_quote/graph.py` (180) + 8 node | 23 node: input_guards → context → policy_retrieval → pricing → ranking → evaluation → explanation → approval; HITL `APPROVE/REQUEST_REVISION/REJECT/SUBMIT_EXCEPTION`; vòng revision `version+1`; freeze canonical JSON → ký KMS Ed25519 → commit. ⚠️ `nodes/context.py` hardcode 68.5 m² / 2BR / VAT 10% / KPBT 2%. |
| **Tools cũ** | `tools/guardrails.py` (220), `policy_search.py`, `pricing_engine.py` | Guardrail N-02/N-14A; wrapper LangChain. |

### 4.8 Pricing sidecar (C-06) — `src/pricing_sidecar/`

- Công thức: `Base_1 = P_listed − D_fixed` → `P_net = Base_1 − round(Base_1·Σrate)` →
  `P_contract = P_net + VAT 10% + KPBT 2%`.
- **Dual cap 35%/40%** → vượt thì **drop ALL** (`DUAL_CAP_EXCEEDED`).
- 6 bất biến `INV-FIN-01..06` → lỗi **422** với `field_errors[]`.
- Độ chính xác `28` chữ số, `ROUND_HALF_UP`, canonical hoá **RFC 8785 JCS** (`canonical_hash.py`).
- Ranking 6 objective, tiebreak `TB-RULE-2026-CHUDONG-V1` (CHỦ ĐỘNG < NĐ NHANH < VAY).
- Server (`server.py`) giao tiếp UDS/TCP bằng **newline-JSON**, timeout 50 ms; `__init__.py` (222)
  là API public; `validation.py` (582) là gate cứng.
- Client phía app: `src/services/pricing/client.py` — fallback `_calculate_deterministic` khi sidecar lỗi/không có.

### 4.9 Orchestrator & worker

- `orchestrator/checkpointer.py`: `CheckpointManager` chia sẻ pool theo `db_uri`; AsyncPostgresSaver
  cần **autocommit** (do `CREATE INDEX CONCURRENTLY`); thread id `presales:{tenant}:{entity}` và
  `quote:{tenant}:{entity}`.
- `worker/tasks.py`: `process_outbox_batch` → `PROCESSED`/`FAILED` (retry 3).
- `worker/watermark_pdf.py`: render PDF bằng reportlab (fallback ghi file text), QR trỏ
  `https://verify.vlandfuture.vn/quote/{id}?hash=&sig=`.

---

## 5. Luồng end-to-end chính

### 5.1 Copilot chat (customer)
`POST /api/v1/copilot/chat` (hoặc stream SSE) → `agents/copilot/graph.py` (ReAct) → planner chọn tool
→ tool gọi `services/rag` (chính sách), `catalog` (giỏ hàng/units), `services/pricing/client`
(phương án thanh toán) → verifier kiểm số liệu → critic kiểm cam kết quá mức → gắn anchor `[n]`
→ `reply_format` chuẩn hoá → trả JSON/SSE.

### 5.2 Pre-sales discovery → hồ sơ → báo giá
`POST /api/v1/pre-sales/sessions` → graph 11 node (discovery → constraints → planning → handoff),
dừng ở **3 HITL gate** (interrupt), resume qua endpoint resume → tạo `lead_dossiers`
→ `POST /api/v1/leads/{id}/convert-to-quote` để chuyển sang luồng báo giá chính thức.

### 5.3 Official quote (sales → manager)
`POST /api/v1/quotes` (idempotency-key) → `calculate` (gọi pricing) → policy retrieval + evidence
bundle → ranking/evaluation → `submit-review` → manager `approve`/`reject`/`revision`/`exception`
→ approval service: kiểm SoD → ghi audit + outbox → PDF worker ký số + QR → `GET /quotes/{id}/pdf`
và `GET /quotes/{id}/audit-trail`. SSE tiến trình qua `/quotes/{id}/events` với `Last-Event-ID`.

### 5.4 RAG “compile & retrieve bundle”
`policies` (đã `APPROVED_FOR_USE`) → `Compiler` atomize + provenance → `policy_atoms`/`policy_edges`
→ retrieve: temporal filter (SQL, time-travel) → bi-encoder + dual-polarity → RRF → rerank
→ TDEC closure (hops=1, cap 25) → `EvidenceBinder` → `evidence_bundles` (`EB-…`) → compliance gate.

### 5.5 Compliance F8 (gửi tin tư vấn)
`POST /api/v1/messages/send` → `ComplianceGateService.enforce_send` (3 mode × 4 tier, POL-08)
→ hạch toán sha256 + mask PII → `compliance_checks` → `ALLOW_SEND` hoặc **403** `COMPLIANCE_SEND_BLOCKED`.

### 5.6 Governance (ký & audit)
Freeze snapshot (bất biến) → canonical JSON (JCS) → Ed25519 sign (KMS server / seed / ephemeral)
→ commit trong 1 transaction (audit chain + outbox) → worker phát PDF/SSE → verifier có thể kiểm lại
hash-chain và chữ ký từ dữ liệu DB.

---

## 6. Frontend — `frontend/`

npm workspaces, Node 22, Vite + React + TS.

| Workspace | Cổng | Nội dung |
|---|---|---|
| `apps/customer` | 5173 | Trang public + `/tu-van` (chat tư vấn) |
| `apps/internal` | 5174 | Login; `/sale/workspace|leads|quotes|messages|policies`; `/manager/approvals[/:id]`; `/admin/policies|benchmark|copilot-quality`; `/admin_cp`. Trang lớn nhất: `SalesWorkspacePage.tsx` (~4610 dòng). |
| `packages/api-client` | — | `endpoints.ts` = **danh bạ 75 endpoint** (nguồn sự thật method+path, có `source: TD-4.4|PROPOSED` và `auth`); `client.ts`/`http.ts`; hooks theo domain (13 file); `sse.ts`, `copilotStream.ts` (fetch POST SSE kèm `Idempotency-Key`), `copilotTurn.ts` (luật kết thúc một lượt chat: thiếu `final` ⇒ tự gọi bản gom); `normalizeQuote.ts`, `errors.ts`, `devtools.ts`. |
| `packages/ui` | — | shadcn/ui + `MoneyText`, `Evidence`, `ReasoningTrace`, `markdownTables`, `speech`… |
| `packages/mock-server` | 8787 | Node mock 11 nhóm handler + engine/fixtures; có test vitest. |

Cấu hình `api-client/src/config.ts`: `API_MODE='real'`; local → `http://<host>:8000/api/v1`,
prod → `/api/v1`; timeout 10s, SSE idle 20s.

---

## 7. Dữ liệu & file runtime

| Loại | Đường dẫn / biến | Ghi chú |
|---|---|---|
| DB dev | `./data/app.db` (SQLite) | `DATABASE_URL` ghi đè |
| DB prod | Supabase Postgres 16 + pgvector | HNSW m=16, ef=64 |
| Checkpoint | `CHECKPOINT_DB_URI` + `USE_POSTGRES_CHECKPOINTER` | ngược lại dùng MemorySaver |
| Pricing sidecar | `./data/pricing.sock` hoặc `:28001` | `PRICING_FALLBACK_TO_DIRECT=true` mặc định → chạy in-process |
| Lịch sử copilot | `data/copilot_conversations.json` | env `COPILOT_HISTORY_PATH`, khoá flock |
| Feedback copilot | `eval/results/copilot_feedback.jsonl` | env `COPILOT_FEEDBACK_PATH` |
| Usage LLM | `data/llm_usage.jsonl` | phục vụ `/admin/llm/usage` |
| Catalog seed | `scripts/seed_data.py`, `seed_canonical_inventory.py` | THE_ZEN_PARK + VLANDFUTURE_SAPPHIRE, 5 unit (ZEN-A-1205 4.2B, ZEN-A-0803 2.5B…) |
| User seed | trong seed scripts | `nam.hoang` (SALE), `ha.nguyen` (MANAGER), `minh.tuan` (POLICY_ADMIN) |

---

## 8. Tests & eval

- `tests/conftest.py`: override DB sang **SQLite in-memory**, fixture cách ly grounding.
- Phân bố test function: pricing_sidecar ~252 · copilot ~170 · api ~117 · services ~51 (chưa kể 3
  subdir con) · benchmarks 44 · contracts 22 · pre_sales 12 · security 7 · integration 6 · official_quote 5.
- `eval/`: `rag/{integrity,performance,retrieval,temporal}` + `copilot/` (golden questions, sale
  scenarios) + `results/`. Runner: `scripts/run_eval.py` (⚠️ hardcode đường dẫn macOS —
  xem §11), `scripts/run_copilot_eval.py`.
- `dataset/fixtures/golden_scenarios.json` dùng cho benchmark.

**Chạy local:**
```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env
python -m src.db.init_db
uvicorn src.main:app --port 8000        # hoặc: make run
pytest tests/ -v                        # hoặc: make test
```

---

## 9. Infra, CI/CD

- `Dockerfile` + `docker-compose.yml`: pgvector/pg16, redis:7, minio, backend.
- `.github/workflows/ci.yml` (3 job):
  1. **lint-and-test** — Python 3.11, `ruff check src/ tests/`, `pytest tests/ -v` (env `APP_ENV=test`, `OPENAI_API_KEY=test-key`).
  2. **deploy-scripts** — `bash -n deploy/*.sh` + `shellcheck -S warning`.
  3. **frontend** — `npm ci`, `tsc` cho packages + apps, `oxlint`, `npm test`.
  > Trigger chỉ `main`/`develop` → **branch hiện tại không được CI chạy**.
- `deploy/`: `p096.nginx.conf`, `ecosystem.config.cjs` (pm2 `p096-backend`, uvicorn ×2 worker trên `127.0.0.1:8000`),
  `deploy.sh`/`rollback.sh`/`install-git-up.sh`.

---

## 10. Bản đồ "muốn sửa X → đọc/sửa file nào"

| Muốn thay đổi… | File/hằng số |
|---|---|
| Công thức giá, làm tròn, cap | `src/pricing_sidecar/engine.py`, `validation.py`, `contracts.py` |
| Bảng giá/khuyến mại theo dự án | `scripts/seed_data.py`, `scripts/seed_canonical_inventory.py`, bảng `units` |
| Thêm tool cho Copilot | `tools.py` (+ đăng ký `COPILOT_TOOLS`) · `intents.py` (nhánh detect) · `planner.py` (`_WORKFLOW_ORDER` + `_tool_for` + `_args_for` + nhãn) · `prompts.py` · `reply_format.py` (`_TOOL_LABELS`) · `graph.py` (`_legacy_tool_plan` cho nhánh offline) + test trong `tests/test_agents/copilot/` + kịch bản trong `eval/copilot/sale_scenarios.json` rồi sinh lại `docs/team_report/copilot_sale_scenarios.md` (`python scripts/gen_sale_scenarios_doc.py`) |
| Đổi luật kiểm chứng câu trả lời | `src/agents/copilot/verifier.py`, `critic.py`, `anchors.py` |
| Ngưỡng/rule compliance F8 | `src/services/compliance/rules.py`, `gate.py` |
| Luồng phê duyệt & SoD | `src/services/approval/review.py`, `src/api/endpoints/quotes.py`, `src/api/deps.py` |
| Chữ ký số / khoá | `src/services/approval/signing.py`, env `KMS_ED25519_SEED`, `SIGNING_KMS_URL` |
| Audit chain | `src/services/audit/chain.py` + `verifier.py` |
| Ingestion chính sách | `src/services/rag/ingestion/*`, `compiler/atomizer.py` |
| Retrieval (time-travel, rerank) | `src/services/rag/retrieval/*`, `retriever/*`, `service.py` |
| Thêm endpoint | `src/api/endpoints/<domain>.py` + `src/api/routes.py` + `frontend/packages/api-client/src/endpoints.ts` (+ mock-server) |
| Thêm bảng | `src/db/models.py` + `init_db.py` + repository tương ứng |
| Provider LLM/TTS | `src/services/llm_providers.py`, `tts_providers.py`, `src/api/endpoints/{llm_admin,tts_admin}.ts…` |
| UI Sales workspace | `frontend/apps/internal/src/features/sale/*` |
| Trang quản trị | `frontend/apps/internal/src/features/admin/*`, `admin_cp` API |

---

## 11. Nợ kỹ thuật & điểm không nhất quán (đã xác minh bằng đọc code)

| # | Vấn đề | Bằng chứng / tác động |
|---|---|---|
| 1 | **Số chiều embedding lệch tài liệu** | `config.py` dùng `all-MiniLM-L6-v2` = **384 dim**; README/ARCHITECTURE/`requirements.txt` ghi **1536 dims**. Ảnh hưởng trực tiếp cột `vector(N)` trong DB. |
| 2 | **RAG trùng lặp** | `src/services/rag/service.py` (được export/dùng) vs `rag/facade.py` (bản cũ, 202 dòng) cùng chức năng → dễ sửa nhầm file. |
| 3 | **Key lọc lệch nhau** | `customer_tier` (retrieval) vs `applicable_units` (metadata_enricher) → filter tier có thể không khớp. |
| 4 | **Module chết** | `src/agents/graph.py` import `src.agents.nodes.example_node` (không tồn tại) nhưng vẫn được import bởi `routes.py` cho `/chat`, `/status`; `src/agents/tools/catalog_tools.py` **0 byte**. |
| 5 | **Hash mật khẩu yếu** | `src/api/endpoints/admin_cp.py` dùng **MD5** cho mật khẩu user. |
| 6 | **Fallback dev nguy hiểm nếu lên prod** | Khóa Ed25519 ephemeral trong process; secret Fernet mặc định; pricing fallback in-process. |
| 7 | **Eval không chạy được ngoài máy tác giả** | `scripts/run_eval.py` hardcode `/Users/mac/AITC/PROJECT/report/...`; cần `EVAL_DATASET_PATH`/`EVAL_POLICIES_DIR`/`EVAL_CANONICAL_DIR`. |
| 8 | **`init_db.py` không chạy được trên SQLite** | DDL pgvector/HNSW/FTS chỉ dành Postgres; nếu gọi trên dev SQLite sẽ lỗi. |
| 9 | **Hardcode nghiệp vụ trong graph** | `official_quote/nodes/context.py` cố định 68.5 m² / 2BR / VAT 10% / KPBT 2%. |
| 10 | **Lệch số test** | README 498 · RASOAT 455 · thực tế **745** hàm `def test_` (pytest gom **778** test, gồm cả tham số hoá). |
| 11 | **CI không phủ branch làm việc** | Workflow chỉ chạy `main`/`develop`; branch `arena/*` không có check. |
| 12 | **Endpoint frontend đặt tên khác backend** | Nhiều mục `PROPOSED` trong `endpoints.ts` (auth login, admin users, `/messages/*`) — cần đối chiếu với router thật khi tích hợp. |

---

## 12. Thuật ngữ & mã tham chiếu

| Mã / thuật ngữ | Nghĩa |
|---|---|
| **C-01…C-11** | Mã component trong kế hoạch dự án (C-06 = pricing sidecar, C-02/03/04 = RAG, C-05 = HITL/ký, C-09 = pre-sales, C-10/11 = …). |
| **F1–F8** | Chặng chức năng full-funnel: F1–F5 pre-sales discovery; F6–F8 báo giá chính thức; F8 = compliance gửi tin. |
| **PEC-RAG** | Pipeline bằng chứng chính sách: parse → atom → edges → retrieve → evidence bundle. |
| **TDEC** | Temporal & Dependency Evidence Closure — đóng bao 1-hop trên `policy_edges`, cap 25. |
| **Time-travel retrieval** | Lọc theo hiệu lực tại thời điểm (`TemporalScopeFilter`, SQL-first) → route T0/T1/T2. |
| **Evidence bundle** | `EB-{sha256[:12]}`, trạng thái `VERIFIED/CONDITIONAL/REJECTED/UNLINKED`. |
| **Abstention** | Nếu không đủ bằng chứng → `ABSTAINED` thay vì bịa. |
| **3-checkpoint gate** | ON_DRAFT / DEBOUNCE / FINAL_SEND. |
| **4-tier compliance** | SUPPORTED / CONDITIONAL / UNSUPPORTED / PROHIBITED → ALLOW/WARN/BLOCK. |
| **SOD** | Separation of Duties — người tạo báo giá ≠ người phê duyệt (`chk_quote_sod`). |
| **OCC / ETag / If-Match** | Optimistic concurrency; lệch → 412. |
| **Idempotency-Key** | Chống tạo trùng; replay → header `Idempotent-Replayed`; payload khác → 409. |
| **Outbox** | `transactional_outbox` — phát PDF/SSE tin cậy sau commit. |
| **HITL** | Human-in-the-loop interrupt trong LangGraph. |
| **INV-RT-04 / INV-FIN-01..06** | Mã bất biến runtime / tài chính. |
| **N-02, N-14A** | Guardrail chống prompt-injection & nội dung cấm. |
| **TB-RULE-2026-CHUDONG-V1** | Quy tắc tiebreak xếp hạng phương án. |

---

## 13. Quy ước code

- **Ngôn ngữ**: docstring/log/comment tiếng Việt; tên hàm/biến tiếng Anh (`snake_case` Python,
  `camelCase` TS).
- **Lỗi**: luôn ném `DomainError` với `ErrorCode` + `correlation_id`; API trả envelope
  `{"detail": {...}}`; HTTP status chuẩn hoá (403 SoD/compliance, 409 idempotency, 412 OCC, 422 invariants).
- **Enum**: tách biệt theo “Triple Enum Isolation”, có alias legacy cho giá trị cũ.
- **Tiền**: `Decimal` (không bao giờ dùng `float` trong engine); JSON canonical JCS khi băm/ký.
- **Router**: mỗi domain 1 file trong `src/api/endpoints/`; frontend khai báo endpoint mới trong
  `endpoints.ts` (đây là nguồn sự thật; mock-server dùng chính bảng này).
- **Test**: đặt theo tầng (`tests/test_<layer>/...`), dùng fixture ở `conftest.py`, không gọi mạng thật.
- **Ruff**: `ruff.toml` ở root; CI chạy `ruff check src/ tests/`.

---

*Tạo: 2026-10-07 · Người dựng: phân tích tĩnh toàn repo · Mọi phát hiện ở §11 nên được xác minh lại
bằng cách chạy test sau khi cài dependencies trước khi sửa.*
