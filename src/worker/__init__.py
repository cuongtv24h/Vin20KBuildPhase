"""Background worker — Transactional Outbox consumer (PDF, SSE dispatch).

Chạy tách tiến trình (ARQ + Redis theo TD-4.1); bật `arq` trong requirements
khi implement. Trạng thái PDF quản lý qua enum `PdfStatus` độc lập.
"""
