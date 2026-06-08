"""Knowledge base backup service — automated backup with rotation."""

import gzip
import hashlib
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_DIR = os.environ.get("UDIP_BACKUP_DIR", "data/backups")
MAX_BACKUPS = int(os.environ.get("UDIP_MAX_BACKUPS", "5"))
DATA_DIR = os.environ.get("UDIP_DATA_DIR", "data")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _compress_tree(src: Path, dst_gz: Path) -> int:
    import tarfile
    with tarfile.open(dst_gz, "w:gz") as tar:
        tar.add(src, arcname=src.name)
    return dst_gz.stat().st_size


def _decompress_tree(archive: Path, dest: Path) -> None:
    import tarfile
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(dest)


def get_backup_dir() -> Path:
    """Return the backup directory, creating it if needed."""
    p = Path(BACKUP_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def create_backup(kb_name: str | None = None) -> dict:
    """Create a backup of knowledge bases.

    If ``kb_name`` is provided, only that KB is backed up.
    Otherwise, all KBs under ``data/knowledge/`` are backed up.

    Returns a dict with backup metadata.
    """
    from app.services.security import resolve_within, safe_name

    backup_dir = get_backup_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Sanitize kb_name if provided
    safe_kb = None
    if kb_name:
        safe_kb = safe_name(kb_name)
        if not safe_kb:
            return {"success": False, "error": "Invalid knowledge base name"}

    label = safe_kb or "all"
    backup_name = f"kb_backup_{label}_{timestamp}"
    backup_path = backup_dir / backup_name

    try:
        resolve_within(backup_dir, backup_path)
    except ValueError as exc:
        return {"success": False, "error": f"Invalid backup path: {exc}"}

    src = Path(DATA_DIR) / "knowledge"
    if not src.exists():
        return {"success": False, "error": "No knowledge base directory found"}

    if safe_kb:
        src = src / safe_kb
        try:
            resolve_within(Path(DATA_DIR) / "knowledge", src)
        except ValueError as exc:
            return {"success": False, "error": f"Invalid source path: {exc}"}
        if not src.exists():
            return {"success": False, "error": f"KB '{kb_name}' not found"}

    try:
        shutil.copytree(src, backup_path)
        raw_size = sum(f.stat().st_size for f in backup_path.rglob("*") if f.is_file())
        gz_path = backup_path.parent / f"{backup_path.name}.tar.gz"
        compressed_size = _compress_tree(backup_path, gz_path)
        checksum = _sha256_file(gz_path)
        checksum_path = backup_path.parent / f"{backup_path.name}.sha256"
        checksum_path.write_text(checksum, encoding="utf-8")
        shutil.rmtree(backup_path)
        logger.info("backup_created: name=%s raw=%d compressed=%d sha256=%s",
                     backup_name, raw_size, compressed_size, checksum[:16])
        _rotate_backups()
        return {
            "success": True,
            "name": backup_name,
            "path": str(gz_path),
            "raw_size_bytes": raw_size,
            "compressed_size_bytes": compressed_size,
            "sha256": checksum,
        }
    except Exception as exc:
        logger.error("backup_failed: name=%s error=%s", backup_name, exc)
        return {"success": False, "error": str(exc)}


def restore_backup(backup_name: str, kb_name: str | None = None) -> dict:
    """Restore a knowledge base from backup.

    If ``kb_name`` is provided, only that KB is restored.
    Otherwise, the entire backup is restored.
    """
    from app.services.security import resolve_within, safe_name

    backup_dir = get_backup_dir()

    cleaned_backup_name = safe_name(backup_name)
    if not cleaned_backup_name:
        return {"success": False, "error": "Invalid backup name"}

    backup_path = backup_dir / cleaned_backup_name
    try:
        resolve_within(backup_dir, backup_path)
    except ValueError as exc:
        return {"success": False, "error": f"Invalid backup path: {exc}"}

    if not backup_path.exists():
        gz_path = backup_dir / f"{cleaned_backup_name}.tar.gz"
        if not gz_path.exists():
            return {"success": False, "error": f"Backup '{backup_name}' not found"}
        backup_path = backup_dir / cleaned_backup_name
        _decompress_tree(gz_path, backup_dir)

    dest = Path(DATA_DIR) / "knowledge"
    dest.mkdir(parents=True, exist_ok=True)

    safe_kb = None
    if kb_name:
        safe_kb = safe_name(kb_name)
        if not safe_kb:
            return {"success": False, "error": "Invalid knowledge base name"}

    try:
        if safe_kb:
            src = backup_path / safe_kb
            resolve_within(backup_path, src)
            if not src.exists():
                return {"success": False, "error": f"KB '{kb_name}' not in backup"}
            target = dest / safe_kb
            resolve_within(dest, target)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        else:
            for item in backup_path.iterdir():
                target = dest / item.name
                resolve_within(dest, target)
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(item, target)

        logger.info("backup_restored: name=%s", cleaned_backup_name)
        return {"success": True, "name": cleaned_backup_name}
    except Exception as exc:
        logger.error("restore_failed: name=%s error=%s", cleaned_backup_name, exc)
        return {"success": False, "error": str(exc)}


def list_backups() -> list[dict]:
    """List all available backups sorted by creation time (newest first)."""
    backup_dir = get_backup_dir()
    backups = []
    for item in sorted(backup_dir.iterdir(), reverse=True):
        if item.is_dir() and item.name.startswith("kb_backup_"):
            gz = backup_dir / f"{item.name}.tar.gz"
            sha = backup_dir / f"{item.name}.sha256"
            size = gz.stat().st_size if gz.exists() else sum(
                f.stat().st_size for f in item.rglob("*") if f.is_file()
            )
            checksum = sha.read_text().strip() if sha.exists() else None
            backups.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "size_bytes": size,
                    "sha256": checksum,
                    "created": datetime.fromtimestamp(
                        item.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
    return backups


def _rotate_backups():
    """Remove oldest backups if count exceeds MAX_BACKUPS."""
    backup_dir = get_backup_dir()
    backups = sorted(
        [d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("kb_backup_")],
        key=lambda d: d.stat().st_mtime,
    )
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        shutil.rmtree(oldest)
        gz = backup_dir / f"{oldest.name}.tar.gz"
        sha = backup_dir / f"{oldest.name}.sha256"
        if gz.exists():
            gz.unlink()
        if sha.exists():
            sha.unlink()
        logger.info("backup_rotated: removed=%s", oldest.name)
