"""Xếp hạng phương án theo 6 mục tiêu tối ưu — node N-12 (Tie-Break tất định)."""

from src.contracts.enums import OptimizationObjective


def rank_scenarios(scenarios: list[dict], objective: OptimizationObjective) -> dict:
    """Sắp xếp 3 phương án theo `objective`; hòa điểm → áp tie-break rule
    từ `tiebreak_rule_id` (deterministic, cùng input luôn cùng thứ tự)."""
    raise NotImplementedError("C-06/N-12: ranking + tie-break")
