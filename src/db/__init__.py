"""Persistence layer — Supabase PostgreSQL 16 (TD-4.2 schema).

Quy ước vùng code này:
- Truy cập DB chỉ qua repositories (không query rải trong node/service)
- Ghi nhiều bảng bắt buộc trong MỘT transaction (N-20 atomic commit)
- `sqlalchemy[asyncio]` + `asyncpg` sẽ bổ sung vào requirements.txt khi bật
  (hiện đang comment trong template — bật đúng lúc implement C-02/C-07)
"""
