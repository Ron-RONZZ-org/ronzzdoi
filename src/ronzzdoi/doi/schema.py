"""Pydantic models for DOI data.

Used for request validation and response serialization in the API layer
and as structured representations in the CLI and tests.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RedirectRecord(BaseModel):
    """A single redirect entry in the DOI's history."""

    old_url: str
    note: str = ""
    created_at: str


class DOIAssignRequest(BaseModel):
    """Request model for assigning a new DOI."""

    target_url: str = Field(..., description="The target URL the DOI resolves to")
    doi_type: str = Field(
        default="external",
        description="Free-text type descriptor (e.g. 'book', 'webpage', 'circulaire')",
    )
    title: str = Field(default="", description="Human-readable title of the resource")
    creator: str = Field(default="", description="Author or creator of the resource")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata stored as JSON",
    )


class DOIModifyRequest(BaseModel):
    """Request model for modifying an existing DOI.

    All fields are optional — only provided fields are updated.
    """

    target_url: str | None = Field(
        default=None,
        description="New target URL (triggers soft redirect if changed)",
    )
    title: str | None = None
    creator: str | None = None
    doi_type: str | None = None
    metadata: dict[str, Any] | None = None


class DOIResponse(BaseModel):
    """Response model representing a DOI record.

    ``metadata`` is deserialized from the database ``metadata_json`` column.
    """

    doi: str
    target_url: str
    title: str = ""
    creator: str = ""
    doi_type: str = "external"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class DOIResolveResponse(DOIResponse):
    """Extended response for DOI resolution, including redirect history."""

    status: str = "active"  # "active" or "tombstone"
    redirect_history: list[RedirectRecord] = Field(
        default_factory=list,
        description="Chronological list of past target URLs",
    )


__all__ = [
    "RedirectRecord",
    "DOIAssignRequest",
    "DOIModifyRequest",
    "DOIResponse",
    "DOIResolveResponse",
]
