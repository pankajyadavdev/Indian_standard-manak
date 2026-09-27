"""
Phase 11: Certification Engine (Rule-based)

Rules:
1. Every standard cited in a tender must be checked for QCO (Quality Control Order) applicability.
2. If a standard is under QCO, the corresponding product MUST carry a valid BIS Standard Mark (ISI mark).
3. If a standard is mandatory QCO and no ISI mark requirement is cited → FLAG as COMPLIANCE FAIL.
4. If a standard is non-mandatory but recommended → FLAG as ADVISORY.
5. If the cited standard has no certifications in the database → status is UNKNOWN.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.standard import Standard
from app.models.certification import Certification

COMPLIANCE_STATUS = {
    "MANDATORY_COMPLIANT": "MANDATORY_COMPLIANT",    # QCO/mandatory standard cited correctly
    "MANDATORY_MISSING": "MANDATORY_MISSING",         # QCO/mandatory but ISI mark not required
    "ADVISORY": "ADVISORY",                            # Non-mandatory certification recommended
    "UNKNOWN": "UNKNOWN",                              # No certification data available
    "NOT_APPLICABLE": "NOT_APPLICABLE"                 # Standard found but has no certification rules
}

ISI_MARK_KEYWORDS = [
    "isi mark", "bis mark", "bis standard mark", "bma", "license", "crs", "mandatory marking"
]

class CertificationCheckResult:
    def __init__(
        self,
        standard_code: str,
        compliance_status: str,
        is_mandatory: bool,
        qco_order: Optional[str],
        applicable_ministry: Optional[str],
        certification_type: Optional[str],
        alert: Optional[str],
        recommendation: str
    ):
        self.standard_code = standard_code
        self.compliance_status = compliance_status
        self.is_mandatory = is_mandatory
        self.qco_order = qco_order
        self.applicable_ministry = applicable_ministry
        self.certification_type = certification_type
        self.alert = alert
        self.recommendation = recommendation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_code": self.standard_code,
            "compliance_status": self.compliance_status,
            "is_mandatory": self.is_mandatory,
            "qco_order": self.qco_order,
            "applicable_ministry": self.applicable_ministry,
            "certification_type": self.certification_type,
            "alert": self.alert,
            "recommendation": self.recommendation
        }


class CertificationEngine:
    """Rule-based certification compliance engine for BIS/QCO standards."""

    def check_certification(
        self,
        db: Session,
        standard_code: str,
        tender_clause_text: Optional[str] = None
    ) -> CertificationCheckResult:
        """Evaluate whether the standard cited in a tender meets certification requirements."""
        std = db.query(Standard).filter(
            Standard.standard_code.ilike(standard_code),
            Standard.is_deleted == False
        ).first()

        if not std:
            return CertificationCheckResult(
                standard_code=standard_code,
                compliance_status=COMPLIANCE_STATUS["UNKNOWN"],
                is_mandatory=False,
                qco_order=None,
                applicable_ministry=None,
                certification_type=None,
                alert=f"Standard '{standard_code}' not found in BIS catalog.",
                recommendation="Verify standard code against current BIS catalog."
            )

        # Find mandatory certification (QCO)
        mandatory_cert = next(
            (c for c in std.certifications if c.is_mandatory), None
        )
        advisory_cert = next(
            (c for c in std.certifications if not c.is_mandatory), None
        )

        if mandatory_cert:
            # Check if tender clause text requires ISI/BIS mark
            isi_mark_cited = False
            if tender_clause_text:
                text_lower = tender_clause_text.lower()
                isi_mark_cited = any(kw in text_lower for kw in ISI_MARK_KEYWORDS)

            if isi_mark_cited or not tender_clause_text:
                return CertificationCheckResult(
                    standard_code=std.standard_code,
                    compliance_status=COMPLIANCE_STATUS["MANDATORY_COMPLIANT"],
                    is_mandatory=True,
                    qco_order=mandatory_cert.qco_order_number,
                    applicable_ministry=mandatory_cert.applicable_ministry,
                    certification_type=mandatory_cert.certification_type,
                    alert=None,
                    recommendation=(
                        f"Standard {std.standard_code} is under mandatory QCO "
                        f"({mandatory_cert.qco_order_number}). "
                        f"BIS Mark requirement is correctly specified."
                    )
                )
            else:
                return CertificationCheckResult(
                    standard_code=std.standard_code,
                    compliance_status=COMPLIANCE_STATUS["MANDATORY_MISSING"],
                    is_mandatory=True,
                    qco_order=mandatory_cert.qco_order_number,
                    applicable_ministry=mandatory_cert.applicable_ministry,
                    certification_type=mandatory_cert.certification_type,
                    alert=(
                        f"COMPLIANCE FAIL: {std.standard_code} is under mandatory QCO "
                        f"({mandatory_cert.qco_order_number}) but tender clause does NOT "
                        f"require BIS Standard Mark (ISI Mark)."
                    ),
                    recommendation=(
                        f"Add explicit requirement: 'Products must carry valid BIS Standard Mark "
                        f"(ISI Mark) as mandated by QCO {mandatory_cert.qco_order_number}.'"
                    )
                )

        elif advisory_cert:
            return CertificationCheckResult(
                standard_code=std.standard_code,
                compliance_status=COMPLIANCE_STATUS["ADVISORY"],
                is_mandatory=False,
                qco_order=advisory_cert.qco_order_number,
                applicable_ministry=advisory_cert.applicable_ministry,
                certification_type=advisory_cert.certification_type,
                alert=None,
                recommendation=(
                    f"Standard {std.standard_code} has a non-mandatory "
                    f"{advisory_cert.certification_type} certification. "
                    f"Consider specifying it for quality assurance."
                )
            )
        else:
            return CertificationCheckResult(
                standard_code=std.standard_code,
                compliance_status=COMPLIANCE_STATUS["NOT_APPLICABLE"],
                is_mandatory=False,
                qco_order=None,
                applicable_ministry=None,
                certification_type=None,
                alert=None,
                recommendation=f"No specific certification rule found for {std.standard_code}."
            )

    def evaluate_tender(
        self,
        db: Session,
        standard_codes: List[str],
        tender_clause_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Evaluate all standards in a tender for certification compliance."""
        results = []
        summary = {
            "MANDATORY_COMPLIANT": 0,
            "MANDATORY_MISSING": 0,
            "ADVISORY": 0,
            "UNKNOWN": 0,
            "NOT_APPLICABLE": 0
        }

        for code in standard_codes:
            res = self.check_certification(db, code, tender_clause_text)
            results.append(res.to_dict())
            summary[res.compliance_status] = summary.get(res.compliance_status, 0) + 1

        overall_status = "COMPLIANT" if summary["MANDATORY_MISSING"] == 0 else "NON_COMPLIANT"

        return {
            "overall_status": overall_status,
            "summary": summary,
            "standards_evaluated": len(standard_codes),
            "checks": results
        }


certification_engine = CertificationEngine()
