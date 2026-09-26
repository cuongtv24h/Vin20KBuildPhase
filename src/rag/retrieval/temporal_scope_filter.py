"""Hard Temporal and Scope Pre-Filter for Policy Atoms."""
from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any, List, Optional
from sqlalchemy import text
from src.db.session import engine

logger = logging.getLogger(__name__)


class TemporalScopeFilter:
    """D1-2: Hard temporal/scope filter.
    
    Thực hiện SQL exact filter trước semantic search để đảm bảo bất biến an toàn:
    100% không rò rỉ chính sách quá hạn hoặc chưa có hiệu lực.
    """

    async def filter_db_candidates(
        self,
        transaction_date: date | str,
        customer_tier: Optional[str] = None,
        service_code: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> List[dict[str, Any]]:
        """Lọc danh sách Policy Atoms từ CSDL PostgreSQL theo ngày và phạm vi áp dụng."""
        if isinstance(transaction_date, str):
            tx_date = datetime.strptime(transaction_date[:10], "%Y-%m-%d").date()
        else:
            tx_date = transaction_date

        query = text("""
            SELECT atom_id, policy_id, atom_type, chapter, article, clause, point,
                   section_path, canonical_text, retrieval_text, content_hash,
                   valid_from, valid_to, customer_tiers, service_codes, channel,
                   embedding
            FROM policy_atoms
            WHERE valid_from <= :tx_date AND valid_to >= :tx_date
        """)

        async with engine.connect() as conn:
            result = await conn.execute(query, {"tx_date": tx_date})
            rows = result.mappings().all()

        candidates = []
        for r in rows:
            # Client-side scope check on array fields if needed
            tiers = r.get("customer_tiers") or ["ALL"]
            services = r.get("service_codes") or ["ALL"]
            
            if customer_tier and "ALL" not in tiers and customer_tier not in tiers:
                continue
            if service_code and "ALL" not in services and service_code not in services:
                continue
                
            candidates.append(dict(r))

        return candidates

    def filter_memory_candidates(
        self,
        atoms: List[dict[str, Any]],
        transaction_date: date | str,
        customer_tier: Optional[str] = None,
        service_code: Optional[str] = None,
    ) -> List[dict[str, Any]]:
        """Lọc các candidate atoms trong bộ nhớ (dành cho Unit Test / Local fallback)."""
        if isinstance(transaction_date, str):
            tx_date = datetime.strptime(transaction_date[:10], "%Y-%m-%d").date()
        else:
            tx_date = transaction_date

        valid = []
        for atom in atoms:
            v_from = atom.get("valid_from")
            v_to = atom.get("valid_to")
            
            if isinstance(v_from, str):
                v_from = datetime.strptime(v_from[:10], "%Y-%m-%d").date()
            if isinstance(v_to, str):
                v_to = datetime.strptime(v_to[:10], "%Y-%m-%d").date()

            if v_from and v_to and not (v_from <= tx_date <= v_to):
                continue

            tiers = atom.get("customer_tiers") or ["ALL"]
            if customer_tier and "ALL" not in tiers and customer_tier not in tiers:
                continue

            services = atom.get("service_codes") or ["ALL"]
            if service_code and "ALL" not in services and service_code not in services:
                continue

            valid.append(atom)

        return valid
