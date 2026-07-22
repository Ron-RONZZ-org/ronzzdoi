"""Tests for auth middleware — route-level auth dependencies."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


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
        assert "Requires at least 'edit'" in resp.text

    def test_valid_edit_key(self, client: TestClient, admin_api_key_edit: str) -> None:
        """POST with a valid edit-access API key → 200."""
        resp = client.post(
            "/api/test/write",
            headers={"Authorization": f"Bearer {admin_api_key_edit}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["user_id"] == "admin-test-001"
        assert data["role"] == "administrator"


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


class TestRequirePermission:
    """Tests for the ``require_permission(min_tier)`` dependency factory."""

    def test_full_access_passes_full_key(self, client: TestClient, admin_api_key_full: str) -> None:
        """require_permission('full_access') passes with full_access key."""
        resp = client.post(
            "/api/test/require/full_access",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user_id"] == "admin-test-001"

    def test_full_access_rejects_edit_key(self, client: TestClient, admin_api_key_edit: str) -> None:
        """require_permission('full_access') rejects edit key → 403."""
        resp = client.post(
            "/api/test/require/full_access",
            headers={"Authorization": f"Bearer {admin_api_key_edit}"},
        )
        assert resp.status_code == 403, resp.text
        assert "Requires at least 'full_access'" in resp.text

    def test_edit_passes_edit_key(self, client: TestClient, admin_api_key_edit: str) -> None:
        """require_permission('edit') passes with edit key."""
        resp = client.post(
            "/api/test/require/edit",
            headers={"Authorization": f"Bearer {admin_api_key_edit}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user_id"] == "admin-test-001"

    def test_edit_passes_full_key(self, client: TestClient, admin_api_key_full: str) -> None:
        """require_permission('edit') passes with full_access key (hierarchy)."""
        resp = client.post(
            "/api/test/require/edit",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user_id"] == "admin-test-001"

    def test_edit_rejects_readonly_key(self, client: TestClient, admin_api_key_readonly: str) -> None:
        """require_permission('edit') rejects read_only key → 403."""
        resp = client.post(
            "/api/test/require/edit",
            headers={"Authorization": f"Bearer {admin_api_key_readonly}"},
        )
        assert resp.status_code == 403, resp.text
        assert "Requires at least 'edit'" in resp.text

    def test_readonly_passes_readonly_key(self, client: TestClient, admin_api_key_readonly: str) -> None:
        """require_permission('read_only') passes with read_only key."""
        resp = client.post(
            "/api/test/require/read_only",
            headers={"Authorization": f"Bearer {admin_api_key_readonly}"},
        )
        assert resp.status_code == 200, resp.text

    def test_readonly_passes_any_key(self, client: TestClient, admin_api_key_edit: str, admin_api_key_full: str) -> None:
        """require_permission('read_only') passes with any key."""
        resp1 = client.post(
            "/api/test/require/read_only",
            headers={"Authorization": f"Bearer {admin_api_key_edit}"},
        )
        assert resp1.status_code == 200
        resp2 = client.post(
            "/api/test/require/read_only",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp2.status_code == 200


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
