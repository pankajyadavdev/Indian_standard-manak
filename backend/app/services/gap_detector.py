"""
Phase 12: Gap Detection

Identifies missing mandatory standards in tender documents compared to:
1. The domain/category of standards explicitly cited
2. Normative references required by the cited standards
3. Mandatory QCO-regulated standards for the product categories detected
"""

import re
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session
from app.models.standard import Standard
from app.services.entity_extractor import extract_entities

# Known mandatory standard clusters by domain
DOMAIN_MANDATORY_STANDARDS = {
    "Civil": ["IS 456", "IS 1786", "IS 269"],
    "Electrical": ["IS 694", "IS 732", "IS 3043"],
    "Metallurgy": ["IS 2062", "IS 1786"],
    "Mechanical": ["IS 1239"],
}

class GapReport:
    def __init__(
        self,
        total_cited: int,
        gaps_found: int,
        missing_standards: List[Dict[str, Any]],
        missing_normative_refs: List[Dict[str, Any]],
        recommendations: List[str]
    ):
        self.total_cited = total_cited
        self.gaps_found = gaps_found
        self.missing_standards = missing_standards
        self.missing_normative_refs = missing_normative_refs
        self.recommendations = recommendations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cited_standards": self.total_cited,
            "total_gaps_found": self.gaps_found,
            "missing_mandatory_standards": self.missing_standards,
            "missing_normative_references": self.missing_normative_refs,
            "recommendations": self.recommendations
        }


class GapDetector:
    def detect_gaps(
        self,
        db: Session,
        cited_codes: List[str],
        categories: Optional[List[str]] = None
    ) -> GapReport:
        """
        Detect specification gaps:
        1. Missing mandatory domain standards not cited
        2. Missing normative references required by cited standards
        """
        cited_set: Set[str] = set()
        for code in cited_codes:
            base = re.sub(r":\d{4}", "", code).strip().upper()
            cited_set.add(base)

        missing_mandatory = []
        recommendations = []

        # 1. Check domain mandatory standard clusters
        cats = categories or []
        for domain, mandatory_codes in DOMAIN_MANDATORY_STANDARDS.items():
            # If any standard from this domain is cited, all mandatory ones must be present
            domain_stds_cited = [c for c in cited_set if any(c.startswith(m) for m in mandatory_codes)]
            if domain_stds_cited or (domain in cats):
                for mand_code in mandatory_codes:
                    if not any(c.startswith(mand_code) for c in cited_set):
                        std = db.query(Standard).filter(
                            Standard.standard_code.ilike(mand_code)
                        ).first()
                        if std:
                            missing_mandatory.append({
                                "standard_code": std.standard_code,
                                "title": std.title,
                                "category": std.category,
                                "reason": f"Mandatory standard for {domain} domain not cited in tender.",
                                "severity": "HIGH"
                            })
                            recommendations.append(
                                f"Add {std.standard_code} ({std.title}) to tender specifications for {domain} works."
                            )

        # 2. Check normative references of each cited standard
        missing_normative = []
        for code in cited_codes:
            base = re.sub(r":\d{4}", "", code).strip()
            std = db.query(Standard).filter(Standard.standard_code.ilike(base)).first()
            if not std:
                continue
            for ref in std.outbound_references:
                if ref.relationship_type == "normative":
                    target = ref.target_standard
                    if not any(c.startswith(target.standard_code.split(":")[0]) for c in cited_set):
                        missing_normative.append({
                            "source_standard": std.standard_code,
                            "missing_normative": target.standard_code,
                            "title": target.title,
                            "clause": ref.clause_reference,
                            "reason": f"Required normative reference per {std.standard_code} {ref.clause_reference}",
                            "severity": "MEDIUM"
                        })
                        recommendations.append(
                            f"Add normative reference {target.standard_code} "
                            f"required by {std.standard_code} ({ref.clause_reference})."
                        )

        total_gaps = len(missing_mandatory) + len(missing_normative)
        return GapReport(
            total_cited=len(cited_codes),
            gaps_found=total_gaps,
            missing_standards=missing_mandatory,
            missing_normative_refs=missing_normative,
            recommendations=recommendations
        )

    def detect_gaps_from_text(self, db: Session, text: str) -> GapReport:
        """Auto-extract cited standards + categories, then detect gaps."""
        entities = extract_entities(text)
        return self.detect_gaps(db, entities.standards_cited, entities.categories)


gap_detector = GapDetector()
