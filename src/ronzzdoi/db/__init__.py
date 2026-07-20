"""Database module — SQLite backend for ronzzdoi.

Extends lightercore's database infrastructure with DOI-specific
schema definitions, migrations, and service classes.

Usage::

    from ronzzdoi.db import init_db

    db, doi_svc, cit_svc, red_svc = init_db()
    doi = doi_svc.create({"doi": "10.ronzz/books/2024/smith", "target_url": "..."})
"""

from __future__ import annotations

from lightercore.db import LighterDB
from lightercore.paths import data_dir, ensure_dirs, set_app_name

from ronzzdoi.db.schema import MIGRATIONS
from ronzzdoi.db.service import CitationService, DOIService, RedirectService

__all__ = [
    "LighterDB",
    "DOIService",
    "CitationService",
    "RedirectService",
    "init_db",
    "get_db",
]


def init_db(app_name: str = "ronzzdoi") -> tuple[LighterDB, DOIService, CitationService, RedirectService]:
    """Initialize the database, apply migrations, and return service instances.

    Call this once at application startup.  Idempotent — subsequent calls
    return the same service instances (singleton via ``get_db``).

    Args:
        app_name: Application name for XDG path resolution.
                  Defaults to ``"ronzzdoi"``.

    Returns:
        Tuple of ``(db, doi_svc, cit_svc, red_svc)``.
    """
    set_app_name(app_name)
    ensure_dirs()

    db_path = data_dir() / "ronzzdoi.db"
    db = LighterDB(db_path)
    db.migrate(MIGRATIONS)

    doi_svc = DOIService(db)
    cit_svc = CitationService(db)
    red_svc = RedirectService(db)

    return db, doi_svc, cit_svc, red_svc


_db_state: dict[str, tuple[LighterDB, DOIService, CitationService, RedirectService]] = {}
"""Module-level singleton cache keyed by *app_name*."""


def get_db(app_name: str = "ronzzdoi") -> tuple[LighterDB, DOIService, CitationService, RedirectService]:
    """Return cached DB and service instances, or initialize if absent.

    Args:
        app_name: Application name (must match the first call's value).

    Returns:
        Tuple of ``(db, doi_svc, cit_svc, red_svc)``.
    """
    if app_name not in _db_state:
        _db_state[app_name] = init_db(app_name)
    return _db_state[app_name]
