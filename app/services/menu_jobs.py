"""
Menu uploads run in the background. The upload returns a job at once, and the
owner's page polls the job for real progress: indexing, then reading the
dishes part by part, then saving.

Jobs live in `menu_jobs`, so a page reload shows where a menu got to. A job
that was running when the server restarted is reported as interrupted, not
left spinning forever.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from core.database import get_database
from services.knowledge_ingestion import ingest_pdf_bytes_for_tenant
from services.menu_extraction import chunk_text, extract_menu_items, replace_menu_items

logger = logging.getLogger(__name__)

MENU_JOBS = "menu_jobs"
STALE_AFTER = timedelta(minutes=10)
ACTIVE_STATUSES = ("queued", "running")

# Keep a reference to each running task, so it isn't garbage collected mid-run.
_tasks: set = set()


def public(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["id"] = doc["job_id"]
    return out


async def create_job(db, tenant_id: str, filename: str) -> str:
    now = datetime.now(timezone.utc)
    job_id = f"menu_{uuid.uuid4().hex[:12]}"
    await db[MENU_JOBS].insert_one({
        "job_id": job_id,
        "tenant_id": tenant_id,
        "filename": filename,
        "status": "queued",
        "stage": "received",
        "label": "Received your menu",
        "chunks_done": 0,
        "chunks_total": 0,
        "items_found": 0,
        "error": None,
        "created_at": now,
        "updated_at": now,
    })
    return job_id


async def active_job(db, tenant_id: str) -> Optional[Dict[str, Any]]:
    """A menu that is still being read for this restaurant, if any."""
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    doc = await db[MENU_JOBS].find_one({
        "tenant_id": tenant_id,
        "status": {"$in": list(ACTIVE_STATUSES)},
        "updated_at": {"$gte": cutoff},
    })
    return doc


async def _update(job_id: str, **fields: Any) -> None:
    fields["updated_at"] = datetime.now(timezone.utc)
    await get_database()[MENU_JOBS].update_one({"job_id": job_id}, {"$set": fields})


async def _run(job_id: str, tenant_id: str, file_bytes: bytes, filename: str) -> None:
    try:
        await _update(job_id, status="running", stage="indexing", label="Indexing your menu for the agent")
        result = await ingest_pdf_bytes_for_tenant(file_bytes=file_bytes, filename=filename, tenant_id=tenant_id)
        if result.get("status") == "error":
            await _update(job_id, status="failed", stage="failed", error=result.get("message", "Could not read that PDF."))
            return

        full_text = result.pop("full_text", "")
        total = len(chunk_text(full_text))
        await _update(job_id, stage="reading", label="Reading dishes, prices and categories",
                      chunks_done=0, chunks_total=total)

        async def progress(done: int, all_parts: int, note: Optional[str]) -> None:
            fields: Dict[str, Any] = {"chunks_done": done, "chunks_total": all_parts}
            # While the model is busy, say so instead of a silent bar.
            fields["label"] = note or "Reading dishes, prices and categories"
            await _update(job_id, **fields)

        items = await extract_menu_items(full_text, on_progress=progress)

        await _update(job_id, stage="saving", label="Saving dishes")
        count = await replace_menu_items(get_database(), tenant_id, result["doc_id"], items)
        await _update(job_id, status="done", stage="done",
                      label=f"{count} dishes found", items_found=count, error=None)
    except Exception as e:
        logger.exception(f"Menu job {job_id} failed: {e}")
        await _update(job_id, status="failed", stage="failed",
                      error="We couldn't finish reading this menu. Try again, or upload a clearer PDF.")


def start_job(job_id: str, tenant_id: str, file_bytes: bytes, filename: str) -> None:
    task = asyncio.create_task(_run(job_id, tenant_id, file_bytes, filename))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def mark_stale_jobs(db, tenant_id: str) -> None:
    """Jobs left 'running' by a server restart are reported as interrupted."""
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    await db[MENU_JOBS].update_many(
        {"tenant_id": tenant_id, "status": {"$in": list(ACTIVE_STATUSES)}, "updated_at": {"$lt": cutoff}},
        {"$set": {"status": "failed", "stage": "failed",
                  "error": "The reading was interrupted. Upload the menu again.",
                  "updated_at": datetime.now(timezone.utc)}},
    )


async def ensure_menu_job_indexes(db) -> None:
    await db[MENU_JOBS].create_index([("job_id", 1)], unique=True, name="uniq_menu_job")
    await db[MENU_JOBS].create_index([("tenant_id", 1), ("created_at", -1)], name="tenant_menu_jobs")
