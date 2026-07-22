"""Auth configuration — DB path resolution and permission constants.

The auth database is kept separate from the main ronzzdoi database to
isolate secrets (hashed keys, user credentials) from public data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from lightercore.paths import data_dir as core_data_dir

DEFAULT_AUTH_DB_NAME = "auth.db"
"""Filename for the auth database within the data directory."""

# ── API key permissions ────────────────────────────────────────────────────

PERMISSION_READ_ONLY = "read_only"
"""Read-only API key — can query public endpoints with higher rate limits."""

PERMISSION_EDIT = "edit"
"""Edit API key — can create, modify, and delete resources."""

PERMISSION_FULL_ACCESS = "full_access"
"""Full-access API key — can create, modify, delete resources, and manage API keys."""

WRITE_PERMISSIONS: list[str] = [PERMISSION_EDIT, PERMISSION_FULL_ACCESS]
"""Permissions that allow write operations (edit or full_access)."""

ALL_PERMISSIONS: list[str] = [PERMISSION_READ_ONLY, PERMISSION_EDIT, PERMISSION_FULL_ACCESS]
"""All valid API key permissions."""

PERMISSION_HIERARCHY: dict[str, int] = {
    PERMISSION_READ_ONLY: 0,
    PERMISSION_EDIT: 1,
    PERMISSION_FULL_ACCESS: 2,
}
"""Numeric hierarchy for permission-level comparison (higher = more access)."""


def resolve_auth_db_path(data_dir: str | Path | None = None) -> Path:
    """Resolve the auth database file path.

    Resolution order:

    1. ``data_dir`` argument (explicit path).
    2. ``RONZZDOI_DATA_DIR`` environment variable.
    3. ``lightercore.paths.data_dir()`` default (XDG-compliant).

    The auth DB is stored as ``{data_dir}/auth.db``.

    Args:
        data_dir: Explicit data directory path.

    Returns:
        Absolute ``Path`` to the auth database file.
    """
    if data_dir is not None:
        resolved_data = Path(data_dir).expanduser().resolve()
    elif os.environ.get("RONZZDOI_DATA_DIR"):
        resolved_data = Path(os.environ["RONZZDOI_DATA_DIR"]).expanduser().resolve()
    else:
        resolved_data = core_data_dir()

    resolved_data.mkdir(parents=True, exist_ok=True)
    return resolved_data / DEFAULT_AUTH_DB_NAME


# ── Auth middleware config constants ───────────────────────────────────────

AUTH_HEADER_SCHEME = "Bearer"
"""Expected ``Authorization`` header scheme."""

API_KEY_PREFIX = "la_"
"""Prefix for all API keys (must match ``lighterauth.api_key.API_KEY_PREFIX``)."""


def get_auth_config() -> dict[str, Any]:
    """Return a dict of auth configuration for the ``Lighterauth`` constructor.

    Looks up ``JWT_SECRET`` from the environment, falling back to the
    lighterauth dev default.
    """
    return {
        "jwt_secret": os.environ.get("JWT_SECRET"),
    }
