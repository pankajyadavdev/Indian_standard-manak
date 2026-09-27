# Phase 24: Docker deployment

## Implemented

- `backend/Dockerfile` uses a two-stage Python build, pinned Python dependencies, a preloaded pinned embedding-model revision, the Tesseract OCR runtime, an unprivileged app user, health check, and no model download at runtime.
- `frontend/Dockerfile` builds the locked Vite application and serves it from an unprivileged Nginx image on port 8080. Nginx proxies `/api/` to the backend and serves SPA routes.
- `docker-compose.yml` starts PostgreSQL, the API, and the web frontend. PostgreSQL is not published to the host; database and upload data use separate persistent volumes. Health checks gate startup dependencies.
- Containers drop capabilities and disallow privilege escalation. The frontend filesystem is read-only with bounded temporary filesystems.
- Compose requires a secret signing key, database password, and one-time administrator identity. Production seeding omits the documented demo users/passwords; bootstrap credentials are unset before the API server starts.
- Uvicorn trusts forwarded client addresses only from the explicitly configured Compose network range, so Nginx proxying preserves per-client rate limiting.

## Verification

- Compose YAML parsed and service health dependencies were checked with PyYAML.
- Frontend Vite production build passed.
- Docker image build, Compose config expansion, container startup, health checks, and full-system API flow were **not run**: no Docker/Podman CLI is installed in this workspace.

## Deployment constraints

- Set `SECRET_KEY`, `POSTGRES_PASSWORD`, `BOOTSTRAP_ADMIN_EMAIL`, and `BOOTSTRAP_ADMIN_PASSWORD` in an ignored local `.env` or deployment secret store. Use URL-safe characters for `POSTGRES_PASSWORD` because it is embedded in the SQLAlchemy URL. Use at least 16 bytes for the bootstrap password.
- The bootstrap administrator is inserted only when the volume is empty. Store the initial credential securely and rotate it after first login.
- This compose file runs one API worker. Horizontal scaling needs a shared rate limiter, persistent shared document/vector indexing, and metrics aggregation.
