"""F4 — Gắn mỏ neo chứng cứ cấp câu vào từng claim của LLM."""


class ClaimEvidenceLinker:
    """Kiểm chứng mỗi claim số/tiền/ví có PolicyChunk nguồn tương ứng."""

    def link_claims(self, explanation: dict, policy_chunks: list[dict]) -> list[dict]:
        """Trả về `EvidenceBackedClaim[]` + cờ `UNSUPPORTED` nếu thiếu chứng cứ.

        5 kiểm chứng của N-14B: clause tồn tại, version active, tọa độ nguồn
        (doc_id, doc_hash, page, section), số tiền khớp 100% với Math Engine.
        """
        raise NotImplementedError("C-04/F4: claim evidence linking")
