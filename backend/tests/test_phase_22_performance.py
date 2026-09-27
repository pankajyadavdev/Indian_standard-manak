from concurrent.futures import ThreadPoolExecutor

import pytest

from app.db.session import SessionLocal
from app.models.standard import Standard
from app.services.embedding_service import generate_fallback_embedding
from app.services.search_service import HybridSearchEngine, search_engine


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_standard_embeddings_are_cached_and_invalidated(db_session, monkeypatch):
    import app.services.search_service as search_module

    original_embed = search_module.embed_texts
    calls = []

    def counted_embed(texts):
        calls.append(len(texts))
        return original_embed(texts)

    monkeypatch.setattr(search_module, "embed_texts", counted_embed)
    engine = HybridSearchEngine()
    engine.semantic_search(db_session, "concrete code", top_k=3)
    assert len(calls) == 2  # one catalogue batch and one query

    engine.semantic_search(db_session, "steel reinforcement", top_k=3)
    assert len(calls) == 3  # query only; catalogue embeddings were reused

    standard = db_session.query(Standard).filter(Standard.standard_code == "IS 456").one()
    previous_title = standard.title
    try:
        standard.title = f"{previous_title} cache invalidation fixture"
        db_session.commit()
        engine.semantic_search(db_session, "concrete code", top_k=3)
        assert len(calls) == 5
    finally:
        standard.title = previous_title
        db_session.commit()


def test_warm_hybrid_search_completes_for_parallel_sessions():
    def search_once(_):
        db = SessionLocal()
        try:
            return search_engine.hybrid_search(db, "reinforcement steel IS 1786", top_k=3)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=4) as executor:
        outputs = list(executor.map(search_once, range(8)))
    assert len(outputs) == 8
    assert all(any(item.standard.standard_code == "IS 1786" for item in result) for result in outputs)


def test_offline_fallback_preserves_lexical_similarity_without_random_vectors():
    import numpy as np

    query = generate_fallback_embedding("plain reinforced concrete code")
    related = generate_fallback_embedding("reinforced concrete structural code")
    unrelated = generate_fallback_embedding("quantum spacecraft propulsion")
    assert np.allclose(query, generate_fallback_embedding("plain reinforced concrete code"))
    assert float(np.dot(query, related)) > float(np.dot(query, unrelated))
