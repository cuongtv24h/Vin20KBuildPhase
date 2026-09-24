from typing import List, Dict, Any

class HybridFusion:
    """
    D1-2: Hybrid Fusion using Reciprocal Rank Fusion (RRF)
    Kết hợp kết quả từ PostgreSQL FTS (Lexical) + pgvector (Dense).
    """
    def __init__(self, k: int = 60):
        self.k = k
        
    def reciprocal_rank_fusion(self, lexical_results: List[str], dense_results: List[str]) -> List[str]:
        """
        Merge lexical/dense không phụ thuộc raw score bằng RRF.
        """
        scores: Dict[str, float] = {}
        
        for rank, atom_id in enumerate(lexical_results):
            scores[atom_id] = scores.get(atom_id, 0.0) + 1.0 / (self.k + rank + 1)
            
        for rank, atom_id in enumerate(dense_results):
            scores[atom_id] = scores.get(atom_id, 0.0) + 1.0 / (self.k + rank + 1)
            
        sorted_atoms = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [atom[0] for atom in sorted_atoms]
