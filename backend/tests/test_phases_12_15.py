import pytest
import os
from app.db.session import SessionLocal
from app.services.gap_detector import gap_detector
from app.services.conflict_detector import conflict_detector
from app.services.multilingual import (
    translate_term, get_standard_title_hindi,
    transliterate_standard_code, detect_language
)
from app.services.explainable_ai import explainer

@pytest.fixture
def auth_header(client):
    from app.core.rate_limit import RateLimitMiddleware
    RateLimitMiddleware.reset()
    resp = client.post("/api/v1/auth/login", json={"email": "officer@cpwd.gov.in", "password": os.environ["TEST_DEMO_PASSWORD"]})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ──────────────── PHASE 12: GAP DETECTION ────────────────

def test_gap_detection_missing_mandatory_civil(db_session):
    # IS 456 cited but IS 1786 and IS 269 missing for Civil works
    result = gap_detector.detect_gaps(db_session, ["IS 456"], categories=["Civil"])
    assert result.total_cited == 1
    assert result.gaps_found >= 1
    missing_codes = [g["standard_code"] for g in result.missing_standards]
    assert "IS 1786" in missing_codes or "IS 269" in missing_codes

def test_gap_detection_normative_reference_missing(db_session):
    # IS 456 requires IS 1786 (normative) — detect it's missing
    result = gap_detector.detect_gaps(db_session, ["IS 456"])
    normative_missing = [r["missing_normative"] for r in result.missing_normative_refs]
    assert "IS 1786" in normative_missing

def test_gap_detection_no_gaps_complete_civil(db_session):
    # All mandatory civil standards cited
    result = gap_detector.detect_gaps(db_session, ["IS 456", "IS 1786", "IS 269"], categories=["Civil"])
    mandatory_missing = [g["standard_code"] for g in result.missing_standards]
    assert "IS 456" not in mandatory_missing
    assert "IS 1786" not in mandatory_missing

def test_gap_detect_from_text(db_session):
    text = "All plain and reinforced concrete shall conform to IS 456:2000 in seismic zone IV."
    result = gap_detector.detect_gaps_from_text(db_session, text)
    assert result.total_cited >= 1

def test_api_detect_gaps(client, auth_header):
    payload = {"cited_standards": ["IS 456"], "categories": ["Civil"]}
    resp = client.post("/api/v1/analysis/detect-gaps", json=payload, headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_gaps_found" in data
    assert data["total_gaps_found"] >= 1

# ──────────────── PHASE 13: CONFLICT DETECTION ────────────────

def test_conflict_detection_steel_grade(db_session):
    text = "Reinforcement bars shall be Fe 415 grade. In seismic areas, Fe 500D grade shall be used."
    result = conflict_detector.detect_conflicts(db_session, text, [])
    assert any(c["conflict_type"] == "conflicting_material_grades" for c in result.conflicts)

def test_conflict_detection_version_conflict(db_session):
    text = "All concrete per IS 456."
    refs = ["IS 456:2000", "IS 456:1978"]
    result = conflict_detector.detect_conflicts(db_session, text, refs)
    assert any(c["conflict_type"] in ("version_conflict", "conflicting_versions") for c in result.conflicts)

def test_conflict_detection_isi_mark_contradiction(db_session):
    text = "All TMT bars must carry valid BIS Standard Mark (ISI mark). However, ISI mark is not required for imported bars."
    result = conflict_detector.detect_conflicts(db_session, text, [])
    assert any(c["conflict_type"] == "contradictory_certification_requirement" for c in result.conflicts)
    assert any(c["severity"] == "CRITICAL" for c in result.conflicts)

def test_conflict_detection_no_conflict(db_session):
    text = "All reinforced concrete shall be M25 grade per IS 456:2000. Steel shall be Fe 500D per IS 1786:2008."
    result = conflict_detector.detect_conflicts(db_session, text, ["IS 456:2000", "IS 1786:2008"])
    conflicts = [c for c in result.conflicts if c["severity"] in ("CRITICAL", "HIGH")]
    assert len(conflicts) == 0

def test_api_detect_conflicts(client, auth_header):
    payload = {
        "text": "Steel shall be Fe 415 for slabs and Fe 500D for columns.",
        "cited_references": []
    }
    resp = client.post("/api/v1/analysis/detect-conflicts", json=payload, headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_conflicts" in data
    assert data["total_conflicts"] >= 1

# ──────────────── PHASE 14: MULTILINGUAL ────────────────

def test_translate_term_to_hindi():
    assert translate_term("Civil", "hi") == "सिविल"
    assert translate_term("MANDATORY_COMPLIANT", "hi") == "अनिवार्य अनुपालन — सही"
    assert translate_term("CRITICAL", "hi") == "अत्यंत महत्वपूर्ण"
    assert translate_term("Insufficient verified evidence.", "hi") == "पर्याप्त सत्यापित साक्ष्य उपलब्ध नहीं है।"

def test_hindi_standard_title():
    title = get_standard_title_hindi("IS 456")
    assert title == "सादा और प्रबलित कंक्रीट — अभ्यास की संहिता"

def test_transliterate_standard_code():
    result = transliterate_standard_code("IS 456")
    assert "आई.एस." in result
    assert "456" in result

def test_detect_language_english():
    assert detect_language("All concrete works shall conform to IS 456:2000.") == "en"

def test_detect_language_hindi():
    assert detect_language("सादा और प्रबलित कंक्रीट — अभ्यास की संहिता आई.एस. ४५६") == "hi"

def test_api_translate(client):
    resp = client.get("/api/v1/analysis/translate?term=Civil&lang=hi")
    assert resp.status_code == 200
    assert resp.json()["translation"] == "सिविल"

def test_api_hindi_standard_title(client):
    resp = client.get("/api/v1/analysis/standard-hindi-title?standard_code=IS+456")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hindi_title"] is not None
    assert "आई.एस." in data["transliterated_code"]

# ──────────────── PHASE 15: EXPLAINABLE AI ────────────────

def test_explain_search_with_results():
    results = [{
        "standard_code": "IS 456",
        "title": "Plain and Reinforced Concrete",
        "match_type": "exact+keyword",
        "score": 0.95,
        "explanation": "Exact code match on IS 456"
    }]
    exp = explainer.explain_search_result("IS 456 concrete", results, "hybrid")
    assert "IS 456" in exp["decision"]
    assert exp["confidence"] == 0.95
    assert len(exp["reasoning_steps"]) >= 4

def test_explain_search_no_results():
    exp = explainer.explain_search_result("alien quantum propulsion", [], "hybrid")
    assert exp["confidence"] == 0.0
    assert "No standards found" in exp["decision"]

def test_explain_gap():
    gap = {"standard_code": "IS 1786", "reason": "Mandatory for Civil domain.", "severity": "HIGH"}
    explanation = explainer.explain_gap(gap)
    assert "IS 1786" in explanation
    assert "HIGH" in explanation

def test_explain_conflict():
    conflict = {
        "conflict_type": "conflicting_material_grades",
        "description": "Fe 415 and Fe 500D both specified.",
        "severity": "HIGH",
        "recommendation": "Specify a single grade."
    }
    explanation = explainer.explain_conflict(conflict)
    assert "HIGH" in explanation
    assert "Fe 415" in explanation

def test_explain_rag_refusal():
    exp = explainer.explain_rag_refusal("alien spacecraft")
    assert exp["confidence"] == 0.0
    assert "refused" in exp["decision"].lower()
    assert len(exp["reasoning_steps"]) >= 5

def test_explain_version_superseded():
    result = {
        "standard_code": "IS 456",
        "status": "superseded",
        "cited_version": "IS 456:1978",
        "superseded_by": "IS 456:2000",
        "current_version": "IS 456:2000"
    }
    explanation = explainer.explain_version_check(result)
    assert "CRITICAL" in explanation
    assert "IS 456:1978" in explanation
    assert "IS 456:2000" in explanation
