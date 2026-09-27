# Production readiness assessment

Assessment date: 2026-09-27. This is a verification record for the current checkout; it is not a production approval.

## Checklist

| Area | Status | Evidence / follow-up |
|---|---|---|
| Application starts | PASS | FastAPI startup and readiness exercised by the backend API tests. |
| Database works | PASS / PARTIAL | Fresh SQLite schema and API flows work. PostgreSQL 17 job is configured in CI but was not run from this checkout. |
| Migrations work | PASS / PARTIAL | Clean Alembic migration chain passed on SQLite. A live PostgreSQL migration is still required. |
| Authentication | PASS | Login, token and auth/security tests passed in an isolated test database. |
| Authorization | PASS | Project scoping, review permissions, and reviewer-only final decisions covered in API tests. |
| Documents | PASS / PARTIAL | TXT, PDF text, DOCX, XLSX, archive validation and upload flow are implemented. Upload processing is synchronous and antivirus scanning is not configured. |
| OCR | IMPLEMENTED / RUNTIME UNVERIFIED | Sparse PDF pages now use PDFium rendering and Tesseract OCR, capped at 50 pages. The CI job installs Tesseract. A scanned-PDF integration test is present, but the local machine and container image were not available for a real OCR run. |
| Search | PASS / PARTIAL | Exact, keyword, semantic and hybrid search are implemented. Historical AI evaluation passed against the small seeded catalogue; current local full model tests stall during model initialization. |
| Vector search | PARTIAL | FAISS embedding and lookup code exists; the document index is in-memory and per process, and is not rebuilt durably after restart. |
| Reranking | PARTIAL | Hybrid search uses reciprocal-rank fusion and score ordering. There is no separately trained or learned reranker. |
| RAG | PASS / PARTIAL | Deterministic explanations cite retrieved catalogue/document evidence and refuse when no evidence clears the threshold. This is not a proof of compliance or a guarantee against every false retrieval. |
| No invented standards | PASS WITH LIMITS | Explanations and recommendation creation use server-side catalogue results. Entity extraction can still surface an unverified code string from source text; human verification is required. |
| Evidence | PASS / PARTIAL | Recommendations preserve tender excerpts and catalogue scope as distinct evidence types. The application does not include full licensed BIS standard text. |
| Version / amendment engine | PASS / PARTIAL | Current/superseded versions and stored amendments are exposed by the catalogue engine; external BIS updates are not synchronized automatically. |
| Reference engine | PASS / PARTIAL | Seeded normative/test/safety/etc. relationships and graph endpoints work. The reference dataset is small and requires curation. |
| Certification engine | PASS / PARTIAL | Rule engine checks stored certification/QCO entries. It does not guarantee the completeness or currency of that source data. |
| Gap / conflict detection | PASS / PARTIAL | Deterministic checks are implemented and tested against seeded examples; coverage is limited to rules and catalogue entries present. |
| Multilingual | PARTIAL | Hindi terms use explicit dictionary expansion; OCR defaults to English and broad Indian-language support is not evaluated. |
| Human review | PASS | Queue, evidence, comments, accept/reject permissions, final-decision protection and audit event are covered. |
| Audit | PASS / PARTIAL | Application events are append-only through the API, including recommendation creation, review decisions and report export. A database administrator can still alter the underlying table. |
| Export | PASS / PARTIAL | Authorized project PDF export includes evidence, limitations and review history. The report is not a legal certification. |
| Security tests | PASS / PARTIAL | Phase 27 security/auth/config tests passed locally; Bandit reported no medium/high findings. Dependency audit and container scan remain pending. |
| AI tests | PARTIAL | Historical eight-case retrieval evaluation passed (Phase 21). Current complete model-backed suite did not finish on this host. |
| Performance tests | PASS / PARTIAL | Historical CPU benchmark and 3 Phase 22 tests passed. First model load took 41.18 seconds; measurements used 9 seeded standards, not production scale. |
| Docker / Compose | UNVERIFIED | Docker and Podman are unavailable locally. The Dockerfiles and Compose health checks have been reviewed, but build/startup/health checks need a hosted or equipped runner. |
| CI and dependency audits | CONFIGURED / UNVERIFIED | GitHub Actions workflow is present. Local `pip-audit` database access timed out after the JWT dependency change; `npm audit` failed through the local network proxy. No remote or GitHub Actions run is configured from this checkout. |
| Monitoring | PARTIAL | Readiness, request IDs, structured request logs and Prometheus-style metrics exist. Metrics are per process and no central alerting/error tracking is configured. |
| Documentation | PASS | Phase records, backup procedure, CI/deployment notes, this assessment and `PROJECT_STATUS.md` are present. |

## Required before production traffic

1. Run the full CI workflow successfully, including Python and npm vulnerability audits, PostgreSQL migration/integration, model-backed tests, and image scans.
2. Build and start Compose with a real deployment `.env`; verify readiness, OCR on a known scanned sample, login, upload, review, and PDF export.
3. Perform and record a PostgreSQL plus uploads restore drill. The 24-hour RPO and 4-hour RTO are targets, not measured results.
4. Provide durable shared document/vector storage and cross-worker rate limiting/metrics before scaling beyond one API worker.
5. Set an operational owner for BIS/QCO source data, its update cadence, licensed standard access, and review of false positives/negatives.
6. Add malware scanning, job queue/resource controls for large files, central monitoring/alerting, and a privacy/retention policy appropriate to the deployment.

The current checkout is **not production-ready for real procurement decisions**. The verified local components can be reviewed and deployed to a non-production environment for the outstanding drills; release to production depends on the listed external checks and data/operations controls.
