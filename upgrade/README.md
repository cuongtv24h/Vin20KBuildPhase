# Thư mục `upgrade/` — Nhật ký & kế hoạch nâng cấp

> ⚠️ **Bản ghi chính thức đã chuyển sang [`docs/team_report/upgrade_new.md`](../docs/team_report/upgrade_new.md)**
> theo yêu cầu mới. Các file dưới đây giữ nguyên làm lịch sử soạn thảo; khi có khác biệt,
> `docs/team_report/upgrade_new.md` là bản đúng.

Thư mục này là **nơi lưu toàn bộ thay đổi của đợt nâng cấp** theo yêu cầu: mọi việc đã làm,
đang làm, còn lại, kèm bằng chứng chạy thật. Code vẫn nằm ở đúng vị trí chuẩn của repo
(`src/`, `frontend/`, `tests/`, `eval/`…); thư mục này là **bản đồ + biên bản** để không thất lạc.

| File | Nội dung |
| :--- | :--- |
| `PLAN.md` | Kế hoạch ưu tiên P0/P1/P2, phạm vi, tiêu chí nghiệm thu |
| `CHANGELOG.md` | Nhật ký từng thay đổi: file nào, vì sao, bằng chứng |
| `README.md` | File này — chỉ mục |

## Trạng thái tổng

| Hạng mục | Trạng thái |
| :--- | :--- |
| A. Copilot thông minh hơn (planner, memory, verifier, tool) | ✅ xong |
| B. Eval harness cho Copilot (đo được độ thông minh) | ✅ xong |
| C. UI/UX P0 (bỏ tiến trình giả, citation thật, lỗi/retry) | ✅ xong |
| D. UI/UX P1 (slash palette, context chips, nudge/undo thật) | ✅ xong |
| E. CI + typecheck package dùng chung | ✅ xong |
| F. Tài liệu, số liệu, README | ✅ xong |

## Số liệu kiểm chứng cuối đợt (chạy thật, 2026-10-02)

| Lệnh | Kết quả |
| :--- | :--- |
| `pytest tests/ -q` | **479 passed** |
| `ruff check src/ tests/` | sạch |
| `scripts/run_copilot_eval.py` | tool 1.00 · citation 1.00 · hallucination 0.00 · p95 4 ms |
| `npx tsc -p packages/tsconfig.json` | exit 0 (trước: 8 lỗi) |
| `npx tsc -b apps/internal apps/customer` | exit 0 |
| `npm test` | 22/22 |
| `npx oxlint` | 0 error · 125 warning (trước: 151) |
| `npm run build` | build Vite thành công |

Chi tiết từng thay đổi: `CHANGELOG.md`. Việc còn lại (chưa làm, có lý do): `CHANGELOG.md` §"Còn lại / chưa làm".
