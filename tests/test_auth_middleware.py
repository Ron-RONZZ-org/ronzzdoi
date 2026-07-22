"""Tests for auth middleware — route-level auth dependencies."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestRequireWritePermission:
    """Tests for the ``require_permission("edit")`` dependency (write endpoints)."""

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

    def test_valid_admin_key(self, client: TestClient, admin_api_key_admin: str) -> None:
        """POST with a valid admin API key → 200."""
        resp = client.post(
            "/api/test/write",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
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


class TestRequireAdminPermission:
    """Tests for the ``require_permission("admin")`` dependency."""

    def test_no_auth_header(self, client: TestClient) -> None:
        """GET /api/test/admin without auth → 401."""
        resp = client.get("/api/test/admin")
        assert resp.status_code == 401, resp.text

    def test_valid_admin_key(self, client: TestClient, admin_api_key_admin: str) -> None:
        """GET /api/test/admin with valid admin key → 200."""
        resp = client.get(
            "/api/test/admin",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["user_id"] == "admin-test-001"
        assert data["role"] == "administrator"

    def test_readonly_key_rejected(self, client: TestClient, admin_api_key_readonly: str) -> None:
        """GET /api/test/admin with read-only key → 403."""
        resp = client.get(
            "/api/test/admin",
            headers={"Authorization": f"Bearer {admin_api_key_readonly}"},
        )
        assert resp.status_code == 403, resp.text
        assert "Requires at least 'admin'" in resp.text

    def test_edit_key_rejected(self, client: TestClient, admin_api_key_edit: str) -> None:
        """GET /api/test/admin with edit key → 403."""
        resp = client.get(
            "/api/test/admin",
            headers={"Authorization": f"Bearer {admin_api_key_edit}"},
        )
        assert resp.status_code == 403, resp.text
        assert "Requires at least 'admin'" in resp.text


class TestRequirePermission:
    """Tests for the ``require_permission(min_tier)`` dependency factory."""

    def test_admin_passes_admin_key(self, client: TestClient, admin_api_key_admin: str) -> None:
        """require_permission('admin') passes with admin key."""
        resp = client.post(
            "/api/test/require/admin",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user_id"] == "admin-test-001"

    def test_admin_rejects_edit_key(self, client: TestClient, admin_api_key_edit: str) -> None:
        """require_permission('admin') rejects edit key → 403."""
        resp = client.post(
            "/api/test/require/admin",
            headers={"Authorization": f"Bearer {admin_api_key_edit}"},
        )
        assert resp.status_code == 403, resp.text
        assert "Requires at least 'admin'" in resp.text

    def test_edit_passes_edit_key(self, client: TestClient, admin_api_key_edit: str) -> None:
        """require_permission('edit') passes with edit key."""
        resp = client.post(
            "/api/test/require/edit",
            headers={"Authorization": f"Bearer {admin_api_key_edit}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user_id"] == "admin-test-001"

    def test_edit_passes_admin_key(self, client: TestClient, admin_api_key_admin: str) -> None:
        """require_permission('edit') passes with admin key (hierarchy)."""
        resp = client.post(
            "/api/test/require/edit",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
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

    def test_readonly_passes_any_key(self, client: TestClient, admin_api_key_edit: str, admin_api_key_admin: str) -> None:
        """require_permission('read_only') passes with any key."""
        resp1 = client.post(
            "/api/test/require/read_only",
            headers={"Authorization": f"Bearer {admin_api_key_edit}"},
        )
        assert resp1.status_code == 200
        resp2 = client.post(
            "/api/test/require/read_only",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
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

    def test_require_permission_without_init(self, monkeypatch) -> None:
        """Calling ``require_permission("edit")`` without init raises RuntimeError."""
        import asyncio
        import ronzzdoi.server.auth_middleware as mw

        monkeypatch.setattr(mw, "_auth", None)

        # Grab the inner callable from the factory
        checker = mw.require_permission("edit")

        with pytest.raises(RuntimeError, match="auth_middleware not initialised"):
            # Run synchronously — _check_inited() fires before any await
            asyncio.run(checker(authorization="Bearer test"))
