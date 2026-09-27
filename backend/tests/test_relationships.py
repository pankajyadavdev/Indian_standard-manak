import pytest
from app.db.session import SessionLocal
from app.services.relationship_engine import relationship_engine

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. Test Normative Reference (IS 456 -> IS 1786)
def test_normative_reference(db_session):
    rels = relationship_engine.get_relationships(db_session, "IS 456", rel_type="normative")
    assert len(rels) >= 1
    assert any(r.target_code == "IS 1786" for r in rels)
    assert rels[0].relationship_type == "normative"

# 2. Test Test Method Reference (IS 1786 -> IS 1608)
def test_test_method_reference(db_session):
    rels = relationship_engine.get_relationships(db_session, "IS 1786", rel_type="test_method")
    assert len(rels) >= 1
    assert any(r.target_code == "IS 1608" for r in rels)
    assert rels[0].relationship_type == "test_method"

# 3. Test Safety Reference (IS 732 -> IS 3043)
def test_safety_reference(db_session):
    rels = relationship_engine.get_relationships(db_session, "IS 732", rel_type="safety")
    assert len(rels) >= 1
    assert any(r.target_code == "IS 3043" for r in rels)
    assert rels[0].relationship_type == "safety"

# 4. Test Installation Reference (IS 456 -> IS 732)
def test_installation_reference(db_session):
    rels = relationship_engine.get_relationships(db_session, "IS 456", rel_type="installation")
    assert len(rels) >= 1
    assert any(r.target_code == "IS 732" for r in rels)

# 5. Test Material Reference (IS 456 -> IS 269)
def test_material_reference(db_session):
    rels = relationship_engine.get_relationships(db_session, "IS 456", rel_type="material")
    assert len(rels) >= 1
    assert any(r.target_code == "IS 269" for r in rels)

# 6. Test Terminology Reference (IS 456 -> IS 1950)
def test_terminology_reference(db_session):
    rels = relationship_engine.get_relationships(db_session, "IS 456", rel_type="terminology")
    assert len(rels) >= 1
    assert any(r.target_code == "IS 1950" for r in rels)

# 7. Test Related Standards Reference (IS 2062 -> IS 1786)
def test_related_standards_reference(db_session):
    rels = relationship_engine.get_relationships(db_session, "IS 2062", rel_type="related")
    assert len(rels) >= 1
    assert any(r.target_code == "IS 1786" for r in rels)

# 8. Test Relationship Graph Traversal
def test_relationship_graph(db_session):
    graph = relationship_engine.get_relationship_graph(db_session, "IS 456", max_depth=2)
    assert graph["root"] == "IS 456"
    assert graph["total_nodes"] >= 4
    assert graph["total_edges"] >= 3
    node_ids = [n["id"] for n in graph["nodes"]]
    assert "IS 456" in node_ids
    assert "IS 1786" in node_ids
    assert "IS 1608" in node_ids # Depth 2 transitive dependency!

# 9. Test API Endpoint
def test_api_relationships_endpoint(client):
    resp = client.get("/api/v1/standards/IS 456/relationships")
    assert resp.status_code == 200
    data = resp.json()
    assert data["standard_code"] == "IS 456"
    assert data["total_relationships"] >= 4
    rel_types = {r["relationship_type"] for r in data["relationships"]}
    assert "normative" in rel_types
    assert "material" in rel_types

def test_api_relationships_graph_endpoint(client):
    resp = client.get("/api/v1/standards/IS 456/relationships?graph=true")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) >= 4
