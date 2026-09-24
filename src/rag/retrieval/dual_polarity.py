from typing import List, Dict, Tuple
from src.models.pec_contracts import PolicyQuery

class DualPolarityRetriever:
    """
    D1-2: Dual-polarity retrieval: Why và Why-not
    Chưa tách positive và negative retrieval sẽ làm Why-not bỏ sót exclusion.
    """
    
    def retrieve(self, query: PolicyQuery) -> Tuple[List[str], List[str]]:
        """
        Hai retrieval lanes trong D1-2: 
        1. Positive query
        2. Exclusion/prerequisite query
        """
        # Logic giả lập: Query CSDL lấy atom_ids
        positive_seed_ids = ["ATOM-POS-001"]
        negative_seed_ids = ["ATOM-NEG-001"]
        
        return positive_seed_ids, negative_seed_ids
