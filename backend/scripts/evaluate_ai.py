"""Evaluate the deterministic standards retrieval and analysis fixture dataset."""
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.conflict_detector import conflict_detector
from app.services.entity_extractor import extract_entities
from app.services.gap_detector import gap_detector
from app.services.search_service import calculate_ir_metrics, search_engine
from app.services.version_engine import version_engine


FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ai_evaluation.json"


def evaluate() -> dict:
    dataset = json.loads(FIXTURE.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        case_results = []
        all_metrics = []
        for case in dataset["search_cases"]:
            results = search_engine.hybrid_search(db, case["query"], top_k=5, min_score=0.35)
            retrieved = [item.standard.standard_code for item in results]
            metrics = calculate_ir_metrics(retrieved, case["relevant_codes"], k=3)
            all_metrics.append(metrics)
            case_results.append({"id": case["id"], "relevant": case["relevant_codes"], "retrieved": retrieved, "metrics": metrics})

        no_match_results = {}
        for case in dataset["no_match_cases"]:
            retrieved = search_engine.hybrid_search(db, case["query"], top_k=5, min_score=0.7)
            no_match_results[case["id"]] = [item.standard.standard_code for item in retrieved]

        analysis_cases = dataset["analysis_cases"]
        old_version = version_engine.check_version(db, analysis_cases["old_standard_reference"]).to_dict()
        gap_report = gap_detector.detect_gaps(db, analysis_cases["normative_gap_input"]).to_dict()
        conflict_report = conflict_detector.detect_conflicts(db, analysis_cases["conflicting_tender"]).to_dict()
        hindi_results = search_engine.hybrid_search(db, analysis_cases["hindi_query"], top_k=5, min_score=0.35)
        malicious_entities = extract_entities(analysis_cases["malicious_document"])
        malicious_fake_code_results = search_engine.exact_search(db, "IS 999999")

        metric_names = all_metrics[0].keys()
        aggregate = {name: round(sum(item[name] for item in all_metrics) / len(all_metrics), 4) for name in metric_names}
        return {
            "dataset_version": dataset["dataset_version"],
            "search_case_count": len(case_results),
            "search_cases": case_results,
            "mean_metrics": aggregate,
            "no_match_results": no_match_results,
            "old_standard_status": old_version.get("status"),
            "normative_gaps": gap_report["missing_normative_references"],
            "conflict_count": conflict_report["total_conflicts"],
            "hindi_retrieved_codes": [item.standard.standard_code for item in hindi_results],
            "malicious_document_extracted_codes": malicious_entities.standards_cited,
            "malicious_fake_code_verified_results": [item.standard.standard_code for item in malicious_fake_code_results],
        }
    finally:
        db.close()


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
