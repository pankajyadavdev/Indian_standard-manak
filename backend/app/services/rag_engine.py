from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.standard import Standard
from app.services.search_service import search_engine
from app.services.embedding_service import vector_index
from app.core.logging import logger

INSUFFICIENT_EVIDENCE_MSG = "Insufficient verified evidence."

class EvidenceCitation:
    def __init__(self, source: str, snippet: str, confidence: float, clause: Optional[str] = None):
        self.source = source
        self.snippet = snippet
        self.confidence = confidence
        self.clause = clause

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "snippet": self.snippet,
            "confidence": round(self.confidence, 4),
            "clause": self.clause
        }

class RAGResponse:
    def __init__(
        self,
        query: str,
        explanation: str,
        is_verified: bool,
        evidence: List[EvidenceCitation],
        recommended_standards: List[str]
    ):
        self.query = query
        self.explanation = explanation
        self.is_verified = is_verified
        self.evidence = evidence
        self.recommended_standards = recommended_standards

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "explanation": self.explanation,
            "is_verified": self.is_verified,
            "evidence": [e.to_dict() for e in self.evidence],
            "recommended_standards": self.recommended_standards
        }

class GroundedRAGEngine:
    """
    Strict evidence-grounded RAG Engine.
    Enforces the Master Development Prompt rule:
    1. The system can ONLY explain retrieved evidence.
    2. If evidence is absent: Do NOT generate a factual answer. Return 'Insufficient verified evidence.'
    """
    def __init__(self, confidence_threshold: float = 0.45):
        self.confidence_threshold = confidence_threshold

    def retrieve_evidence(
        self,
        db: Session,
        query: str,
        document_id: Optional[str] = None
    ) -> Tuple[List[EvidenceCitation], List[Standard]]:
        evidence: List[EvidenceCitation] = []
        matched_standards: List[Standard] = []

        # 1. Search standards database
        search_results = search_engine.hybrid_search(
            db,
            query,
            top_k=3,
            min_score=self.confidence_threshold
        )

        for res in search_results:
            matched_standards.append(res.standard)
            snippet = f"{res.standard.standard_code} - {res.standard.title}: {res.standard.scope or ''}"
            evidence.append(EvidenceCitation(
                source=f"Bureau of Indian Standards ({res.standard.standard_code})",
                snippet=snippet.strip(),
                confidence=res.score,
                clause="Scope / Classification"
            ))

        # 2. Search document chunks in FAISS if document_id provided
        if document_id:
            chunk_results = vector_index.search(query, top_k=3)
            for c in chunk_results:
                if c.get("document_id") == document_id and c.get("similarity_score", 0.0) >= self.confidence_threshold:
                    evidence.append(EvidenceCitation(
                        source=f"Document Page {c.get('page_number', 1)}",
                        snippet=c["text"],
                        confidence=c.get("similarity_score", 0.0),
                        clause=f"Page {c.get('page_number', 1)}"
                    ))

        # Sort evidence by confidence descending
        evidence.sort(key=lambda x: x.confidence, reverse=True)
        return evidence, matched_standards

    def generate_grounded_explanation(
        self,
        db: Session,
        query: str,
        document_id: Optional[str] = None
    ) -> RAGResponse:
        """
        Query → retrieval → evidence selection → explanation.
        Strict verification: if evidence is absent or below threshold,
        refuses to answer and strictly returns 'Insufficient verified evidence.'
        """
        evidence, standards = self.retrieve_evidence(db, query, document_id)

        # STRICT RULE CHECK: Absence of verified evidence
        if not evidence or len(evidence) == 0:
            logger.info("RAG request yielded zero verified evidence. Refusing answer.")
            return RAGResponse(
                query=query,
                explanation=INSUFFICIENT_EVIDENCE_MSG,
                is_verified=False,
                evidence=[],
                recommended_standards=[]
            )

        # Generate factual explanation strictly restricted to retrieved evidence
        standard_codes = [s.standard_code for s in standards]
        explanation_lines = [
            "Based on verified technical evidence relevant to the submitted query:"
        ]

        for idx, ev in enumerate(evidence, 1):
            explanation_lines.append(f"[{idx}] {ev.source} (Confidence: {ev.confidence:.2f}): \"{ev.snippet}\"")

        if standards:
            explanation_lines.append(
                f"\nApplicable Indian Standard(s) identified with verified evidence: {', '.join(standard_codes)}."
            )

        explanation = "\n".join(explanation_lines)

        return RAGResponse(
            query=query,
            explanation=explanation,
            is_verified=True,
            evidence=evidence,
            recommended_standards=standard_codes
        )

rag_engine = GroundedRAGEngine(confidence_threshold=0.45)
