"""Tests for DOI API endpoints — assign, resolve, modify, delete, merge, search.

All endpoints except ``GET /{doi}`` (public redirect) require
authentication via ``Authorization: Bearer <key>``.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from lightercore.db import LighterDB

DOI_FORMAT_RE = re.compile(r"^10\.ronzz/[0-9a-f]{32}$")


# ── Helpers ────────────────────────────────────────────────────────────────


def _auth_header(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


# ── Test: GET /{doi} (public redirect) ────────────────────────────────────


class TestPublicRedirect:
    """``GET /{doi}`` — public HTTP redirect (no auth required)."""

    def test_redirect_to_url(
        self, doi_client: TestClient, doi_crud_svc
    ) -> None:
        """A DOI with target_url → 302 redirect."""
        record = doi_crud_svc.assign("https://example.com")
        doi = record["doi"]

        resp = doi_client.get(f"/{doi}", follow_redirects=False)
        assert resp.status_code == 302, resp.text
        assert resp.headers["location"] == "https://example.com"
        assert resp.headers.get("x-doi") == doi

    def test_entity_doi_no_target(
        self, doi_client: TestClient, doi_crud_svc
    ) -> None:
        """A person/entity DOI with no target_url → 204."""
        record = doi_crud_svc.assign(
            doi_type="person",
            title="Ada Lovelace",
            metadata={"first_name": "Ada", "last_name": "Lovelace"},
        )
        resp = doi_client.get(f"/{record['doi']}", follow_redirects=False)
        assert resp.status_code == 204, resp.text

    def test_tombstoned_doi(self, doi_client: TestClient, doi_crud_svc) -> None:
        """A tombstoned DOI → 410 Gone."""
        record = doi_crud_svc.assign("https://example.com")
        doi_crud_svc.delete_doi(record["doi"])
        resp = doi_client.get(f"/{record['doi']}", follow_redirects=False)
        assert resp.status_code == 410, resp.text
        assert "tombstoned" in resp.text

    def test_nonexistent_doi(self, doi_client: TestClient) -> None:
        """A non-existent DOI → 404."""
        resp = doi_client.get(
            "/10.ronzz/00000000000000000000000000000000", follow_redirects=False
        )
        assert resp.status_code == 404, resp.text

    def test_non_doi_path(self, doi_client: TestClient) -> None:
        """A non-DOI path at root → 404."""
        resp = doi_client.get("/not-a-doi", follow_redirects=False)
        assert resp.status_code == 404, resp.text


# ── Test: GET /api/v1/doi/{doi} (resolve) ─────────────────────────────────


class TestResolveEndpoint:
    """``GET /api/v1/doi/{doi}`` — resolve DOI metadata."""

    def test_unauthenticated(self, doi_client: TestClient, doi_crud_svc) -> None:
        """GET without auth → 401."""
        created = doi_crud_svc.assign("https://example.com")
        resp = doi_client.get(f"/api/v1/doi/{created['doi']}")
        assert resp.status_code == 401, resp.text

    def test_resolve_by_full_doi(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """Resolve by complete DOI string."""
        created = doi_crud_svc.assign("https://example.com", title="Test")
        resp = doi_client.get(
            f"/api/v1/doi/{created['doi']}",
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["doi"] == created["doi"]
        assert data["target_url"] == "https://example.com"
        assert data["title"] == "Test"
        assert data["status"] == "active"

    def test_resolve_tombstoned(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """Tombstoned DOI returns record with deleted_at and status."""
        created = doi_crud_svc.assign("https://example.com")
        doi_crud_svc.delete_doi(created["doi"])
        resp = doi_client.get(
            f"/api/v1/doi/{created['doi']}",
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["deleted_at"] is not None
        assert data["status"] == "tombstone"

    def test_nonexistent(
        self, doi_client: TestClient, admin_api_key_admin: str
    ) -> None:
        """Non-existent DOI → 404."""
        resp = doi_client.get(
            "/api/v1/doi/10.ronzz/00000000000000000000000000000000",
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 404, resp.text

    def test_readonly_key_can_resolve(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_readonly: str
    ) -> None:
        """Read-only API keys can resolve DOIs."""
        created = doi_crud_svc.assign("https://example.com")
        resp = doi_client.get(
            f"/api/v1/doi/{created['doi']}",
            headers=_auth_header(admin_api_key_readonly),
        )
        assert resp.status_code == 200, resp.text


# ── Test: POST /api/v1/doi (assign) ───────────────────────────────────────


class TestAssignEndpoint:
    """``POST /api/v1/doi`` — assign a new DOI."""

    def test_unauthenticated(self, doi_client: TestClient) -> None:
        """POST without auth → 401."""
        resp = doi_client.post(
            "/api/v1/doi",
            json={"target_url": "https://example.com"},
        )
        assert resp.status_code == 401, resp.text

    def test_assign_minimal(
        self, doi_client: TestClient, admin_api_key_admin: str
    ) -> None:
        """Assign with only target_url."""
        resp = doi_client.post(
            "/api/v1/doi",
            json={"target_url": "https://example.com"},
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["target_url"] == "https://example.com"
        assert DOI_FORMAT_RE.match(data["doi"])
        assert data["title"] == ""
        assert data["doi_type"] == "external"

    def test_assign_full(
        self, doi_client: TestClient, admin_api_key_admin: str
    ) -> None:
        """Assign with all optional fields."""
        resp = doi_client.post(
            "/api/v1/doi",
            json={
                "target_url": "https://example.org/doc",
                "doi_type": "book",
                "title": "Test Book",
                "metadata": {"author": "Test Author", "year": 2026},
            },
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["target_url"] == "https://example.org/doc"
        assert data["doi_type"] == "book"
        assert data["title"] == "Test Book"
        assert data["metadata"]["author"] == "Test Author"

    def test_assign_entity_no_url(
        self, doi_client: TestClient, admin_api_key_admin: str
    ) -> None:
        """Assign an entity DOI without target_url."""
        resp = doi_client.post(
            "/api/v1/doi",
            json={
                "doi_type": "person",
                "title": "Ada Lovelace",
                "metadata": {"first_name": "Ada", "last_name": "Lovelace"},
            },
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["target_url"] is None

    def test_readonly_key_cannot_assign(
        self, doi_client: TestClient, auth_db: LighterDB
    ) -> None:
        """Read-only API key → 403."""
        import secrets
        from lighterauth.api_key import generate_api_key

        now = "2026-01-01T00:00:00+00:00"
        raw_key, prefix, hashed_key = generate_api_key()
        auth_db.execute(
            "INSERT INTO api_keys (id, name, key, prefix, permission, owner, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ak_ro_test_" + secrets.token_hex(8), "ro-key", hashed_key, prefix, "read_only", "test-ro", now, now),
        )

        resp = doi_client.post(
            "/api/v1/doi",
            json={"target_url": "https://example.com"},
            headers=_auth_header(raw_key),
        )
        assert resp.status_code == 403, resp.text


# ── Test: PUT /api/v1/doi/{doi} (modify) ──────────────────────────────────


class TestModifyEndpoint:
    """``PUT /api/v1/doi/{doi}`` — modify DOI metadata."""

    def test_unauthenticated(self, doi_client: TestClient, doi_crud_svc) -> None:
        """PUT without auth → 401."""
        created = doi_crud_svc.assign("https://example.com")
        resp = doi_client.put(
            f"/api/v1/doi/{created['doi']}",
            json={"title": "Updated"},
        )
        assert resp.status_code == 401, resp.text

    def test_modify_title(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """Modify the title of a DOI."""
        created = doi_crud_svc.assign("https://example.com", title="Original")
        resp = doi_client.put(
            f"/api/v1/doi/{created['doi']}",
            json={"title": "Updated"},
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["title"] == "Updated"
        assert data["target_url"] == "https://example.com"

    def test_modify_url_creates_redirect(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """Changing target_url creates a redirect record."""
        created = doi_crud_svc.assign("https://original.com")
        resp = doi_client.put(
            f"/api/v1/doi/{created['doi']}",
            json={"target_url": "https://new.com"},
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["target_url"] == "https://new.com"
        assert len(data["redirect_history"]) == 1
        assert data["redirect_history"][0]["old_url"] == "https://original.com"

    def test_modify_with_redirect_note(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """``redirect_note`` is recorded in the redirect entry."""
        created = doi_crud_svc.assign("https://original.com")
        resp = doi_client.put(
            f"/api/v1/doi/{created['doi']}",
            json={
                "target_url": "https://new.com",
                "redirect_note": "Moved to new server",
            },
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["redirect_history"]) == 1
        assert data["redirect_history"][0]["note"] == "Moved to new server"

    def test_modify_nonexistent(
        self, doi_client: TestClient, admin_api_key_admin: str
    ) -> None:
        """Modifying a non-existent DOI → 404."""
        resp = doi_client.put(
            "/api/v1/doi/10.ronzz/00000000000000000000000000000000",
            json={"title": "Nope"},
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 404, resp.text

    def test_readonly_key_cannot_modify(
        self, doi_client: TestClient, doi_crud_svc, auth_db: LighterDB
    ) -> None:
        """Read-only API key → 403."""
        import secrets
        from lighterauth.api_key import generate_api_key

        now = "2026-01-01T00:00:00+00:00"
        raw_key, prefix, hashed_key = generate_api_key()
        auth_db.execute(
            "INSERT INTO api_keys (id, name, key, prefix, permission, owner, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ak_ro_mod_" + secrets.token_hex(8), "ro-mod-key", hashed_key, prefix, "read_only", "test-ro-mod", now, now),
        )

        created = doi_crud_svc.assign("https://example.com")
        resp = doi_client.put(
            f"/api/v1/doi/{created['doi']}",
            json={"title": "Nope"},
            headers=_auth_header(raw_key),
        )
        assert resp.status_code == 403, resp.text


# ── Test: DELETE /api/v1/doi/{doi} (tombstone) ────────────────────────────


class TestDeleteEndpoint:
    """``DELETE /api/v1/doi/{doi}`` — tombstone a DOI."""

    def test_unauthenticated(self, doi_client: TestClient, doi_crud_svc) -> None:
        """DELETE without auth → 401."""
        created = doi_crud_svc.assign("https://example.com")
        resp = doi_client.delete(
            f"/api/v1/doi/{created['doi']}",
        )
        assert resp.status_code == 401, resp.text

    def test_delete_active(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """Delete an active DOI → 204."""
        created = doi_crud_svc.assign("https://example.com")
        resp = doi_client.delete(
            f"/api/v1/doi/{created['doi']}",
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 204, resp.text
        row = doi_crud_svc.db.execute_one(
            "SELECT * FROM dois WHERE doi = ?", (created["doi"],)
        )
        assert row["deleted_at"] is not None

    def test_delete_nonexistent(
        self, doi_client: TestClient, admin_api_key_admin: str
    ) -> None:
        """Delete a non-existent DOI → 404."""
        resp = doi_client.delete(
            "/api/v1/doi/10.ronzz/00000000000000000000000000000000",
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 404, resp.text

    def test_readonly_key_cannot_delete(
        self, doi_client: TestClient, doi_crud_svc, auth_db: LighterDB
    ) -> None:
        """Read-only API key → 403."""
        import secrets
        from lighterauth.api_key import generate_api_key

        now = "2026-01-01T00:00:00+00:00"
        raw_key, prefix, hashed_key = generate_api_key()
        auth_db.execute(
            "INSERT INTO api_keys (id, name, key, prefix, permission, owner, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ak_ro_del_" + secrets.token_hex(8), "ro-del-key", hashed_key, prefix, "read_only", "test-ro-del", now, now),
        )

        created = doi_crud_svc.assign("https://example.com")
        resp = doi_client.delete(
            f"/api/v1/doi/{created['doi']}",
            headers=_auth_header(raw_key),
        )
        assert resp.status_code == 403, resp.text


# ── Test: GET /api/v1/doi (list) ────────────────────────────────────────────


class TestListEndpoint:
    """``GET /api/v1/doi`` — list DOI records."""

    def test_unauthenticated(self, doi_client: TestClient) -> None:
        """GET without auth → 401."""
        resp = doi_client.get("/api/v1/doi")
        assert resp.status_code == 401, resp.text

    def test_list_active_only(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """By default, only active (non-tombstoned) DOIs are returned."""
        doi_crud_svc.assign("https://active.com", title="Active One")
        doi_crud_svc.assign("https://active2.com", title="Active Two")
        doomed = doi_crud_svc.assign("https://doomed.com")
        doi_crud_svc.delete_doi(doomed["doi"])

        resp = doi_client.get(
            "/api/v1/doi",
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        dois = {item["doi"]: item for item in data["items"]}
        assert doomed["doi"] not in dois, "tombstoned DOI should be excluded"
        assert all(not item.get("deleted_at") for item in data["items"])

    def test_list_include_deleted(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """``include_deleted=true`` includes tombstoned DOIs."""
        alive = doi_crud_svc.assign("https://alive.com")
        doomed = doi_crud_svc.assign("https://doomed.com")
        doi_crud_svc.delete_doi(doomed["doi"])

        resp = doi_client.get(
            "/api/v1/doi",
            params={"include_deleted": "true"},
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        dois = {item["doi"]: item for item in data["items"]}
        assert alive["doi"] in dois
        assert doomed["doi"] in dois
        assert dois[doomed["doi"]]["deleted_at"] is not None

    def test_list_filter_by_type(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """``doi_type`` filter returns only matching type."""
        doi_crud_svc.assign("https://book.com", doi_type="book")
        doi_crud_svc.assign("https://page.com", doi_type="webpage")

        resp = doi_client.get(
            "/api/v1/doi",
            params={"doi_type": "webpage"},
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert all(item["doi_type"] == "webpage" for item in data["items"])

    def test_list_empty(
        self, doi_client: TestClient, admin_api_key_admin: str
    ) -> None:
        """Empty database returns empty list."""
        resp = doi_client.get(
            "/api/v1/doi",
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_readonly_allowed(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_readonly: str
    ) -> None:
        """Read-only keys can list DOIs."""
        doi_crud_svc.assign("https://ex.com")
        resp = doi_client.get(
            "/api/v1/doi",
            headers=_auth_header(admin_api_key_readonly),
        )
        assert resp.status_code == 200, resp.text


# ── Test: POST /api/v1/doi/merge (merge) ──────────────────────────────────


class TestMergeEndpoint:
    """``POST /api/v1/doi/merge`` — merge source DOI into target."""

    def test_unauthenticated(self, doi_client: TestClient) -> None:
        """POST without auth → 401."""
        resp = doi_client.post(
            "/api/v1/doi/merge",
            json={"source_doi": "x", "target_doi": "y"},
        )
        assert resp.status_code == 401, resp.text

    def test_merge_simple(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """Merge source into target, source gets tombstoned."""
        source = doi_crud_svc.assign(
            "https://source.com", title="Source", doi_type="book"
        )
        target = doi_crud_svc.assign(
            "https://target.com", title="Target", doi_type="webpage"
        )

        resp = doi_client.post(
            "/api/v1/doi/merge",
            json={
                "source_doi": source["doi"],
                "target_doi": target["doi"],
                "delete_source": True,
            },
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["doi"] == target["doi"]

        # Source should be tombstoned
        source_record = doi_crud_svc.resolve(source["doi"])
        assert source_record["deleted_at"] is not None

    def test_merge_nonexistent_source(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """Merge with non-existent source → 404."""
        target = doi_crud_svc.assign("https://target.com")
        resp = doi_client.post(
            "/api/v1/doi/merge",
            json={
                "source_doi": "10.ronzz/00000000000000000000000000000000",
                "target_doi": target["doi"],
            },
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 404, resp.text


# ── Test: GET /api/v1/doi/search (search) ─────────────────────────────────


class TestSearchEndpoint:
    """``GET /api/v1/doi/search`` — search DOIs by type and query."""

    def test_unauthenticated(self, doi_client: TestClient) -> None:
        """GET without auth → 401."""
        resp = doi_client.get("/api/v1/doi/search?q=test")
        assert resp.status_code == 401, resp.text

    def test_search_by_type(
        self, doi_client: TestClient, doi_crud_svc, admin_api_key_admin: str
    ) -> None:
        """Search by DOI type."""
        doi_crud_svc.assign("https://person.com", doi_type="person", title="Ada")
        doi_crud_svc.assign("https://book.com", doi_type="book", title="A Book")

        resp = doi_client.get(
            "/api/v1/doi/search?q=&doi_type=person",
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["doi_type"] == "person"

    def test_search_empty(
        self, doi_client: TestClient, admin_api_key_admin: str
    ) -> None:
        """Empty database returns empty results."""
        resp = doi_client.get(
            "/api/v1/doi/search?q=test",
            headers=_auth_header(admin_api_key_admin),
        )
        assert resp.status_code == 200, resp.text
