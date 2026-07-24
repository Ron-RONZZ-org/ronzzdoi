"""Command handlers — import domain modules to register commands.

Side-effect imports register handlers with the command registry
via the ``@command()`` decorator.  Each module is auto-discovered
by the ``command/__init__.py`` import chain.
"""

from __future__ import annotations

from typing import Any

from ronzzdoi.auth.config import PERMISSION_HIERARCHY


def check_permission(
    user: dict[str, Any] | None,
    min_permission: str,
) -> dict[str, Any] | None:
    """Check user has at least *min_permission*.

    Returns an error response dict if insufficient, ``None`` if OK.

    Args:
        user: The authenticated user dict, or ``None``.
        min_permission: Minimum permission level required
            (``"read_only"``, ``"edit"``, or ``"admin"``).

    Returns:
        An error response dict with ``type: "error"`` if the user lacks
        the required permission, or ``None`` if the check passes.
    """
    actual = user.get("api_key_permission") if user else None
    if not actual:
        return {
            "type": "error",
            "title": "Authentication Required",
            "data": {"message": "Valid API key required."},
        }
    min_level = PERMISSION_HIERARCHY.get(min_permission, 0)
    actual_level = PERMISSION_HIERARCHY.get(actual, -1)
    if actual_level < min_level:
        return {
            "type": "error",
            "title": "Permission Denied",
            "data": {
                "message": f"Insufficient permissions. Requires at least '{min_permission}'.",
            },
        }
    return None


# Side-effect imports: each module registers its handlers as a
# side effect of module-level ``@command()`` decorator evaluation.
from ronzzdoi.server.command.handlers import auth  # noqa: F401
from ronzzdoi.server.command.handlers import help  # noqa: F401
from ronzzdoi.server.command.handlers import citation  # noqa: F401
from ronzzdoi.server.command.handlers import doi  # noqa: F401
