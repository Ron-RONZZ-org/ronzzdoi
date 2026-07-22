"""FastAPI dependency helpers for route-level auth.

Wraps ``lighterauth.middleware.Lighterauth`` with ronzzdoi-specific
permission checks.

Usage::

    from fastapi import Depends
    from ronzzdoi.server.auth_middleware import require_permission

    @app.post("/api/v1/doi")
    async def assign_doi(
        user: dict = Depends(require_permission("edit")),
    ):
        ...
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Header, HTTPException
from starlette.status import HTTP_403_FORBIDDEN

from lighterauth.middleware import Lighterauth

from ronzzdoi.auth.config import PERMISSION_HIERARCHY

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

    The permission hierarchy is ``read_only`` (0) < ``edit`` (1) <
    ``admin`` (2).  API-key-authenticated users must have a permission
    level at or above the required minimum.

    Args:
        min_permission: The minimum required permission level
            (one of ``read_only``, ``edit``, ``admin``).

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


# ── Internal helpers ───────────────────────────────────────────────────


def _check_inited() -> None:
    """Raise if ``init_auth_deps()`` has not been called."""
    if _auth is None:
        raise RuntimeError(
            "auth_middleware not initialised. "
            "Call init_auth_deps(auth) during server startup."
        )
