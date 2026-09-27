import pytest
import os
from app.db.session import SessionLocal
from app.services.certification_engine import certification_engine, COMPLIANCE_STATUS

@pytest.fixture
def auth_header(client):
    from app.core.rate_limit import RateLimitMiddleware
    RateLimitMiddleware.reset()
    resp = client.post("/api/v1/auth/login", json={
        "email": "officer@cpwd.gov.in",
        "password": os.environ["TEST_DEMO_PASSWORD"]
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

# 1. Mandatory QCO standard with ISI mark requirement in clause
def test_mandatory_qco_compliant(db_session):
    res = certification_engine.check_certification(
        db_session, "IS 1786",
        tender_clause_text="All TMT rebars must carry valid BIS standard mark (ISI mark)."
    )
    assert res.compliance_status == COMPLIANCE_STATUS["MANDATORY_COMPLIANT"]
    assert res.is_mandatory is True
    assert res.alert is None

# 2. Mandatory QCO standard WITHOUT ISI mark requirement → COMPLIANCE FAIL
def test_mandatory_qco_missing_isi_mark(db_session):
    res = certification_engine.check_certification(
        db_session, "IS 1786",
        tender_clause_text="Supply TMT rebars conforming to IS 1786:2008 Grade Fe 500D."
    )
    assert res.compliance_status == COMPLIANCE_STATUS["MANDATORY_MISSING"]
    assert res.is_mandatory is True
    assert res.alert is not None
    assert "COMPLIANCE FAIL" in res.alert or "mandatory QCO" in res.alert.lower()

# 3. Mandatory QCO — no tender clause provided → treated as compliant (check-only mode)
def test_mandatory_qco_no_clause(db_session):
    res = certification_engine.check_certification(db_session, "IS 694")
    assert res.compliance_status == COMPLIANCE_STATUS["MANDATORY_COMPLIANT"]
    assert res.is_mandatory is True

# 4. Non-mandatory (advisory) certification
def test_advisory_certification(db_session):
    db = db_session
    # IS 2062 has advisory certification in seed data
    res = certification_engine.check_certification(db, "IS 2062")
    assert res.compliance_status in (
        COMPLIANCE_STATUS["ADVISORY"],
        COMPLIANCE_STATUS["MANDATORY_COMPLIANT"],
        COMPLIANCE_STATUS["NOT_APPLICABLE"]
    )

# 5. Unknown / unlisted standard
def test_certification_unknown_standard(db_session):
    res = certification_engine.check_certification(db_session, "IS 99999")
    assert res.compliance_status == COMPLIANCE_STATUS["UNKNOWN"]
    assert res.alert is not None
    assert res.recommendation is not None

# 6. Full tender evaluation — mixed compliant and non-compliant
def test_evaluate_tender_mixed(db_session):
    result = certification_engine.evaluate_tender(
        db_session,
        standard_codes=["IS 1786", "IS 694", "IS 732", "IS 99999"],
        tender_clause_text="All materials must carry valid ISI mark as per BIS standard mark mandate."
    )
    assert result["standards_evaluated"] == 4
    assert result["summary"]["MANDATORY_COMPLIANT"] >= 2
    assert result["summary"]["UNKNOWN"] >= 1

# 7. Full tender evaluation → NON_COMPLIANT if ISI mark missing
def test_evaluate_tender_non_compliant(db_session):
    result = certification_engine.evaluate_tender(
        db_session,
        standard_codes=["IS 1786", "IS 694"],
        tender_clause_text="Supply materials conforming to IS 1786 and IS 694."
    )
    # ISI mark not mentioned → NON_COMPLIANT
    assert result["overall_status"] == "NON_COMPLIANT"
    assert result["summary"]["MANDATORY_MISSING"] >= 1

# 8. API endpoint test
def test_api_certification_check(client, auth_header):
    payload = {
        "standards": ["IS 1786", "IS 694"],
        "tender_clause_text": "All products must carry valid BIS Standard Mark (ISI mark) under QCO."
    }
    resp = client.post("/api/v1/analysis/certification-check", json=payload, headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "COMPLIANT"
    assert data["standards_evaluated"] == 2
