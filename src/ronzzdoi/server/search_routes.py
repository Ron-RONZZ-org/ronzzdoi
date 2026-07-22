"""Search API endpoints — FTS5 and semantic search across DOI metadata."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from starlette.status import HTTP_501_NOT_IMPLEMENTED

from ronzzdoi.db.service import DOIService
from ronzzdoi.server.auth_middleware import require_permission

router = APIRouter(prefix="/api/v1", tags=["search"])

# ── Module-level references (set by mount_search_routes) ──────────────


_search_svc: DOIService | None = None


def mount_search_routes(app: Any, search_svc: DOIService) -> None:
    """Register search routes on the FastAPI application.

    Args:
        app: The FastAPI application instance.
        search_svc: A configured ``DOIService`` instance (from
            ``ronzzdoi.db.service``) with FTS5 and optional semantic
            search support.
    """
    global _search_svc
    _search_svc = search_svc
    app.include_router(router)


def _get_search_svc() -> DOIService:
    """Return the module-level search service or raise."""
    if _search_svc is None:
        raise RuntimeError(
            "search_routes not initialised. "
            "Call mount_search_routes() during startup."
        )
    return _search_svc


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("/search")
async def search(
    q: str = "",
    mode: str = "fts",
    limit: int = 20,
    offset: int = 0,
    user: dict[str, Any] = Depends(require_permission("read_only")),
) -> dict[str, Any]:
    """Full-text search across DOI metadata.

    Uses FTS5 on the ``dois_fts`` virtual table by default (``mode=fts``).
    When ``mode=semantic`` and the ``lightersearch`` package is installed,
    performs semantic (vector) search instead.

    Returns paginated results with ``items``, ``total``, ``limit``,
    ``offset``, and ``mode``.
    """
    svc = _get_search_svc()

    if not q.strip():
        # Empty query — return empty results
        return {
            "items": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "mode": mode,
        }

    # Validate mode
    if mode not in ("fts", "semantic"):
        mode = "fts"

    results = svc.search(q, mode=mode, limit=limit)

    # Deserialize metadata_json and paginate
    items = []
    for r in results:
        meta = r.get("metadata", json.loads(r.get("metadata_json", "{}")))
        items.append({
            "doi": r["doi"],
            "target_url": r.get("target_url"),
            "title": r.get("title", ""),
            "doi_type": r.get("doi_type", "external"),
            "metadata": meta,
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "deleted_at": r.get("deleted_at"),
        })

    return {
        "items": items,
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "mode": mode,
    }
