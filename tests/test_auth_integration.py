"""Integration tests for ``setup_auth()`` and ``create_app()`` — end-to-end."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lightercore.db import LighterDB


class TestInitAuthDb:
    """Tests for the ``init_auth_db()`` factory."""

    def test_creates_tables(self, tmp_path: Path) -> None:
        """``init_auth_db`` creates a valid DB with auth schema tables."""
        from ronzzdoi.auth import init_auth_db

        db_path = tmp_path / "test_auth.db"
        db = init_auth_db(db_path)

        assert db_path.exists()
        assert db.table_exists("users")
        assert db.table_exists("api_keys")

        # Verify columns exist
        user_cols = {c["name"] for c in db.get_pragma_table_info("users")}
        assert "id" in user_cols
        assert "email" in user_cols
        assert "role" in user_cols
        assert "status" in user_cols

        key_cols = {c["name"] for c in db.get_pragma_table_info("api_keys")}
        assert "id" in key_cols
        assert "prefix" in key_cols
        assert "permission" in key_cols
        assert "user_id" in key_cols

    def test_idempotent(self, tmp_path: Path) -> None:
        """Calling ``init_auth_db`` twice on the same path is safe."""
        from ronzzdoi.auth import init_auth_db

        db_path = tmp_path / "test_auth.db"
        init_auth_db(db_path)
        # Second call should not error
        db2 = init_auth_db(db_path)
        assert db2.table_exists("users")


class TestSetupAuth:
    """Tests for the ``setup_auth()`` factory."""

    def test_returns_db_and_auth(self, tmp_path: Path) -> None:
        """``setup_auth`` returns a ``(LighterDB, Lighterauth)`` tuple."""
        from ronzzdoi.auth import setup_auth

        db_path = tmp_path / "auth.db"
        auth_db, auth = setup_auth(db_path)

        assert isinstance(auth_db, LighterDB)
        assert auth_db.table_exists("users")
        # Lighterauth has the expected attributes
        assert hasattr(auth, "require_user")
        assert hasattr(auth, "optional_user")
        assert hasattr(auth, "require_active_user")
        assert hasattr(auth, "require_role")

    def test_jwt_secret_passthrough(self, tmp_path: Path) -> None:
        """Custom ``jwt_secret`` is passed through to ``Lighterauth``."""
        from ronzzdoi.auth import setup_auth

        db_path = tmp_path / "auth.db"
        _, auth = setup_auth(db_path, jwt_secret="custom-secret")
        # Verify by checking the private attribute
        assert auth._jwt_secret == "custom-secret"


class TestCreateApp:
    """End-to-end tests for the ``create_app()`` factory."""

    def test_health_check(self, tmp_path: Path) -> None:
        """GET /api/health returns 200 without auth."""
        from ronzzdoi.server.app import create_app

        app = create_app(data_dir=str(tmp_path))
        client = TestClient(app)

        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "version": "0.1.0"}

    def test_root_health(self, tmp_path: Path) -> None:
        """GET / returns 200 without auth."""
        from ronzzdoi.server.app import create_app

        app = create_app(data_dir=str(tmp_path))
        client = TestClient(app)

        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "service": "ronzzdoi"}

    def test_auth_route_protected_without_key(self, tmp_path: Path) -> None:
        """Auth routes are protected — no key → 401."""
        from ronzzdoi.server.app import create_app

        app = create_app(data_dir=str(tmp_path))
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "test", "permission": "read_only"},
        )
        assert resp.status_code == 401

    def test_openapi_docs_available(self, tmp_path: Path) -> None:
        """OpenAPI docs are accessible at /api/docs."""
        from ronzzdoi.server.app import create_app

        app = create_app(data_dir=str(tmp_path))
        client = TestClient(app)

        resp = client.get("/api/docs")
        assert resp.status_code == 200

    def test_cors_headers_present(self, tmp_path: Path) -> None:
        """CORS headers are present on responses when Origin header is sent."""
        from ronzzdoi.server.app import create_app

        app = create_app(data_dir=str(tmp_path), enable_cors=True)
        client = TestClient(app)

        # Starlette's CORSMiddleware echoes back the specific origin value
        # when allow_origins=["*"] and allow_credentials=True
        resp = client.get("/", headers={"Origin": "https://example.com"})
        cors_origin = resp.headers.get("access-control-allow-origin")
        assert cors_origin is not None, "CORS header missing"
        # Should either be "*" or echo back the origin
        assert cors_origin in ("*", "https://example.com")

    def test_cors_disabled(self, tmp_path: Path) -> None:
        """CORS can be disabled via ``enable_cors=False``."""
        from ronzzdoi.server.app import create_app

        app = create_app(data_dir=str(tmp_path), enable_cors=False)
        client = TestClient(app)

        # No CORS headers when disabled, even with Origin header
        resp = client.get("/", headers={"Origin": "https://example.com"})
        assert resp.headers.get("access-control-allow-origin") is None

    def test_create_app_idempotent(self, tmp_path: Path) -> None:
        """Calling ``create_app`` multiple times with same data_dir is safe."""
        from ronzzdoi.server.app import create_app

        app1 = create_app(data_dir=str(tmp_path))
        app2 = create_app(data_dir=str(tmp_path))

        # Both apps should serve health check
        c1 = TestClient(app1)
        c2 = TestClient(app2)
        assert c1.get("/api/health").status_code == 200
        assert c2.get("/api/health").status_code == 200
