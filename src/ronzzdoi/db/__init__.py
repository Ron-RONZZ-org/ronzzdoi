"""Database module — SQLite backend for ronzzdoi.

Extends lightercore's database infrastructure with DOI-specific
schema definitions, migrations, and service classes.

Usage::

    from ronzzdoi.db import init_db

    db, doi_svc, red_svc = init_db()
    doi = doi_svc.create({"doi": "10.ronzz/books/2024/smith", "target_url": "..."})
"""

from __future__ import annotations

import sqlite3

from lightercore.db import LighterDB
from lightercore.paths import data_dir, ensure_dirs, set_app_name

from ronzzdoi.db.schema import MIGRATIONS
from ronzzdoi.db.service import DOIService, RedirectService

__all__ = [
    "LighterDB",
    "DOIService",
    "RedirectService",
    "init_db",
    "get_db",
]


def _after_connect(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension via lightersearch (if available).

    Called once per thread by :class:`LighterDB` on first connection.
    """
    try:
        from lightersearch.vec import load

        load(conn)
    except ImportError:
        pass


def init_db(app_name: str = "ronzzdoi") -> tuple[LighterDB, DOIService, RedirectService]:
    """Initialize the database, apply migrations, and return service instances.

    Call this once at application startup.  Idempotent — subsequent calls
    return the same service instances (singleton via ``get_db``).

    If ``lightersearch`` is installed, sqlite-vec is loaded on each new
    connection and the ``vec_dois`` table is created automatically.

    Args:
        app_name: Application name for XDG path resolution.
                  Defaults to ``"ronzzdoi"``.

    Returns:
        Tuple of ``(db, doi_svc, red_svc)``.
    """
    set_app_name(app_name)
    ensure_dirs()

    db_path = data_dir() / "ronzzdoi.db"
    db = LighterDB(db_path, after_connect=_after_connect)
    db.migrate(MIGRATIONS)

    _ensure_vec_table(db)

    doi_svc = DOIService(db)
    red_svc = RedirectService(db)

    return db, doi_svc, red_svc


def _ensure_vec_table(db: LighterDB) -> None:
    """Create the ``vec_dois`` table if lightersearch is available."""
    try:
        from lightersearch.vec import ensure_vec_table

        ensure_vec_table(db)
    except ImportError:
        pass


_db_state: dict[str, tuple[LighterDB, DOIService, RedirectService]] = {}
"""Module-level singleton cache keyed by *app_name*."""


def get_db(app_name: str = "ronzzdoi") -> tuple[LighterDB, DOIService, RedirectService]:
    """Return cached DB and service instances, or initialize if absent.

    Args:
        app_name: Application name (must match the first call's value).

    Returns:
        Tuple of ``(db, doi_svc, red_svc)``.
    """
    if app_name not in _db_state:
        _db_state[app_name] = init_db(app_name)
    return _db_state[app_name]
