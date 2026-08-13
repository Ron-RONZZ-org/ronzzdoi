"""Snippet API endpoints — assign, resolve, modify, tombstone.

All endpoints require authentication via ``Authorization: Bearer <key>``:
``edit`` permission for writes, ``read_only`` for resolution.  Snippet
content is served to the public via ``/public/v1/snippet`` (see
``public_routes.py``) and rendered as embeds by the public web app.

IMPORTANT: Route order matters.  Specific paths must be registered before
path-parameter routes so that FastAPI/Starlette matches them first.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)

from ronzzdoi.doi.exceptions import DOIAmbiguousError, DOINotFoundError
from ronzzdoi.server.auth_middleware import require_permission
from ronzzdoi.snippet.exceptions import (
    SnippetInvalidError,
    SnippetNotFoundError,
    SnippetSourceNotFoundError,
)
from ronzzdoi.snippet.schema import (
    SnippetAssignRequest,
    SnippetModifyRequest,
)
from ronzzdoi.snippet.service import SnippetService

# ═══════════════════════════════════════════════════════════════════════
# Module state
# ═══════════════════════════════════════════════════════════════════════

_snippet_svc: SnippetService | None = None

router = APIRouter(prefix="/api/v1", tags=["snippet"])


# ═══════════════════════════════════════════════════════════════════════
# Mount helper
# ═══════════════════════════════════════════════════════════════════════


def mount_snippet_routes(app: Any, snippet_svc: SnippetService) -> None:
    """Register snippet API routes on the FastAPI application.

    Args:
        app: The FastAPI application instance.
        snippet_svc: A configured :class:`SnippetService` instance.
    """
    global _snippet_svc
    _snippet_svc = snippet_svc
    app.include_router(router)


def _get_snippet_svc() -> SnippetService:
    """Return the module-level SnippetService or raise."""
    if _snippet_svc is None:
        raise RuntimeError(
            "snippet_routes not initialised. Call mount_snippet_routes() during startup."
        )
    return _snippet_svc


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _record_to_snippet_response(
    record: dict[str, Any],
    include_status: bool = False,
) -> dict[str, Any]:
    """Convert a snippet record dict to an API response dict.

    The record is the merged DOI + snippets row produced by
    :class:`SnippetService`.
    """
    result = {
        "doi": record["doi"],
        "title": record.get("title", ""),
        "content_kind": record.get("content_kind", "text"),
        "content": record.get("content", ""),
        "language": record.get("language", ""),
        "source_doi": record.get("source_doi"),
        "page_start": record.get("page_start", ""),
        "page_end": record.get("page_end", ""),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "deleted_at": record.get("deleted_at"),
    }
    if include_status:
        result["status"] = record.get("status", "active")
        result["redirect_history"] = record.get("redirect_history", [])
    return result


# ═══════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════


@router.post("/snippet", status_code=201)
async def assign_snippet(
    body: SnippetAssignRequest,
    user: dict[str, Any] = Depends(require_permission("edit")),
) -> dict[str, Any]:
    """Assign a new snippet (text quotation, code, or KaTeX math).

    Creates a DOI (``doi_type='snippet'``) plus the snippet content
    atomically.
    """
    svc = _get_snippet_svc()
    try:
        result = svc.assign(
            content_kind=body.content_kind,
            content=body.content,
            title=body.title,
            language=body.language,
            source_doi=body.source_doi,
            page_start=body.page_start,
            page_end=body.page_end,
        )
    except SnippetInvalidError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except SnippetSourceNotFoundError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _record_to_snippet_response(result)


@router.get("/snippet/{doi:path}")
async def resolve_snippet(
    doi: str,
    include_redirects: bool = True,
    user: dict[str, Any] = Depends(require_permission("read_only")),
) -> dict[str, Any]:
    """Resolve a snippet DOI and return its content + metadata.

    Returns 404 for unknown DOIs.  A DOI that exists but is not a
    snippet resolves to its DOI record (snippet fields omitted).
    """
    svc = _get_snippet_svc()
    try:
        record = svc.resolve(doi, include_redirects=include_redirects)
    except DOIAmbiguousError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))

    if record is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail=f"DOI '{doi}' not found."
        )

    return _record_to_snippet_response(record, include_status=True)


@router.put("/snippet/{doi:path}")
async def modify_snippet(
    doi: str,
    body: SnippetModifyRequest,
    user: dict[str, Any] = Depends(require_permission("edit")),
) -> dict[str, Any]:
    """Modify an existing snippet.  All fields optional."""
    svc = _get_snippet_svc()
    try:
        result = svc.modify(
            doi,
            content=body.content,
            content_kind=body.content_kind,
            title=body.title,
            language=body.language,
            source_doi=body.source_doi,
            page_start=body.page_start,
            page_end=body.page_end,
        )
    except DOINotFoundError as exc:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(exc))
    except SnippetNotFoundError as exc:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(exc))
    except DOIAmbiguousError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))
    except SnippetInvalidError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except SnippetSourceNotFoundError as exc:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return _record_to_snippet_response(result, include_status=True)


@router.delete("/snippet/{doi:path}", status_code=204)
async def delete_snippet(
    doi: str,
    user: dict[str, Any] = Depends(require_permission("edit")),
) -> None:
    """Tombstone a snippet (soft-delete both the DOI and content rows)."""
    svc = _get_snippet_svc()
    try:
        deleted = svc.delete(doi)
    except DOIAmbiguousError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))
    except SnippetNotFoundError as exc:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(exc))

    if not deleted:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND, detail=f"DOI '{doi}' not found."
        )
