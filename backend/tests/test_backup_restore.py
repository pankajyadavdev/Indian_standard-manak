import hashlib
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

import pytest

from scripts.sqlite_backup import create_backup, restore_backup


def _create_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as database:
        database.execute("CREATE TABLE records (value TEXT NOT NULL)")
        database.commit()
        database.execute("INSERT INTO records (value) VALUES ('before-backup')")
        database.commit()


def test_sqlite_and_upload_backup_restores_consistent_snapshot(tmp_path):
    source_database = tmp_path / "source.sqlite3"
    source_uploads = tmp_path / "source-uploads"
    source_uploads.mkdir()
    _create_database(source_database)
    upload_file = source_uploads / "nested" / "tender.txt"
    upload_file.parent.mkdir()
    upload_file.write_text("uploaded tender", encoding="utf-8")
    archive = create_backup(source_database, source_uploads, tmp_path / "backup.zip")

    with closing(sqlite3.connect(source_database)) as database:
        database.execute("INSERT INTO records (value) VALUES ('after-backup')")
        database.commit()
    upload_file.write_text("changed after backup", encoding="utf-8")

    restored = restore_backup(archive, tmp_path / "restored")
    with closing(sqlite3.connect(restored / "database.sqlite3")) as database:
        values = database.execute("SELECT value FROM records ORDER BY rowid").fetchall()
    assert values == [("before-backup",)]
    assert (restored / "uploads" / "nested" / "tender.txt").read_text(encoding="utf-8") == "uploaded tender"


def test_restore_rejects_checksum_mismatch_without_creating_destination(tmp_path):
    source_database = tmp_path / "source.sqlite3"
    source_uploads = tmp_path / "uploads"
    source_uploads.mkdir()
    _create_database(source_database)
    archive_path = create_backup(source_database, source_uploads, tmp_path / "backup.zip")
    corrupt_path = tmp_path / "corrupt.zip"

    with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(corrupt_path, "w") as corrupt:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "database.sqlite3":
                data += b"tampered"
            corrupt.writestr(item.filename, data)

    destination = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="CRC|checksum"):
        restore_backup(corrupt_path, destination)
    assert not destination.exists()


def test_restore_rejects_path_traversal_before_writing(tmp_path):
    archive_path = tmp_path / "traversal.zip"
    payload = b"forbidden"
    manifest = {
        "format_version": 1,
        "files": {
            "database.sqlite3": hashlib.sha256(payload).hexdigest(),
            "../escape.txt": hashlib.sha256(payload).hexdigest(),
        },
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("database.sqlite3", payload)
        archive.writestr("../escape.txt", payload)

    destination = tmp_path / "restore-target"
    with pytest.raises(ValueError, match="unsafe"):
        restore_backup(archive_path, destination)
    assert not destination.exists()
    assert not (tmp_path.parent / "escape.txt").exists()
