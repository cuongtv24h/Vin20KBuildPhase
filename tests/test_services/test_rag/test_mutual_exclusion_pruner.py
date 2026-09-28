"""Unit tests for MutualExclusionPruner."""

from datetime import date

from src.models.rag_schemas import RetrievedClause
from src.services.rag.retriever.pruner import MutualExclusionPruner


def test_hard_exclusion_pruning(tmp_path):
    # Setup temporary exclusion rule file
    rules_json = tmp_path / "mutual_exclusions.json"
    rules_json.write_text(
        """[
      {
        "conflict_id": "CONF-01",
        "tier": "TIER_1_HARD",
        "policy_a": "POL-2026-VLF-EARLY",
        "policy_b": "POL-2026-VLF-BANK",
        "description": "Chiết khấu thanh toán sớm loại trừ gói vay HTLS",
        "action": "MUTUALLY_EXCLUSIVE"
      },
      {
        "conflict_id": "CONF-02",
        "tier": "TIER_2_CONDITIONAL",
        "policy_a": "POL-2026-VLF-INTERIOR",
        "policy_b": "POL-2026-VLF-EARLY",
        "condition": "Nội thất giảm 50% khi thanh toán sớm",
        "action": "REDUCE_BENEFIT"
      },
      {
        "conflict_id": "CONF-03",
        "tier": "TIER_3_AMBIGUOUS",
        "policy_a": "POL-2026-VLF-VIP-EXP",
        "policy_b": "ALL_POLICIES",
        "condition": "Cần Tổng Giám Đốc phê duyệt",
        "action": "SAFE_ABSTAIN"
      }
    ]""",
        encoding="utf-8",
    )

    pruner = MutualExclusionPruner(exclusions_path=rules_json)

    clause_early = RetrievedClause(
        node_id="node_early",
        policy_id="POL-2026-VLF-EARLY",
        policy_title="Thanh toán sớm",
        article="Điều 1",
        clause="Khoản 1",
        text="Chiết khấu 8%",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 6, 30),
        score=0.9,
    )

    clause_bank = RetrievedClause(
        node_id="node_bank",
        policy_id="POL-2026-VLF-BANK",
        policy_title="HTLS Ngân hàng",
        article="Điều 1",
        clause="Khoản 1",
        text="Vay 70% lãi suất 0%",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 6, 30),
        score=0.7,
    )

    # When both are present and no preference given, higher score (EARLY: 0.9) wins
    surviving, decisions = pruner.prune([clause_early, clause_bank])
    assert len(surviving) == 1
    assert surviving[0].policy_id == "POL-2026-VLF-EARLY"
    assert len(decisions) == 1
    assert decisions[0].conflict_id == "CONF-01"
    assert decisions[0].pruned_policy == "POL-2026-VLF-BANK"

    # When user explicitly prefers BANK, BANK wins despite lower score
    surviving_bank, decisions_bank = pruner.prune([clause_early, clause_bank], preferred_policy_id="POL-2026-VLF-BANK")
    assert len(surviving_bank) == 1
    assert surviving_bank[0].policy_id == "POL-2026-VLF-BANK"


def test_conditional_and_ambiguous_pruning(tmp_path):
    rules_json = tmp_path / "mutual_exclusions.json"
    rules_json.write_text(
        """[
      {
        "conflict_id": "CONF-02",
        "tier": "TIER_2_CONDITIONAL",
        "policy_a": "POL-2026-VLF-INTERIOR",
        "policy_b": "POL-2026-VLF-EARLY",
        "condition": "Nội thất giảm 50% khi thanh toán sớm",
        "action": "REDUCE_BENEFIT"
      },
      {
        "conflict_id": "CONF-03",
        "tier": "TIER_3_AMBIGUOUS",
        "policy_a": "POL-2026-VLF-VIP-EXP",
        "policy_b": "ALL_POLICIES",
        "condition": "Cần Tổng Giám Đốc phê duyệt",
        "action": "SAFE_ABSTAIN"
      }
    ]""",
        encoding="utf-8",
    )

    pruner = MutualExclusionPruner(exclusions_path=rules_json)

    clause_interior = RetrievedClause(
        node_id="node_interior",
        policy_id="POL-2026-VLF-INTERIOR",
        policy_title="Nội thất",
        article="Điều 1",
        clause="Khoản 1",
        text="Tặng gói nội thất 200 triệu",
        valid_from=date(2026, 2, 1),
        valid_to=date(2026, 5, 31),
        score=0.8,
    )

    clause_early = RetrievedClause(
        node_id="node_early",
        policy_id="POL-2026-VLF-EARLY",
        policy_title="Thanh toán sớm",
        article="Điều 1",
        clause="Khoản 1",
        text="Chiết khấu 8%",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 6, 30),
        score=0.85,
    )

    clause_vip = RetrievedClause(
        node_id="node_vip",
        policy_id="POL-2026-VLF-VIP-EXP",
        policy_title="Ngoại lệ VIP",
        article="Điều 1",
        clause="Khoản 1",
        text="Chiết khấu ngoại lệ 12%",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        score=0.95,
    )

    surviving, decisions = pruner.prune([clause_interior, clause_early, clause_vip])
    assert len(surviving) == 3

    # Check Tier 2 reduction annotation
    interior_clause = next(c for c in surviving if c.policy_id == "POL-2026-VLF-INTERIOR")
    assert "Nội thất giảm 50%" in interior_clause.metadata["conditional_benefit_reduction"]

    # Check Tier 3 escalation annotation
    vip_clause = next(c for c in surviving if c.policy_id == "POL-2026-VLF-VIP-EXP")
    assert vip_clause.metadata["requires_management_approval"] is True
