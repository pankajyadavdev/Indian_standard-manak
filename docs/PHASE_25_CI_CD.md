# Phase 25: CI/CD

## Pipeline

`.github/workflows/ci.yml` runs on pushes and pull requests. It:

1. Lints backend source and runs Bandit and `pip-audit`.
2. Applies the Alembic chain and seed routines against a clean PostgreSQL service.
3. Creates a separate seeded SQLite test database and runs the backend suite.
4. Runs `npm audit` and builds the locked frontend dependency tree.
5. Builds both production Docker images and fails if Trivy reports an unfixed high or critical vulnerability. On non-PR events, it publishes those exact scanned images under the commit SHA in GHCR.
6. Allows deployment only for a manually dispatched run with `deploy=true`, after all checks pass, on a protected `production` environment and a self-hosted runner labeled `is-platform-production`. Deployment pulls the previously scanned SHA images and starts Compose without rebuilding them.

Dependabot checks Python, npm, both container bases, and GitHub Actions weekly. Workflow permissions are read-only by default; only image publication and deployment receive package write/read permissions. Deployment requires environment secrets for the Compose credentials.

## Local verification

The workflow YAML and available local checks are validated in Phase 30. Python requirements resolve against the configured dependency feed; a local `pip-audit` scan first surfaced an `ecdsa` issue through the prior JWT dependency, so the application moved to PyJWT. The post-change vulnerability database request timed out locally. The npm audit endpoint also failed through the local network proxy. Both strict dependency audits remain configured in CI but need a successful hosted run.

The GitHub workflow itself, Dependabot, PostgreSQL service job, container scans, production environment protection, and self-hosted deployment runner cannot be exercised from this local checkout. Docker/Podman is not installed here, so image build, OCR runtime image, startup, and Trivy stages remain unverified locally. A repository owner must configure the protected GitHub environment and runner before a manual production deployment can succeed.
