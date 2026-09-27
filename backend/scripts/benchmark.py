"""Small reproducible latency benchmark for the seeded local environment."""
import json
import math
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.standard import Standard
from app.main import app
from app.services.document_processor import chunk_text, normalize_text
from app.services.embedding_service import embed_texts
from app.services.search_service import search_engine


def elapsed_ms(operation):
    start = time.perf_counter()
    value = operation()
    return (time.perf_counter() - start) * 1000, value


def summarize(samples):
    ordered = sorted(samples)
    return {
        "count": len(ordered),
        "mean_ms": round(statistics.mean(ordered), 2),
        "p50_ms": round(statistics.median(ordered), 2),
        "p95_ms": round(ordered[min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)], 2),
    }


def main():
    db = SessionLocal()
    try:
        cold_ms, _ = elapsed_ms(lambda: search_engine.semantic_search(db, "plain and reinforced concrete", top_k=5))
        semantic_samples = [elapsed_ms(lambda: search_engine.semantic_search(db, "plain and reinforced concrete", top_k=5))[0] for _ in range(8)]
        hybrid_samples = [elapsed_ms(lambda: search_engine.hybrid_search(db, "high strength steel reinforcement", top_k=5))[0] for _ in range(8)]
        standard_count = db.query(Standard).count()
    finally:
        db.close()

    text = ("Concrete shall comply with IS 456 and reinforcement with IS 1786. " * 300)
    process_ms, chunks = elapsed_ms(lambda: chunk_text(normalize_text(text), "benchmark-document"))
    embedding_ms, _ = elapsed_ms(lambda: embed_texts([chunk["text"] for chunk in chunks]))

    def concurrent_search(_):
        session = SessionLocal()
        try:
            return search_engine.hybrid_search(session, "PVC insulated electrical cable", top_k=5)
        finally:
            session.close()

    concurrent_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        concurrent_result_counts = list(pool.map(lambda _: len(concurrent_search(None)), range(8)))
    concurrent_wall_ms = (time.perf_counter() - concurrent_start) * 1000

    with TestClient(app) as client:
        health_samples = [elapsed_ms(lambda: client.get("/api/v1/health/ready"))[0] for _ in range(10)]
        benchmark_password = os.environ.get("BENCHMARK_LOGIN_PASSWORD")
        if not benchmark_password:
            raise RuntimeError("Set BENCHMARK_LOGIN_PASSWORD to the benchmark account password")
        login = client.post("/api/v1/auth/login", json={"email": "officer@cpwd.gov.in", "password": benchmark_password})
        if login.status_code != 200:
            raise RuntimeError("Benchmark login failed; verify the benchmark account and database seed")
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        exact_samples = [elapsed_ms(lambda: client.post(
            "/api/v1/standards/search", headers=headers,
            json={"query": "IS 456", "search_type": "exact"},
        ))[0] for _ in range(8)]

    print(json.dumps({
        "standard_count": standard_count,
        "cold_semantic_search_ms": round(cold_ms, 2),
        "warm_semantic_search": summarize(semantic_samples),
        "warm_hybrid_search": summarize(hybrid_samples),
        "readiness_api": summarize(health_samples),
        "exact_search_api": summarize(exact_samples),
        "document_chunking_ms": round(process_ms, 2),
        "document_chunks": len(chunks),
        "document_embedding_ms": round(embedding_ms, 2),
        "concurrent_4_workers_8_searches_wall_ms": round(concurrent_wall_ms, 2),
        "concurrent_result_counts": concurrent_result_counts,
        "limitations": ["Local CPU and SQLite benchmark only", "No OCR/PDF benchmark", "No sustained load test", "No background worker is configured"],
    }, indent=2))


if __name__ == "__main__":
    main()
