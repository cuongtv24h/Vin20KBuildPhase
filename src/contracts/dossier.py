"""DTO Lead Dossier — C-10 (Dev 3 UI + TechLead flow).

Nguồn: TD-4.4 (GET /leads/dossiers, POST /leads/dossiers/{id}/convert-to-quote),
TD-4.5 (Sales Handover Dossier lifecycle).

Model cần định nghĩa khi implement:
- `LeadDossier`              — hồ sơ lead có cấu trúc bàn giao cho Sale
- `DossierAssignment`        — phân công + SLA countdown
- `ConvertToQuoteRequest`    — 1-click chuyển dossier → báo giá chính thức
"""
