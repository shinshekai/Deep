"""Data export, deletion, summary, and audit routes."""

import io
import json as _json
import zipfile
import logging

import io
import json as _json
import zipfile
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app import state
from app.services.provenance_audit import verify_provenance_integrity
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["data"])

USER_DATA_DIRS = ["solve", "research", "notebooks", "guide"]


@router.get("/system/data/export")
async def export_user_data():
    """Export all user data as a ZIP archive (GDPR data portability)."""
    data_root = Path("data/user")
    buf = io.BytesIO()
    file_count = 0

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for subdir in USER_DATA_DIRS:
            dir_path = data_root / subdir
            if not dir_path.exists():
                continue
            for f in dir_path.rglob("*"):
                if f.is_file():
                    arcname = f"data/{subdir}/{f.relative_to(dir_path)}"
                    zf.write(f, arcname)
                    file_count += 1

        metadata = {
            "exported_at": time.time(),
            "file_count": file_count,
            "directories": USER_DATA_DIRS,
        }
        zf.writestr("metadata.json", _json.dumps(metadata, indent=2))

    buf.seek(0)
    ts = int(time.time())
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=udip-export-{ts}.zip"},
    )


@router.delete("/system/data")
async def delete_user_data(confirm: bool = False):
    """Delete all user data (GDPR right to erasure). Requires confirm=true."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to delete all user data")

    data_root = Path("data/user")
    deleted = 0

    for subdir in USER_DATA_DIRS:
        dir_path = data_root / subdir
        if not dir_path.exists():
            continue
        for f in dir_path.rglob("*"):
            if f.is_file():
                try:
                    f.unlink()
                    deleted += 1
                except OSError as e:
                    logger.warning("Failed to delete %s: %s", f, e)

    logger.info("GDPR deletion: removed %d files", deleted)
    return {"deleted_count": deleted}


@router.get("/system/data/summary")
async def data_summary():
    """Summary of stored user data (file counts and sizes per directory)."""
    data_root = Path("data/user")
    directories = {}
    total_files = 0
    total_size = 0

    for subdir in USER_DATA_DIRS:
        dir_path = data_root / subdir
        if not dir_path.exists():
            directories[subdir] = {"files": 0, "size_bytes": 0}
            continue
        count = 0
        size = 0
        for f in dir_path.rglob("*"):
            if f.is_file():
                count += 1
                size += f.stat().st_size
        directories[subdir] = {"files": count, "size_bytes": size}
        total_files += count
        total_size += size

    return {
        "directories": directories,
        "total_files": total_files,
        "total_size_bytes": total_size,
    }


@router.get("/system/data/provenance-audit")
async def audit_provenance():
    """Verify provenance_log integrity against entity tables."""
    if not state.memory_service:
        raise HTTPException(status_code=503, detail="Memory service not available")
    db = await state.memory_service._get_db()
    try:
        result = await verify_provenance_integrity(db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/system/data/audit-log")
async def get_audit_log(format: str = "json", event: str | None = None, limit: int = 1000):
    """Export audit events as JSON or CSV for SIEM ingestion."""
    from app.services.audit import export_audit_log

    if format not in ("json", "csv"):
        raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")
    result = export_audit_log(format=format, event_filter=event, limit=limit)
    if format == "csv":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=result, media_type="text/csv")
    return _json.loads(result)


@router.get("/system/data/audit-stats")
async def get_audit_stats():
    """Get audit event statistics and catalog."""
    from app.services.audit import get_audit_stats

    return get_audit_stats()
