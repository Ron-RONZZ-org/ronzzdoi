"""Command endpoint — dispatches ``!xxx`` commands from the frontend.

Provides two endpoints:

- ``POST /api/v1/command`` — execute a command and return structured data.
- ``GET /api/v1/command/tree`` — return the command tree for autocomplete.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_400_BAD_REQUEST

from ronzzdoi.server.command import dispatch, get_command_tree
from ronzzdoi.server.command.models import CommandRequest, CommandResponse
from ronzzdoi.server.command.registry import (
    CommandAmbiguousError,
    CommandNotFoundError,
)
from ronzzdoi.server.auth_middleware import require_authenticated

router = APIRouter(prefix="/api/v1", tags=["command"])


# ── Module-level references ─────────────────────────────────────────────


def mount_command_routes(app: Any) -> None:
    """Register command routes on the FastAPI application.

    The command tree is built automatically from registered ``@command``
    decorators and served via ``GET /api/v1/command/tree`` for frontend
    autocomplete.

    Args:
        app: The FastAPI application instance.
    """
    app.include_router(router)


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post("/command", response_model=CommandResponse)
async def execute_command(
    body: CommandRequest,
    user: dict[str, Any] = Depends(require_authenticated),
) -> CommandResponse:
    """Execute a ``!command`` and return structured data.

    Requires a valid ``Authorization: Bearer <key>`` header.
    The frontend sends parsed tokens and flags; the backend dispatches to
    the registered handler and returns a ``{type, title, data}`` response
    that the frontend renders as a tab.
    """
    try:
        result = dispatch(body.tokens, body.flags, user)
    except CommandNotFoundError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))
    except CommandAmbiguousError as exc:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=str(exc))

    return CommandResponse(
        type=result.get("type", "detail"),
        title=result.get("title", "Result"),
        data=result.get("data"),
    )


@router.get("/command/tree")
async def command_tree() -> list[dict[str, Any]]:
    """Return the command tree for frontend autocomplete.

    The frontend fetches this on startup to provide ``!``-prefixed
    completion suggestions as the user types.
    """
    return get_command_tree()
