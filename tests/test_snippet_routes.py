"""Tests for the snippet API endpoints — /api/v1/snippet + public snippet.

Exercises auth (edit/read_only), validation errors, and the ``!snippet``
command dispatch path through the HTTP layer.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lighterauth.middleware import Lighterauth
from lightercore.db import LighterDB

from ronzzdoi.db.schema import MIGRATIONS

DOI_FORMAT_RE = re.compile(r"^10\.ronzz/[0-9a-f]{32}$")


# ── App fixture (full schema + snippet routes) ──────────────────────────────


@pytest.fixture
def ronzzdoi_db(tmp_path) -> Iterator[LighterDB]:
    """Full-schema ronzzdoi database."""
    db = LighterDB(tmp_path / "ronzzdoi.db")
    db.migrate(MIGRATIONS)
    yield db
    db.close()


@pytest.fixture
def snippet_app(auth_db: LighterDB, ronzzdoi_db: LighterDB) -> FastAPI:
    """FastAPI app with auth + DOI + snippet + command + public routes."""
    from fastapi.middleware.cors import CORSMiddleware

    from ronzzdoi.db.service import DOIService as DBDOIService
    from ronzzdoi.doi.service import DOIService as DOICrudService
    from ronzzdoi.server.auth_middleware import init_auth_deps
    from ronzzdoi.server.auth_routes import mount_auth_routes
    from ronzzdoi.server.command_routes import mount_command_routes
    from ronzzdoi.server.doi_routes import mount_doi_routes, register_doi_redirect
    from ronzzdoi.server.public_routes import mount_public_routes
    from ronzzdoi.server.snippet_routes import mount_snippet_routes
    from ronzzdoi.snippet.service import SnippetService

    auth = Lighterauth(auth_db, keyonly=True)
    init_auth_deps(auth)

    app = FastAPI(title="ronzzdoi-test", version="0.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    doi_crud_svc = DOICrudService(ronzzdoi_db)
    db_search_svc = DBDOIService(ronzzdoi_db)
    snippet_svc = SnippetService(ronzzdoi_db, doi_crud_svc)

    mount_auth_routes(app, auth_db)
    mount_command_routes(app)
    mount_doi_routes(app, doi_svc=doi_crud_svc, search_svc=db_search_svc)
    mount_snippet_routes(app, snippet_svc)
    mount_public_routes(
        app, doi_svc=doi_crud_svc, search_svc=db_search_svc, snippet_svc=snippet_svc
    )

    # DOI redirect must be last
    register_doi_redirect(app)

    return app


@pytest.fixture
def client(snippet_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(snippet_app) as c:
        yield c


# ── Helpers ────────────────────────────────────────────────────────────────


def _auth_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


# ── POST /api/v1/snippet ───────────────────────────────────────────────────


class TestAssignRoute:
    def test_assign_snippet(self, client, admin_api_key_edit):
        resp = client.post(
            "/api/v1/snippet",
            json={
                "content_kind": "text",
                "content": "To be or not to be.",
                "title": "Hamlet",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert DOI_FORMAT_RE.match(body["doi"])
        assert body["content_kind"] == "text"
        assert body["content"] == "To be or not to be."
        assert body["title"] == "Hamlet"
        assert body["source_doi"] is None

    def test_assign_multilingual_title(self, client, admin_api_key_edit):
        """A language-map title round-trips through the API (#47)."""
        resp = client.post(
            "/api/v1/snippet",
            json={
                "content_kind": "text",
                "content": "To be or not to be.",
                "title": {"en": "Hamlet", "fr": "Hamlet (FR)"},
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["title"] == {"en": "Hamlet", "fr": "Hamlet (FR)"}

        # Resolve returns the same language map.
        resolved = client.get(
            f"/api/v1/snippet/{body['doi']}",
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["title"] == {"en": "Hamlet", "fr": "Hamlet (FR)"}

    def test_assign_requires_edit_permission(self, client, admin_api_key_readonly):
        resp = client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "quote"},
            headers=_auth_headers(admin_api_key_readonly),
        )
        assert resp.status_code == 403

    def test_assign_requires_auth(self, client):
        resp = client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "quote"},
        )
        assert resp.status_code == 401

    def test_assign_invalid_kind(self, client, admin_api_key_edit):
        resp = client.post(
            "/api/v1/snippet",
            json={"content_kind": "image", "content": "x"},
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 422

    def test_assign_missing_source(self, client, admin_api_key_edit):
        resp = client.post(
            "/api/v1/snippet",
            json={
                "content_kind": "text",
                "content": "x",
                "source_doi": "10.ronzz/nope",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 422
        assert "not found" in resp.json()["detail"]

    def test_assign_with_source(self, client, admin_api_key_edit):
        book = client.post(
            "/api/v1/doi",
            json={
                "target_url": "https://example.com/book",
                "doi_type": "book",
                "title": "Hamlet",
            },
            headers=_auth_headers(admin_api_key_edit),
        ).json()
        resp = client.post(
            "/api/v1/snippet",
            json={
                "content_kind": "text",
                "content": "To be…",
                "source_doi": book["doi"],
                "page_start": "12",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["source_doi"] == book["doi"]
        assert body["page_start"] == "12"


# ── GET /api/v1/snippet/{doi} ──────────────────────────────────────────────


class TestResolveRoute:
    def _create(self, client, key, **overrides):
        payload = {
            "content_kind": "code",
            "content": "print('hi')",
            "language": "python",
            **overrides,
        }
        resp = client.post("/api/v1/snippet", json=payload, headers=_auth_headers(key))
        assert resp.status_code == 201
        return resp.json()

    def test_resolve_snippet(self, client, admin_api_key_edit, admin_api_key_readonly):
        created = self._create(client, admin_api_key_edit)
        resp = client.get(
            f"/api/v1/snippet/{created['doi']}",
            headers=_auth_headers(admin_api_key_readonly),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["content_kind"] == "code"
        assert body["content"] == "print('hi')"
        assert body["language"] == "python"
        assert body["status"] == "active"

    def test_resolve_missing(self, client, admin_api_key_readonly):
        resp = client.get(
            "/api/v1/snippet/10.ronzz/does-not-exist",
            headers=_auth_headers(admin_api_key_readonly),
        )
        assert resp.status_code == 404

    def test_resolve_requires_auth(self, client, admin_api_key_edit):
        created = self._create(client, admin_api_key_edit)
        resp = client.get(f"/api/v1/snippet/{created['doi']}")
        assert resp.status_code == 401

    def test_resolve_after_tombstone(self, client, admin_api_key_edit):
        created = self._create(client, admin_api_key_edit)
        client.delete(
            f"/api/v1/snippet/{created['doi']}",
            headers=_auth_headers(admin_api_key_edit),
        )
        resp = client.get(
            f"/api/v1/snippet/{created['doi']}",
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "tombstone"


# ── PUT /api/v1/snippet/{doi} ──────────────────────────────────────────────


class TestModifyRoute:
    def _create(self, client, key):
        resp = client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "old"},
            headers=_auth_headers(key),
        )
        return resp.json()

    def test_modify_content(self, client, admin_api_key_edit):
        created = self._create(client, admin_api_key_edit)
        resp = client.put(
            f"/api/v1/snippet/{created['doi']}",
            json={"content": "new", "content_kind": "code", "language": "js"},
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == "new"
        assert body["content_kind"] == "code"
        assert body["language"] == "js"

    def test_modify_requires_edit(
        self, client, admin_api_key_edit, admin_api_key_readonly
    ):
        created = self._create(client, admin_api_key_edit)
        resp = client.put(
            f"/api/v1/snippet/{created['doi']}",
            json={"content": "new"},
            headers=_auth_headers(admin_api_key_readonly),
        )
        assert resp.status_code == 403

    def test_modify_non_snippet(self, client, admin_api_key_edit):
        book = client.post(
            "/api/v1/doi",
            json={"target_url": "https://example.com", "doi_type": "book"},
            headers=_auth_headers(admin_api_key_edit),
        ).json()
        resp = client.put(
            f"/api/v1/snippet/{book['doi']}",
            json={"content": "x"},
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 404
        assert "not a snippet" in resp.json()["detail"]


# ── DELETE /api/v1/snippet/{doi} ───────────────────────────────────────────


class TestDeleteRoute:
    def test_delete_tombstones(self, client, admin_api_key_edit):
        resp = client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "quote"},
            headers=_auth_headers(admin_api_key_edit),
        )
        doi = resp.json()["doi"]
        resp = client.delete(
            f"/api/v1/snippet/{doi}", headers=_auth_headers(admin_api_key_edit)
        )
        assert resp.status_code == 204

    def test_delete_missing(self, client, admin_api_key_edit):
        resp = client.delete(
            "/api/v1/snippet/10.ronzz/does-not-exist",
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 404


# ── !snippet command dispatch (through HTTP) ───────────────────────────────


class TestSnippetCommand:
    def test_add_missing_content_returns_form(self, client, admin_api_key_edit):
        resp = client.post(
            "/api/v1/command",
            json={
                "tokens": ["snippet", "add"],
                "flags": {},
                "raw_input": "!snippet add",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "form"
        assert body["data"]["form"] == "snippet-add"

    def test_add_full_flags(self, client, admin_api_key_edit):
        resp = client.post(
            "/api/v1/command",
            json={
                "tokens": ["snippet", "add"],
                "flags": {
                    "type": "code",
                    "content": "print('hello')",
                    "language": "python",
                    "title": "Hello",
                },
                "raw_input": "!snippet add --type code --content print('hello')",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "snippet"
        assert body["data"]["content_kind"] == "code"
        assert body["data"]["content"] == "print('hello')"

    def test_view_via_command(self, client, admin_api_key_edit):
        created = client.post(
            "/api/v1/snippet",
            json={"content_kind": "math", "content": r"\frac{1}{2}"},
            headers=_auth_headers(admin_api_key_edit),
        ).json()
        resp = client.post(
            "/api/v1/command",
            json={
                "tokens": ["snippet", "view", created["doi"]],
                "flags": {},
                "raw_input": "",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "snippet"
        assert body["data"]["content_kind"] == "math"

    def test_view_accepts_full_link(self, client, admin_api_key_edit):
        created = client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "linked"},
            headers=_auth_headers(admin_api_key_edit),
        ).json()
        resp = client.post(
            "/api/v1/command",
            json={
                "tokens": [
                    "snippet",
                    "view",
                    f"https://doi.ronzz.org/{created['doi']}",
                ],
                "flags": {},
                "raw_input": "",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "snippet"
        assert body["data"]["content"] == "linked"

    def test_view_non_snippet_returns_error(self, client, admin_api_key_edit):
        book = client.post(
            "/api/v1/doi",
            json={"target_url": "https://example.com", "doi_type": "book"},
            headers=_auth_headers(admin_api_key_edit),
        ).json()
        resp = client.post(
            "/api/v1/command",
            json={
                "tokens": ["snippet", "view", book["doi"]],
                "flags": {},
                "raw_input": "",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "error"
        assert "not a snippet" in body["data"]["message"]

    def test_search_lists_snippets(self, client, admin_api_key_edit):
        client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "alpha", "title": "Alpha"},
            headers=_auth_headers(admin_api_key_edit),
        )
        resp = client.post(
            "/api/v1/command",
            json={
                "tokens": ["snippet", "search"],
                "flags": {},
                "raw_input": "!snippet search",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "snippet-list"
        assert body["data"]["results"]
        assert body["data"]["results"][0]["content_kind"] == "text"

    def test_search_filters_by_query(self, client, admin_api_key_edit):
        client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "beta marker"},
            headers=_auth_headers(admin_api_key_edit),
        )
        client.post(
            "/api/v1/snippet",
            json={"content_kind": "code", "content": "gamma"},
            headers=_auth_headers(admin_api_key_edit),
        )
        resp = client.post(
            "/api/v1/command",
            json={
                "tokens": ["snippet", "search", "marker"],
                "flags": {},
                "raw_input": "!snippet search marker",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        body = resp.json()
        assert body["type"] == "snippet-list"
        dois = [r["doi"] for r in body["data"]["results"]]
        assert len(dois) == 1

    def test_modify_without_flags_returns_edit_form(self, client, admin_api_key_edit):
        created = client.post(
            "/api/v1/snippet",
            json={
                "content_kind": "code",
                "content": "old code",
                "language": "js",
                "title": "Old",
            },
            headers=_auth_headers(admin_api_key_edit),
        ).json()
        resp = client.post(
            "/api/v1/command",
            json={
                "tokens": ["snippet", "modify", created["doi"]],
                "flags": {},
                "raw_input": "",
            },
            headers=_auth_headers(admin_api_key_edit),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "form"
        assert body["data"]["form"] == "snippet-edit"
        initial = body["data"]["initialData"]
        assert initial["doi"] == created["doi"]
        assert initial["type"] == "code"
        assert initial["content"] == "old code"
        assert initial["language"] == "js"

    def test_command_requires_edit_for_add(self, client, admin_api_key_readonly):
        resp = client.post(
            "/api/v1/command",
            json={
                "tokens": ["snippet", "add"],
                "flags": {"type": "text", "content": "x"},
                "raw_input": "",
            },
            headers=_auth_headers(admin_api_key_readonly),
        )
        assert resp.status_code == 200
        assert resp.json()["type"] == "error"

    def test_command_tree_contains_snippet(self, client):
        resp = client.get("/api/v1/command/tree")
        assert resp.status_code == 200
        names = [n["name"] for n in resp.json()]
        assert "snippet" in names


# ── Public endpoint ─────────────────────────────────────────────────────────


class TestPublicSnippetRoute:
    def test_public_snippet_no_auth(self, client, admin_api_key_edit):
        created = client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "public quote", "title": "Pub"},
            headers=_auth_headers(admin_api_key_edit),
        ).json()
        resp = client.get(f"/public/v1/snippet/{created['doi']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == "public quote"
        assert body["content_kind"] == "text"
        assert body["title"] == "Pub"

    def test_public_snippet_missing(self, client):
        resp = client.get("/public/v1/snippet/10.ronzz/does-not-exist")
        assert resp.status_code == 404

    def test_public_snippet_tombstoned(self, client, admin_api_key_edit):
        created = client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "gone"},
            headers=_auth_headers(admin_api_key_edit),
        ).json()
        client.delete(
            f"/api/v1/snippet/{created['doi']}",
            headers=_auth_headers(admin_api_key_edit),
        )
        resp = client.get(f"/public/v1/snippet/{created['doi']}")
        assert resp.status_code == 410

    def test_public_snippet_non_snippet_doi(self, client, admin_api_key_edit):
        book = client.post(
            "/api/v1/doi",
            json={"target_url": "https://example.com", "doi_type": "book"},
            headers=_auth_headers(admin_api_key_edit),
        ).json()
        resp = client.get(f"/public/v1/snippet/{book['doi']}")
        assert resp.status_code == 404
        assert "not a snippet" in resp.json()["detail"]

    def test_public_search_finds_snippet_content(self, client, admin_api_key_edit):
        client.post(
            "/api/v1/snippet",
            json={"content_kind": "text", "content": "Cogito ergo sum"},
            headers=_auth_headers(admin_api_key_edit),
        )
        resp = client.get("/public/v1/search", params={"q": "cogito"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["content_kind"] == "text"
