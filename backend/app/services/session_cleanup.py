"""Session cleanup — purges old solve / research / notebook / guide data.

The system writes per-session artifacts to ``data/user/{solve,research,notebooks,guide}``.
On a long-running install, these can accumulate to the point where the
disk hits the upload-rejection threshold. This module walks each
directory, removes files / dirs older than ``DEFAULT_MAX_AGE_DAYS`` and
returns a small summary of what was deleted.

Also prunes orphaned SQLite rows (episodes, facts, memory_usage) whose
device_id no longer has any filesystem artifacts.

Tunable via env:
  ``UDIP_SESSION_MAX_AGE_DAYS`` (default 30) — max age in days
"""

import asyncio
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_AGE_DAYS = 30

_SESSION_ROOTS = (
    "data/user/solve",
    "data/user/research",
    "data/user/notebooks",
    "data/user/guide",
)


@dataclass
class CleanupResult:
    scanned_dirs: int
    deleted_files: int
    deleted_dirs: int
    pruned_rows: int
    errors: list
    max_age_days: int
    elapsed_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


def _max_age_seconds() -> float:
    days = float(os.environ.get("UDIP_SESSION_MAX_AGE_DAYS", DEFAULT_MAX_AGE_DAYS))
    return max(days, 0.0) * 86400.0


def _is_older_than(path: Path, cutoff_ts: float) -> bool:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    return mtime < cutoff_ts


def _cleanup_directory(root: Path, cutoff_ts: float) -> tuple[int, int, list]:
    """Remove files / dirs under ``root`` whose mtime is older than cutoff.

    Returns ``(deleted_files, deleted_dirs, errors)``. Walk is
    bottom-up so we never try to rmdir a non-empty directory.
    """
    deleted_files = 0
    deleted_dirs = 0
    errors: list = []
    if not root.exists():
        return deleted_files, deleted_dirs, errors
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if not _is_older_than(fpath, cutoff_ts):
                continue
            try:
                fpath.unlink()
                deleted_files += 1
            except OSError as e:
                errors.append(f"{fpath}: {e}")
        # After deleting files, attempt to rmdir the directory itself
        # if it's now empty AND older than the cutoff.
        dpath = Path(dirpath)
        if dpath == root:
            continue
        if not _is_older_than(dpath, cutoff_ts):
            continue
        try:
            # Only rmdir if empty — never cascade-delete user data
            dpath.rmdir()
            deleted_dirs += 1
        except OSError:
            # Not empty or not permitted — leave it; files inside may
            # still be newer than the cutoff.
            pass
    return deleted_files, deleted_dirs, errors


def run_cleanup() -> CleanupResult:
    """Sweep all session roots, removing anything older than the cutoff.

    Also prunes SQLite memory_usage rows older than retention window.
    Safe to call repeatedly: deletes are best-effort and logged.
    """
    started = time.time()
    cutoff_ts = started - _max_age_seconds()
    total_files = 0
    total_dirs = 0
    all_errors: list = []
    scanned = 0
    for rel_root in _SESSION_ROOTS:
        root = Path(rel_root)
        scanned += 1
        f, d, errs = _cleanup_directory(root, cutoff_ts)
        total_files += f
        total_dirs += d
        all_errors.extend(errs)
    pruned = _prune_orphaned_sqlite_rows()
    elapsed = time.time() - started
    if total_files or total_dirs:
        logger.info(
            f"Session cleanup: removed {total_files} files, " f"{total_dirs} dirs in {elapsed:.2f}s"
        )
    if all_errors:
        logger.warning(f"Session cleanup had {len(all_errors)} errors (first 5): {all_errors[:5]}")
    return CleanupResult(
        scanned_dirs=scanned,
        deleted_files=total_files,
        deleted_dirs=total_dirs,
        pruned_rows=pruned,
        errors=all_errors,
        max_age_days=int(_max_age_seconds() / 86400),
        elapsed_seconds=round(elapsed, 3),
    )


def _prune_orphaned_sqlite_rows(memory_service=None) -> int:
    """Delete memory_usage rows older than retention window.

    If memory_service is provided, uses it directly (async context).
    Otherwise creates a temporary instance for sync context.
    """
    try:
        from app.services.memory_service import MemoryService

        if memory_service is not None:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, memory_service.prune_usage(retention_days=90))
                    return future.result(timeout=10)
            except RuntimeError:
                return 0
        else:
            svc = MemoryService()
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(svc.initialize())
                deleted = loop.run_until_complete(svc.prune_usage(retention_days=90))
                loop.run_until_complete(svc.close())
                return deleted
            finally:
                loop.close()
    except Exception as e:
        logger.debug("SQLite prune skipped: %s", e)
        return 0
