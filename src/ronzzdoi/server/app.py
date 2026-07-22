"""FastAPI application factory for ronzzdoi.

Creates and configures the API server in one of three modes:

- ``"full"`` (default, dev): both internal and public routes on the same
  process, with wide-open CORS.
- ``"internal"`` (production-safe): only auth-protected API routes,
  CORS disabled (bound to loopback).
- ``"public"``: only rate-limited public read-only routes, wide-open CORS.

Usage::

    import uvicorn
    from ronzzdoi.server.app import create_app

    # Development — single process, both internal and public routes
    app = create_app(mode="full")
    uvicorn.run(app, host="127.0.0.1", port=8000)

    # Production — two separate processes
    # Process 1: internal API (auth-protected, loopback only)
    app_int = create_app(mode="internal")
    uvicorn.run(app_int, host="127.0.0.1", port=8001)

    # Process 2: public API (rate-limited, 0.0.0.0)
    app_pub = create_app(mode="public")
    uvicorn.run(app_pub, host="0.0.0.0", port=8002)
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lightercore.paths import set_app_name

from ronzzdoi.auth import setup_auth
from ronzzdoi.auth.config import resolve_auth_db_path
from ronzzdoi.citation import CitationFormatter
from ronzzdoi.db import init_db as init_ronzzdoi_db
from ronzzdoi.doi.service import DOIService as DOICrudService
from ronzzdoi.server.auth_middleware import init_auth_deps
from ronzzdoi.server.auth_routes import mount_auth_routes
from ronzzdoi.server.citation_routes import mount_citation_routes
from ronzzdoi.server.command_routes import mount_command_routes
from ronzzdoi.server.doi_routes import mount_doi_routes, register_doi_redirect
from ronzzdoi.server.search_routes import mount_search_routes
from ronzzdoi.server.public_routes import mount_public_routes

_DEFAULT_PORT = 8000
"""Default port for the API server."""

_APP_TITLE = "ronzzdoi API"
_APP_DESCRIPTION = (
    "In-house DOI & citation management system at ronzz.org. "
    "Provides persistent DOI assignment, resolution, citation management "
    "in multiple styles, and semantic web federation."
)

ServerMode = Literal["full", "internal", "public"]
"""Valid server modes."""


def create_app(
    data_dir: str | Path | None = None,
    *,
    mode: ServerMode = "full",
    enable_cors: bool | None = None,
) -> FastAPI:
    """Create and return a configured FastAPI application.

    Call this once during server startup::

        app = create_app(data_dir="/var/lib/ronzzdoi", mode="internal")

    Args:
        data_dir: Path to the data directory containing ``auth.db``
            and ``ronzzdoi.db``.  Defaults to the XDG-compliant
            path from ``lightercore.paths``.
        mode: Server mode — ``"full"`` (both internal and public routes),
            ``"internal"`` (auth-protected only), or ``"public"``
            (rate-limited read-only).  Default ``"full"``.
        enable_cors: Explicit override for CORS.  When ``None`` (the
            default), the effective value is derived from the mode:
            ``False`` for ``"internal"``, ``True`` for ``"full"`` and
            ``"public"``.

    Returns:
        A configured FastAPI application instance.

    Raises:
        ValueError: If an unknown ``mode`` is provided.
    """
    if mode not in ("full", "internal", "public"):
        raise ValueError(f"Unknown mode: {mode!r}. Expected 'full', 'internal', or 'public'.")

    # ── Resolve effective CORS ─────────────────────────────────────────
    if enable_cors is None:
        effective_cors = mode != "internal"
    else:
        effective_cors = enable_cors

    # Ensure lightercore path resolution uses the ronzzdoi app name
    set_app_name("ronzzdoi")

    # ── Auth database (not needed in "public" mode, but harmless) ──────
    auth_db_path = resolve_auth_db_path(data_dir)
    auth_db, auth = setup_auth(auth_db_path)

    # ── Wire up middleware dependencies ────────────────────────────────
    init_auth_deps(auth)

    # ── ronzzdoi database ──────────────────────────────────────────────
    ronzzdoi_db, db_search_svc, _redirect_svc = init_ronzzdoi_db()
    doi_crud_svc = DOICrudService(ronzzdoi_db)
    citation_formatter = CitationFormatter(doi_crud_svc)

    # ── Create the FastAPI application ─────────────────────────────────
    docs_url = "/api/docs" if mode != "public" else None
    redoc_url = "/api/redoc" if mode != "public" else None

    app = FastAPI(
        title=_APP_TITLE,
        description=_APP_DESCRIPTION,
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
    )

    # ── CORS ───────────────────────────────────────────────────────────
    if effective_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ── Internal routes (auth-protected) ───────────────────────────────
    if mode in ("full", "internal"):
        mount_auth_routes(app, auth_db)
        mount_command_routes(app)
        mount_doi_routes(app, doi_svc=doi_crud_svc, search_svc=db_search_svc)
        mount_citation_routes(app, citation_formatter)
        mount_search_routes(app, db_search_svc)

        @app.get("/api/health")
        async def health_check() -> dict[str, str]:
            """Simple health check endpoint (no auth required)."""
            return {"status": "ok", "version": "0.1.0"}

    # ── Public routes (rate-limited, no auth) ─────────────────────────
    if mode in ("full", "public"):
        mount_public_routes(
            app,
            doi_svc=doi_crud_svc,
            search_svc=db_search_svc,
            formatter=citation_formatter,
        )

    # Root health endpoint (available in all modes)
    @app.get("/")
    async def root_health() -> dict[str, str]:
        return {"status": "ok", "service": "ronzzdoi"}

    # ── DOI redirect (must be last — catch-all route) ─────────────────
    register_doi_redirect(app)

    return app
