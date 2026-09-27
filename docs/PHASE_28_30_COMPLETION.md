# Phases 28–30: Functional test, production assessment, final report

## Phase 28 — End-to-end workflow

**Status:** Implemented and locally verified with controlled retrieval.

- Added `POST /api/v1/reviews/recommendations`. It verifies project/document scope, completed document state, a source excerpt that is the exact document prefix, server-side retrieval membership, active standard status and current version. It saves tender and catalogue-scope evidence and leaves the record `pending_review`.
- Added permission-scoped `GET /api/v1/projects/{project_id}/report.pdf`. It includes project counts, recommendation rationale/scores/versions/status, evidence, limitations and review history. It records `report.exported` without placing source text in the audit details.
- Connected document-based analysis candidates to “Create for review” and project report download in the frontend.
- Added `backend/tests/test_phase_28_e2e.py`: sign-in, project creation, upload/processing, extraction, search route, versions, relationships, certification, gaps, conflicts, RAG, forged-excerpt rejection, recommendation, reviewer acceptance, PDF export and audit assertions.

**Database changes:** None; existing recommendation, evidence, review and audit tables are used.

**Test result:** The deterministic API E2E test passes. Retrieval is controlled in this test; the historical Phase 21 evaluation covers real model retrieval. The full model-backed suite did not finish on this local host.

**Security result:** Project scope, server-side candidate validation, excerpt provenance, human-only final decision, escaped PDF text, and export audit event are exercised or enforced by the endpoint.

**Known issues:** PDF export and true model-driven end-to-end ranking still need a Docker/PostgreSQL/real-model smoke run.

## Phase 29 — Production checklist

**Status:** Checklist evaluated; production sign-off remains open.

- Replaced the previous fabricated scanned-PDF fallback text with PDFium rendering and Tesseract OCR, a 30-second page timeout, a 50-page limit, and explicit failure on unreadable scans. Added the pinned `pypdfium2` dependency and Tesseract to the API image/CI test host.
- Added focused OCR tests for PDF rendering, recognized-text insertion and no-text failure.
- Recorded every requested Phase 29 capability and its evidence or limitation in `docs/PRODUCTION_READINESS.md`.

**Database changes:** None.

**Test result:** OCR renderer test uses a stubbed Tesseract call because this Windows host has no Tesseract executable. The real executable integration test is included in the CI backend suite; it awaits a hosted run.

**Security result:** Bandit medium/high scan reports zero issues. Dependency audit and container scan remain unverified due local network/runner constraints.

**Known issues:** Docker/Compose, PostgreSQL migration/restore, full model-backed suite, dependency audits, actual Tesseract binary, and hosted CI remain external verification gates. The readiness checklist names additional operational/data risks.

## Phase 30 — Final report

**Status:** Complete.

- Wrote `PROJECT_STATUS.md` with architecture, features, technology stack, database, AI pipeline, security, API, tests, evaluation, performance, deployment, limitations, risks and production readiness.
- Wrote `docs/PRODUCTION_READINESS.md` with the full checklist and release gates.
- Updated earlier Phase 17–19 and Phase 24–26 records where Phase 28 report export, Phase 29 OCR, or final verification changed their implementation status.

**Database changes:** None.

**Final local verification:** Fresh SQLite Alembic migration passed; 27 focused auth/security/config/backup/archive/E2E/OCR tests passed; Ruff passed; Bandit found zero medium/high findings; frontend production build passed; CI/Dependabot/Compose YAML parsed; `git diff --check` passed.

**Known issues / next action:** Do not mark the product production-ready. Run hosted CI and image scans, real Tesseract OCR in the image, PostgreSQL migration and restore drill, and operational readiness work listed in `docs/PRODUCTION_READINESS.md` before production traffic.
