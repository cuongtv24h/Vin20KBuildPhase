# 🎬 DEMO RUNBOOK — PricePolicy AI Agent
## Sổ tay Diễn tập Demo (Phase 5 — TASK-P5-04)

**Phiên bản:** 1.2 · **Cập nhật:** 2026-09-27 · **Sở hữu:** TechLead (cuongtv_02560)

Tài liệu hướng dẫn diễn tập demo toàn bộ 5 chặng full-funnel, 5 kịch bản lỗi biên
và quy trình reset môi trường. Toàn bộ demo chạy **offline 100%** (SQLite +
MemorySaver + PricingClient fallback Decimal 28) — không cần OpenAI key, không cần
Postgres, không cần sidecar UDS.

---

## 1. Chuẩn bị môi trường (5 phút trước giờ G)

```bash
# 1. Cài dependencies (Python 3.11/3.12)
py -3 -m pip install -r requirements.txt

# 2. Reset môi trường demo về trạng thái tinh khôi (< 15 giây)
bash scripts/demo_reset.sh

# 3. Kiểm tra sức khỏe bộ test trước khi diễn tập
py -3 -m pytest tests/ -q --no-header
# Kỳ vọng: 477 passed (đã gồm 34 test Copilot + eval harness; xem README §6)
```

---

## 2. Diễn tập Full-Funnel 5 chặng (TASK-P5-01)

Chạy bộ test E2E:

```bash
py -3 -m pytest tests/integration/test_full_funnel_e2e.py -v
```

| Chặng | Nội dung | Test xác minh |
|---|---|---|
| **1** | Pre-Sales chat: init → thu thập ràng buộc → xác nhận → tính 3 kịch bản → plan watermark | `test_leg_1_2_presales_to_dossier` |
| **2** | Handoff: consent PII → LeadDossier NEW, SLA 15 phút | `test_leg_1_2_presales_to_dossier` |
| **3** | Official Quote 23 nodes → READY_FOR_REVIEW (HITL N-16) | `test_leg_3_official_quote_to_ready_for_review` |
| **4** | Manager APPROVE → N-19A freeze hash → N-19B KMS Ed25519 → N-20 commit APPROVED | `test_leg_4_kms_attestation_and_commit`, `test_leg_4b_revision_loop_bumps_version` |
| **5** | F8 Send Gate: tin có dẫn chứng gửi OK; cam kết sinh lời bị chặn 403 | `test_leg_5_f8_gate_allows_compliant_and_blocks_violation` |

**Điểm nhấn trình bày khi demo:**
- Kịch bản `PA-NHANH` được xếp hạng 1 cho mục tiêu `MIN_NET_PRICE` — nhấn mạnh 6 Objectives ADR-021.
- Watermark `BẢN ƯỚC TÍNH THAM KHẢO TIỀN BÁN HÀNG - KHÔNG PHẢI BÁO GIÁ CHÍNH THỨC` luôn hiện trên bản Pre-Sales — Invariant #2.
- Chữ ký Ed25519 verify thành công bằng public key trong state — Invariant #1 chuẩn RFC 8032.

---

## 3. Diễn tập 5 kịch bản lỗi biên (TASK-P5-02)

```bash
py -3 -m pytest tests/security/test_failure_modes.py -v
```

| Mã | Kịch bản | Hành vi kỳ vọng | Test |
|---|---|---|---|
| **FAIL-01** | Sidecar trả dữ liệu hỏng / crash giữa lúc tính | N-11 Sanity bắt lỗi → `CALCULATION_FAILED`, không sập server; hard-crash raise `CALCULATION_ENGINE_ERROR` có cấu trúc | `test_fail_01_*` |
| **FAIL-02** | DB ngắt ngay sau khi KMS ký | Atomic Commit-Discard: rollback → không chữ ký mồ côi, không outbox event | `test_fail_02_db_crash_after_kms_sign_discards_orphan_signature` |
| **FAIL-03** | Chính sách hết hạn mid-flight | N-05 abstain → `ABSTAINED` + lý do, không tính giá, không commit | `test_fail_03_policy_expired_midflight_abstains` |
| **FAIL-04** | 2 manager cùng thao tác 1 version | OCC: người cầm version cũ nhận `VERSION_CONFLICT` (412 ở tầng API) | `test_fail_04_stale_version_conflict_on_concurrent_approval` |
| **FAIL-05** | Bypass cổng gửi F8 | `COMPLIANCE_SEND_BLOCKED` (403) cho cả 3 đường: chưa thẩm định / hash lệch / nội dung cấm | `test_fail_05_f8_gate_blocks_all_bypass_paths` |

---

## 4. Reset demo giữa các lượt diễn tập

```bash
bash scripts/demo_reset.sh
```

Script thực hiện 5 bước (tổng thời gian < 15 giây):
1. Kill uvicorn của dự án (nếu đang chạy).
2. Drop & recreate schema PostgreSQL demo (nếu psql khả dụng).
3. Xóa SQLite `./data/app.db` + journal/WAL.
4. Xóa PDF tham khảo cũ (`data/pre_sales_pdfs`, `data/test_pdfs`).
5. Tái tạo schema 14 bảng qua SQLAlchemy `Base.metadata.create_all`.

---

## 5. Quy ước trình diễn cho người điều phối

1. **Mở đầu:** nêu bối cảnh Zero-Trust — "LLM không tự tính tiền; mọi claim phải có dẫn chứng".
2. **Chặng 1-2 (Pre-Sales):** nhấn 3 interrupt HITL khách hàng bấm xác nhận — phiên TTL 30 phút.
3. **Chặng 3-4 (Official Quote):** dừng màn hình ở N-16 cho khán giả thấy HITL quản lý; SoD chặn creator tự duyệt chính mình (test `test_sod_blocks_creator_self_approval`).
4. **Chặng 5 (F8):** gõ trực tiếp tin "Cam kết sinh lời 20%" để khán giả thấy chặn đỏ 403.
5. **Kết:** chạy `bash scripts/demo_reset.sh` live để chứng minh reset < 15s.

---

## 6. Khắc phục sự cố nhanh

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `ModuleNotFoundError: cryptography` | Thiếu dependency | `py -3 -m pip install cryptography psycopg[binary,pool] langgraph-checkpoint-postgres` |
| Server lỗi "psycopg cannot use the 'ProactorEventLoop'" | Chạy `uvicorn src.main:app` trực tiếp trên Windows | Chạy bằng `py -3 run.py` (tự đặt WindowsSelectorEventLoopPolicy) |
| Lỗi `CREATE INDEX CONCURRENTLY cannot run inside a transaction block` | Pool checkpointer không autocommit | Đã fix trong CheckpointManager (pool `autocommit=True`); nếu tự dựng pool phải đặt `kwargs={"autocommit": True}` |
| Test API fail vì port chiếm | Server cũ còn chạy | `bash scripts/demo_reset.sh` (bước 1 tự kill) |
| LangGraph warning "unregistered type" | Enum trong checkpoint | Vô hại với demo; đặt `LANGGRAPH_STRICT_MSGPACK=false` để im warning |
| Pricing trả số lạ | Sidecar UDS đang bật với dữ liệu cũ | Đặt `PRICING_USE_MOCK=true` hoặc xóa `./data/pricing.sock` |

---

*Tài liệu thuộc gói bàn giao Phase 5 — mọi thay đổi phải ghi log vào `mydoc/cuongtv_02560.md`.*

---

## 7. Chế độ Persistent (tuỳ chọn — checkpoint Postgres thật)

Demo mặc định chạy offline (MemorySaver). Nếu muốn diễn tập thêm kịch bản
"sập server giữa phiên → resume không mất state" (AC-WF-01 / INV-RT-04):

```bash
# Trong .env:
#   USE_POSTGRES_CHECKPOINTER=true
#   CHECKPOINT_DB_URI=postgresql://<user>:<pass>@<host>/<db>

py -3 run.py
# Log kỳ vọng: "Checkpointing: AsyncPostgresSaver (persistent) enabled"

# Đối soát schema models.py vs DB (read-only, không sửa gì):
py -3 scripts/verify_schema.py
# Kỳ vọng: "OK: 14 bang khop hoan toan ... 0 lech."
```

Đã kiểm chứng: graph tối giản ghi checkpoint → đọc lại bằng pool/saver mới
hoàn toàn (mô phỏng restart process) → dữ liệu nguyên vẹn; phiên Pre-Sales
chạy end-to-end trên checkpointer Postgres thật qua lifespan của app.
