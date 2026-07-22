"""Tests for auth middleware — route-level auth dependencies."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from lightercore.db import LighterDB


class TestRequireWriteAccess:
    """Tests for the ``require_write_access`` dependency."""

    def test_no_auth_header(self, client: TestClient) -> None:
        """POST to a write endpoint without auth → 401."""
        resp = client.post("/api/test/write")
        assert resp.status_code == 401, resp.text
        assert "Authentication required" in resp.text

    def test_invalid_scheme(self, client: TestClient) -> None:
        """POST with non-Bearer auth → 401."""
        resp = client.post("/api/test/write", headers={"Authorization": "Basic abc123"})
        assert resp.status_code == 401, resp.text

    def test_invalid_key(self, client: TestClient) -> None:
        """POST with a garbage API key → 401."""
        resp = client.post(
            "/api/test/write",
            headers={"Authorization": "Bearer la_not_a_real_key_12345"},
        )
        assert resp.status_code == 401, resp.text

    def test_valid_full_access(self, client: TestClient, admin_api_key_full: str) -> None:
        """POST with a valid full-access API key → 200."""
        resp = client.post(
            "/api/test/write",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["user_id"] == "admin-test-001"
        assert data["role"] == "administrator"

    def test_readonly_key_rejected(self, client: TestClient, admin_api_key_readonly: str) -> None:
        """POST with a read-only API key → 403."""
        resp = client.post(
            "/api/test/write",
            headers={"Authorization": f"Bearer {admin_api_key_readonly}"},
        )
        assert resp.status_code == 403, resp.text
        assert "full_access" in resp.text


class TestOptionalReadAccess:
    """Tests for the ``optional_read_access`` dependency."""

    def test_no_auth_header(self, client: TestClient) -> None:
        """GET without auth → 200 (returns authenticated: false)."""
        resp = client.get("/api/test/read")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"authenticated": False}

    def test_valid_key(self, client: TestClient, admin_api_key_full: str) -> None:
        """GET with valid API key → 200 (authenticated: true)."""
        resp = client.get(
            "/api/test/read",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"authenticated": True}

    def test_invalid_key(self, client: TestClient) -> None:
        """GET with invalid API key → 200 (authenticated: false, key ignored)."""
        resp = client.get(
            "/api/test/read",
            headers={"Authorization": "Bearer la_bogus_bogus_bogus"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"authenticated": False}


class TestRequireAdminRole:
    """Tests for the ``require_admin_role`` dependency."""

    def test_no_auth_header(self, client: TestClient) -> None:
        """GET /api/test/admin without auth → 401."""
        resp = client.get("/api/test/admin")
        assert resp.status_code == 401, resp.text

    def test_valid_admin_key(self, client: TestClient, admin_api_key_full: str) -> None:
        """GET /api/test/admin with valid admin key → 200."""
        resp = client.get(
            "/api/test/admin",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["user_id"] == "admin-test-001"
        assert data["role"] == "administrator"

    def test_readonly_still_admin(self, client: TestClient, admin_api_key_readonly: str) -> None:
        """GET /api/test/admin with read-only but admin role key → 200.

        ``require_admin_role`` checks the user's role, not the
        API key's permission.  A read-only key belonging to an
        admin user should still pass.
        """
        resp = client.get(
            "/api/test/admin",
            headers={"Authorization": f"Bearer {admin_api_key_readonly}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["role"] == "administrator"


class TestInitDepsGuard:
    """Tests for the ``_check_inited()`` guard — RuntimeError if
    ``init_auth_deps()`` was never called."""

    def test_check_inited_raises(self, monkeypatch) -> None:
        """Calling ``_check_inited`` before ``init_auth_deps`` raises RuntimeError."""
        import ronzzdoi.server.auth_middleware as mw

        # Reset the module-level _auth to simulate uninitialised state
        monkeypatch.setattr(mw, "_auth", None)

        from ronzzdoi.server.auth_middleware import _check_inited

        with pytest.raises(RuntimeError, match="auth_middleware not initialised"):
            _check_inited()

    def test_require_write_access_without_init(self, monkeypatch) -> None:
        """Calling ``require_write_access`` without init raises RuntimeError."""
        import asyncio
        import ronzzdoi.server.auth_middleware as mw

        monkeypatch.setattr(mw, "_auth", None)

        from ronzzdoi.server.auth_middleware import require_write_access

        with pytest.raises(RuntimeError, match="auth_middleware not initialised"):
            # Run synchronously — _check_inited() fires before any await
            asyncio.run(require_write_access(authorization="Bearer test"))


class TestRequirePermission:
    """Tests for the ``require_permission`` dependency factory."""

    def test_readonly_no_auth(self, client: TestClient) -> None:
        """GET /api/test/perm-readonly without auth → 401."""
        resp = client.get("/api/test/perm-readonly")
        assert resp.status_code == 401, resp.text

    def test_fullaccess_no_auth(self, client: TestClient) -> None:
        """GET /api/test/perm-fullaccess without auth → 401."""
        resp = client.get("/api/test/perm-fullaccess")
        assert resp.status_code == 401, resp.text

    def test_readonly_with_readonly_key(
        self, client: TestClient, admin_api_key_readonly: str
    ) -> None:
        """read-only key on read_only endpoint → 200 (admin bypass)."""
        resp = client.get(
            "/api/test/perm-readonly",
            headers={"Authorization": f"Bearer {admin_api_key_readonly}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["permission"] == "read_only"

    def test_readonly_with_full_key(
        self, client: TestClient, admin_api_key_full: str
    ) -> None:
        """full-access key on read_only endpoint → 200."""
        resp = client.get(
            "/api/test/perm-readonly",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["permission"] == "full_access"

    def test_admin_role_bypasses_permission_check(
        self, client: TestClient, admin_api_key_readonly: str
    ) -> None:
        """Admin users bypass permission checks (read-only key on full_access → 200)."""
        resp = client.get(
            "/api/test/perm-fullaccess",
            headers={"Authorization": f"Bearer {admin_api_key_readonly}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["permission"] == "read_only"

    def test_fullaccess_accepts_full_key(
        self, client: TestClient, admin_api_key_full: str
    ) -> None:
        """full-access key on full_access endpoint → 200."""
        resp = client.get(
            "/api/test/perm-fullaccess",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["permission"] == "full_access"

    def test_non_admin_readonly_rejected(
        self, client: TestClient, auth_db: LighterDB
    ) -> None:
        """A non-admin user with read-only key is rejected on full_access endpoint.

        Creates a regular user (user role) with a read-only API key
        to test the permission check without admin bypass.
        """
        import secrets
        from lighterauth.api_key import generate_api_key
        from lighterauth.password import hash_password

        now = "2026-01-01T00:00:00+00:00"

        # Create a regular user (not admin)
        user_id = "regular-user-001"
        hashed = hash_password("password123")
        auth_db.execute(
            "INSERT INTO users (id, email, username, password, role, status, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, "regular@test.com", "regular", hashed, "user", "active", now, now),
        )

        # Create a read-only API key for the regular user
        raw_key, prefix, hashed_key = generate_api_key()
        auth_db.execute(
            "INSERT INTO api_keys (id, name, key, prefix, permission, "
            "created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "ak_regular_ro_" + secrets.token_hex(8),
                "regular-read-only",
                hashed_key,
                prefix,
                "read_only",
                now,
                now,
                user_id,
            ),
        )

        # Regular user with read-only key → 403 on full_access endpoint
        resp = client.get(
            "/api/test/perm-fullaccess",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code == 403, resp.text
