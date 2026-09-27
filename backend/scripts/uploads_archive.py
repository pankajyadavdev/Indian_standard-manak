"""Stream and safely restore the configured upload directory as a gzip tar archive."""

from __future__ import annotations

import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


def upload_root() -> Path:
    root = Path(os.environ.get("UPLOAD_DIR", "./data/uploads")).resolve()
    if not root.is_dir():
        raise ValueError(f"Upload directory does not exist: {root}")
    return root


def backup_uploads(root: Path, output) -> None:
    root = root.resolve(strict=True)
    paths = sorted(root.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("Upload backup refuses symbolic links")
    with tarfile.open(fileobj=output, mode="w|gz") as archive:
        for path in paths:
            archive.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)


def restore_uploads(source, root: Path) -> None:
    """Restore only regular files/directories into a new or empty upload volume."""
    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("Upload restore target must be empty")
    root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="is-upload-restore-") as temp_name:
        temporary = Path(temp_name)
        archive_path = temporary / "uploads.tar.gz"
        with archive_path.open("wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)

        staging = temporary / "uploads"
        staging.mkdir()
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
            seen = set()
            for member in members:
                name = member.name
                relative = PurePosixPath(name)
                if (
                    not name
                    or "\\" in name
                    or relative.is_absolute()
                    or any(part in {"", ".", ".."} for part in relative.parts)
                    or (relative.parts and ":" in relative.parts[0])
                ):
                    raise ValueError("Upload archive contains an unsafe path")
                if name in seen:
                    raise ValueError("Upload archive contains duplicate paths")
                seen.add(name)
                if not (member.isfile() or member.isdir()):
                    raise ValueError("Upload archive contains a link or special file")
            archive.extractall(path=staging, members=members, filter="data")

        shutil.copytree(staging, root, dirs_exist_ok=True)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"backup", "restore"}:
        raise SystemExit("Usage: uploads_archive.py backup|restore")
    root = upload_root()
    if sys.argv[1] == "backup":
        backup_uploads(root, sys.stdout.buffer)
    else:
        restore_uploads(sys.stdin.buffer, root)


if __name__ == "__main__":
    main()
