from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.standard import Standard, StandardReference

RELATIONSHIP_TYPES = [
    "normative",
    "test_method",
    "safety",
    "installation",
    "terminology",
    "material",
    "related"
]

class StandardRelationshipNode:
    def __init__(
        self,
        source_code: str,
        target_code: str,
        target_title: str,
        relationship_type: str,
        clause: Optional[str] = None,
        description: Optional[str] = None
    ):
        self.source_code = source_code
        self.target_code = target_code
        self.target_title = target_title
        self.relationship_type = relationship_type
        self.clause = clause
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_code": self.source_code,
            "target_code": self.target_code,
            "target_title": self.target_title,
            "relationship_type": self.relationship_type,
            "clause": self.clause,
            "description": self.description
        }

class RelationshipEngine:
    def get_relationships(
        self,
        db: Session,
        standard_code: str,
        rel_type: Optional[str] = None
    ) -> List[StandardRelationshipNode]:
        """Fetch all outbound standard relationships for a given standard code."""
        std = db.query(Standard).filter(Standard.standard_code.ilike(standard_code)).first()
        if not std:
            return []

        q = db.query(StandardReference).filter(StandardReference.source_standard_id == std.id)
        if rel_type and rel_type.lower() in RELATIONSHIP_TYPES:
            q = q.filter(StandardReference.relationship_type == rel_type.lower())

        refs = q.all()
        results = []
        for r in refs:
            results.append(StandardRelationshipNode(
                source_code=std.standard_code,
                target_code=r.target_standard.standard_code,
                target_title=r.target_standard.title,
                relationship_type=r.relationship_type,
                clause=r.clause_reference,
                description=r.description
            ))
        return results

    def get_relationship_graph(
        self,
        db: Session,
        root_code: str,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """Build directed relationship graph nodes and edges up to max_depth."""
        root_std = db.query(Standard).filter(Standard.standard_code.ilike(root_code)).first()
        if not root_std:
            return {"nodes": [], "edges": []}

        nodes_dict: Dict[str, Dict[str, Any]] = {
            root_std.standard_code: {
                "id": root_std.standard_code,
                "label": root_std.standard_code,
                "title": root_std.title,
                "category": root_std.category,
                "status": root_std.status,
                "is_root": True
            }
        }
        edges: List[Dict[str, Any]] = []
        visited = set()
        queue = [(root_std, 0)]

        while queue:
            current_std, depth = queue.pop(0)
            if current_std.standard_code in visited or depth >= max_depth:
                continue
            visited.add(current_std.standard_code)

            for ref in current_std.outbound_references:
                target = ref.target_standard
                if target.standard_code not in nodes_dict:
                    nodes_dict[target.standard_code] = {
                        "id": target.standard_code,
                        "label": target.standard_code,
                        "title": target.title,
                        "category": target.category,
                        "status": target.status,
                        "is_root": False
                    }
                edges.append({
                    "from": current_std.standard_code,
                    "to": target.standard_code,
                    "relationship_type": ref.relationship_type,
                    "clause": ref.clause_reference,
                    "description": ref.description
                })
                if depth + 1 < max_depth:
                    queue.append((target, depth + 1))

        return {
            "root": root_std.standard_code,
            "total_nodes": len(nodes_dict),
            "total_edges": len(edges),
            "nodes": list(nodes_dict.values()),
            "edges": edges
        }

relationship_engine = RelationshipEngine()
