import pytest
from app.db.session import SessionLocal
from app.services.version_engine import version_engine

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. Current version — no year specified
def test_check_current_version_no_year(db_session):
    res = version_engine.check_version(db_session, "IS 456")
    assert res.status in ("current", "unknown_version")
    assert res.standard_code == "IS 456"
    assert res.current_version is not None

# 2. Current version — correct year specified
def test_check_current_version_with_correct_year(db_session):
    from app.models.standard import Standard, StandardVersion
    db = db_session
    std = db.query(Standard).filter(Standard.standard_code == "IS 456").first()
    cur_ver = next((v for v in std.versions if v.is_current), None)
    res = version_engine.check_version(db, f"IS 456:{cur_ver.year}")
    assert res.status == "current"
    assert res.is_current is True
    assert res.conflict_alert is None

# 3. Superseded version detection
def test_check_superseded_version(db_session):
    from app.models.standard import Standard, StandardVersion
    db = db_session
    std = db.query(Standard).filter(Standard.standard_code == "IS 456").first()
    cur_ver = next((v for v in std.versions if v.is_current), None)

    # Create a historical superseded version
    old_ver = StandardVersion(
        standard_id=std.id,
        year=1978,
        version_label="IS 456:1978",
        is_current=False
    )
    db.add(old_ver)
    db.flush()
    old_ver.superseded_by_id = cur_ver.id
    db.commit()

    res = version_engine.check_version(db, "IS 456:1978")
    assert res.status == "superseded"
    assert res.is_current is False
    assert res.conflict_alert is not None
    assert "SUPERSEDED" in res.conflict_alert or "CRITICAL" in res.conflict_alert
    assert res.superseded_by is not None

# 4. Not-found standard
def test_check_version_not_found(db_session):
    res = version_engine.check_version(db_session, "IS 99999")
    assert res.status == "not_found"
    assert res.is_current is False
    assert res.recommendation is not None

# 5. Parse references
def test_parse_standard_reference():
    parsed = version_engine.parse_standard_reference("IS 1786:2008 Amendment No. 2")
    assert parsed["standard_code"] == "IS 1786"
    assert parsed["year"] == 2008
    assert parsed["amendment"] == 2

def test_parse_standard_reference_no_year():
    parsed = version_engine.parse_standard_reference("IS 732")
    assert parsed["standard_code"] == "IS 732"
    assert parsed["year"] is None
    assert parsed["amendment"] is None

# 6. Conflict detection — contradictory versions in same tender
def test_detect_conflicting_versions(db_session):
    references = ["IS 456:2000", "IS 456:1978", "IS 1786:2008"]
    conflicts = version_engine.detect_version_conflicts(db_session, references)
    assert any(c["conflict_type"] == "conflicting_versions" for c in conflicts)
    c = next(c for c in conflicts if c["conflict_type"] == "conflicting_versions")
    assert c["standard_code"] == "IS 456"

# 7. API endpoint — check-version
def test_api_check_version(client):
    resp = client.get("/api/v1/standards/check-version?reference=IS+1786")
    assert resp.status_code == 200
    data = resp.json()
    assert data["standard_code"] == "IS 1786"
    assert data["is_current"] is True

# 8. API endpoint — detect-conflicts
def test_api_detect_conflicts(client):
    payload = {"references": ["IS 456:2000", "IS 456:1978"]}
    resp = client.post("/api/v1/standards/detect-conflicts", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_conflicts"] >= 1
