"""C-02 — Time-Travel Semantic Search (co-owner: Dev 1 + TechLead)."""


class TimeTravelPolicyRetriever:
    """Truy vấn chunk chính sách theo ngữ nghĩa + SQL filter ngày hiệu lực.

    Ràng buộc thiết kế (TD-4.2):
    - pgvector HNSW index, 1536 dims
    - luôn kèm điều kiện `effective_from <= transaction_date <= effective_to`
    - PostgreSQL Exclusion Constraint (`btree_gist`) chặn 2 policy chồng lấn
      thời gian trong cùng một phân khúc
    """

    async def search(
        self,
        query: str,
        transaction_date: str,
        project_id: str,
        top_k: int = 8,
    ) -> list[dict]:
        raise NotImplementedError("C-02: time-travel retrieval")
