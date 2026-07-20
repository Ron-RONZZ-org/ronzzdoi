"""API key management endpoints.

Provides CRUD operations for API keys, accessible to administrators only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_404_NOT_FOUND, HTTP_503_SERVICE_UNAVAILABLE

from lighterauth.api_key import generate_api_key, lookup_api_keys
from lighterauth.models import (
    ApiKeyCreate,
    ApiKeyPublic,
    ApiKeyWithSecret,
)
from lightercore.db import LighterDB

from ronzzdoi.auth.config import ALL_PERMISSIONS
from ronzzdoi.server.auth_middleware import require_admin_role

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── Module-level references (set by mount_auth_routes) ─────────────────


_auth_db: LighterDB | None = None


def mount_auth_routes(app: Any, auth_db: LighterDB) -> None:
    """Register auth routes on the FastAPI application.

    Args:
        app: The FastAPI application instance.
        auth_db: The auth database instance.
    """
    global _auth_db
    _auth_db = auth_db
    app.include_router(router)


# ── Endpoints ──────────────────────────────────────────────────────────


@router.post("/keys", response_model=ApiKeyWithSecret, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    user: dict[str, Any] = Depends(require_admin_role),
) -> ApiKeyWithSecret:
    """Generate a new API key.

    The raw key is returned **only once** in the response.
    Requires ``administrator`` role.
    """
    if _auth_db is None:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth database not initialised",
        )

    if body.permission.value not in ALL_PERMISSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid permission '{body.permission.value}'. "
            f"Must be one of: {ALL_PERMISSIONS}",
        )

    # Generate key pair
    raw_key, prefix, hashed_key = generate_api_key()

    # Create record in DB
    key_id = _generate_id()
    now = datetime.now(timezone.utc).isoformat()

    _auth_db.execute(
        "INSERT INTO api_keys (id, name, key, prefix, permission, expires_at, "
        "created_at, updated_at, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            key_id,
            body.name,
            hashed_key,
            prefix,
            body.permission.value,
            body.expires_at.isoformat() if body.expires_at else None,
            now,
            now,
            user["id"],
        ),
    )

    # Re-read to return the full record
    row = _auth_db.execute_one("SELECT * FROM api_keys WHERE id = ?", (key_id,))
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create API key")

    return ApiKeyWithSecret(
        id=row["id"],
        name=row["name"],
        prefix=row["prefix"],
        key=raw_key,
        permission=row["permission"],
        expires_at=_parse_dt(row.get("expires_at")),
        last_used_at=_parse_dt(row.get("last_used_at")),
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
    )


@router.get("/keys", response_model=list[ApiKeyPublic])
async def list_api_keys(
    include_expired: bool = False,
    user: dict[str, Any] = Depends(require_admin_role),
) -> list[ApiKeyPublic]:
    """List all API keys (optionally including expired/revoked ones).

    Requires ``administrator`` role.
    """
    if _auth_db is None:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth database not initialised",
        )

    rows = lookup_api_keys(
        _auth_db,
        include_expired=include_expired,
    )
    return [
        ApiKeyPublic(
            id=r["id"],
            name=r["name"],
            prefix=r["prefix"],
            permission=r["permission"],
            expires_at=_parse_dt(r.get("expires_at")),
            last_used_at=_parse_dt(r.get("last_used_at")),
            created_at=_parse_dt(r["created_at"]),
            updated_at=_parse_dt(r["updated_at"]),
        )
        for r in rows
    ]


@router.delete("/keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    user: dict[str, Any] = Depends(require_admin_role),
) -> None:
    """Revoke (delete) an API key by ID.

    Permanently removes the key record from the database.
    Requires ``administrator`` role.
    """
    if _auth_db is None:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth database not initialised",
        )

    row = _auth_db.execute_one("SELECT id FROM api_keys WHERE id = ?", (key_id,))
    if row is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"API key not found: {key_id}",
        )

    _auth_db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))


# ── Helpers ────────────────────────────────────────────────────────────


def _generate_id() -> str:
    """Generate a short unique ID for the API key record."""
    import secrets

    return "ak_" + secrets.token_hex(12)


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime string, or return ``None``."""
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
