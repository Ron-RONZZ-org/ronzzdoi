"""FastAPI application factory for ronzzdoi.

Creates and configures the API server with:
- Auth middleware (API key verification, route protection)
- API key management endpoints
- CORS (ready for future Svelte frontend)

Usage::

    import uvicorn
    from ronzzdoi.server.app import create_app

    app = create_app(data_dir="/path/to/data")
    uvicorn.run(app, host="127.0.0.1", port=8000)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lightercore.paths import set_app_name

from ronzzdoi.auth import setup_auth
from ronzzdoi.auth.config import resolve_auth_db_path
from ronzzdoi.server.auth_middleware import init_auth_deps
from ronzzdoi.server.auth_routes import mount_auth_routes

_DEFAULT_PORT = 8000
"""Default port for the API server."""

_APP_TITLE = "ronzzdoi API"
_APP_DESCRIPTION = (
    "In-house DOI & citation management system at ronzz.org. "
    "Provides persistent DOI assignment, resolution, citation management "
    "in multiple styles, and semantic web federation."
)


def create_app(
    data_dir: str | Path | None = None,
    *,
    enable_cors: bool = True,
) -> FastAPI:
    """Create and return a fully configured FastAPI application.

    Call this once during server startup::

        app = create_app(data_dir="/var/lib/ronzzdoi")

    Args:
        data_dir: Path to the data directory containing ``auth.db``
            (and future ``ronzzdoi.db``).  Defaults to the XDG-compliant
            path from ``lightercore.paths``.
        enable_cors: Whether to add the CORS middleware (default True).
            Disable for production if a reverse proxy handles CORS.

    Returns:
        A configured FastAPI application instance.
    """
    # Ensure lightercore path resolution uses the ronzzdoi app name
    set_app_name("ronzzdoi")

    # ── Auth database ──────────────────────────────────────────────────
    auth_db_path = resolve_auth_db_path(data_dir)
    auth_db, auth = setup_auth(auth_db_path)

    # ── Wire up middleware dependencies ────────────────────────────────
    init_auth_deps(auth)

    # ── Create the FastAPI application ─────────────────────────────────
    app = FastAPI(
        title=_APP_TITLE,
        description=_APP_DESCRIPTION,
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # ── CORS ───────────────────────────────────────────────────────────
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ── Mount auth routes ──────────────────────────────────────────────
    mount_auth_routes(app, auth_db)

    # ── Health check ───────────────────────────────────────────────────
    @app.get("/api/health")
    async def health_check() -> dict[str, str]:
        """Simple health check endpoint (no auth required)."""
        return {"status": "ok", "version": "0.1.0"}

    # Also register the root health check
    @app.get("/")
    async def root_health() -> dict[str, str]:
        return {"status": "ok", "service": "ronzzdoi"}

    return app
