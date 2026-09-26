"""Hợp đồng dùng chung toàn hệ thống (Contracts-First — nguyên tắc ngày 1 trong
`mydoc/ImplementPlan.md`).

Module này là điểm trỏ (single import point) cho Pydantic schemas + enums mà
TechLead khóa trước khi 4 thành viên code song song:

- Dev 3 (UI) dựng màn hình dựa trên DTO tại đây kèm Mock Server JSON.
- Dev 1 / Dev 2 implement service phía sau hợp đồng mà không đổi shape.
- Mọi thay đổi hợp đồng BẮT BUỘC đi qua review TechLead và ghi vào
  `mydoc/baocaothaydoi.md` (CHANGELOG-ARCH).

Nguồn tham chiếu: TD-4.3 (state models), TD-4.4 (API/event/tool contracts).
"""
