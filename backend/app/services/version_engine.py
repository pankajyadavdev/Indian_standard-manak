import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.standard import Standard, StandardVersion, Amendment

class VersionCheckResult:
    def __init__(
        self,
        standard_code: str,
        status: str, # "current", "superseded", "withdrawn", "not_found"
        is_current: bool,
        cited_version: Optional[str] = None,
        current_version: Optional[str] = None,
        superseded_by: Optional[str] = None,
        amendments: Optional[List[Dict[str, Any]]] = None,
        conflict_alert: Optional[str] = None,
        recommendation: Optional[str] = None
    ):
        self.standard_code = standard_code
        self.status = status
        self.is_current = is_current
        self.cited_version = cited_version
        self.current_version = current_version
        self.superseded_by = superseded_by
        self.amendments = amendments or []
        self.conflict_alert = conflict_alert
        self.recommendation = recommendation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_code": self.standard_code,
            "status": self.status,
            "is_current": self.is_current,
            "cited_version": self.cited_version,
            "current_version": self.current_version,
            "superseded_by": self.superseded_by,
            "amendments_count": len(self.amendments),
            "amendments": self.amendments,
            "conflict_alert": self.conflict_alert,
            "recommendation": self.recommendation
        }

class VersionEngine:
    def parse_standard_reference(self, raw_reference: str) -> Dict[str, Any]:
        """
        Extract code, year, and amendment from a string like:
        'IS 456:1978', 'IS 1786:2008 with Amendment 2', etc.
        """
        match = re.search(r"\b(IS\s*\d{3,5})(?:\s*:\s*(\d{4}))?", raw_reference, re.IGNORECASE)
        if not match:
            return {"standard_code": raw_reference.strip(), "year": None, "amendment": None}

        std_code = re.sub(r"\s+", " ", match.group(1).upper())
        year = int(match.group(2)) if match.group(2) else None

        amndt_match = re.search(r"amend(?:ment)?\s*(?:no\.?)?\s*(\d+)", raw_reference, re.IGNORECASE)
        amendment_num = int(amndt_match.group(1)) if amndt_match else None

        return {
            "standard_code": std_code,
            "year": year,
            "amendment": amendment_num
        }

    def check_version(
        self,
        db: Session,
        raw_reference: str
    ) -> VersionCheckResult:
        """
        Evaluates a cited standard reference against the BIS version database.
        Detects if old standard is cited, provides current replacement,
        lists operative amendments, and raises conflict alerts.
        """
        parsed = self.parse_standard_reference(raw_reference)
        code = parsed["standard_code"]
        cited_year = parsed["year"]
        cited_amendment = parsed["amendment"]

        std = db.query(Standard).filter(Standard.standard_code.ilike(code), Standard.is_deleted == False).first()
        if not std:
            return VersionCheckResult(
                standard_code=code,
                status="not_found",
                is_current=False,
                recommendation=f"Standard '{code}' not identified in BIS catalog. Manual verification required."
            )

        if std.status == "withdrawn":
            return VersionCheckResult(
                standard_code=std.standard_code,
                status="withdrawn",
                is_current=False,
                conflict_alert=f"Standard {std.standard_code} has been officially WITHDRAWN by BIS.",
                recommendation=f"Do not procure against withdrawn standard {std.standard_code}."
            )

        current_ver = next((v for v in std.versions if v.is_current), None)
        current_label = current_ver.version_label if current_ver else None

        # If a specific year was cited
        if cited_year:
            matched_ver = next((v for v in std.versions if v.year == cited_year), None)
            if matched_ver:
                if matched_ver.is_current:
                    # Current version cited
                    amendments_data = [{
                        "amendment_number": a.amendment_number,
                        "amendment_code": a.amendment_code,
                        "issue_date": a.issue_date.isoformat() if a.issue_date else None,
                        "summary": a.summary
                    } for a in sorted(matched_ver.amendments, key=lambda x: x.amendment_number)]

                    return VersionCheckResult(
                        standard_code=std.standard_code,
                        status="current",
                        is_current=True,
                        cited_version=matched_ver.version_label,
                        current_version=current_label,
                        amendments=amendments_data,
                        recommendation=f"Cited version {matched_ver.version_label} is the current operative BIS standard."
                    )
                else:
                    # Superseded version cited!
                    sup_by = matched_ver.superseded_by.version_label if matched_ver.superseded_by else current_label
                    return VersionCheckResult(
                        standard_code=std.standard_code,
                        status="superseded",
                        is_current=False,
                        cited_version=matched_ver.version_label,
                        current_version=current_label,
                        superseded_by=sup_by,
                        conflict_alert=f"CRITICAL: Obsolete version {matched_ver.version_label} is cited. It has been SUPERSEDED by {sup_by}.",
                        recommendation=f"Update tender specifications from {matched_ver.version_label} to current standard {sup_by}."
                    )
            else:
                # Cited year does not match known versions
                return VersionCheckResult(
                    standard_code=std.standard_code,
                    status="unknown_version",
                    is_current=False,
                    cited_version=f"{code}:{cited_year}",
                    current_version=current_label,
                    conflict_alert=f"Cited edition year {cited_year} is not recognized. Operative edition is {current_label}.",
                    recommendation=f"Verify tender clause and align with current standard {current_label}."
                )

        # No year specified: evaluate current
        amendments_data = []
        if current_ver:
            amendments_data = [{
                "amendment_number": a.amendment_number,
                "amendment_code": a.amendment_code,
                "issue_date": a.issue_date.isoformat() if a.issue_date else None,
                "summary": a.summary
            } for a in sorted(current_ver.amendments, key=lambda x: x.amendment_number)]

        return VersionCheckResult(
            standard_code=std.standard_code,
            status="current",
            is_current=True,
            cited_version=code,
            current_version=current_label,
            amendments=amendments_data,
            recommendation=f"Standard cited without year. Defaulting to operative standard {current_label} with {len(amendments_data)} amendment(s)."
        )

    def detect_version_conflicts(
        self,
        db: Session,
        raw_references: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Inspects a list of standard references cited within a tender for internal conflicts
        (e.g. citing multiple conflicting versions or obsolete editions of the same standard).
        """
        conflicts = []
        parsed_by_code: Dict[str, List[Dict[str, Any]]] = {}

        for ref in raw_references:
            p = self.parse_standard_reference(ref)
            code = p["standard_code"]
            parsed_by_code.setdefault(code, []).append({
                "raw": ref,
                "year": p["year"],
                "amendment": p["amendment"]
            })

        for code, entries in parsed_by_code.items():
            years = {e["year"] for e in entries if e["year"] is not None}
            if len(years) > 1:
                conflicts.append({
                    "standard_code": code,
                    "conflict_type": "conflicting_versions",
                    "severity": "CRITICAL",
                    "details": f"Tender cites contradictory versions for {code}: {', '.join([f'{code}:{y}' for y in sorted(years)])}.",
                    "cited_entries": [e["raw"] for e in entries],
                    "recommendation": f"Harmonize all references to the latest operative BIS standard version."
                })

            # Check if any cited is superseded
            for e in entries:
                check = self.check_version(db, e["raw"])
                if check.status == "superseded":
                    conflicts.append({
                        "standard_code": code,
                        "conflict_type": "superseded_version",
                        "severity": "HIGH",
                        "details": check.conflict_alert,
                        "cited_entries": [e["raw"]],
                        "recommendation": check.recommendation
                    })

        return conflicts

version_engine = VersionEngine()
