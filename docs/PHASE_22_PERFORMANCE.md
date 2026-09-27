# Phase 22: Performance

## Changes

- Standard-catalog embeddings are now cached per ordered catalogue signature and refreshed when a code/title/scope/status changes. Concurrent first-use computation is protected by a lock.
- SentenceTransformer model loading is protected by a process lock and pinned to a fixed model revision. Encoding progress bars are disabled for service requests.
- If the transformer cannot load, fallback vectors use stable word and character feature hashing. The previous whole-string random vectors had no useful semantic relationship and could create arbitrary matches.
- `backend/scripts/benchmark.py` measures cold/warm retrieval, readiness and search API latency, document chunking/embedding, and parallel search sessions.

## Local benchmark

Environment: Python 3.13, CPU, seeded SQLite database with 9 standards, and the pinned `all-MiniLM-L6-v2` model. These are local measurements, not production capacity claims.

| Measurement | Result |
|---|---:|
| First semantic search (model/runtime initialization plus catalogue vectors) | 41.18 s |
| Warm semantic search mean / p95 | 27.47 ms / 35.47 ms |
| Warm hybrid search mean / p95 | 30.84 ms / 41.03 ms |
| Readiness API mean / p95 | 15.06 ms / 37.50 ms |
| Exact search API p50 / p95 | 20.79 ms / 69.29 ms |
| 33-chunk normalization/chunking | 3.66 ms |
| 33-chunk embedding on CPU | 2.05 s |
| 8 concurrent warm searches, 4 workers | 253.48 ms total |

## Remaining performance risks

- The first search in each worker pays a large model/runtime initialization cost. Model preloading and image-bundled weights should be part of deployment; otherwise the first user request can take tens of seconds.
- Document extraction and embeddings run synchronously in the upload request. Large PDFs, OCR, or concurrent large uploads need a background job queue and resource limits.
- This benchmark does not cover sustained load, real BIS catalogue scale, production Postgres, OCR/PDF worst cases, or multi-process operation. The in-memory FAISS document index is per-process and not durable.

## Verification

- `test_phase_22_performance.py`: **3 passed**, covering cached catalogue embedding reuse, cache invalidation, parallel sessions, and deterministic lexical fallback similarity.
- Reproduce in a seeded backend environment with `python -m scripts.benchmark`.
- Set `BENCHMARK_LOGIN_PASSWORD` to the benchmark account's supplied password; the script contains no demo credential.
