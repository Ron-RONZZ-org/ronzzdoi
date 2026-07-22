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

from typing import Any, Callable

from fastapi import Header, HTTPException
from starlette.status import HTTP_403_FORBIDDEN

from lighterauth.middleware import Lighterauth

from ronzzdoi.auth.config import PERMISSION_FULL_ACCESS, PERMISSION_HIERARCHY, PERMISSION_READ_ONLY, WRITE_PERMISSIONS

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


def require_permission(min_permission: str) -> Callable[..., Any]:
    """FastAPI dependency factory: require minimum API key permission tier.

    Usage::

        @app.post("/api/v1/doi")
        async def assign_doi(
            user: dict = Depends(require_permission("edit")),
        ):
            ...

    The permission hierarchy is ``read_only`` (0) < ``edit`` (1) < ``full_access`` (2).

    - JWT-authenticated users bypass the permission check (their role is
      verified separately via ``require_role`` / ``require_admin_role``).
    - API-key-authenticated users must have a permission level at or above
      the required minimum.

    Args:
        min_permission: The minimum required permission level
            (one of ``PERMISSION_READ_ONLY``, ``PERMISSION_EDIT``,
            ``PERMISSION_FULL_ACCESS``).

    Returns:
        A dependency callable that authenticates and checks permission level.
    """

    async def _check_permission(
        authorization: str | None = Header(None),
    ) -> dict[str, Any]:
        _check_inited()
        try:
            user = await _auth.require_active_user(authorization)
        except HTTPException:
            raise

        permission = user.get("api_key_permission")
        if permission:
            min_level = PERMISSION_HIERARCHY.get(min_permission, 0)
            actual_level = PERMISSION_HIERARCHY.get(permission, -1)
            if actual_level < min_level:
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail=(
                        f"Insufficient permissions. Requires at least "
                        f"'{min_permission}'."
                    ),
                )

        return user

    return _check_permission


require_write_access: Callable[..., Any] = require_permission("edit")
"""Require an authenticated user with at least ``edit`` permission.

Use on POST, PUT, DELETE endpoints.

Convenience alias for ``require_permission("edit")``.
"""


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

def require_permission(min_permission: str = PERMISSION_READ_ONLY) -> Callable[..., Any]:
    """FastAPI dependency factory: require a minimum permission tier.

    Tier ordering: ``read_only`` < ``full_access``.
    ``admin`` role bypasses all permission checks.

    Use on endpoints that need tiered access::

        # Read-only endpoint
        @app.get("/api/v1/doi/{doi}")
        async def resolve_doi(user=Depends(require_permission("read_only"))):
            ...

        # Write endpoint
        @app.post("/api/v1/doi")
        async def assign_doi(user=Depends(require_permission("full_access"))):
            ...

    Args:
        min_permission: Minimum permission tier required.
            ``"read_only"`` accepts read_only and full_access keys
            (and all admin users).  ``"full_access"`` requires
            full_access permission.

    Returns:
        A dependency callable that authenticates the user and checks
        the permission tier.
    """

    async def _permission_checker(
        authorization: str | None = Header(None),
    ) -> dict[str, Any]:
        _check_inited()
        try:
            user = await _auth.require_active_user(authorization)
        except HTTPException:
            raise

        # Admin role bypasses permission checks
        if user.get("role") == "administrator":
            return user

        # Check API key permission tier
        permission = user.get("api_key_permission")
        if permission:
            if min_permission == PERMISSION_FULL_ACCESS and permission != PERMISSION_FULL_ACCESS:
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Requires '{min_permission}'.",
                )
            if min_permission == PERMISSION_READ_ONLY:
                if permission not in (PERMISSION_READ_ONLY, PERMISSION_FULL_ACCESS):
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions. Requires at least '{min_permission}'.",
                    )

        return user

    return _permission_checker


# ── Internal helpers ───────────────────────────────────────────────────


def _check_inited() -> None:
    """Raise if ``init_auth_deps()`` has not been called."""
    if _auth is None:
        raise RuntimeError(
            "auth_middleware not initialised. "
            "Call init_auth_deps(auth) during server startup."
        )
