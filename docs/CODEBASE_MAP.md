# Bản đồ Codebase — PricePolicy AI Agent

> Ánh xạ **11 Logic Components (C-01 → C-11)** và **6 Implementation Spikes**
> từ `mydoc/ImplementPlan.md` onto cấu trúc thư mục thực tế. Đây là tài liệu
> định vị code — mỗi khi tạo/thêm module, cập nhật bảng dưới.

## 1. Nguyên tắc tổ chức (tại sao giữ layout template)

Template AI20K khóa sẵn CI/Docker/Makefile quanh layout `src/`:

- CI: `ruff check src/ tests/` + `pytest` (`.github/workflows/ci.yml`)
- Chạy: `uvicorn src.main:app` → `make run`
- Docker: `Dockerfile` copy `src/`

Do đó các phân vùng `/backend/...` trong `mydoc/Implement_plan_detail.md`
được ánh xạ vào `src/` như bảng dưới — **giữ nguyên ý nghĩa phân vùngowner**,
chỉ đổi gốc đường dẫn. `frontend/` nằm ở repo root vì là app Next.js độc lập.

## 2. Ma trận Component → Đường dẫn → Owner

| Component | Nội dung | Đường dẫn | Owner | Thiết kế |
|---|---|---|---|---|
| **Contracts** | Enums + DTO dùng chung (khóa trước khi code song song) | `src/contracts/` | TechLead | TD-4.3, TD-4.4 |
| **C-01** | Official Quote StateGraph (23 node N-01→N-20, 3 interrupt) | `src/agents/official_quote/` | TechLead | TD-4.3 |
| **C-02** | Time-Travel & Policy Snapshot Engine | `src/services/rag/retrieval.py`, `src/services/snapshot/` | TechLead + Dev 1 | TD-4.2 |
| **C-03** | Policy Registry & Ingestion (F9 rule extraction) | `src/services/rag/` | Dev 1 | TD-4.2, TD-4.4 |
| **C-04** | Claim-Level Evidence Linking (F4) | `src/services/evidence/` | Dev 1 | TD-4.3 (N-06/N-14B) |
| **C-05** | HITL Review + Ed25519 KMS Attestation | `src/services/approval/` | TechLead | TD-4.3 (N-16→N-19B) |
| **C-06** | Deterministic Pricing Engine sidecar (FCS v2.6) | `src/pricing_sidecar/` | Dev 2 | `mydoc/0.2.financial-calculation-spec.md` |
| **C-07** | Append-Only Audit Trail (hash chain) | `src/services/audit/` | TechLead | TD-4.3 (N-20) |
| **C-08** | Next.js Multi-Role Workspace UI | `frontend/` | Dev 3 | `docs/team_report/Wireframe_UI_Flow.md` |
| **C-09** | Pre-Sales Advisory StateGraph (F1/F2/F3/F5) | `src/agents/pre_sales/` | TechLead + Dev 3 | TD-4.3, TD-4.5 |
| **C-10** | Lead Dossier handover (F6/F7) | `src/services/dossier/` + `src/api/endpoints/leads.py` | Dev 3 | TD-4.4, TD-4.5 |
| **C-11** | Message Compliance Gate (F8, 3 checkpoint × 4 tier) | `src/services/compliance/` + `src/api/endpoints/compliance.py` | Dev 1 | TD-4.4, POL-08 |

Spikes: S1 → `src/pricing_sidecar/engine/` (+ `tests/benchmarks/`); S2 →
checkpoint trong `src/agents/official_quote/graph.py`; S3 → `src/services/approval/signing.py`;
S4 → `src/services/audit/`; S5 → `src/agents/pre_sales/graph.py` (TTL);
S6 → `src/services/compliance/gate.py` + endpoint `/messages/send`.

## 3. Ánh xạ từ Implement_plan_detail.md

| Kế hoạch phân vùng | Thư mục thực tế |
|---|---|
| `/backend/orchestrator/` | `src/agents/` (+ `src/contracts/`) |
| `/backend/services/rag/` | `src/services/rag/`, `src/services/evidence/`, `src/services/compliance/` |
| `/backend/pricing_sidecar/` | `src/pricing_sidecar/` |
| `/tests/benchmarks/` | `tests/benchmarks/` |
| `/frontend/` | `frontend/` (Next.js, do Dev 3 init) |
| `/backend/contracts/` | `src/contracts/` |

## 4. Tầng đỡ dùng chung

| Thư mục | Vai trò |
|---|---|
| `src/api/endpoints/` | 7 router bám 29 endpoint TD-4.4 (`quotes`, `quote_events`, `pre_sales`, `leads`, `compliance`, `policies`, `evaluation`) — aggregator `src/api/routes.py` |
| `src/api/deps.py` | Idempotency-Key, If-Match/ETag, principal/RBAC |
| `src/db/` | Session + models + repositories (quotes/audit/outbox); migration ở `src/db/migrations/` |
| `src/worker/` | Transactional Outbox consumer (PDF, SSE dispatch) |
| `src/services/llm.py` | LLM client + fallback (giữ từ template) |
| `src/agents/tools/` | Tool catalog: `policy_time_travel_search`, `calculate_financial_plan`, guardrails |

## 5. Dữ liệu & seed

- Nguồn chuẩn tắc: `mydoc/dataset/` (canonical JSON, policies_md, fixtures)
- Nạp thử: `make seed-data` (dry-run) — script `scripts/seed_data.py`
- `data/` là thư mục runtime (gitignored): sqlite dev, chroma, socket sidecar

## 6. Test map (mirror cấu trúc src)

| Test | Khóa điều gì |
|---|---|
| `tests/test_contracts/` | Enum Triple Isolation, 6 objectives, TransactionContext, canonical json |
| `tests/test_agents/official_quote/` | Registry đúng 23 node N-01→N-20, node async |
| `tests/test_api/test_endpoint_contracts.py` | Routing TD-4.4 + Idempotency-Key 400 + 501 |
| `tests/test_services/` | Skeleton services + 6 sanity checks + fingerprint |
| `tests/test_sidecar/` | Decimal 28, 9 đợt, engine NotImplemented |
| `tests/benchmarks/` | Bất biến kế toán golden cases Δ = 0 VNĐ |

## 7. Quy ước làm việc

1. **Contracts-First**: sửa `src/contracts/` phải qua review TechLead + ghi
   `mydoc/baocaothaydoi.md` (schema CHANGELOG trong chính file đó).
2. **Owner review**: bảng ownership mục 2 — PR chạm vùng ai thì người đó review.
3. **Định nghĩa "done" cho scaffold**: test NotImplemented → test thật khi
   implement; không bỏ `raise NotImplementedError` sau khi feature ship.
4. **CI xanh là luật**: `make lint && make test` phải pass trước mọi PR.
