import io
import tarfile

import pytest

from scripts.uploads_archive import backup_uploads, restore_uploads


def test_upload_archive_round_trip(tmp_path):
    source = tmp_path / "source"
    (source / "nested").mkdir(parents=True)
    (source / "nested" / "tender.txt").write_text("tender evidence", encoding="utf-8")
    archive = io.BytesIO()
    backup_uploads(source, archive)
    (source / "nested" / "tender.txt").write_text("changed", encoding="utf-8")

    target = tmp_path / "restored"
    restore_uploads(io.BytesIO(archive.getvalue()), target)
    assert (target / "nested" / "tender.txt").read_text(encoding="utf-8") == "tender evidence"


def test_upload_restore_rejects_path_traversal(tmp_path):
    archive_bytes = io.BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode="w:gz") as archive:
        payload = b"unsafe"
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    target = tmp_path / "restored"

    with pytest.raises(ValueError, match="unsafe path"):
        restore_uploads(io.BytesIO(archive_bytes.getvalue()), target)
    assert not (tmp_path.parent / "escape.txt").exists()
