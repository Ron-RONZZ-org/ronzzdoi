"""FastAPI dependency helpers for route-level auth.

Wraps ``lighterauth.middleware.Lighterauth`` with ronzzdoi-specific
permission checks.

Usage::

    from fastapi import Depends
    from ronzzdoi.server.auth_middleware import require_write_access

    @app.post("/api/v1/doi")
    async def assign_doi(user: dict = Depends(require_write_access)):
        ...
"""

from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException
from starlette.status import HTTP_403_FORBIDDEN

from lighterauth.middleware import Lighterauth

from ronzzdoi.auth.config import WRITE_PERMISSIONS

# Module-level reference set by ``init_auth_deps()``.
_auth: Lighterauth | None = None


def init_auth_deps(auth: Lighterauth) -> None:
    """Initialise the module-level ``Lighterauth`` reference.

    Must be called during server startup, once the ``Lighterauth``
    instance has been created::

        auth_db, auth = setup_auth(db_path)
        init_auth_deps(auth)

    Args:
        auth: A configured ``Lighterauth`` instance.
    """
    global _auth
    _auth = auth


# ── Public dependency callables ────────────────────────────────────────


async def require_write_access(
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Require an authenticated user with write permission.

    Use on POST, PUT, DELETE endpoints.

    Validates:
    - The ``Authorization: Bearer <token>`` header is present and valid.
    - The user's account is active (not suspended).
    - The API key or JWT has ``full_access`` permission.

    Raises:
        HTTPException (401): Missing or invalid credentials.
        HTTPException (403): Insufficient permissions or suspended account.
    """
    _check_inited()
    try:
        user = await _auth.require_active_user(authorization)
    except HTTPException:
        raise

    # Check permission for API-key-authenticated requests
    permission = user.get("api_key_permission")
    if permission and permission not in WRITE_PERMISSIONS:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Requires full_access.",
        )

    return user


async def optional_read_access(
    authorization: str | None = Header(None),
) -> dict[str, Any] | None:
    """Optional authentication for read endpoints.

    Returns the user dict if a valid ``Authorization`` header is present,
    or ``None`` if not.  Never raises.

    Use on GET endpoints that may benefit from knowing the caller
    (e.g. for rate-limit tier selection or audit logging).
    """
    _check_inited()
    return await _auth.optional_user(authorization)


async def require_authenticated(
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Require any authenticated user (no permission check).

    Use on endpoints that need to know the caller's identity but don't
    need specific permissions (e.g. the command dispatch endpoint).

    Validates:
    - The ``Authorization: Bearer <token>`` header is present and valid.
    - The user's account is active (not suspended).

    Raises:
        HTTPException (401): Missing or invalid credentials.
        HTTPException (403): Suspended account.
    """
    _check_inited()
    return await _auth.require_active_user(authorization)


async def require_admin_role(
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Require the user to have the ``administrator`` role.

    Use on admin-only endpoints (e.g. API key management).

    Raises:
        HTTPException (401): Missing or invalid credentials.
        HTTPException (403): User is not an administrator.
    """
    _check_inited()
    user = await _auth.require_user(authorization)
    if user.get("role") != "administrator":
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Requires administrator role.",
        )
    return user


# ── Internal helpers ───────────────────────────────────────────────────


def _check_inited() -> None:
    """Raise if ``init_auth_deps()`` has not been called."""
    if _auth is None:
        raise RuntimeError(
            "auth_middleware not initialised. "
            "Call init_auth_deps(auth) during server startup."
        )
