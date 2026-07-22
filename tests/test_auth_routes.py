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

    def test_create_read_only(self, client: TestClient, admin_api_key_admin: str) -> None:
        """POST with valid admin auth creates a read-only key."""
        resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "ci-read-only", "permission": "read_only"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "ci-read-only"
        assert data["permission"] == "read_only"
        assert data["prefix"].startswith("la_")  # prefix is first 8 chars
        assert data["key"].startswith("la_")  # raw key returned once
        assert "id" in data

    def test_create_admin(self, client: TestClient, admin_api_key_admin: str) -> None:
        """POST with valid admin auth creates an admin key."""
        resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "ci-admin", "permission": "admin"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "ci-admin"
        assert data["permission"] == "admin"
        assert data["key"].startswith("la_")

    def test_create_with_expiry(self, client: TestClient, admin_api_key_admin: str) -> None:
        """POST with expires_at sets the expiration date."""
        resp = client.post(
            "/api/v1/auth/keys",
            json={
                "name": "expiring-key",
                "permission": "read_only",
                "expires_at": "2027-06-01T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["expires_at"] is not None
        assert "2027" in data["expires_at"]

    def test_invalid_permission(self, client: TestClient, admin_api_key_admin: str) -> None:
        """POST with an invalid permission value → 422."""
        resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "bad-perm", "permission": "super_admin"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 422, resp.text


class TestListApiKeys:
    """GET /api/v1/auth/keys — list API keys."""

    def test_unauthenticated(self, client: TestClient) -> None:
        """GET without auth → 401."""
        resp = client.get("/api/v1/auth/keys")
        assert resp.status_code == 401, resp.text

    def test_list_keys(self, client: TestClient, admin_api_key_admin: str, admin_api_key_readonly: str) -> None:
        """GET with valid admin auth returns the list of keys."""
        resp = client.get(
            "/api/v1/auth/keys",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # full_access + read_only from fixtures
        # The raw key value must NEVER be in the list response
        for entry in data:
            assert "key" not in entry, f"Raw key leaked in list: {entry}"

    def test_include_expired(self, client: TestClient, admin_api_key_admin: str, auth_db) -> None:
        """GET with include_expired=true includes expired keys."""
        # Insert an expired key directly
        import secrets
        from lighterauth.api_key import generate_api_key

        raw, prefix, hashed = generate_api_key()
        auth_db.execute(
            "INSERT INTO api_keys (id, name, key, prefix, permission, "
            "owner, expires_at, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "ak_expired_" + secrets.token_hex(8),
                "expired-key",
                hashed,
                prefix,
                "read_only",
                "test-expired",
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:00:00Z",
            ),
        )

        # Without include_expired — should be excluded
        resp = client.get(
            "/api/v1/auth/keys",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        names_without = [k["name"] for k in resp.json()]
        assert "expired-key" not in names_without

        # With include_expired — should appear
        resp = client.get(
            "/api/v1/auth/keys?include_expired=true",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        names_with = [k["name"] for k in resp.json()]
        assert "expired-key" in names_with


class TestRevokeApiKey:
    """DELETE /api/v1/auth/keys/{key_id} — revoke an API key."""

    def test_unauthenticated(self, client: TestClient) -> None:
        """DELETE without auth → 401."""
        resp = client.delete("/api/v1/auth/keys/some-id")
        assert resp.status_code == 401, resp.text

    def test_revoke_nonexistent(self, client: TestClient, admin_api_key_admin: str) -> None:
        """DELETE with a non-existent key ID → 404."""
        resp = client.delete(
            "/api/v1/auth/keys/nonexistent-id-12345",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 404, resp.text

    def test_revoke_and_verify_gone(
        self, client: TestClient, admin_api_key_admin: str, auth_db
    ) -> None:
        """DELETE a key, then verify it's gone from the list."""
        # First create a key
        create_resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "to-be-revoked", "permission": "read_only"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert create_resp.status_code == 201
        key_id = create_resp.json()["id"]

        # Revoke it
        delete_resp = client.delete(
            f"/api/v1/auth/keys/{key_id}",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert delete_resp.status_code == 204, delete_resp.text

        # Verify it's gone from the list
        list_resp = client.get(
            "/api/v1/auth/keys",
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        names = [k["name"] for k in list_resp.json()]
        assert "to-be-revoked" not in names


class TestUpdateApiKey:
    """PATCH /api/v1/auth/keys/{key_id} — update an API key."""

    def test_unauthenticated(self, client: TestClient) -> None:
        """PATCH without auth → 401."""
        resp = client.patch(
            "/api/v1/auth/keys/some-id",
            json={"name": "new-name"},
        )
        assert resp.status_code == 401, resp.text

    def test_update_name(
        self, client: TestClient, admin_api_key_admin: str
    ) -> None:
        """PATCH updates the key name."""
        # First create a key
        create_resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "original-name", "permission": "read_only"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert create_resp.status_code == 201
        key_id = create_resp.json()["id"]

        # Update the name
        resp = client.patch(
            f"/api/v1/auth/keys/{key_id}",
            json={"name": "updated-name"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == "updated-name"
        assert data["id"] == key_id
        assert "key" not in data  # must not leak the raw key

    def test_update_permission(
        self, client: TestClient, admin_api_key_admin: str
    ) -> None:
        """PATCH updates the permission."""
        create_resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "perm-test", "permission": "read_only"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert create_resp.status_code == 201
        key_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/auth/keys/{key_id}",
            json={"permission": "admin"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["permission"] == "admin"

    def test_update_expiry(
        self, client: TestClient, admin_api_key_admin: str
    ) -> None:
        """PATCH updates the expiration date."""
        create_resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "expiry-test", "permission": "read_only"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert create_resp.status_code == 201
        key_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/auth/keys/{key_id}",
            json={"expires_at": "2028-12-31T23:59:59Z"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["expires_at"] is not None
        assert "2028" in data["expires_at"]

    def test_clear_expiry(
        self, client: TestClient, admin_api_key_admin: str
    ) -> None:
        """PATCH with expires_at=null clears the expiration."""
        create_resp = client.post(
            "/api/v1/auth/keys",
            json={
                "name": "clear-expiry",
                "permission": "read_only",
                "expires_at": "2028-01-01T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert create_resp.status_code == 201
        key_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/auth/keys/{key_id}",
            json={"expires_at": None},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["expires_at"] is None

    def test_invalid_permission(
        self, client: TestClient, admin_api_key_admin: str
    ) -> None:
        """PATCH with an invalid permission → 422."""
        create_resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "bad-perm-upd", "permission": "read_only"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert create_resp.status_code == 201
        key_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/auth/keys/{key_id}",
            json={"permission": "super_admin"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 422, resp.text

    def test_nonexistent_key(
        self, client: TestClient, admin_api_key_admin: str
    ) -> None:
        """PATCH on a non-existent key → 404."""
        resp = client.patch(
            "/api/v1/auth/keys/nonexistent-99999",
            json={"name": "noop"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 404, resp.text

    def test_no_changes(
        self, client: TestClient, admin_api_key_admin: str
    ) -> None:
        """PATCH with no fields → returns current key unchanged."""
        create_resp = client.post(
            "/api/v1/auth/keys",
            json={"name": "no-change", "permission": "read_only"},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert create_resp.status_code == 201
        key_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/auth/keys/{key_id}",
            json={},
            headers={"Authorization": f"Bearer {admin_api_key_admin}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == "no-change"
        assert data["permission"] == "read_only"
