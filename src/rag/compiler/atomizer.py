from typing import List, Dict, Any
import hashlib
from src.models.pec_contracts import PolicyAtom, PolicyAtomType

class PolicyAtomizer:
    """
    D1-1: Policy Compiler MVP
    Chịu trách nhiệm parse documents thành các PolicyAtom (clause, table row, footnote, definition).
    """
    
    def __init__(self, embedding_model_id: str = "text-embedding-3-small"):
        self.embedding_model_id = embedding_model_id

    def create_atom(self, raw_text: str, atom_type: PolicyAtomType, metadata: Dict[str, Any]) -> PolicyAtom:
        """
        Sinh atoms theo clause/table row/footnote/definition.
        Mỗi atom có content_hash. Sinh deterministic context từ metadata.
        """
        content_hash = hashlib.sha256(raw_text.encode('utf-8')).hexdigest()
        
        # Build deterministic context: title + section path + clause title + scope + canonical text
        canonical_text = f"[{metadata.get('section_path', '')}] {raw_text}"
        
        return PolicyAtom(
            atom_id=f"ATOM-{content_hash[:8]}",
            atom_type=atom_type,
            content_hash=content_hash,
            canonical_text=canonical_text
        )
    
    def process_document(self, document: str) -> List[PolicyAtom]:
        """Parse raw document into atoms (Mock implementation for now)"""
        return []
