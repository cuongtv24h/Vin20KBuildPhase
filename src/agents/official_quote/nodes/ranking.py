"""Node xếp hạng phương án (N-12)."""

from src.agents.official_quote.state import OfficialQuoteState


async def rank_scenarios(state: OfficialQuoteState) -> dict:
    """N-12 — Pure (Deterministic).

    Xếp hạng 3 phương án theo `OptimizationObjective` (6 mục tiêu chuẩn tắc)
    với Tie-Break tất định. Dùng: `src.services.pricing.ranking`.
    Output: `RecommendationResult`.
    """
    raise NotImplementedError("C-01/N-12: theo TD-4.3 — scenario ranking")
