# Phase 16: Frontend workspace

The frontend now provides a responsive, authenticated workspace for Dashboard, Projects, Document Upload, Analysis, Recommendations, Standards Explorer, Certification, Review, Audit, and Settings.

## Connected workflows

- Projects can be created and listed for the signed-in user's department.
- PDF, DOCX, XLSX, and TXT files can be uploaded to a project and listed with their processing status.
- Analysis can extract specification entities from pasted text or a processed document. Pasted text also runs gap and conflict checks; both sources run a standards search when there is a usable query.
- Standards search, details, version history, relationships, and certification metadata are visible in the explorer.
- Certification checks use the existing rule-based endpoint. Recommendations show search candidates as candidates and RAG answers with their retrieved evidence.
- Review shows recommendation evidence and supports permission-gated decisions. Audit is read-only and requires the `audit:read` permission. Project, upload, review, and audit UI calls are authenticated and permission checked.
- The client stores access and refresh tokens locally, refreshes an expired access token once, and signs out through the backend.

## API support added for this phase

- `GET /api/v1/projects`, `GET /api/v1/projects/{project_id}`, and `POST /api/v1/projects` provide permission-checked project access.
- `GET /api/v1/documents?project_id=...` lists documents for an accessible project. Upload also checks project access and `document:upload` permission.
- `GET /api/v1/audit` provides read-only audit events for users with `audit:read`.

## Known phase boundary

Human review can record accept, reject, flag, comment, and request-review actions against a recommendation. Accept/reject requires reviewer permission and never approves a tender. Hindi preference is stored locally; most interface labels remain English.

## Verification

The backend test suite expects both the base BIS seed and the extended relationship seed. For a clean run, set `DATABASE_URL` and `UPLOAD_DIR` to temporary paths, create the schema, run `seed_database()` and `seed_extended_relationships()`, then run `python -m pytest -q` with those same paths. This phase was checked that way: **112 backend tests passed**. The frontend production bundle passed with the installed Vite CLI.
