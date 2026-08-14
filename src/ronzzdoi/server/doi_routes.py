"""DOI API endpoints — assign, resolve, modify, tombstone, merge, search.

All endpoints require authentication via ``Authorization: Bearer <key>``
except ``GET /{doi}`` (public HTTP redirect).

IMPORTANT: Route order matters.  Specific paths (``/search``, ``/merge``)
MUST be registered before path-parameter routes (``/{doi:path}``) so that
FastAPI/Starlette matches them first.
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from starlette.status import (
    HTTP_204_NO_CONTENT,
    HTTP_302_FOUND,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
)

from ronzzdoi.db.service import DOIService as DBDOIService
from ronzzdoi.doi.constants import is_doi_prefix
from ronzzdoi.doi.exceptions import (
    DOIAmbiguousError,
    DOIExistsError,
    DOIInvalidError,
    DOINotFoundError,
)
from ronzzdoi.doi.schema import (
    DOIAssignRequest,
    DOIModifyRequest,
)
from ronzzdoi.doi.service import DOIService
from ronzzdoi.server.auth_middleware import require_permission

# ═══════════════════════════════════════════════════════════════════════
# Module state
# ═══════════════════════════════════════════════════════════════════════

_doi_svc: DOIService | None = None
_search_svc: DBDOIService | None = None

# ── Routers ───────────────────────────────────────────────────────────
# Generic router holds all /api/v1/doi/* routes.
# The redirect catch-all is on a separate router registered later.
router = APIRouter(tags=["doi"])

# ── Canonical resolution base ──────────────────────────────────────────
# A DOI's browser-resolvable URL must be stable and independent of the
# API origin that served the request (the admin GUI runs on
# doi-admin.ronzz.org, the resolver on doi.ronzz.org — issue #40).
_DEFAULT_RESOLVE_BASE = "https://doi.ronzz.org"
"""Default canonical base for browser-resolvable DOI URLs."""


def _resolve_base() -> str:
    """Return the canonical resolution base for DOI links.

    Read from ``RONZZDOI_RESOLVE_BASE`` at call time (like the public
    rate limits) so tests and operators can override without restart.
    """
    return os.environ.get("RONZZDOI_RESOLVE_BASE", _DEFAULT_RESOLVE_BASE).rstrip("/")


# ═══════════════════════════════════════════════════════════════════════
# mount helpers
# ═══════════════════════════════════════════════════════════════════════


def mount_doi_routes(
    app: Any, doi_svc: DOIService, search_svc: DBDOIService | None = None
) -> None:
    """Register DOI API routes on the FastAPI application.

    Call this BEFORE ``register_doi_redirect(app)`` so that API
    routes (under ``/api/``) take priority over the redirect catch-all.

    Args:
        app: The FastAPI application instance.
        doi_svc: A configured ``DOIService`` instance (from ``ronzzdoi.doi.service``).
        search_svc: An optional ``DBDOIService`` instance (from ``ronzzdoi.db.service``)
            for FTS5 search support.  Falls back to basic listing if omitted.
    """
    global _doi_svc, _search_svc
    _doi_svc = doi_svc
    _search_svc = search_svc
    app.include_router(router)


def register_doi_redirect(app: Any, doi_svc: DOIService | None = None) -> None:
    """Register the public DOI redirect catch-all route.

    MUST be called as the LAST route registration so that all API
    routes take priority.

    The route only responds to paths starting with ``10.ronzz/``.
    Other paths return 404 without interfering with other handlers.

    Args:
        app: The FastAPI application instance.
        doi_svc: Optional DOI service for the redirect handler.  When
            omitted, falls back to the module-level service (set by
            ``mount_doi_routes``).  Pass it explicitly in modes that do
            not mount the internal DOI routes (e.g. ``"public"``) so the
            redirect still works without crashing.
    """
    redirect_router = APIRouter()

    @redirect_router.api_route(
        "/{doi:path}", methods=["GET", "HEAD"], include_in_schema=False
    )
    async def redirect_doi(doi: str, request: Request) -> Response:
        return _handle_redirect(doi, request, doi_svc)

    app.include_router(redirect_router)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _get_doi_svc() -> DOIService:
    """Return the module-level DOIService or raise."""
    if _doi_svc is None:
        raise RuntimeError(
            "doi_routes not initialised. Call mount_doi_routes() during startup."
        )
    return _doi_svc


def _record_to_response(
    record: dict[str, Any],
    include_status: bool = False,
) -> dict[str, Any]:
    """Convert a DOI service record dict to an API response dict.

    Args:
        record: Raw record dict from the DOI service.
        include_status: If True, include ``status`` and ``redirect_history``.

    Returns:
        Response dict.  A browser-resolvable ``resolve_url`` is always
        added, built from the canonical resolution base
        (``RONZZDOI_RESOLVE_BASE``, default ``https://doi.ronzz.org``) —
        not from the request origin, so the URL is stable across the
        admin GUI (doi-admin.ronzz.org) and any other API consumer.
    """
    title = record.get("title", "")
    # Multilingual titles are stored as JSON text — deserialize to a dict
    # for API consumers (idempotent for plain strings and dicts).
    if isinstance(title, str):
        try:
            parsed = json.loads(title)
            if isinstance(parsed, dict):
                title = parsed
        except (json.JSONDecodeError, TypeError):
            pass
    result = {
        "doi": record["doi"],
        "target_url": record.get("target_url"),
        "title": title,
        "doi_type": record.get("doi_type", "external"),
        "metadata": record.get(
            "metadata", json.loads(record.get("metadata_json", "{}"))
        ),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "deleted_at": record.get("deleted_at"),
        "resolve_url": f"{_resolve_base()}/{record['doi']}",
    }
    if record.get("content_kind"):
        # Snippet hits from unified search carry content_kind — pass it
        # through so the frontend can render them distinctly.
        result["content_kind"] = record["content_kind"]
    if include_status:
        result["status"] = record.get("status", "active")
        result["redirect_history"] = record.get("redirect_history", [])
    return result


def _inject_resolve_url(data: Any) -> Any:
    """Recursively add ``resolve_url`` to any dict that has a ``doi`` key.

    Used by the command endpoint so that command-driven GUI tabs
    (e.g. ``!doi resolve``) receive the same resolvable URL as REST
    responses.  Mutates and returns *data*.
    """
    if isinstance(data, dict):
        doi = data.get("doi")
        if isinstance(doi, str) and "resolve_url" not in data:
            data["resolve_url"] = f"{_resolve_base()}/{doi}"
        for value in data.values():
            _inject_resolve_url(value)
    elif isinstance(data, list):
        for item in data:
            _inject_resolve_url(item)
    return data


# ═══════════════════════════════════════════════════════════════════════
# SPECIFIC ROUTES FIRST — must precede path-parameter routes
# ═══════════════════════════════════════════════════════════════════════


class DOIMergeRequest(BaseModel):
    """Request model for merging two DOIs."""

    source_doi: str = Field(..., description="DOI to merge from (will be tombstoned)")
    target_doi: str = Field(..., description="DOI to merge into")
    delete_source: bool = Field(
        default=True, description="If True, tombstone the source after merge"
    )


@router.post("/api/v1/doi/merge")
async def merge_dois(
    body: DOIMergeRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("edit")),
) -> dict[str, Any]:
    """Merge a source DOI into a target DOI.

    The source's redirect history is moved to the target, and the source
    DOI is optionally tombstoned.  If the target DOI has no
    ``target_url`` or ``title``, the source's values are adopted.
    """
    svc = _get_doi_svc()
    try:
        result = svc.merge_dois(
            source_doi=body.source_doi,
            target_doi=body.target_doi,
            delete_source=body.delete_source,
        )
    except DOINotFoundError as exc:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(exc))
    except DOIAmbiguousError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))
    return _record_to_response(result, include_status=True)


@router.get("/api/v1/doi")
async def list_dois(
    request: Request,
    doi_type: str = "",
    include_deleted: bool = False,
    limit: int = 20,
    offset: int = 0,
    user: dict[str, Any] = Depends(require_permission("read_only")),
) -> dict[str, Any]:
    """List DOI records with optional type filter.

    By default only active (non-tombstoned) DOIs are returned.
    """
    svc = _get_doi_svc()
    results = svc.list_dois(limit=limit, offset=offset, include_deleted=include_deleted)
    if doi_type:
        results = [r for r in results if r.get("doi_type") == doi_type]
    return {
        "items": [_record_to_response(r) for r in results],
        "total": len(results),
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/v1/doi/types")
async def doi_types(
    user: dict[str, Any] = Depends(require_permission("read_only")),
) -> dict[str, Any]:
    """Return the supported DOI types and their metadata field schemas.

    Used by the GUI assign/modify form to render a type dropdown
    (autocomplete) and type-specific metadata inputs.  The citation
    module's ``DOC_TYPE_SCHEMAS`` and ``ENTITY_SCHEMAS`` are the source
    of truth.
    """
    from ronzzdoi.citation.schemas import (
        DOC_TYPE_SCHEMAS,
        DOC_TYPES,
        ENTITY_SCHEMAS,
        ENTITY_TYPES,
    )

    return {
        "types": ["external", *DOC_TYPES, *ENTITY_TYPES],
        "schemas": {
            name: [
                {
                    "name": field_name,
                    "required": field_def.required,
                    "types": [t.__name__ for t in field_def.types],
                    "description": field_def.description,
                }
                for field_name, field_def in schema.items()
            ]
            for name, schema in {**DOC_TYPE_SCHEMAS, **ENTITY_SCHEMAS}.items()
        },
    }


@router.get("/api/v1/doi/search")
async def search_dois(
    request: Request,
    q: str = "",
    doi_type: str = "",
    limit: int = 20,
    offset: int = 0,
    user: dict[str, Any] = Depends(require_permission("read_only")),
) -> dict[str, Any]:
    """Search DOIs by type and query.

    Uses FTS5 full-text search when a search service is available.
    Falls back to basic listing.
    """
    svc = _get_doi_svc()

    if not q.strip():
        results = svc.list_dois(limit=limit, offset=offset)
        if doi_type:
            results = [r for r in results if r.get("doi_type") == doi_type]
        return {
            "items": [_record_to_response(r) for r in results],
            "total": len(results),
            "limit": limit,
            "offset": offset,
        }

    if _search_svc is not None:
        results = _search_svc.search_fts(q, limit=limit)
    else:
        results = svc.list_dois(limit=limit, offset=offset)

    if doi_type:
        results = [r for r in results if r.get("doi_type") == doi_type][:limit]

    return {
        "items": [_record_to_response(r) for r in results],
        "total": len(results),
        "limit": limit,
        "offset": offset,
    }


# ═══════════════════════════════════════════════════════════════════════
# PATH-PARAMETER ROUTES — these use {doi:path} to capture slashes
# ═══════════════════════════════════════════════════════════════════════


@router.post("/api/v1/doi", status_code=201)
async def assign_doi(
    body: DOIAssignRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("edit")),
) -> dict[str, Any]:
    """Assign a new ronzzDOI."""
    svc = _get_doi_svc()
    try:
        result = svc.assign(
            target_url=body.target_url,
            doi_type=body.doi_type,
            title=body.title,
            metadata=body.metadata,
        )
    except DOIInvalidError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except DOIExistsError as exc:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(exc))
    return _record_to_response(result)


@router.get("/api/v1/doi/{doi:path}")
async def resolve_doi(
    doi: str,
    request: Request,
    include_redirects: bool = True,
    user: dict[str, Any] = Depends(require_permission("read_only")),
) -> dict[str, Any]:
    """Resolve a DOI and return its full metadata.

    If the DOI is tombstoned, returns the record with ``deleted_at``
    and status ``"tombstone"``.
    """
    svc = _get_doi_svc()
    try:
        record = svc.resolve(doi, include_redirects=include_redirects)
    except DOIAmbiguousError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))

    if record is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail=f"DOI '{doi}' not found."
        )

    return _record_to_response(record, include_status=True)


@router.put("/api/v1/doi/{doi:path}")
async def modify_doi(
    doi: str,
    body: DOIModifyRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_permission("edit")),
) -> dict[str, Any]:
    """Modify an existing DOI record."""
    svc = _get_doi_svc()
    try:
        result = svc.modify(
            doi,
            target_url=body.target_url,
            title=body.title,
            doi_type=body.doi_type,
            metadata=body.metadata,
            redirect_note=body.redirect_note,
        )
    except DOINotFoundError as exc:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(exc))
    except DOIAmbiguousError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))

    return _record_to_response(result, include_status=True)


@router.delete("/api/v1/doi/{doi:path}", status_code=204)
async def delete_doi(
    doi: str,
    user: dict[str, Any] = Depends(require_permission("edit")),
) -> None:
    """Tombstone a DOI (soft-delete)."""
    svc = _get_doi_svc()
    try:
        deleted = svc.delete_doi(doi)
    except DOIAmbiguousError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))

    if not deleted:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail=f"DOI '{doi}' not found."
        )


# ═══════════════════════════════════════════════════════════════════════
# Public DOI redirect (no auth, catch-all, registered last)
# ═══════════════════════════════════════════════════════════════════════


def _handle_redirect(
    doi: str, request: Request, svc: DOIService | None = None
) -> Response:
    """Handle DOI redirect resolution.

    - DOI with ``target_url`` → HTTP 302.
    - Entity DOI with no target_url → HTTP 204.
    - Tombstoned DOI → HTTP 410.
    - Non-existent DOI → HTTP 404.
    - Non-DOI path → HTTP 404.

    Args:
        doi: The DOI path (e.g. ``10.ronzz/abc``).
        request: The incoming request (unused, kept for signature parity).
        svc: Optional DOI service.  Falls back to the module-level
            service; if none is available (redirect registered without a
            service), returns 404 instead of crashing.
    """
    if not is_doi_prefix(doi):
        return Response(status_code=HTTP_404_NOT_FOUND)

    svc = svc or _doi_svc
    if svc is None:
        return Response(
            status_code=HTTP_404_NOT_FOUND,
            content=b'{"detail":"DOI resolution unavailable"}',
            media_type="application/json",
        )

    try:
        record = svc.resolve(doi)
    except DOIAmbiguousError:
        return Response(
            status_code=HTTP_400_BAD_REQUEST,
            content=b'{"detail":"Ambiguous DOI prefix"}',
            media_type="application/json",
        )

    if record is None:
        return Response(
            status_code=HTTP_404_NOT_FOUND,
            content=bytes(f'{{"detail":"DOI \'{doi}\' not found."}}', "utf-8"),
            media_type="application/json",
        )

    if record.get("deleted_at"):
        return Response(
            status_code=410,
            content=bytes(
                f'{{"detail":"DOI \'{doi}\' has been deleted (tombstoned)."}}', "utf-8"
            ),
            media_type="application/json",
        )

    target_url = record.get("target_url")
    if not target_url:
        return Response(status_code=HTTP_204_NO_CONTENT)

    return RedirectResponse(
        url=target_url, status_code=HTTP_302_FOUND, headers={"X-DOI": doi}
    )
