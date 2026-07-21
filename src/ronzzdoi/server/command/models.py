"""Request/response models for the command endpoint.

Lightweight Pydantic models used by ``POST /api/v1/command``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    """Request payload from the frontend command input."""

    tokens: list[str] = Field(
        ...,
        description="Command tokens, e.g. ['auth', 'api_key', 'list']",
    )
    flags: dict[str, str] = Field(
        default_factory=dict,
        description="Flag arguments parsed from the command, e.g. {'include_expired': ''}",
    )
    raw_input: str = Field(
        default="",
        description="The raw input string as typed by the user",
    )


class CommandResponse(BaseModel):
    """Structured response rendered as a tab in the frontend.

    The ``type`` field determines how the frontend displays the data:

    - ``"list"``: render as a sortable, selectable list table.
    - ``"detail"``: render as a metadata detail view.
    - ``"form"``: render as an interactive form with fields.
    - ``"error"``: render as an error popup.
    - ``"success"``: render as a transient success message.
    - ``"confirm"``: render as a confirmation dialog.
    """

    type: str = Field(..., description="Display type: list, detail, form, error, success, confirm")
    title: str = Field(..., description="Tab title")
    data: Any = Field(default=None, description="Display data (dict, list, or null)")
    id_key: str | None = Field(
        default=None,
        description="Dedup key — tabs with the same id_key replace each other",
    )
