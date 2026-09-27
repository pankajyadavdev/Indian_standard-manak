import pytest
from app.db.session import SessionLocal
from app.services.search_service import search_engine, calculate_ir_metrics

@pytest.fixture
def auth_header(client):
    from app.core.rate_limit import RateLimitMiddleware
    RateLimitMiddleware.reset()
    resp = client.post("/api/v1/auth/login", json={
        "email": "officer@cpwd.gov.in",
        "password": "Officer@12345"
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. Exact Search Test
def test_exact_search(db_session):
    results = search_engine.exact_search(db_session, "IS 456")
    assert len(results) >= 1
    assert results[0].standard.standard_code == "IS 456"
    assert results[0].score == 1.0

# 2. Keyword Search Test
def test_keyword_search(db_session):
    results = search_engine.keyword_search(db_session, "deformed steel bars reinforcement")
    assert len(results) >= 1
    codes = [r.standard.standard_code for r in results]
    assert "IS 1786" in codes

# 3. Semantic Search Test
def test_semantic_search(db_session):
    results = search_engine.semantic_search(db_session, "building wire insulation pvc conductor", top_k=3)
    assert len(results) >= 1
    codes = [r.standard.standard_code for r in results]
    assert "IS 694" in codes

# 4. Metadata Filtering Test
def test_metadata_filtering(db_session):
    electrical_results = search_engine.keyword_search(db_session, "installation", category_filter="Electrical")
    for r in electrical_results:
        assert r.standard.category == "Electrical"

# 5. Hybrid Search with RRF Reranking
def test_hybrid_search(db_session):
    results = search_engine.hybrid_search(db_session, "plain and reinforced concrete code of practice", top_k=5)
    assert len(results) >= 1
    assert results[0].standard.standard_code == "IS 456"

# 6. Unrelated Standards Filtering (Must NOT recommend unrelated standards)
def test_unrelated_query_no_hallucination(db_session):
    unrelated_query = "quantum semiconductor photon laser satellite propulsion unit"
    results = search_engine.hybrid_search(db_session, unrelated_query, min_score=0.7)
    # The system must not recommend concrete or electrical building codes for satellite lasers
    assert len(results) == 0

# 7. IR Evaluation: Measure Precision@K, Recall@K, MRR, NDCG
def test_ir_metrics_evaluation(db_session):
    benchmark_queries = [
        ("IS 456 concrete design", ["IS 456"]),
        ("high strength deformed bars for concrete", ["IS 1786"]),
        ("pvc cables for electric lighting", ["IS 694"]),
        ("electrical wiring code of practice", ["IS 732"]),
        ("earthing and grounding practice", ["IS 3043"]),
        ("hot rolled structural steel plates", ["IS 2062"])
    ]

    all_precision = []
    all_recall = []
    all_mrr = []
    all_ndcg = []

    for query, relevant in benchmark_queries:
        search_res = search_engine.hybrid_search(db_session, query, top_k=5, min_score=0.1)
        retrieved = [r.standard.standard_code for r in search_res]
        metrics = calculate_ir_metrics(retrieved, relevant, k=3)
        all_precision.append(metrics["Precision@3"])
        all_recall.append(metrics["Recall@3"])
        all_mrr.append(metrics["MRR"])
        all_ndcg.append(metrics["NDCG@3"])

    avg_precision = sum(all_precision) / len(all_precision)
    avg_recall = sum(all_recall) / len(all_recall)
    avg_mrr = sum(all_mrr) / len(all_mrr)
    avg_ndcg = sum(all_ndcg) / len(all_ndcg)

    assert avg_recall >= 0.8, f"Mean Recall@3 ({avg_recall:.2f}) should be >= 0.8"
    assert avg_mrr >= 0.8, f"MRR ({avg_mrr:.2f}) should be >= 0.8"
    assert avg_ndcg >= 0.8, f"NDCG@3 ({avg_ndcg:.2f}) should be >= 0.8"

# 8. API Search Endpoint Test
def test_api_search_endpoint(client, auth_header):
    payload = {
        "query": "earthing installation guide",
        "search_type": "hybrid",
        "top_k": 3
    }
    resp = client.post("/api/v1/standards/search", json=payload, headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] >= 1
    codes = [r["standard_code"] for r in data["results"]]
    assert "IS 3043" in codes
