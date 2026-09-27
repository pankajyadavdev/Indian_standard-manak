import pytest
import os
from app.services.entity_extractor import extract_entities

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

# 1. Real-World Civil & Concrete Tender Example
def test_extract_civil_tender_specifications():
    text = """
    TENDER NOTICE NO: CPWD/2026/CIVIL/042
    Project: Construction of Multi-Storey Administrative Complex in Seismic Zone IV.
    Technical Specifications:
    1. Plain and Reinforced Concrete: Ready mix concrete shall be Grade M35 conforming strictly to IS 456:2000.
       Minimum characteristic compressive strength of 35 N/mm2 at 28 days is required.
    2. Steel Reinforcement: High strength deformed steel bars conforming to IS 1786:2008 Grade Fe 500D.
       Diameter sizes: 12mm dia, 16mm dia, and 25mm dia.
       Minimum elongation of 16% and yield stress of 500 N/mm2.
    3. Exposure Condition: Severe exposure in coastal marine corrosive environment with minimum clear cover of 50mm.
    4. Testing: Mandatory tensile test and bend and rebend test for every 50 MT batch.
    5. Certifications: All TMT rebars must carry valid BIS standard mark (ISI mark).
    """
    res = extract_entities(text)
    
    assert any("concrete" in p.lower() or "rebars" in p.lower() for p in res.products)
    assert "Civil" in res.categories
    assert any("Fe 500D" in m for m in res.materials)
    assert any("M 35" in m or "M35" in m for m in res.materials)
    assert any("16mm" in d or "25mm" in d for d in res.dimensions)
    assert any("characteristic compressive strength" in p.lower() or "elongation" in p.lower() for p in res.performance)
    assert any("seismic" in a.lower() for a in res.applications)
    assert any("coastal" in e.lower() or "marine" in e.lower() for e in res.environments)
    assert any("bend and rebend" in t.lower() or "tensile test" in t.lower() for t in res.testing)
    assert any("clear cover" in i.lower() for i in res.installation)
    assert any("ISI mark" in c or "BIS" in c for c in res.certification_hints)
    assert any("IS 456:2000" in s for s in res.standards_cited)
    assert any("IS 1786:2008" in s for s in res.standards_cited)
    assert res.confidence_score >= 0.8

# 2. Real-World Electrical Tender Example
def test_extract_electrical_tender_specifications():
    text = """
    TECHNICAL SPECIFICATION FOR INTERNAL ELECTRIFICATION (RDSO / RAILWAYS)
    Supply and installation of 1100V grade PVC insulated unsheathed electric wires conforming to IS 694.
    Conductor shall be annealed copper conductor of size 4 sq mm and 6 sq mm.
    Insulation shall be flame retardant low smoke (FRLS) for fire safety.
    System wiring must follow conduit wiring as per IS 732.
    Protective earthing system and earth fault protection must satisfy IS 3043.
    Mandatory testing: Spark test and insulation resistance test before energizing.
    Manufacturer must hold valid ISI mark under mandatory QCO order.
    """
    res = extract_entities(text)

    assert any("wire" in p.lower() or "cable" in p.lower() for p in res.products)
    assert "Electrical" in res.categories
    assert any("copper conductor" in m.lower() or "PVC" in m for m in res.materials)
    assert any("4 sq mm" in d for d in res.dimensions)
    assert any("1100V" in c or "1100 V" in c for c in res.capacities)
    assert any("flame retardant" in s.lower() or "FRLS" in s or "earthing" in s.lower() for s in res.safety)
    assert any("spark test" in t.lower() or "insulation resistance" in t.lower() for t in res.testing)
    assert any("conduit wiring" in i.lower() for i in res.installation)
    assert any("QCO" in c or "ISI mark" in c for c in res.certification_hints)
    assert any("IS 694" in s for s in res.standards_cited)
    assert any("IS 732" in s for s in res.standards_cited)
    assert any("IS 3043" in s for s in res.standards_cited)

# 3. Real-World Mechanical & Water Supply Piping Example
def test_extract_mechanical_piping_specifications():
    text = """
    TENDER FOR WATER DISTRIBUTION NETWORK (CPWD)
    Supply of mild steel pipes and fittings conforming to IS 1239 for potable water supply.
    Nominal bore: NB 150 mm, underground buried installation.
    Every pipe length must undergo hydrostatic pressure test without leakage.
    Products must bear BIS standard mark.
    """
    res = extract_entities(text)

    assert any("pipe" in p.lower() for p in res.products)
    assert "Mechanical" in res.categories
    assert any("mild steel" in m.lower() for m in res.materials)
    assert any("150 mm" in d for d in res.dimensions)
    assert any("potable water supply" in a.lower() for a in res.applications)
    assert any("underground buried" in e.lower() for e in res.environments)
    assert any("hydrostatic pressure test" in t.lower() for t in res.testing)
    assert any("BIS" in c for c in res.certification_hints)
    assert any("IS 1239" in s for s in res.standards_cited)

# 4. Real-World Structural Steel Example
def test_extract_structural_steel_specifications():
    text = """
    TECHNICAL SPECIFICATION FOR STRUCTURAL STEEL FABRICATION
    Structural steel plates and sections conforming to IS 2062 Grade E250.
    Minimum tensile strength of 410 MPa and yield stress of 250 MPa.
    Charpy V-notch impact test at 0 degree C required.
    Mandatory compliance with Ministry of Steel Quality Control Order (QCO).
    """
    res = extract_entities(text)

    assert any("structural steel" in p.lower() for p in res.products)
    assert "Metallurgy" in res.categories
    assert any("E 250" in m or "E250" in m for m in res.materials)
    assert any("tensile strength" in p.lower() or "yield stress" in p.lower() for p in res.performance)
    assert any("charpy" in t.lower() for t in res.testing)
    assert any("QCO" in c or "Quality Control Order" in c for c in res.certification_hints)
    assert any("IS 2062" in s for s in res.standards_cited)

# 5. API Endpoint Tests
def test_analysis_endpoint_custom_text(client, auth_header):
    payload = {
        "custom_text": "Supply of Fe 500D TMT rebars complying with IS 1786:2008 with mandatory ISI mark."
    }
    response = client.post("/api/v1/analysis/extract-specifications", json=payload, headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert data["total_entities_found"] > 0
    assert data["standards_matched_count"] >= 1
    assert "IS 1786:2008" in data["entities"]["standards_cited"]

def test_analysis_endpoint_empty_text(client, auth_header):
    payload = {"custom_text": "    "}
    response = client.post("/api/v1/analysis/extract-specifications", json=payload, headers=auth_header)
    assert response.status_code == 400
    assert "no readable content" in response.json()["detail"]

def test_analysis_endpoint_missing_payload(client, auth_header):
    payload = {}
    response = client.post("/api/v1/analysis/extract-specifications", json=payload, headers=auth_header)
    assert response.status_code == 400
    assert "Either document_id or custom_text" in response.json()["detail"]
