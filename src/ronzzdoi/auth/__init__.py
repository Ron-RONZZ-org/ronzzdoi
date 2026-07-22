"""Authentication module for ronzzdoi.

Wraps ``lighterauth`` to provide API key management and access control
for the ronzzdoi API server.

Auth database is stored separately from the main ronzzdoi database
(to isolate secrets).

Usage::

    from ronzzdoi.auth import setup_auth
    from ronzzdoi.auth.config import resolve_auth_db_path

    db_path = resolve_auth_db_path(data_dir="/path/to/data")
    auth_db, auth = setup_auth(db_path)
"""

from __future__ import annotations

from pathlib import Path

from lighterauth.keyonly import init_keyonly_schema
from lighterauth.middleware import Lighterauth
from lightercore.db import LighterDB

__all__ = [
    "setup_auth",
    "init_auth_db",
]


def init_auth_db(db_path: str | Path) -> LighterDB:
    """Initialize the auth database and schema.

    Creates the database file and ``api_keys`` table (key-only auth, no users)
    if they do not already exist.

    Args:
        db_path: Path to the auth SQLite database file.

    Returns:
        An open ``LighterDB`` instance (WAL mode, auto-commit).
    """
    db = LighterDB(str(db_path))
    init_keyonly_schema(db)
    return db


def setup_auth(
    db_path: str | Path,
    *,
    jwt_secret: str | None = None,
) -> tuple[LighterDB, Lighterauth]:
    """Create the auth database and middleware provider.

    Uses the key-only auth model (no users table, no passwords).
    Call during server startup::

        auth_db, auth = setup_auth("/path/to/auth.db")

    Args:
        db_path: Path to the auth SQLite database file.
        jwt_secret: Optional JWT HMAC secret. Falls back to
            ``JWT_SECRET`` env var / dev default.

    Returns:
        A tuple of ``(auth_db, auth)`` where:
        - ``auth_db`` is the initialized ``LighterDB`` instance.
        - ``auth`` is a ``Lighterauth`` middleware provider
          (has ``require_user``, ``optional_user``,
          ``require_active_user``, ``require_role``).
    """
    auth_db = init_auth_db(db_path)
    auth = Lighterauth(auth_db, jwt_secret=jwt_secret, keyonly=True)
    return auth_db, auth
