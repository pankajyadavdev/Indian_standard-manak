"""
Phase 13: Conflict Detection

Detects conflicting requirements within a tender document:
1. Same standard cited at contradictory versions
2. Conflicting material grade requirements (e.g., Fe 415 and Fe 500 for same item)
3. Conflicting performance specifications (e.g., two different compressive strengths for same grade)
4. Contradictory exposure/environment classifications
5. Contradictory certification requirements (ISI mark required vs explicitly waived)
"""

import re
from typing import List, Dict, Any, Optional
from app.services.version_engine import version_engine
from sqlalchemy.orm import Session

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

STEEL_GRADE_RE = re.compile(r"Fe\s*(415|500|550|600)D?", re.IGNORECASE)
CONCRETE_GRADE_RE = re.compile(r"M\s*(20|25|30|35|40|45|50|55|60)", re.IGNORECASE)
EXPOSURE_RE = re.compile(r"\b(mild|moderate|severe|very severe|extreme)\s+exposure", re.IGNORECASE)
ISI_REQUIRED_RE = re.compile(r"must carry.{0,30}(isi|bis)\s+mark|mandatory.{0,20}(isi|bis)\s+mark|shall\s+be\s+bis\s+marked", re.IGNORECASE)
ISI_WAIVED_RE = re.compile(r"(isi|bis)\s+mark.{0,20}(not required|waived|optional|exempted)", re.IGNORECASE)


class ConflictReport:
    def __init__(self, conflicts: List[Dict[str, Any]]):
        self.conflicts = conflicts
        self.total_conflicts = len(conflicts)
        self.critical_count = sum(1 for c in conflicts if c.get("severity") == SEVERITY_CRITICAL)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_conflicts": self.total_conflicts,
            "critical_conflicts": self.critical_count,
            "conflicts": self.conflicts
        }


class ConflictDetector:
    def detect_conflicts(self, db: Session, text: str, cited_references: Optional[List[str]] = None) -> ConflictReport:
        conflicts = []

        # 1. Conflicting standard versions
        if cited_references:
            version_conflicts = version_engine.detect_version_conflicts(db, cited_references)
            for vc in version_conflicts:
                conflicts.append({
                    "conflict_type": "version_conflict",
                    "severity": SEVERITY_CRITICAL,
                    "description": vc["details"],
                    "items_involved": vc.get("cited_entries", []),
                    "recommendation": vc.get("recommendation", "")
                })

        # 2. Conflicting steel grade requirements
        steel_grades = set(STEEL_GRADE_RE.findall(text))
        if len(steel_grades) > 1:
            grades_str = ", ".join([f"Fe {g}" for g in sorted(steel_grades)])
            conflicts.append({
                "conflict_type": "conflicting_material_grades",
                "severity": SEVERITY_HIGH,
                "description": f"Multiple steel grades specified for reinforcement: {grades_str}. This may indicate contradictory requirements.",
                "items_involved": [f"Fe {g}" for g in sorted(steel_grades)],
                "recommendation": "Specify a single steel grade for each structural element or zone. Separate by element type."
            })

        # 3. Conflicting concrete grades
        concrete_grades = set(CONCRETE_GRADE_RE.findall(text))
        if len(concrete_grades) > 2:
            grades_str = ", ".join([f"M{g}" for g in sorted(concrete_grades, key=int)])
            conflicts.append({
                "conflict_type": "conflicting_concrete_grades",
                "severity": SEVERITY_MEDIUM,
                "description": f"Multiple concrete grades found: {grades_str}. Verify each is assigned to the correct structural element.",
                "items_involved": [f"M{g}" for g in sorted(concrete_grades, key=int)],
                "recommendation": "Clarify which concrete grade applies to each structural member (foundation, columns, slabs)."
            })

        # 4. Contradictory exposure classifications
        exposures = list(set(e[0].lower() for e in EXPOSURE_RE.findall(text)))
        if len(exposures) > 1:
            conflicts.append({
                "conflict_type": "contradictory_exposure_classification",
                "severity": SEVERITY_MEDIUM,
                "description": f"Multiple exposure classifications found: {', '.join(exposures)}. IS 456 Table 3 allows only one classification per element.",
                "items_involved": exposures,
                "recommendation": "Define exposure classification per structural zone. Do not apply multiple exposure conditions to a single element."
            })

        # 5. Contradictory ISI mark requirement
        isi_required = bool(ISI_REQUIRED_RE.search(text))
        isi_waived = bool(ISI_WAIVED_RE.search(text))
        if isi_required and isi_waived:
            conflicts.append({
                "conflict_type": "contradictory_certification_requirement",
                "severity": SEVERITY_CRITICAL,
                "description": "Tender simultaneously requires and waives ISI/BIS mark. This is a critical compliance contradiction.",
                "items_involved": ["BIS Mark Requirement", "BIS Mark Waiver"],
                "recommendation": "Retain ISI/BIS mark requirement. Waiver clauses for QCO-mandated products are invalid under law."
            })

        return ConflictReport(conflicts)


conflict_detector = ConflictDetector()
