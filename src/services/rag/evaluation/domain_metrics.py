class DomainMetrics:
    """
    Metric và release gate mới cho MVP PEC-RAG.
    Giữ Recall@k nhưng bổ sung:
    - Temporal Validity Precision (TVP)
    - Scope Match Precision
    - Conflict-Complete Evidence Recall (CCER)
    - Why-not Coverage (WNC)
    - Source Coordinate Exactness (SCE)
    - Critical Abstention Recall
    - Unsupported Claim Leakage
    """

    def calculate_tvp(self, retrieved_dates: list, valid_dates: list) -> float:
        """Temporal Validity Precision"""
        pass

    def calculate_ccer(self, retrieved_pairs: list, golden_pairs: list) -> float:
        """Conflict-Complete Evidence Recall"""
        pass

    def calculate_wnc(self, negative_seeds: list, golden_exclusions: list) -> float:
        """Why-not Coverage"""
        pass
