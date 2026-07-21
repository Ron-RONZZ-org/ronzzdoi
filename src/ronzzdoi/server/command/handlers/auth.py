"""``!auth api_key`` command handler — list API keys for the authenticated user.

v0.1.0 scope:
- ``!auth api_key list`` — list the authenticated user's own API keys

API key create/delete is admin CLI only (not exposed via command dispatch).
``!auth api_key update`` is a frontend-local operation (updates localStorage).
"""

from __future__ import annotations

from typing import Any

from lighterauth.api_key import lookup_api_keys

from ronzzdoi.server.command.registry import command

# ── Module-level DB reference (set by mount_command_routes) ────────────

_auth_db: Any = None


def set_auth_db(db: Any) -> None:
    """Set the auth database reference for command handlers.

    Called during server startup from ``mount_command_routes``.
    """
    global _auth_db
    _auth_db = db


def _ensure_db() -> None:
    """Raise if the auth database has not been initialised."""
    if _auth_db is None:
        raise RuntimeError("Auth database not initialised. Call set_auth_db() during startup.")


# ── Helpers ─────────────────────────────────────────────────────────────


def _parse_dt(value: str | None) -> str | None:
    """Return the value as-is if present (ISO string), else None."""
    if value is None:
        return None
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


# ── !auth api_key list ───────────────────────────────────────────────────


@command("auth.api_key.list", description="List your API keys")
def _auth_api_key_list(
    flags: dict[str, str],
    user: dict[str, Any] | None,
) -> dict[str, Any]:
    """List the authenticated user's own API keys.

    Only returns keys belonging to the authenticated user
    (determined by the ``Authorization`` header).

    Flags:
        --include-expired: Include expired and revoked keys.
    """
    if user is None:
        return {
            "type": "error",
            "title": "Not Authenticated",
            "data": {"message": "You must be authenticated to list API keys."},
        }

    _ensure_db()
    include_expired = "include-expired" in flags or "include_expired" in flags

    rows = lookup_api_keys(
        _auth_db,
        user_id=user["id"],
        include_expired=include_expired,
    )

    keys = [
        {
            "id": r["id"],
            "name": r["name"],
            "prefix": r["prefix"],
            "permission": r["permission"],
            "expires_at": _parse_dt(r.get("expires_at")),
            "last_used_at": _parse_dt(r.get("last_used_at")),
            "created_at": _parse_dt(r["created_at"]),
        }
        for r in rows
    ]

    return {
        "type": "list",
        "title": "My API Keys",
        "data": keys,
        "id_key": "auth-api-key-list",
    }
