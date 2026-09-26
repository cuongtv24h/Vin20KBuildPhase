"""DTO Compliance Gate — C-11 / F8 (Dev 1 + Dev 3 UI).

Nguồn: TD-4.4 endpoint 7/8 (check-message, messages/send), POL-08 (phát ngôn).

Model cần định nghĩa khi implement:
- `MessageCheckRequest`      — nội dung tin nhắn + ngữ cảnh quote/lead
- `MessageVerdict`           — tier (4 tầng) + danh sách vi phạm + evidence anchor
- `EvidenceAnchor`           — mỏ neo [1], [2] trỏ về PolicyChunk
- `SendMessageCommand`       — yêu cầu gửi qua cổng backend có kiểm soát
- `DispatchReceipt`          — biên lai gửi (dispatch_id) sau khi qua gate
"""
