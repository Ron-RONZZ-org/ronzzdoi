"""Pydantic response schemas for public API endpoints.

These schemas expose only the subset of fields that are safe for
unauthenticated public consumers.  Fields like ``status``,
``redirect_history``, and ``deleted_at`` are excluded.

Usage::

    from ronzzdoi.server.public_schemas import PublicDOIResponse

    @router.get("/public/v1/doi/{doi}")
    async def resolve_doi(doi: str) -> PublicDOIResponse:
        ...
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PublicDOIResponse(BaseModel):
    """Public-safe DOI metadata response.

    Only basic metadata is exposed — no internal state, status flags,
    redirect history, or deletion timestamps.

    The ``snippet`` field is only populated by search endpoints that
    use FTS5 highlighting.  It is ``None`` for direct DOI resolution
    and semantic search results.
    """

    doi: str
    target_url: str | None = None
    title: str = ""
    doi_type: str = "external"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    snippet: str | None = None


class PublicSearchResponse(BaseModel):
    """Paginated search result for public API consumers.

    Each item uses :class:`PublicDOIResponse`.  The ``limit`` field
    reflects the actual cap applied (max 50).  The ``mode`` field
    indicates which search mode was used (``"fts"`` or ``"semantic"``).
    """

    items: list[PublicDOIResponse]
    total: int
    limit: int
    offset: int
    mode: str = "fts"


class PublicCitationResponse(BaseModel):
    """Formatted citation response for public API consumers."""

    doi: str
    style: str
    citation: str


class PublicHealthResponse(BaseModel):
    """Public health check response."""

    status: str
    version: str


__all__ = [
    "PublicDOIResponse",
    "PublicSearchResponse",
    "PublicCitationResponse",
    "PublicHealthResponse",
]
