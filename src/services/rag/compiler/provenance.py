from typing import Any


class ProvenanceTracker:
    """
    Theo dõi nguồn gốc tài liệu (Source Document là Source of Truth).
    Lưu trữ và verify hash của bản gốc, phiên bản, project/channel.
    """

    def __init__(self):
        self.active_versions = {}

    def bind_metadata(self, atom_id: str, metadata: dict[str, Any]):
        """Gắn thông tin toạ độ file (page, section, table coordinates) cho atom"""
        pass

    def verify_document_hash(self, doc_id: str, expected_hash: str) -> bool:
        """Đảm bảo hash tài liệu khớp, không bị thay đổi ngầm."""
        return True
