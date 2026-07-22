"""Citation API endpoints — list styles and format citations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from ronzzdoi.citation import CitationFormatter
from ronzzdoi.doi.exceptions import DOINotFoundError
from ronzzdoi.server.auth_middleware import require_permission

router = APIRouter(prefix="/api/v1", tags=["citation"])

# ── Module-level references (set by mount_citation_routes) ─────────────


_formatter: CitationFormatter | None = None


def mount_citation_routes(app: Any, formatter: CitationFormatter) -> None:
    """Register citation routes on the FastAPI application.

    Args:
        app: The FastAPI application instance.
        formatter: A configured ``CitationFormatter`` instance.
    """
    global _formatter
    _formatter = formatter
    app.include_router(router)


def _get_formatter() -> CitationFormatter:
    """Return the module-level CitationFormatter or raise."""
    if _formatter is None:
        raise RuntimeError(
            "citation_routes not initialised. "
            "Call mount_citation_routes() during startup."
        )
    return _formatter


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("/citation")
async def get_citation(
    doi: str,
    style: str | None = None,
    user: dict[str, Any] = Depends(require_permission("read_only")),
) -> dict[str, Any]:
    """List available styles or return a formatted citation.

    - If ``style`` is omitted, returns the list of available styles.
    - If ``style`` is provided, returns the formatted citation text
      for the given DOI in that style.

    The ``doi`` parameter is just the suffix (the ``10.ronzz/`` prefix
    is implicit and will be prepended if missing).
    """
    formatter = _get_formatter()

    # If the DOI doesn't include the prefix, add it
    full_doi = _normalize_doi(doi)

    if style is None:
        # Return available styles
        return {
            "doi": doi,
            "styles": formatter.available_styles(),
        }

    # Format citation in the specified style
    try:
        text = formatter.format(full_doi, style=style)
    except DOINotFoundError as exc:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        # Unsupported style
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "doi": doi,
        "style": style,
        "citation": text,
    }


# ── Helpers ────────────────────────────────────────────────────────────


def _normalize_doi(doi: str) -> str:
    """Prepend the ``10.ronzz/`` prefix if missing."""
    if not doi.startswith("10."):
        return f"10.ronzz/{doi}"
    return doi
