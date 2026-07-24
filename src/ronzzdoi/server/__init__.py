"""API server module — FastAPI application for ronzzdoi.

Provides:
- Auth middleware (API key verification)
- API key management endpoints
- DOI resolution and HTTP redirect endpoints (issue #6)
- Citation management API (issue #6)
- Keyword search API (issue #6)

Usage::

    import uvicorn
    from ronzzdoi.server import create_app

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8011)
"""

from __future__ import annotations

from ronzzdoi.server.app import create_app

__all__ = ["create_app"]
