import json
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.services.conflict_detector import conflict_detector
from app.services.entity_extractor import extract_entities
from app.services.gap_detector import gap_detector
from app.services.search_service import calculate_ir_metrics, search_engine
from app.services.version_engine import version_engine


DATASET = json.loads((Path(__file__).parent / "fixtures" / "ai_evaluation.json").read_text(encoding="utf-8"))


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_evaluation_dataset_covers_required_quality_cases():
    ids = {case["id"] for case in DATASET["search_cases"]}
    ids.update(case["id"] for case in DATASET["no_match_cases"])
    assert {"civil_concrete", "multiple_standards", "long_tender"} <= ids
    assert {"unrelated_physics", "injected_standard"} <= ids
    analysis = DATASET["analysis_cases"]
    assert analysis["old_standard_reference"]
    assert analysis["normative_gap_input"]
    assert analysis["conflicting_tender"]
    assert analysis["hindi_query"]
    assert analysis["malicious_document"]


def test_search_retrieval_quality_metrics(db_session):
    metrics = []
    case_results = []
    for case in DATASET["search_cases"]:
        results = search_engine.hybrid_search(db_session, case["query"], top_k=5, min_score=0.35)
        retrieved = [item.standard.standard_code for item in results]
        metrics.append(calculate_ir_metrics(retrieved, case["relevant_codes"], k=3))
        case_results.append({"id": case["id"], "retrieved": retrieved})

    mean = {key: sum(item[key] for item in metrics) / len(metrics) for key in metrics[0]}
    print("AI evaluation cases:", json.dumps(case_results))
    print("AI evaluation mean metrics:", json.dumps(mean))
    assert mean["Recall@3"] >= 0.8
    assert mean["MRR"] >= 0.8
    assert mean["NDCG@3"] >= 0.8


def test_no_match_old_version_gaps_conflicts_and_malicious_document(db_session):
    for case in DATASET["no_match_cases"]:
        results = search_engine.hybrid_search(db_session, case["query"], top_k=5, min_score=0.7)
        assert results == [], case["id"]

    version = version_engine.check_version(db_session, DATASET["analysis_cases"]["old_standard_reference"])
    assert version.status == "superseded"

    gaps = gap_detector.detect_gaps(db_session, DATASET["analysis_cases"]["normative_gap_input"])
    missing = {item["missing_normative"] for item in gaps.missing_normative_refs}
    assert "IS 1786" in missing

    conflicts = conflict_detector.detect_conflicts(db_session, DATASET["analysis_cases"]["conflicting_tender"])
    assert conflicts.total_conflicts >= 1

    entities = extract_entities(DATASET["analysis_cases"]["malicious_document"])
    assert "IS 456:2000" in entities.standards_cited
    assert search_engine.exact_search(db_session, "IS 999999") == []


def test_hindi_standard_title_retrieves_its_canonical_standard(db_session):
    results = search_engine.hybrid_search(
        db_session,
        DATASET["analysis_cases"]["hindi_query"],
        top_k=5,
        min_score=0.35,
    )
    assert "IS 456" in [item.standard.standard_code for item in results]
