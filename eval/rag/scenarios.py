import json
import logging
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class RAGTestCase(BaseModel):
    case_id: str
    query_text: str
    expected_policy_ids: list[str]
    is_conflict_test: bool = False
    query_date: str = "2026-05-15" # Default within valid range for most policies

class ScenarioLoader:
    def __init__(self, json_path: str):
        self.json_path = Path(json_path)

    def load_test_cases(self) -> list[RAGTestCase]:
        if not self.json_path.exists():
            logger.warning(f"Golden scenarios not found at {self.json_path}")
            return []

        with open(self.json_path, encoding='utf-8') as f:
            data = json.load(f)

        test_cases = []
        for item in data:
            query_text = item.get("description", "")
            # Determine if this case implicitly involves conflict.
            # e.g., if multiple mutually exclusive policies are selected or mentioned,
            # but golden scenarios resolve them to valid sets.
            # For pure RAG testing, we want to ensure all mentioned are retrieved.
            test_cases.append(RAGTestCase(
                case_id=item["case_id"],
                query_text=query_text,
                expected_policy_ids=item.get("selected_policies", []),
                is_conflict_test=False # Will add synthetic conflict tests later
            ))

        # Add synthetic tests for temporal and conflicts
        self._add_synthetic_tests(test_cases)
        return test_cases

    def _add_synthetic_tests(self, test_cases: list[RAGTestCase]):
        # Synthetic conflict test
        test_cases.append(RAGTestCase(
            case_id="SYNTH-CONFLICT-01",
            query_text="Tôi muốn chọn cả chiết khấu thanh toán sớm 95% và hỗ trợ lãi suất vay ngân hàng",
            expected_policy_ids=["POL-2026-VLF-EARLY", "POL-2026-VLF-BANK"],
            is_conflict_test=True
        ))

        # Synthetic time-travel tests (past and future)
        test_cases.append(RAGTestCase(
            case_id="SYNTH-TIME-PAST",
            query_text="Chính sách thanh toán sớm cho dự án",
            expected_policy_ids=[], # Should retrieve nothing if date is out of bounds
            query_date="2024-01-01"
        ))
        test_cases.append(RAGTestCase(
            case_id="SYNTH-TIME-FUTURE",
            query_text="Chính sách thanh toán sớm cho dự án",
            expected_policy_ids=[],
            query_date="2027-01-01"
        ))
