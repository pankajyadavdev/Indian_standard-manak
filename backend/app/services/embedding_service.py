import numpy as np
import faiss
import hashlib
import re
import threading
from typing import List, Dict, Any
from app.core.config import settings
from app.core.logging import logger

_model = None
_model_lock = threading.Lock()


def embedding_status() -> str:
    if _model is None:
        return "not_loaded"
    if _model == "fallback":
        return "lexical_fallback"
    return "ready"

def get_embedding_model():
    """Lazy load the pinned SentenceTransformer model or use a lexical fallback."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    _model = SentenceTransformer(
                        settings.EMBEDDING_MODEL_NAME,
                        revision=settings.EMBEDDING_MODEL_REVISION,
                    )
                    logger.info(f"Loaded embedding model: {settings.EMBEDDING_MODEL_NAME}@{settings.EMBEDDING_MODEL_REVISION}")
                except Exception as e:
                    logger.warning(f"Could not load SentenceTransformer ({e}). Using deterministic lexical fallback.")
                    _model = "fallback"
    return _model

def generate_fallback_embedding(text: str, dim: int = 384) -> np.ndarray:
    """Generate a stable feature-hashed lexical vector when the model is unavailable."""
    vec = np.zeros(dim, dtype="float32")
    words = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
    features = [(f"w:{word}", 1.0) for word in words]
    for word in words:
        if len(word) >= 3:
            features.extend((f"c:{word[index:index + 3]}", 0.2) for index in range(len(word) - 2))
    if not features:
        features = [("empty:" + text, 1.0)]
    for feature, weight in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vec[index] += sign * weight
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec

def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Generate L2-normalized 384-dimensional dense vectors for a list of texts.
    """
    if not texts:
        return np.empty((0, 384), dtype="float32")

    model = get_embedding_model()
    if model != "fallback":
        try:
            embeddings = model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embeddings.astype("float32")
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}. Falling back to deterministic vectors.")

    # Fallback path
    vectors = [generate_fallback_embedding(t) for t in texts]
    return np.vstack(vectors)

class VectorIndex:
    """
    In-memory FAISS Index supporting cosine similarity search and metadata retrieval.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension) # Cosine similarity with normalized vectors
        self.metadata: List[Dict[str, Any]] = []

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """Embed text chunks and add them to the FAISS index with metadata."""
        if not chunks:
            return

        texts = [c["text"] for c in chunks]
        embeddings = embed_texts(texts)
        self.index.add(embeddings)
        self.metadata.extend(chunks)
        logger.info(f"Indexed {len(chunks)} chunks in FAISS index (Total: {self.index.ntotal})")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search index for top_k most similar chunks to query."""
        if self.index.ntotal == 0:
            return []

        query_vec = embed_texts([query])
        scores, indices = self.index.search(query_vec, min(top_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = dict(self.metadata[idx])
            meta["similarity_score"] = float(score)
            results.append(meta)

        return results

    def clear(self):
        """Reset index and metadata."""
        self.index.reset()
        self.metadata.clear()

# Global default vector index instance
vector_index = VectorIndex()
