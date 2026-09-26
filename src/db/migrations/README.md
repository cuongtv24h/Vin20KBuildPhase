# DB Migrations

Dùng Alembic khi bật persistence (bật `sqlalchemy` + `alembic` trong
`requirements.txt` theo TD-4.1):

```bash
alembic init alembic          # một lần, tại repo root
alembic revision --autogenerate -m "..."
alembic upgrade head
```

Schema nguồn chân lý: `mydoc/4.2-domain-data-financial-design.md` (TD-4.2).
Mọi thay đổi schema BẮT BUỘC migration + ghi `mydoc/baocaothaydoi.md`.
