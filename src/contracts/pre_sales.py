"""DTO phiên Pre-Sales — C-09 (TechLead + Dev 3).

Nguồn: TD-4.3 (PreSalesSession), TD-4.4 endpoint 5/6, TD-4.5 (new features).

Model cần định nghĩa khi implement:
- `PreSalesSessionCreate`    — mở phiên chat F1
- `CustomerMessage`          — tin nhắn khách trong phiên
- `FinancialConstraints`     — ràng buộc tài chính chuẩn hóa (F2)
- `ReferencePlan`            — phương án tham khảo F3/F5 (watermark, KHÔNG phải báo giá)
- `ConsentHandoffRequest`    — F6/F7 đồng ý bàn giao → Lead Dossier
- `PreSalesSafetyBoundary`   — nhãn NOT AN OFFICIAL QUOTE bắt buộc (INV-RT-09)
"""
