import pytest
from app.db.session import SessionLocal
from app.services.rag_engine import rag_engine, INSUFFICIENT_EVIDENCE_MSG
from app.services.embedding_service import vector_index

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

# 1. Test grounded query with valid evidence
def test_rag_with_valid_evidence(db_session):
    query = "What is the code of practice for plain and reinforced concrete?"
    res = rag_engine.generate_grounded_explanation(db_session, query)
    
    assert res.is_verified is True
    assert len(res.evidence) > 0
    assert "IS 456" in res.recommended_standards
    assert "IS 456" in res.explanation
    assert INSUFFICIENT_EVIDENCE_MSG not in res.explanation

# 2. Test absent evidence query strictly returns "Insufficient verified evidence."
def test_rag_absent_evidence_strict_refusal(db_session):
    absent_query = "What is the BIS standard specification for quantum antimatter propulsion reactors?"
    res = rag_engine.generate_grounded_explanation(db_session, absent_query)

    assert res.is_verified is False
    assert res.explanation == INSUFFICIENT_EVIDENCE_MSG
    assert len(res.evidence) == 0
    assert len(res.recommended_standards) == 0

# 3. Test nonexistent standard code query strictly returns "Insufficient verified evidence."
def test_rag_nonexistent_standard_code(db_session):
    query = "Comply with IS 99999999 for imaginary materials"
    res = rag_engine.generate_grounded_explanation(db_session, query)

    assert res.is_verified is False
    assert res.explanation == INSUFFICIENT_EVIDENCE_MSG
    assert len(res.evidence) == 0

# 4. Test document chunk retrieval and citation
def test_rag_with_document_context(db_session):
    doc_id = "test-doc-xyz"
    vector_index.add_chunks([{
        "document_id": doc_id,
        "chunk_index": 0,
        "text": "All internal building wires shall be PVC insulated conforming to IS 694 with high conductivity copper.",
        "page_number": 3,
        "char_start": 0,
        "char_end": 105,
        "word_count": 18
    }])

    query = "internal building wires PVC insulated copper IS 694"
    res = rag_engine.generate_grounded_explanation(db_session, query, document_id=doc_id)

    assert res.is_verified is True
    assert any("Document Page 3" in e.source for e in res.evidence)
    assert any("IS 694" in s for s in res.recommended_standards)

# 5. Test API endpoint POST /api/v1/analysis/rag-explain
def test_rag_api_endpoint(client, auth_header):
    payload = {
        "query": "high strength deformed steel bars reinforcement concrete IS 1786"
    }
    resp = client.post("/api/v1/analysis/rag-explain", json=payload, headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_verified"] is True
    assert "IS 1786" in data["recommended_standards"]
    assert len(data["evidence"]) >= 1

def test_rag_api_endpoint_insufficient_evidence(client, auth_header):
    payload = {
        "query": "alien spacecraft levitation antigravity field specification"
    }
    resp = client.post("/api/v1/analysis/rag-explain", json=payload, headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_verified"] is False
    assert data["explanation"] == INSUFFICIENT_EVIDENCE_MSG
    assert len(data["evidence"]) == 0
