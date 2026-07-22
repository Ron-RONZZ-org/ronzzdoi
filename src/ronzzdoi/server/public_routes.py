"""Public read-only API endpoints with rate-limiting.

These endpoints mirror the internal ``/api/v1/*`` endpoints but:

- Require **no authentication** (no ``Authorization`` header needed).
- Return only **public-safe fields** via dedicated Pydantic schemas.
- Are **rate-limited** via ``slowapi`` (required for public mode — install
  with ``pip install 'ronzzdoi[public]'``).

Mount these via :func:`mount_public_routes` *after* the database and
services are initialised.  Example::

    from ronzzdoi.server.public_routes import mount_public_routes

    mount_public_routes(
        app,
        doi_svc=doi_crud_svc,
        search_svc=db_search_svc,
        formatter=citation_formatter,
    )
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from ronzzdoi.citation import CitationFormatter
from ronzzdoi.doi.exceptions import DOINotFoundError
from ronzzdoi.doi.service import DOIService
from ronzzdoi.db.service import DOIService as DBDOIService
from ronzzdoi.server.public_schemas import (
    PublicCitationResponse,
    PublicDOIResponse,
    PublicHealthResponse,
    PublicSearchResponse,
)

# ═══════════════════════════════════════════════════════════════════════
# slowapi — limiter instance
# ═══════════════════════════════════════════════════════════════════════

_limiter = Limiter(key_func=get_remote_address)
"""Module-level ``Limiter`` instance.  Attached to ``app.state`` by
:func:`mount_public_routes` so the 429 middleware can find it."""


# ═══════════════════════════════════════════════════════════════════════
# Module state — set by mount_public_routes()
# ═══════════════════════════════════════════════════════════════════════

_doi_svc: DOIService | None = None
_search_svc: DBDOIService | None = None
_formatter: CitationFormatter | None = None

# ── Router ────────────────────────────────────────────────────────────
router = APIRouter(prefix="/public/v1", tags=["public"])


# ═══════════════════════════════════════════════════════════════════════
# Mount helper
# ═══════════════════════════════════════════════════════════════════════


def mount_public_routes(
    app: Any,
    doi_svc: DOIService,
    search_svc: DBDOIService | None = None,
    formatter: CitationFormatter | None = None,
) -> None:
    """Register public read-only routes on the FastAPI application.

    Attaches the ``slowapi`` ``Limiter`` to ``app.state`` and registers
    the 429 exception handler.

    Args:
        app: The FastAPI application instance.
        doi_svc: A configured ``DOIService`` instance (DOI CRUD).
        search_svc: An optional ``DOIService`` instance (FTS5 search).
        formatter: An optional ``CitationFormatter`` instance.
    """
    global _doi_svc, _search_svc, _formatter

    _doi_svc = doi_svc
    _search_svc = search_svc
    _formatter = formatter

    # ── slowapi initialisation ──────────────────────────────────────
    app.state.limiter = _limiter
    app.add_exception_handler(429, _rate_limit_exceeded_handler)

    app.include_router(router)


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════


def _get_doi_svc() -> DOIService:
    if _doi_svc is None:
        raise RuntimeError("public_routes not initialised — call mount_public_routes() first")
    return _doi_svc


def _get_search_svc() -> DBDOIService | None:
    return _search_svc


def _get_formatter() -> CitationFormatter | None:
    return _formatter


def _record_to_public(record: dict[str, Any]) -> dict[str, Any]:
    """Convert a DOI service record dict to a public-safe response dict.

    Excludes: ``status``, ``redirect_history``, ``deleted_at``, ``updated_at``.

    Passes through the optional ``snippet`` key (populated by FTS5 search).
    """
    metadata = record.get("metadata")
    if metadata is None:
        metadata = json.loads(record.get("metadata_json", "{}"))
    return {
        "doi": record["doi"],
        "target_url": record.get("target_url"),
        "title": record.get("title", ""),
        "doi_type": record.get("doi_type", "external"),
        "metadata": metadata,
        "created_at": record["created_at"],
        "snippet": record.get("snippet"),
    }


# ── Rate limit helpers (read from env vars at request time) ──────────

_SEARCH_LIMIT_CAP: int = 50
"""Hard cap on the ``limit`` parameter for public search."""


def _default_rate_limit(env_var: str, default: str) -> str:
    """Read a rate limit from an environment variable, falling back to *default*.

    Evaluated at request time (via callable) so that tests and operators
    can change limits without restarting.
    """
    return os.environ.get(env_var, default)


# Each endpoint's limit is a callable so it is evaluated at *request* time.
# This allows tests to ``monkeypatch.setenv()`` and see the new limit
# immediately, and operators to adjust limits without a process restart.
def _doi_rate_limit() -> str:
    return _default_rate_limit("RONZZDOI_PUBLIC_RATE_LIMIT_DOI", "100/minute")


def _search_rate_limit() -> str:
    return _default_rate_limit("RONZZDOI_PUBLIC_RATE_LIMIT_SEARCH", "30/minute")


def _citation_rate_limit() -> str:
    return _default_rate_limit("RONZZDOI_PUBLIC_RATE_LIMIT_CITATION", "60/minute")


# ═══════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════


@router.get("/health", response_model=PublicHealthResponse)
async def public_health() -> dict[str, str]:
    """Public health check (no rate limit, no auth)."""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/doi/{doi:path}", response_model=PublicDOIResponse)
@_limiter.limit(_doi_rate_limit)
async def public_resolve_doi(doi: str, request: Request) -> dict[str, Any]:
    """Resolve a DOI and return its **public** metadata.

    No authentication required.  Returns only public-safe fields.
    """
    svc = _get_doi_svc()
    try:
        record = svc.resolve(doi)
    except Exception:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=f"Invalid DOI: '{doi}'")

    if record is None:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=f"DOI '{doi}' not found.")

    return _record_to_public(record)


@router.get("/search", response_model=PublicSearchResponse)
@_limiter.limit(_search_rate_limit)
async def public_search(
    request: Request,
    q: str = "",
    doi_type: str = "",
    mode: str = "fts",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search DOIs by type and query (public, read-only).

    Two search modes are available:

    - ``mode=fts`` (default): FTS5 full-text search. Results include a
      highlighted ``snippet`` excerpt when a search query is provided.
    - ``mode=semantic``: Vector/semantic search via lightersearch.
      Requires the optional ``lightersearch`` package to be installed
      and the ``ronzzdoi[public,semantic]`` extras.  Falls back to FTS5
      if lightersearch is unavailable.  Semantic results do **not**
      include a ``snippet`` field.

    The ``limit`` parameter is silently capped at **50** to prevent
    bulk export via a single request.  No authentication required.
    """
    svc = _get_doi_svc()

    # Cap pagination
    limit = min(limit, _SEARCH_LIMIT_CAP)

    if not q.strip():
        results = svc.list_dois(limit=limit, offset=offset)
        if doi_type:
            results = [r for r in results if r.get("doi_type") == doi_type]
        return {
            "items": [_record_to_public(r) for r in results],
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "mode": mode,
        }

    search_svc = _get_search_svc()

    if mode == "semantic" and search_svc is not None:
        # Semantic search — use unified dispatch mode
        results = search_svc.search(q, mode="semantic", limit=limit)
    elif search_svc is not None:
        # FTS5 search with snippet highlighting
        results = search_svc.search_fts_with_snippet(q, limit=limit)
    else:
        results = svc.list_dois(limit=limit, offset=offset)

    if doi_type:
        results = [r for r in results if r.get("doi_type") == doi_type][:limit]

    return {
        "items": [_record_to_public(r) for r in results],
        "total": len(results),
        "limit": limit,
        "offset": offset,
        "mode": mode,
    }


@router.get("/citation", response_model=PublicCitationResponse)
@_limiter.limit(_citation_rate_limit)
async def public_get_citation(
    request: Request,
    doi: str,
    style: str = "apa",
) -> dict[str, Any]:
    """Return a formatted citation for a DOI (public, read-only).

    No authentication required.  The ``doi`` parameter is just the
    suffix (the ``10.ronzz/`` prefix is prepended if missing).
    """
    formatter = _get_formatter()
    if formatter is None:
        raise HTTPException(
            status_code=404,
            detail="Citation formatter not available. No citation service configured.",
        )

    # Normalise DOI
    full_doi = doi if doi.startswith("10.") else f"10.ronzz/{doi}"

    try:
        text = formatter.format(full_doi, style=style)
    except DOINotFoundError as exc:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))

    return {
        "doi": doi,
        "style": style,
        "citation": text,
    }
