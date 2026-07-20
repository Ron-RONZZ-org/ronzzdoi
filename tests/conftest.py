"""Shared test fixtures for auth module tests."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lighterauth.api_key import generate_api_key
from lighterauth.db import init_auth_schema
from lighterauth.middleware import Lighterauth
from lighterauth.password import hash_password
from lightercore.db import LighterDB


# ── Database fixtures ──────────────────────────────────────────────────


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Return a temporary path for the auth database."""
    return tmp_path / "auth.db"


@pytest.fixture
def auth_db(tmp_db_path: Path) -> Iterator[LighterDB]:
    """Create and yield an in-memory-like auth database with schema.

    The database lives at ``tmp_db_path`` and is removed after the test.
    """
    db = LighterDB(str(tmp_db_path))
    init_auth_schema(db)
    yield db


@pytest.fixture
def admin_user_id() -> str:
    """Return a deterministic admin user ID."""
    return "admin-test-001"


@pytest.fixture
def admin_password() -> str:
    """Return a test admin password."""
    return "test-admin-password-123"


@pytest.fixture
def seed_admin_user(auth_db: LighterDB, admin_user_id: str, admin_password: str) -> dict[str, Any]:
    """Insert an admin user into the auth database and return the row."""
    now = "2026-01-01T00:00:00+00:00"
    hashed = hash_password(admin_password)
    auth_db.execute(
        "INSERT INTO users (id, email, username, password, role, status, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            admin_user_id,
            "admin@test.ronzz.org",
            "testadmin",
            hashed,
            "administrator",
            "active",
            now,
            now,
        ),
    )
    row = auth_db.execute_one("SELECT * FROM users WHERE id = ?", (admin_user_id,))
    assert row is not None, "Failed to insert admin user"
    return row


@pytest.fixture
def admin_api_key_full(auth_db: LighterDB, seed_admin_user: dict[str, Any]) -> str:
    """Create and return a full-access API key for the admin user.

    Returns the raw key string (usable in ``Authorization`` headers).
    """
    raw_key, prefix, hashed_key = generate_api_key()
    now = "2026-01-01T00:00:00+00:00"
    key_id = "ak_test_full_" + secrets.token_hex(8)
    auth_db.execute(
        "INSERT INTO api_keys (id, name, key, prefix, permission, "
        "created_at, updated_at, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (key_id, "test-full-access", hashed_key, prefix, "full_access", now, now, seed_admin_user["id"]),
    )
    return raw_key


@pytest.fixture
def admin_api_key_readonly(auth_db: LighterDB, seed_admin_user: dict[str, Any]) -> str:
    """Create and return a read-only API key for the admin user.

    Returns the raw key string.
    """
    raw_key, prefix, hashed_key = generate_api_key()
    now = "2026-01-01T00:00:00+00:00"
    key_id = "ak_test_ro_" + secrets.token_hex(8)
    auth_db.execute(
        "INSERT INTO api_keys (id, name, key, prefix, permission, "
        "created_at, updated_at, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (key_id, "test-read-only", hashed_key, prefix, "read_only", now, now, seed_admin_user["id"]),
    )
    return raw_key


# ── App fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def app(tmp_db_path: Path, auth_db: LighterDB) -> FastAPI:
    """Build a FastAPI app with auth wired to the test database.

    This bypasses ``create_app()`` to reuse the pre-seeded fixture DB.
    We use the same wiring pattern as ``create_app()``.
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from ronzzdoi.server.auth_middleware import init_auth_deps
    from ronzzdoi.server.auth_routes import mount_auth_routes

    auth = Lighterauth(auth_db)
    init_auth_deps(auth)

    app = FastAPI(title="ronzzdoi-test", version="0.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    mount_auth_routes(app, auth_db)

    # Add test-only endpoints to exercise the middleware
    from fastapi import Depends

    from ronzzdoi.server.auth_middleware import (
        optional_read_access,
        require_admin_role,
        require_write_access,
    )

    @app.post("/api/test/write")
    async def test_write_endpoint(
        user: dict[str, Any] = Depends(require_write_access),
    ) -> dict[str, Any]:
        return {"user_id": user["id"], "role": user.get("role")}

    @app.get("/api/test/read")
    async def test_read_endpoint(
        user: dict[str, Any] | None = Depends(optional_read_access),
    ) -> dict[str, Any]:
        return {"authenticated": user is not None}

    @app.get("/api/test/admin")
    async def test_admin_endpoint(
        user: dict[str, Any] = Depends(require_admin_role),
    ) -> dict[str, Any]:
        return {"user_id": user["id"], "role": user.get("role")}

    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Return a TestClient bound to the test app."""
    with TestClient(app) as c:
        yield c
