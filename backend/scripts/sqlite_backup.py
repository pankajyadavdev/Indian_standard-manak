"""Create and restore verified SQLite plus upload-directory snapshots for local installs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


MANIFEST_NAME = "manifest.json"
DATABASE_NAME = "database.sqlite3"


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_check(path: Path) -> None:
    with closing(sqlite3.connect(path)) as database:
        result = database.execute("PRAGMA integrity_check").fetchone()
    if not result or result[0] != "ok":
        raise ValueError("SQLite backup failed its integrity check")


def _safe_archive_path(name: str) -> PurePosixPath:
    if not name or "\\" in name:
        raise ValueError("Backup contains an invalid archive path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Backup contains an unsafe archive path")
    if path.parts and ":" in path.parts[0]:
        raise ValueError("Backup contains a drive-qualified archive path")
    return path


def create_backup(database_path: Path, upload_dir: Path, archive_path: Path) -> Path:
    """Write a consistent SQLite snapshot and upload files to a checksummed ZIP."""
    database_path = database_path.resolve(strict=True)
    upload_dir = upload_dir.resolve(strict=True)
    archive_path = archive_path.resolve()
    if not database_path.is_file() or not upload_dir.is_dir():
        raise ValueError("Database file and upload directory are required")
    if archive_path.exists():
        raise FileExistsError(f"Backup destination already exists: {archive_path}")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="is-backup-", dir=archive_path.parent) as temp_name:
        staging = Path(temp_name)
        snapshot = staging / DATABASE_NAME
        with closing(sqlite3.connect(database_path)) as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
        _integrity_check(snapshot)

        staged_uploads = staging / "uploads"
        staged_uploads.mkdir()
        files: dict[str, str] = {DATABASE_NAME: _digest(snapshot)}
        for source_file in sorted(upload_dir.rglob("*")):
            if source_file.is_symlink():
                raise ValueError("Upload backup refuses symbolic links")
            if not source_file.is_file():
                continue
            relative = source_file.relative_to(upload_dir)
            destination = staged_uploads / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, destination)
            files[PurePosixPath("uploads", *relative.parts).as_posix()] = _digest(destination)

        manifest = {
            "format_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "files": files,
        }
        manifest_path = staging / MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        temporary_archive = staging / "snapshot.zip"
        with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.write(manifest_path, MANIFEST_NAME)
            archive.write(snapshot, DATABASE_NAME)
            for source_file in sorted(staged_uploads.rglob("*")):
                if source_file.is_file():
                    archive.write(source_file, PurePosixPath("uploads", *source_file.relative_to(staged_uploads).parts).as_posix())

        with zipfile.ZipFile(temporary_archive, "r") as archive:
            if archive.testzip() is not None:
                raise ValueError("Created backup archive failed its CRC check")
        os.replace(temporary_archive, archive_path)
    return archive_path


def _copy_verified(archive: zipfile.ZipFile, name: str, destination: Path, expected_hash: str) -> None:
    digest = hashlib.sha256()
    with archive.open(name, "r") as source, destination.open("xb") as output:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            output.write(chunk)
    if digest.hexdigest() != expected_hash:
        raise ValueError(f"Backup checksum mismatch for {name}")


def restore_backup(archive_path: Path, destination: Path) -> Path:
    """Verify an archive and restore it into a new directory without overwriting data."""
    archive_path = archive_path.resolve(strict=True)
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"Restore destination must not exist: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or MANIFEST_NAME not in names:
            raise ValueError("Backup has duplicate entries or no manifest")
        for name in names:
            _safe_archive_path(name)
        if archive.testzip() is not None:
            raise ValueError("Backup archive failed its CRC check")

        try:
            manifest = json.loads(archive.read(MANIFEST_NAME))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Backup manifest is not valid JSON") from exc
        if manifest.get("format_version") != 1 or not isinstance(manifest.get("files"), dict):
            raise ValueError("Unsupported or malformed backup manifest")
        expected_files = manifest["files"]
        if set(names) - {MANIFEST_NAME} != set(expected_files):
            raise ValueError("Backup file list does not match its manifest")
        if DATABASE_NAME not in expected_files:
            raise ValueError("Backup does not contain a database snapshot")

        with tempfile.TemporaryDirectory(prefix="is-restore-", dir=destination.parent) as temp_name:
            staging = Path(temp_name) / "restored"
            staging.mkdir()
            for name, digest in expected_files.items():
                relative = _safe_archive_path(name)
                target = staging.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                _copy_verified(archive, name, target, digest)
            _integrity_check(staging / DATABASE_NAME)
            os.replace(staging, destination)
    return destination
