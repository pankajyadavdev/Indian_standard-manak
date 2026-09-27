"""
Phase 15: Explainable AI

Generates structured, human-readable explanations for every AI decision:
1. WHY a standard was recommended (search reasoning chain)
2. WHY a gap was detected
3. WHY a certification compliance failed
4. WHY a conflict was flagged
5. WHY RAG refused to answer
"""

from typing import List, Dict, Any


class ExplanationBuilder:
    """Builds structured, human-readable explanations for AI decisions."""

    def explain_search_result(
        self,
        query: str,
        results: List[Dict[str, Any]],
        search_type: str = "hybrid"
    ) -> Dict[str, Any]:
        """Explain why these search results were returned for this query."""
        if not results:
            return {
                "decision": "No standards found",
                "reason": f"No BIS standards matched the submitted query using {search_type} search above the relevance threshold.",
                "reasoning_steps": [
                    f"1. The submitted query was processed using {search_type} search.",
                    "2. Exact code match: No exact BIS standard code found in query.",
                    "3. Keyword match: No significant term overlap with any standard title or scope.",
                    "4. Semantic match: Vector similarity below threshold (0.45) for all indexed standards.",
                    "5. Conclusion: No results above relevance threshold — returning empty set."
                ],
                "confidence": 0.0
            }

        top = results[0]
        steps = [
            f"1. The submitted query was analyzed using {search_type} search.",
            f"2. Top result: {top['standard_code']} — {top['title']}",
            f"3. Match type(s): {top['match_type']} | Score: {top['score']:.4f}",
            f"4. Evidence: {top['explanation']}",
            f"5. Total relevant standards retrieved: {len(results)} (above relevance threshold)."
        ]
        return {
            "decision": f"Recommended {top['standard_code']} as top-matching BIS standard",
            "reason": f"Standard {top['standard_code']} had the highest combined relevance score among the retrieved standards.",
            "reasoning_steps": steps,
            "confidence": top["score"]
        }

    def explain_gap(self, gap: Dict[str, Any]) -> str:
        """Generate human-readable explanation for a detected gap."""
        std = gap.get("standard_code") or gap.get("missing_normative")
        reason = gap.get("reason", "")
        severity = gap.get("severity", "MEDIUM")
        return (
            f"[{severity}] Gap detected: Standard {std} is not cited in the tender. "
            f"Reason: {reason} "
            f"This omission may cause procurement non-compliance or quality failures."
        )

    def explain_conflict(self, conflict: Dict[str, Any]) -> str:
        """Generate human-readable explanation for a detected conflict."""
        ctype = conflict.get("conflict_type", "unknown")
        desc = conflict.get("description", "")
        severity = conflict.get("severity", "HIGH")
        recommendation = conflict.get("recommendation", "")
        return (
            f"[{severity}] Conflict — {ctype.replace('_', ' ').title()}: "
            f"{desc} "
            f"Action required: {recommendation}"
        )

    def explain_certification_fail(self, check: Dict[str, Any]) -> str:
        """Generate human-readable explanation for a certification compliance failure."""
        code = check.get("standard_code", "")
        status = check.get("compliance_status", "")
        alert = check.get("alert", "")
        rec = check.get("recommendation", "")
        if status == "MANDATORY_MISSING":
            return (
                f"Certification FAIL for {code}: Under mandatory QCO order "
                f"({check.get('qco_order', 'unknown order')}), products must carry BIS Standard Mark. "
                f"Alert: {alert} "
                f"Fix: {rec}"
            )
        return f"Certification status for {code}: {status}. {alert or ''} {rec}"

    def explain_rag_refusal(self, query: str) -> Dict[str, Any]:
        """Explain why RAG refused to answer."""
        return {
            "decision": "Answer refused — insufficient verified evidence",
            "reason": (
                "The submitted query was evaluated against the BIS standards database "
                "using hybrid search (exact + keyword + semantic). No evidence met the "
                "minimum relevance threshold (0.45 similarity score). "
                "Per system policy, the engine does NOT generate answers without verified evidence."
            ),
            "reasoning_steps": [
                "1. The submitted query was evaluated.",
                "2. Exact match: No exact BIS standard code found.",
                "3. Keyword match: No significant overlap with any standard's title or scope.",
                "4. Semantic match: Cosine similarity below threshold (0.45) for all standards.",
                "5. Policy: Evidence-grounded RAG — refused to hallucinate an answer.",
                "6. Output: 'Insufficient verified evidence.'"
            ],
            "confidence": 0.0
        }

    def explain_version_check(self, version_result: Dict[str, Any]) -> str:
        """Explain the version check decision."""
        code = version_result.get("standard_code", "")
        status = version_result.get("status", "")
        current = version_result.get("current_version", "N/A")
        cited = version_result.get("cited_version", code)
        if status == "current":
            return f"{code}: Cited version '{cited}' is the current operative BIS standard ({current}). No action required."
        elif status == "superseded":
            sup_by = version_result.get("superseded_by", current)
            return (f"{code}: CRITICAL — Cited version '{cited}' is OBSOLETE. "
                    f"It has been superseded by {sup_by}. Update tender specification immediately.")
        elif status == "withdrawn":
            return f"{code}: CRITICAL — This standard has been WITHDRAWN by BIS. Do not use."
        elif status == "not_found":
            return f"{code}: Standard not found in BIS catalog. Verify the standard code."
        return f"{code}: Status is '{status}'. Current version: {current}."


explainer = ExplanationBuilder()
