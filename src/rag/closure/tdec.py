"""Temporal Dual-Polarity Evidence Closure (TDEC)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class TDECClosure:
    """D1-3: Typed policy edges + TDEC closure.
    
    Đóng gói bằng chứng (closure) có giới hạn:
    - Bắt trọn vẹn footnote, prerequisite, và conflict partner.
    - Giới hạn 1-2 hops để bảo vệ latency và tránh nổ không gian tìm kiếm.
    """

    def __init__(self, max_hops: int = 1, max_atoms_cap: int = 25):
        self.max_hops = max_hops
        self.max_atoms_cap = max_atoms_cap

    def expand_closure(
        self,
        positive_seeds: List[Dict[str, Any]],
        negative_seeds: List[Dict[str, Any]],
        available_edges: List[Dict[str, Any]],
        atom_lookup: Dict[str, Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Thực hiện mở rộng đồ thị từ tập seed:
        
        Args:
            positive_seeds: Danh sách seed atoms từ cực dương (Why)
            negative_seeds: Danh sách seed atoms từ cực âm (Why-not)
            available_edges: Danh sách các PolicyEdge có trong hệ thống
            atom_lookup: Bảng tra cứu atom_id -> atom dict
            
        Returns:
            Tuple của (closed_atoms, applied_edges, detected_conflicts)
        """
        seed_ids: Set[str] = {a["atom_id"] for a in positive_seeds + negative_seeds if "atom_id" in a}
        closure_ids: Set[str] = set(seed_ids)
        current_layer: Set[str] = set(seed_ids)
        applied_edges: List[Dict[str, Any]] = []
        detected_conflicts: List[Dict[str, Any]] = []

        # Chỉ xét các edge đã được APPROVED_FOR_USE
        valid_edges = [
            e for e in available_edges
            if e.get("validation_status", "APPROVED_FOR_USE") == "APPROVED_FOR_USE"
        ]

        for hop in range(self.max_hops):
            next_layer: Set[str] = set()

            for edge in valid_edges:
                src_id = edge.get("source_atom_id")
                tgt_id = edge.get("target_atom_id")
                edge_type = edge.get("edge_type", "")

                if src_id in current_layer and tgt_id not in closure_ids:
                    # Kéo target vào closure
                    next_layer.add(tgt_id)
                    applied_edges.append(edge)

                    # Nếu là quan hệ EXCLUDES -> Ghi nhận xung đột
                    if edge_type == "EXCLUDES":
                        detected_conflicts.append({
                            "source_atom_id": src_id,
                            "target_atom_id": tgt_id,
                            "relation": "EXCLUDES",
                            "reason": edge.get("description", "Quy tắc loại trừ không áp dụng đồng thời"),
                        })

                # Nếu cả 2 atom đã nằm trong closure và có edge EXCLUDES
                elif src_id in closure_ids and tgt_id in closure_ids and edge_type == "EXCLUDES":
                    conflict_pair = {
                        "source_atom_id": src_id,
                        "target_atom_id": tgt_id,
                        "relation": "EXCLUDES",
                        "reason": edge.get("description", "Quy tắc loại trừ không áp dụng đồng thời"),
                    }
                    if conflict_pair not in detected_conflicts:
                        detected_conflicts.append(conflict_pair)

            if not next_layer:
                break

            closure_ids.update(next_layer)
            current_layer = next_layer

            # Kiểm tra hard cap số lượng atoms để bảo vệ latency
            if len(closure_ids) >= self.max_atoms_cap:
                logger.warning("TDEC closure hit max_atoms_cap (%d)", self.max_atoms_cap)
                break

        # Tập hợp danh sách các atoms hoàn chỉnh sau khi đóng
        closed_atoms: List[Dict[str, Any]] = []
        for atom_id in closure_ids:
            if atom_id in atom_lookup:
                closed_atoms.append(atom_lookup[atom_id])
            else:
                # Placeholder atom nếu chưa load đầy đủ
                closed_atoms.append({
                    "atom_id": atom_id,
                    "canonical_text": f"Atom {atom_id} loaded via closure edge",
                    "retrieval_text": f"Atom {atom_id}",
                    "content_hash": "placeholder_hash",
                    "atom_type": "CLAUSE",
                })

        return closed_atoms, applied_edges, detected_conflicts
