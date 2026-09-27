# IS Compliance and Verification Platform — Project Status

Assessment: 2026-09-27. Current code is a functional prototype with a human review workflow. It is not approved for production procurement decisions.

## Architecture

```text
React/Vite single-page app
        │ HTTPS / Nginx proxy
        ▼
FastAPI API ─── SQLAlchemy/Alembic ─── PostgreSQL (Compose) or SQLite (local tests)
        │
        ├── file extraction and bounded OCR
        ├── hybrid standard search and per-process FAISS document index
        ├── deterministic gap, conflict, version, relationship, certification and RAG rules
        ├── human recommendation review and audit trail
        └── audited project PDF export
```

## Implemented Features

- JWT sign-in/refresh, role/permission checks, project/department scoping and rate limiting.
- Project creation, validated tender document upload, file hashing, text extraction, chunking and processing metadata.
- PDF, DOCX, XLSX and TXT extraction. Sparse PDF pages use PDFium plus Tesseract OCR, with a 50-page OCR limit.
- Standards catalogue/version/amendment/reference APIs; exact, keyword, semantic and hybrid retrieval.
- Specification entity extraction, gap/conflict checks, certification/QCO lookup, deterministic evidence-grounded explanations and Hindi query expansion.
- Server-validated recommendation creation from a processed project document and retrieved active standard. New recommendations enter `pending_review`; the API does not auto-approve.
- Evidence-backed review queue with permission-checked accept/reject/comment/flag/request-review actions.
- Append-oriented audit events and an authorized PDF report that includes recommendation rationale, evidence, limitations, and decision history.
- Readiness/metrics endpoints, Docker/Compose assets, CI workflow, backup/archive tools and restore documentation.

## Technology Stack

- Frontend: React, Vite, JavaScript, CSS, Nginx.
- API: Python 3.13, FastAPI, Pydantic, SQLAlchemy, Alembic.
- Persistence: PostgreSQL 17 in Compose; SQLite for isolated local tests and helper tooling.
- Search and document processing: SentenceTransformers with a pinned model, NumPy/scikit-learn, FAISS, pypdf, PDFium, Tesseract, python-docx, openpyxl.
- Reporting/operations: ReportLab, Bandit, Ruff, pip-audit, npm audit, Trivy in CI.

## Database

Tables cover identities/roles/permissions/departments; projects/tenders/documents; standards/versions/amendments/references/certifications; recommendations/evidence/reviews; and audit logs. Alembic migrations are present. A clean SQLite migration was exercised locally; the PostgreSQL migration path is defined in CI but still needs a successful hosted run.

## AI Pipeline

The application is deterministic retrieval and rules; it does not call a generative language model. It extracts entity strings, retrieves standards through exact/keyword/semantic hybrid rank fusion, checks seeded version/reference/certification data, and constructs explanations from retrieved evidence. Recommendations remain review candidates, and the catalogue scope is explicitly not represented as a full BIS clause.

## Security Architecture

- Environment-injected signing keys; production rejects missing/short keys, debug mode and wildcard CORS.
- No source fallback signing secret or default demo passwords. Production seeding creates only the bootstrap admin.
- JWT access/refresh handling, permission checks, resource scoping, upload size/type/archive checks, filename sanitation, and hash-based integrity metadata.
- PDF OCR runtime has a page limit and timeout; OCR errors fail document processing instead of inserting fabricated text.
- Audit detail avoids storing source text and search query contents. Report export records counts and project identity.
- Bandit medium/high scan passed. Dependency/image audits and a live deployment review remain pending.

## API Architecture

Versioned routes live under `/api/v1`: auth, health/metrics, projects, documents, standards/search, analysis, review queue/actions, audit, and project PDF report. Authentication uses bearer tokens; endpoint permissions gate writes, reviews, audit and project data. See the generated OpenAPI page when running the API for request schemas.

## Testing

- Latest isolated local checks: **27 passed** across auth/security/config/archive, Phase 28 API E2E and OCR rendering checks (two upstream Starlette deprecation warnings).
- The Phase 28 integration test uses controlled retrieval to avoid network/model initialization but exercises upload through export and audit.
- Clean SQLite Alembic migration passed. Backend Ruff lint and Bandit checks are part of the final verification record.
- A previous 112-test baseline passed before the final CI/security additions. The current full model-backed suite stalled during SentenceTransformer initialization on this Windows host; do not treat the older baseline as validation of the current checkout.
- PDFium rasterization and OCR failure handling were tested with Tesseract stubbed. The real local Tesseract binary, PostgreSQL, container, and hosted GitHub Actions validation are pending.

## AI Evaluation

The versioned eight-case evaluation previously measured Precision@3 0.4167, Recall@3 1.0000, MRR 1.0000, and NDCG@3 1.0000 on a seeded catalogue of nine standards with the pinned model. Two high-threshold no-match cases returned no results. This small curated set is not representative of real tenders or production BIS coverage; broad queries include distractors and Hindi is dictionary expansion rather than general multilingual understanding.

## Performance

Previous local CPU measurements on that small corpus: first semantic search 41.18 seconds; warm semantic mean/p95 27.47/35.47 ms; warm hybrid mean/p95 30.84/41.03 ms; and 33 document chunks embedded in 2.05 seconds. These are not production capacity estimates. Upload extraction is synchronous, each worker loads its own model and in-memory FAISS state, and the index is not durable.

## Deployment

Compose defines PostgreSQL, one API worker and an Nginx frontend. Images use non-root users, health checks, pinned application dependencies and environment-provided credentials. CI builds/scans images and includes a gated manual deployment job. Local Docker/Podman is absent and there is no configured remote for this checkout; image build, startup and hosted workflow have not been run.

## Known Limitations

- Seed standards and rules are illustrative and limited; no automatic authoritative BIS/QCO data synchronization or full licensed standard clauses.
- OCR supports English by default, costs CPU, and rejects documents requiring OCR on more than 50 pages.
- Document embeddings and rate limits are process-local; there is no task queue, durable vector store, malware scanner, or multi-worker aggregation.
- RRF is score fusion, not a separately trained reranker. AI/evidence scores express retrieval relevance, not compliance certainty.
- Backup RPO/RTO are targets until PostgreSQL restore drills are timed. Audit rows are not tamper-proof against database operators.
- Full current model-backed tests, dependency audit database refreshes, Trivy, Docker, PostgreSQL integration, and live OCR have not been verified from this environment.

## Remaining Risks

Stale/incomplete catalogue data, false retrievals, OCR recognition errors, synchronous file processing, unavailable shared state after restarts, dependency/image vulnerabilities not caught until remote scans, and operational recovery targets without measured exercises remain material risks.

## Production Readiness

**Not production-ready for real procurement decisions.** Local functional/API, backup-helper, and security checks have passed as described above. Before production, complete a green hosted CI run; Docker/Compose and OCR image smoke tests; PostgreSQL migration plus restore drill; durable/shared runtime services for scaling; and operational ownership of authoritative standards data, monitoring, malware scanning, and review policy. See [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md).
