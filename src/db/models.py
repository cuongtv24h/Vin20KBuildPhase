"""Inventory bảng dữ liệu cần tạo theo TD-4.2 (SQLAlchemy models khi implement).

Group Báo giá: quotes, quote_versions, quote_snapshots, approval_intents,
quote_audit_events, transactional_outbox, idempotency_records
Group Pre-Sales: pre_sales_sessions, lead_dossiers
Group Chính sách: policy_documents, policy_chunks (pgvector), policy_rules,
policy_snapshots
Group Compliance: compliance_checks, message_dispatches

Ràng buộc quan trọng: Exclusion Constraint (btree_gist) chặn chồng lấn thời
gian hiệu lực của policy trong cùng phân khúc (TD-4.2).
"""
