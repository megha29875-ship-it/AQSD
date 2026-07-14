
"""
AQSD Professional
Module: Automatic Backup Manager
Version: 1.0

Creates timestamped backups of Dashboard.xlsx and keeps only the
latest configured number of backups.

Backup folder:
    AQSD/Backups

Examples:
    python auto_backup.py
    python auto_backup.py --keep 30
    python auto_backup.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from datetime import datetime
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
SOURCE = BASE / "Output" / "Dashboard.xlsx"
BACKUP_DIR = BASE / "Backups"

DEFAULT_KEEP = 30


def file_hash(path: Path) -> str:
    """Return a short SHA-256 checksum for backup verification."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()[:12]


def backup_files() -> list[Path]:
    """Return dashboard backups newest first."""
    if not BACKUP_DIR.exists():
        return []

    return sorted(
        BACKUP_DIR.glob("Dashboard_*.xlsx"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def create_backup() -> Path:
    """Create and verify one timestamped Dashboard backup."""
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Dashboard not found:\n{SOURCE}"
        )

    if SOURCE.stat().st_size == 0:
        raise RuntimeError(
            "Dashboard.xlsx is empty. Backup cancelled."
        )

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destination = BACKUP_DIR / f"Dashboard_{timestamp}.xlsx"

    shutil.copy2(SOURCE, destination)

    if not destination.exists():
        raise RuntimeError("Backup file was not created.")

    if destination.stat().st_size != SOURCE.stat().st_size:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            "Backup verification failed: file sizes differ."
        )

    source_hash = file_hash(SOURCE)
    backup_hash = file_hash(destination)

    if source_hash != backup_hash:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            "Backup verification failed: checksums differ."
        )

    return destination


def remove_old_backups(keep: int) -> int:
    """Delete older backups while retaining the newest files."""
    if keep < 1:
        raise ValueError("--keep must be at least 1.")

    files = backup_files()
    removed = 0

    for path in files[keep:]:
        path.unlink()
        removed += 1

    return removed


def list_backups() -> None:
    files = backup_files()

    print("\nAQSD DASHBOARD BACKUPS")
    print("=" * 68)

    if not files:
        print("No backups found.")
        return

    for index, path in enumerate(files, start=1):
        modified = datetime.fromtimestamp(
            path.stat().st_mtime
        ).strftime("%d-%m-%Y %H:%M:%S")

        size_mb = path.stat().st_size / (1024 * 1024)

        print(
            f"{index:>3}. {path.name:<42} "
            f"{size_mb:>7.2f} MB  {modified}"
        )

    print("=" * 68)
    print(f"Total backups: {len(files)}")
    print(f"Folder: {BACKUP_DIR}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and manage AQSD Dashboard backups."
    )

    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=(
            "Number of newest backups to retain "
            f"(default: {DEFAULT_KEEP})."
        ),
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing backups without creating a new one.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.list:
        list_backups()
        return

    print("\nAQSD AUTOMATIC BACKUP")
    print("=" * 68)

    try:
        destination = create_backup()
        removed = remove_old_backups(args.keep)

    except PermissionError as error:
        raise PermissionError(
            "Dashboard.xlsx is locked. Close Excel and run again."
        ) from error

    print("Backup created successfully.")
    print(f"File: {destination}")
    print(f"Checksum: {file_hash(destination)}")
    print(f"Old backups removed: {removed}")
    print(f"Backups retained: {len(backup_files())}")
    print("=" * 68)


if __name__ == "__main__":
    main()
