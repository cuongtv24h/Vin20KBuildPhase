"""Cơ chế ưu đãi + loại trừ: chiết khấu, HTLS 0%, quà tặng, tri ân.

Áp ma trận `mutual_exclusions` (Hard / Conditional / Ambiguous) — nguồn:
`mydoc/dataset/canonical/mutual_exclusions.json`. Quy tắc vàng: ưu đãi loại
trừ lẫn nhau KHÔNG được cộng dồn (VD: chọn HTLS 0% thì mất chiết khấu trả nhanh).
"""


def apply_incentives(scenario_code: str, selected_policy_ids: list[str], exclusions: list[dict]) -> dict:
    """Trả về danh sách ưu đãi được áp dụng + danh sách bị loại (kèm lý do
    `exclusion_rule_id`) — đầu vào cho giải trình Why-not."""
    raise NotImplementedError("C-06: incentive engine + mutual exclusion")
