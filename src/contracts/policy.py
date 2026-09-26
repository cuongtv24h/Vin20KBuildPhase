"""DTO kho chính sách & snapshot — C-02/C-03 (Dev 1 + TechLead).

Nguồn: TD-4.2 (schema pgvector, time-travel), TD-4.4 (policy endpoints, F9).

Model cần định nghĩa khi implement:
- `PolicyDocument`           — metadata văn bản (version, hiệu lực, scope)
- `PolicyChunk`              — chunk ngữ nghĩa kèm tọa độ + hash nguồn
- `PolicySnapshot`           — bản chụp chính sách đóng băng tại thời điểm GD
- `StructuredRule`           — quy tắc có cấu trúc F9 (điều kiện/loại trừ/mức)
- `PrePublishTestReport`     — kết quả regression test trước khi publish
"""
