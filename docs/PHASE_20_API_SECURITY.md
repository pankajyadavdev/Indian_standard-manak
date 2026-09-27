# Phase 20: API security

## Changes

- Document metadata, text chunks, specification extraction, and document-grounded RAG now verify `document:read` and project visibility. Hidden documents return 404.
- Upload reads at most the configured file limit plus one byte before rejecting oversized content.
- DOCX/XLSX archives are rejected when entry count, expanded size, or compression ratio exceeds safe bounds.
- Search, RAG, and specification text fields have explicit length caps; search modes use a closed set of accepted values.
- `X-Forwarded-For` is ignored for client identity because no trusted proxy allowlist is configured. Callers cannot change their rate-limit key with that header.
- SQL-like input remains parameterized data; malformed JSON/schema requests return structured 422 responses. Browser-rendered text remains React-escaped, and API authorization uses bearer tokens rather than ambient cookies.

## Verification

- `test_phase_20_api_security.py`, `test_security.py`, `test_auth.py`, `test_specification_extraction.py`, and `test_document_processing.py`: **37 passed** on a fresh seeded temporary SQLite database.
- Coverage includes cross-department IDOR, proxy-header rate-limit bypass, SQL injection strings, malformed JSON, unsupported search modes, oversized uploads, Office archive expansion, existing CORS/security-header checks, and malicious filenames.

## Remaining security limits

- The rate limiter stores state in process memory. Multi-worker production requires a shared limiter and a deployment-specific trusted-proxy configuration.
- CSRF is not applicable to the present bearer-token API, but localStorage tokens remain exposed to any same-origin script injection; no CSP nonce strategy or independent frontend penetration test has been completed.
