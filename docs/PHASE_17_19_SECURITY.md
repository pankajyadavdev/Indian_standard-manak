# Phases 17–19: Review, audit, and AI security

## Phase 17 — Human review

- `GET /api/v1/reviews/recommendations` returns a scoped, paginated review queue with rationale, limitations, standard version, evidence, and decision history.
- `POST /api/v1/reviews/recommendations/{id}/actions` records accept, reject, flag, comment, and request-review actions in `reviews`, updates recommendation review status, and writes an audit event.
- Queue access requires `review:submit`; accept/reject also requires `review:approve` (or `admin:all`). Accept is rejected if there is no linked evidence. Final accept/reject decisions cannot be replaced by another final decision.
- A recommendation decision does not change tender or project approval status.
- Frontend sign-in now loads `/auth/me`, keeping the UI permissions current with the backend.

## Phase 18 — Audit

- Audit events cover login success/failure/lockout, token refresh, logout, project creation, upload and processing, document reads/chunk reads, specification extraction, gap/conflict/RAG/certification analysis, standards search/explanations, and review decisions.
- Search text and tender contents are not copied into audit details. Search events store length and a SHA-256 digest; analysis events store counts, outcome flags, and identifiers where needed.
- `GET /api/v1/audit` requires `audit:read`. The API exposes no audit update or delete route; a DELETE request returns 405. The audit model itself is append-oriented at the application layer, not tamper-proof against database administrators or host compromise.
- Phase 28 adds a project PDF export at `GET /api/v1/projects/{id}/report.pdf`; exports write a `report.exported` audit event with record counts only.

## Phase 19 — AI security

- The current analysis implementation is deterministic retrieval, regex/entity extraction, and rule-based explanation; it does not call an LLM or expose tool execution. Document/query contents are treated as analysis input, not commands.
- `/analysis/explain-search` retrieves standards on the server. Caller-supplied result candidates are ignored, preventing forged recommendations and evidence.
- RAG returns the fixed `Insufficient verified evidence.` response if retrieval returns no evidence. Explanations and logs no longer echo the submitted query verbatim.
- Adversarial tests cover instruction override, invented standard codes, prompt/system-prompt disclosure, destructive requests, and external-call requests. This is coverage of the present deterministic path, not a guarantee for a future LLM integration.

## Verification

- Phase 17 focused tests: 4 passed.
- Phase 17–18 focused tests: 6 passed.
- Phase 19 adversarial tests after fixing their database fixture: 2 passed.
- Combined review/audit/AI/RAG/search/Phase 12–15 regression run: 44 passed; the run also reported one test setup error from the initial Phase 19 fixture, which was corrected and rerun successfully. A clean full-suite run is still required in Phase 21/28.
- Frontend Vite production build passed after the Phase 17 UI changes.
