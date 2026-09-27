# Phase 23: Observability

## Implemented

- Liveness and readiness remain at `/api/v1/health` and `/api/v1/health/ready`; readiness reports database, storage, and whether the embedding model is not loaded, ready, or in lexical fallback mode.
- A valid inbound request ID is retained; invalid/oversized IDs are replaced with a generated UUID. Responses include `X-Request-ID` and `X-Process-Time`.
- Each completed request emits a JSON structured log with request ID, method, route template, status, and duration. No query, document, or authorization header is logged by this middleware.
- `/api/v1/health/metrics` exposes counters and histograms for request volume, HTTP duration, AI/search operation count, and AI/search duration. `audit:read` permission is required.
- Unhandled failures already produce structured exception logs with the request ID, and responses include that ID for support correlation.

## Verification

- `test_phase_23_observability.py` and `test_health.py`: **8 passed**.
- Tests verify liveness/readiness checks, metric output, search timing, permission denial for officers, and request-ID replacement.

## Operational limit

Metrics are in-process counters and reset when a worker restarts. They are suitable for local scraping, but production multi-worker monitoring needs aggregation or a shared metrics backend. Error events are logged; no external error-tracking service is configured.
