# Phase 26: Backup and recovery

## What is backed up

- PostgreSQL database: custom-format `pg_dump` archive made by the PostgreSQL 17 container.
- Uploaded originals: gzip tar archive streamed by `backend/scripts/uploads_archive.py` from the mounted upload directory.
- Configuration: version-controlled Compose/Docker/workflow files and a separate encrypted, access-controlled copy of deployment secrets. Secrets are deliberately excluded from application backups.
- Local SQLite installs: `backend/scripts/sqlite_backup.py` provides a consistent SQLite online backup, uploads snapshot, SHA-256 manifest, CRC/checksum verification, and restore into a new directory.

## Production backup procedure

Run on the protected deployment host from the Compose project directory. Choose a backup destination on a separate encrypted filesystem and replicate the completed artifacts to a separate account or region. Keep the API stopped during the database and uploads snapshots so that both represent one quiescent point.

```bash
set -euo pipefail
umask 077
backup_root="${BACKUP_ROOT:?Set BACKUP_ROOT to the protected backup mount}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_root"

docker compose stop backend
restart_backend() { docker compose start backend; }
trap restart_backend EXIT

docker compose exec -T db pg_dump \
  -U is_platform -d is_platform --format=custom --no-owner --no-acl \
  > "$backup_root/$stamp.database.pgdump"
docker compose exec -T backend \
  python /app/scripts/uploads_archive.py backup \
  > "$backup_root/$stamp.uploads.tar.gz"
(cd "$backup_root" && sha256sum "$stamp.database.pgdump" "$stamp.uploads.tar.gz" \
  > "$stamp.sha256")

docker compose start backend
trap - EXIT
```

Confirm both files are non-empty, verify the checksum file, and copy all three artifacts to the off-host encrypted store before reporting the backup complete. Alert if any command fails. The `trap` restarts the backend after a failed snapshot attempt.

## Restore procedure

Restore into a new database and a new upload volume in a recovery environment. Keep the public frontend stopped until integrity checks and the API smoke test pass. Do not use `pg_restore --clean` against the live database.

1. Retrieve the database archive, upload archive, and checksum file from the off-host store; verify with `sha256sum -c <stamp>.sha256`.
2. Create a recovery Compose environment with empty PostgreSQL and upload volumes, the protected secrets, and no public frontend.
3. Start PostgreSQL only and wait for its health check: `docker compose up -d db`.
4. Restore the custom database archive into the empty `is_platform` database:

   ```bash
   cat <stamp>.database.pgdump | docker compose exec -T db \
     pg_restore -U is_platform -d is_platform --no-owner --no-acl --exit-on-error
   ```

5. Restore uploaded files into the empty upload volume using the safe extractor:

   ```bash
   docker compose run --rm --no-deps --entrypoint python backend \
     /app/scripts/uploads_archive.py restore < <stamp>.uploads.tar.gz
   ```

6. Verify PostgreSQL tables and row counts, check restored upload files, then start the API and wait for `/api/v1/health/ready` to report `READY`. Run login and document-read smoke checks with a recovery account before starting the frontend.
7. Record restore start/end times, artifact IDs, checksums, failures, data loss window, and operator. Switch traffic only after the recovery owner approves service health.

The archive must come from the trusted backup store. A PostgreSQL dump is executable database input; do not restore an archive from an untrusted source.

## Local restore exercise

The SQLite helper snapshots a live database with SQLite's backup API and tests the restored copy with `PRAGMA integrity_check`. Upload archive restoration verifies member names and checksums before accepting data, rejects symlinks and special files, and writes only into a new target directory. The regression suite is:

```bash
cd backend
python -m pytest -q tests/test_backup_restore.py tests/test_uploads_archive.py
```

Result in this workspace: **5 passed**. This verifies the local SQLite/archive restore path; it is not a substitute for a PostgreSQL restore drill.

## Retention and recovery objectives

- Initial target RPO: 24 hours, based on at least one successful daily off-host backup.
- Initial target RTO: 4 hours for restoring the database, uploads, and service health in a prepared recovery environment.
- Retention starting point: 35 daily copies, 12 month-end copies, and 7 year-end copies, subject to the organization's procurement-record, privacy, and legal retention schedule.
- Encrypt artifacts at rest and in transit, limit decryption and restore privileges, keep keys outside the backup store, and enable immutable/object-lock retention where available.
- Alert on a missing daily artifact or checksum failure. Perform a PostgreSQL plus uploads restore drill at least quarterly and after a schema/storage change. Recalculate RPO/RTO from measured drills.

## Verification boundary

The SQLite restore and upload archive path passed locally. PostgreSQL 17 dump/restore, named-volume recovery, off-host replication, and measured recovery objectives were **not exercised here** because Docker/Podman is unavailable and no production backup destination or recovery credentials are configured.
