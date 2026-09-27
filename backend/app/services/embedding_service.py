import numpy as np
import faiss
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger

_model = None

def get_embedding_model():
    """Lazy load SentenceTransformer model or fallback to hash-based embeddings."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Load local model or download lightweight 384-d model
            _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
            logger.info(f"Loaded embedding model: {settings.EMBEDDING_MODEL_NAME}")
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer ({e}). Using deterministic embedding fallback.")
            _model = "fallback"
    return _model

def generate_fallback_embedding(text: str, dim: int = 384) -> np.ndarray:
    """Generate deterministic normalized pseudo-semantic vector from text hash."""
    import hashlib
    h = hashlib.sha256(text.encode("utf-8")).digest()
    np.random.seed(int.from_bytes(h[:4], "big"))
    vec = np.random.randn(dim).astype("float32")
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
            embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
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
