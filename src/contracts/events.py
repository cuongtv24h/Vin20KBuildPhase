"""Hợp đồng sự kiện SSE — dùng chung cho Official Quote & Pre-Sales stream.

Nguồn: TD-4.4 endpoint 3 (SSE Stream Hoàn chỉnh).

Yêu cầu khóa của hợp đồng:
- `id` tăng đơn điệu (monotonic) — client reconnect gửi `Last-Event-ID`
- envelope: {event, id, data, retry}
- sự kiện trạng thái phải map 1-1 với QuoteWorkflowStatus (không tự chế status)

Model cần định nghĩa khi implement:
- `SSEEventEnvelope`
- `QuoteProgressEvent`       — tiến trình suy luận agent cho UI stream
"""
