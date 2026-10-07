---
trigger: manual
description: "Quy chuẩn mã nguồn và phong cách phát triển phần mềm cho Trần Chí Vĩ (Dev 1)"
---

# Quy Chuẩn Kỹ Thuật & Tác Phong Kỹ Sư Dữ Liệu (Trần Chí Vĩ - Dev 1)

Quy tắc này áp dụng tự động cho mọi phiên làm việc của AI Agent tại workspace PricePolicy AI Agent (P-096).

## 1. Định danh và vai trò thành viên
- **Thành viên:** Trần Chí Vĩ (`civi0411`)
- **Email:** `cuuvi985@gmail.com`
- **Vai trò:** Dev 1 — Chuyên trách Data Architecture, PostgreSQL 16 Schema, pgvector RAG, Database Seeding & Ingestion Pipeline.
- **Nhánh làm việc:** `TranChiVi_02968`
- **Nhánh đích khi tạo PR:** `dev` (theo quy định của Lead, tuyệt đối không PR trực tiếp vào `main`).

## 2. Tiêu chuẩn mã nguồn (Clean Enterprise Code)
- **Không dấu vết AI:** Tuyệt đối không chèn các biểu tượng cảm xúc (emoji/icon như checkmark, rocket, warning, v.v.) vào mã nguồn, tài liệu, commit message hay báo cáo.
- **Code sạch chuẩn công nghiệp:**
  - Viết docstrings và chú thích bằng phong cách kỹ sư backend thực chiến, ngắn gọn, chuẩn xác.
  - Sử dụng Type Annotations đầy đủ (`Mapped`, `mapped_column`, `AsyncSession`).
  - Đảm bảo tính tương thích kép giữa PostgreSQL (asyncpg trên Cloud) và SQLite (aiosqlite chạy test offline).
- **An toàn bảo mật:**
  - Tuyệt đối không ghi cứng chuỗi kết nối, mật khẩu hay API key vào code hoặc tài liệu.
  - File cấu hình môi trường `.env` phải luôn được bảo vệ bởi `.gitignore`.

## 3. Cổng kiểm soát chất lượng (Quality Gate)
Trước khi hoàn tất bất kỳ tác vụ nào hoặc chuẩn bị commit/push, phải đảm bảo:
1. `ruff check .` đạt 0 cảnh báo.
2. `pytest` vượt qua 100% các bài kiểm thử.
3. Không làm ảnh hưởng đến các module nghiệp vụ của thành viên khác (Pricing Engine của Duy, Web UI của Duy, Core Orchestrator của Cường).