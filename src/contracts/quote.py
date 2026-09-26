"""DTO báo giá chính thức — C-01 (TechLead).

Các model cần định nghĩa khi implement (tên khóa theo TD-4.3/TD-4.4):
- `QuoteCreateRequest`        — payload `POST /api/v1/quotes` (kèm TransactionContext)
- `QuoteSnapshot`             — bản chụp bất biến của version báo giá
- `ConflictReport`            — kết quả N-07 (xung đột 3 cấp + precedence rule)
- `PricingScenarioSummary`    — 1 dòng trong bảng đối đầu 3 phương án
- `RecommendationResult`      — kết quả N-12 (objective_matched + tie-break)
- `EvidenceBackedClaim`       — claim kèm tọa độ nguồn (F4)
- `DualExplanation`           — Why / Why-not (N-13)
- `ApprovalPackage`           — hồ sơ N-15 đưa vào HITL
- `HumanReviewDecision`       — output N-16 (approve/reject/revision/exception)
- `ExceptionApprovalRecord`   — chứng từ ủy quyền TGĐ (N-18)

QUAN TRỊ: đổi shape ở đây phải qua review TechLead + ghi `mydoc/baocaothaydoi.md`.
"""
