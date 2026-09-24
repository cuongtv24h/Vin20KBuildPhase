from typing import List
from src.models.pec_contracts import PolicyEdge

class TDECClosure:
    """
    D1-3: Typed policy edges + TDEC closure (Temporal Dual-Polarity Evidence Closure).
    Đóng gói bằng chứng (closure) có giới hạn, tránh bỏ sót prerequisite, footnote, referenced clause.
    """
    
    def __init__(self, max_hops: int = 1):
        self.max_hops = max_hops
        
    def expand_closure(self, seed_atom_ids: List[str], available_edges: List[PolicyEdge]) -> List[str]:
        """
        Mở rộng từ hạt giống (seeds) ra các atom liên quan thông qua edges 
        (REQUIRES, EXCLUDES, REFERENCES).
        Mặc định 1 hop. Mở hop thứ 2 khi target còn REQUIRES chưa khép kín.
        """
        closure_ids = set(seed_atom_ids)
        current_layer = set(seed_atom_ids)
        
        for hop in range(self.max_hops):
            next_layer = set()
            for edge in available_edges:
                # Chỉ lấy edge APPROVED_FOR_USE cho Official Quote
                if edge.validation_status != "APPROVED_FOR_USE":
                    continue
                    
                if edge.source_atom_id in current_layer:
                    next_layer.add(edge.target_atom_id)
                    
            if not next_layer:
                break
                
            closure_ids.update(next_layer)
            current_layer = next_layer
            
        return list(closure_ids)
