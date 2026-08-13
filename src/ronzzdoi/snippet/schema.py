"""Pydantic models for snippet data.

Used for request validation and response serialization in the API layer
and as structured representations in the CLI and tests.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ContentKind = Literal["text", "code", "math"]
"""Allowed values for ``content_kind``."""


class SnippetAssignRequest(BaseModel):
    """Request model for assigning a new snippet.

    A snippet is a DOI (``doi_type='snippet'``) plus snippet content.
    ``content_kind`` selects the input/render mode: text quotation,
    code block, or KaTeX math.
    """

    content_kind: ContentKind = Field(
        ...,
        description="Content kind: 'text' (quotation), 'code', or 'math' (KaTeX)",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="The snippet content (quotation text, code, or KaTeX source)",
    )
    title: str = Field(default="", description="Human-readable title for the snippet")
    language: str = Field(
        default="",
        description="Code language hint (code snippets only). Ignored for text/math.",
    )
    source_doi: str | None = Field(
        default=None,
        description="Optional source DOI the snippet quotes from (e.g. a book). Must exist.",
    )
    page_start: str = Field(
        default="", description="Source page start (text quotations)"
    )
    page_end: str = Field(default="", description="Source page end (text quotations)")


class SnippetModifyRequest(BaseModel):
    """Request model for modifying an existing snippet.

    All fields are optional — only provided fields are updated.
    Set a string field to ``""`` to clear it (e.g. ``source_doi``).
    """

    content_kind: ContentKind | None = None
    content: str | None = Field(default=None, min_length=1)
    title: str | None = None
    language: str | None = None
    source_doi: str | None = Field(
        default=None,
        description="New source DOI, or empty string to clear the reference",
    )
    page_start: str | None = None
    page_end: str | None = None


class SnippetResponse(BaseModel):
    """Response model representing a snippet record."""

    doi: str
    title: str = ""
    content_kind: str = "text"
    content: str = ""
    language: str = ""
    source_doi: str | None = None
    page_start: str = ""
    page_end: str = ""
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    status: str = "active"  # "active" or "tombstone"


__all__ = [
    "ContentKind",
    "SnippetAssignRequest",
    "SnippetModifyRequest",
    "SnippetResponse",
]
