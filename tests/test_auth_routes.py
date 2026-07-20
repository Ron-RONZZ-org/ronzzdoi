"""Tests for auth API endpoints — API key management via ``/api/v1/auth/keys``."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestCreateApiKey:
    """POST /api/v1/auth/keys — create a new API key."""

    def test_unauthenticated(self, client: TestClient) -> None:
        """POST without auth → 401."""
        resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "test-key", "permission": "read_only"},
        )
        assert resp.status_code == 401, resp.text

    def test_create_read_only(self, client: TestClient, admin_api_key_full: str) -> None:
        """POST with valid admin auth creates a read-only key."""
        resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "ci-read-only", "permission": "read_only"},
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "ci-read-only"
        assert data["permission"] == "read_only"
        assert data["prefix"].startswith("la_")  # prefix is first 8 chars
        assert data["key"].startswith("la_")  # raw key returned once
        assert "id" in data

    def test_create_full_access(self, client: TestClient, admin_api_key_full: str) -> None:
        """POST with valid admin auth creates a full-access key."""
        resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "ci-full-access", "permission": "full_access"},
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "ci-full-access"
        assert data["permission"] == "full_access"
        assert data["key"].startswith("la_")

    def test_create_with_expiry(self, client: TestClient, admin_api_key_full: str) -> None:
        """POST with expires_at sets the expiration date."""
        resp = client.post(
            "/api/v1/auth/keys",
            json={
                "name": "expiring-key",
                "permission": "read_only",
                "expires_at": "2027-06-01T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["expires_at"] is not None
        assert "2027" in data["expires_at"]

    def test_invalid_permission(self, client: TestClient, admin_api_key_full: str) -> None:
        """POST with an invalid permission value → 422."""
        resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "bad-perm", "permission": "super_admin"},
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 422, resp.text


class TestListApiKeys:
    """GET /api/v1/auth/keys — list API keys."""

    def test_unauthenticated(self, client: TestClient) -> None:
        """GET without auth → 401."""
        resp = client.get("/api/v1/auth/keys")
        assert resp.status_code == 401, resp.text

    def test_list_keys(self, client: TestClient, admin_api_key_full: str, admin_api_key_readonly: str) -> None:
        """GET with valid admin auth returns the list of keys."""
        resp = client.get(
            "/api/v1/auth/keys",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # full_access + read_only from fixtures
        # The raw key value must NEVER be in the list response
        for entry in data:
            assert "key" not in entry, f"Raw key leaked in list: {entry}"

    def test_include_expired(self, client: TestClient, admin_api_key_full: str, auth_db) -> None:
        """GET with include_expired=true includes expired keys."""
        # Insert an expired key directly
        import secrets
        from lighterauth.api_key import generate_api_key

        raw, prefix, hashed = generate_api_key()
        auth_db.execute(
            "INSERT INTO api_keys (id, name, key, prefix, permission, "
            "expires_at, created_at, updated_at, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "ak_expired_" + secrets.token_hex(8),
                "expired-key",
                hashed,
                prefix,
                "read_only",
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:00:00Z",
                "admin-test-001",
            ),
        )

        # Without include_expired — should be excluded
        resp = client.get(
            "/api/v1/auth/keys",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        names_without = [k["name"] for k in resp.json()]
        assert "expired-key" not in names_without

        # With include_expired — should appear
        resp = client.get(
            "/api/v1/auth/keys?include_expired=true",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        names_with = [k["name"] for k in resp.json()]
        assert "expired-key" in names_with


class TestRevokeApiKey:
    """DELETE /api/v1/auth/keys/{key_id} — revoke an API key."""

    def test_unauthenticated(self, client: TestClient) -> None:
        """DELETE without auth → 401."""
        resp = client.delete("/api/v1/auth/keys/some-id")
        assert resp.status_code == 401, resp.text

    def test_revoke_nonexistent(self, client: TestClient, admin_api_key_full: str) -> None:
        """DELETE with a non-existent key ID → 404."""
        resp = client.delete(
            "/api/v1/auth/keys/nonexistent-id-12345",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert resp.status_code == 404, resp.text

    def test_revoke_and_verify_gone(
        self, client: TestClient, admin_api_key_full: str, auth_db
    ) -> None:
        """DELETE a key, then verify it's gone from the list."""
        # First create a key
        create_resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "to-be-revoked", "permission": "read_only"},
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert create_resp.status_code == 201
        key_id = create_resp.json()["id"]

        # Revoke it
        delete_resp = client.delete(
            f"/api/v1/auth/keys/{key_id}",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        assert delete_resp.status_code == 204, delete_resp.text

        # Verify it's gone from the list
        list_resp = client.get(
            "/api/v1/auth/keys",
            headers={"Authorization": f"Bearer {admin_api_key_full}"},
        )
        names = [k["name"] for k in list_resp.json()]
        assert "to-be-revoked" not in names
