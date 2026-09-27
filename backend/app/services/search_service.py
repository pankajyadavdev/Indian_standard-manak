import re
import math
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.standard import Standard, StandardVersion
from app.services.embedding_service import embed_texts
import numpy as np

class SearchResult:
    def __init__(self, standard: Standard, score: float, match_type: str, explanation: str):
        self.standard = standard
        self.score = score
        self.match_type = match_type
        self.explanation = explanation

    def to_dict(self) -> Dict[str, Any]:
        current_version = next((v for v in self.standard.versions if v.is_current), None)
        return {
            "standard_id": self.standard.id,
            "standard_code": self.standard.standard_code,
            "title": self.standard.title,
            "category": self.standard.category,
            "status": self.standard.status,
            "current_version": current_version.version_label if current_version else None,
            "score": round(self.score, 4),
            "match_type": self.match_type,
            "explanation": self.explanation
        }

class HybridSearchEngine:
    def __init__(self):
        pass

    def exact_search(self, db: Session, query: str) -> List[SearchResult]:
        """Exact standard code match (e.g. 'IS 456' or 'IS 1786')."""
        norm_query = re.sub(r"\s+", " ", query.strip().upper())
        # Find exact matches
        results = []
        standards = db.query(Standard).filter(Standard.is_deleted == False).all()
        for std in standards:
            code_upper = std.standard_code.upper()
            if code_upper == norm_query or norm_query.startswith(code_upper):
                results.append(SearchResult(
                    standard=std,
                    score=1.0,
                    match_type="exact_code",
                    explanation=f"Exact match on standard code {std.standard_code}"
                ))
        return results

    def keyword_search(self, db: Session, query: str, category_filter: Optional[str] = None) -> List[SearchResult]:
        """Token-based BM25/keyword matching against title and scope."""
        tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        if not tokens:
            return []

        q = db.query(Standard).filter(Standard.is_deleted == False)
        if category_filter:
            q = q.filter(Standard.category.ilike(f"%{category_filter}%"))
        standards = q.all()

        results = []
        for std in standards:
            corpus = f"{std.standard_code} {std.title} {std.scope or ''} {std.category}".lower()
            corpus_tokens = set(re.findall(r"\w+", corpus))
            
            # Count token matches and calculate overlap ratio
            matched = [t for t in tokens if t in corpus_tokens]
            if matched:
                score = len(matched) / (len(tokens) + 1)
                results.append(SearchResult(
                    standard=std,
                    score=score,
                    match_type="keyword",
                    explanation=f"Matched keywords: {', '.join(matched)}"
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def semantic_search(self, db: Session, query: str, top_k: int = 5) -> List[SearchResult]:
        """Dense embedding vector search comparing query against standards."""
        standards = db.query(Standard).filter(Standard.is_deleted == False).all()
        if not standards:
            return []

        doc_texts = [f"{std.standard_code}: {std.title}. {std.scope or ''}" for std in standards]
        std_embeddings = embed_texts(doc_texts)
        query_vec = embed_texts([query])[0]

        # Cosine similarity
        scores = np.dot(std_embeddings, query_vec)
        
        results = []
        for std, score in zip(standards, scores):
            if score > 0.45: # Semantic relevance threshold
                results.append(SearchResult(
                    standard=std,
                    score=float(score),
                    match_type="semantic",
                    explanation=f"Semantic vector similarity score: {score:.3f}"
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def hybrid_search(
        self,
        db: Session,
        query: str,
        category_filter: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.35
    ) -> List[SearchResult]:
        """
        Reciprocal Rank Fusion (RRF) combining Exact (weight 0.4), Keyword (weight 0.3),
        and Semantic (weight 0.3) with reranking and unrelated standard filtering.
        """
        exact_results = self.exact_search(db, query)
        keyword_results = self.keyword_search(db, query, category_filter)
        semantic_results = self.semantic_search(db, query, top_k=top_k * 2)

        # RRF dictionary standard_id -> dict
        scores_by_id: Dict[str, Dict[str, Any]] = {}
        k_const = 60

        # Exact match
        for rank, res in enumerate(exact_results):
            sid = res.standard.id
            scores_by_id[sid] = {
                "standard": res.standard,
                "score": 0.4 * (1.0 / (k_const + rank + 1)) * 100,
                "match_types": [res.match_type],
                "explanations": [res.explanation]
            }

        # Keyword
        for rank, res in enumerate(keyword_results):
            sid = res.standard.id
            inc = 0.3 * (1.0 / (k_const + rank + 1)) * 100
            if sid in scores_by_id:
                scores_by_id[sid]["score"] += inc
                scores_by_id[sid]["match_types"].append(res.match_type)
                scores_by_id[sid]["explanations"].append(res.explanation)
            else:
                scores_by_id[sid] = {
                    "standard": res.standard,
                    "score": inc,
                    "match_types": [res.match_type],
                    "explanations": [res.explanation]
                }

        # Semantic
        for rank, res in enumerate(semantic_results):
            sid = res.standard.id
            inc = 0.3 * (1.0 / (k_const + rank + 1)) * 100
            if sid in scores_by_id:
                scores_by_id[sid]["score"] += inc
                scores_by_id[sid]["match_types"].append(res.match_type)
                scores_by_id[sid]["explanations"].append(res.explanation)
            else:
                scores_by_id[sid] = {
                    "standard": res.standard,
                    "score": inc,
                    "match_types": [res.match_type],
                    "explanations": [res.explanation]
                }

        # Normalize final scores to 0.0 - 1.0 range against theoretical maximum
        max_possible = (1.0 / (k_const + 1)) * 100
        combined = []
        for sid, item in scores_by_id.items():
            norm_score = min(1.0, item["score"] / max_possible)
            # Filter out unrelated standards below threshold
            if norm_score >= min_score:
                combined.append(SearchResult(
                    standard=item["standard"],
                    score=norm_score,
                    match_type="+".join(set(item["match_types"])),
                    explanation="; ".join(item["explanations"])
                ))

        # Rerank by score descending
        combined.sort(key=lambda x: x.score, reverse=True)
        return combined[:top_k]

def calculate_ir_metrics(
    retrieved_codes: List[str],
    relevant_codes: List[str],
    k: int = 5
) -> Dict[str, float]:
    """
    Calculate standard Information Retrieval metrics:
    Precision@K, Recall@K, MRR (Mean Reciprocal Rank), and NDCG@K.
    """
    retrieved_at_k = retrieved_codes[:k]
    
    # Precision@K
    hits = [code for code in retrieved_at_k if code in relevant_codes]
    precision = len(hits) / k if k > 0 else 0.0

    # Recall@K
    recall = len(hits) / len(relevant_codes) if relevant_codes else 0.0

    # MRR (Reciprocal rank of first relevant item)
    mrr = 0.0
    for rank, code in enumerate(retrieved_codes, 1):
        if code in relevant_codes:
            mrr = 1.0 / rank
            break

    # DCG and IDCG for NDCG@K
    dcg = 0.0
    for i, code in enumerate(retrieved_at_k, 1):
        rel = 1.0 if code in relevant_codes else 0.0
        dcg += rel / math.log2(i + 1)

    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant_codes), k) + 1))
    ndcg = (dcg / idcg) if idcg > 0 else 0.0

    return {
        f"Precision@{k}": round(precision, 4),
        f"Recall@{k}": round(recall, 4),
        "MRR": round(mrr, 4),
        f"NDCG@{k}": round(ndcg, 4)
    }

search_engine = HybridSearchEngine()
