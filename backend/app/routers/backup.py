"""Backup and maintenance routes."""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.services.audit import audit
from app.services.backup import create_backup as _create_backup
from app.services.backup import list_backups as _list_backups
from app.services.backup import restore_backup as _restore_backup
from app.services.security import safe_name
from app.services.session_cleanup import run_cleanup

router = APIRouter(prefix="/api/v1", tags=["backup"])


# ── Maintenance ──


@router.post("/maintenance/sessions/cleanup")
async def cleanup_sessions():
    """Run a one-shot sweep of old session artifacts.

    Removes files under ``data/user/{solve,research,notebooks,guide}``
    whose mtime is older than ``UDIP_SESSION_MAX_AGE_DAYS`` (default 30).
    Returns a small report with counts and any per-file errors so the
    operator can see what happened. Safe to call repeatedly; the walk
    is idempotent.
    """
    return run_cleanup().to_dict()


# ── Backup endpoints ────────────────────────────────────────────────


@router.post("/backup")
async def create_backup(kb_name: str | None = None):
    """Create a backup of knowledge bases.

    If ``kb_name`` is provided, only that KB is backed up.
    Otherwise, all knowledge bases are backed up.
    """
    result = _create_backup(kb_name)
    if result["success"]:
        audit("backup.created", kb_name=kb_name, backup_name=result["name"])
        return result
    raise HTTPException(status_code=500, detail=result["error"])


@router.get("/backup")
async def list_backups():
    """List all available knowledge base backups."""
    return {"backups": _list_backups()}


@router.post("/backup/{backup_name}/restore")
async def restore_backup(backup_name: str, kb_name: str | None = None):
    """Restore a knowledge base from backup."""
    safe_backup = safe_name(backup_name)
    if not safe_backup or safe_backup == "default":
        raise HTTPException(status_code=400, detail="Invalid backup name")

    result = _restore_backup(safe_backup, kb_name)
    if result["success"]:
        audit("backup.restored", backup_name=result["name"], kb_name=kb_name)
        return result
    raise HTTPException(status_code=404, detail=result["error"])
