"""Tests for public read-only API endpoints with rate-limiting.

Covers:
- Public endpoints return data without ``Authorization`` header
- Response schemas expose only public-safe fields
- Search ``limit`` parameter is capped at 50
- Rate-limiting returns 429 after exceeding limit
- Internal endpoints still require auth in full mode
- DOI redirect remains public
- Health check works without auth
"""

from __future__ import annotations

from typing import Any, Iterator

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from lighterauth.middleware import Lighterauth

from ronzzdoi.server.auth_middleware import init_auth_deps
from ronzzdoi.server.doi_routes import register_doi_redirect
from ronzzdoi.server.public_routes import mount_public_routes


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def public_app(
    auth_db,
    doi_crud_svc,
    citation_formatter,
) -> FastAPI:
    """Build a FastAPI app with public routes only (no internal routes)."""
    auth = Lighterauth(auth_db, keyonly=True)
    init_auth_deps(auth)

    app = FastAPI(title="ronzzdoi-public-test", version="0.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    mount_public_routes(
        app,
        doi_svc=doi_crud_svc,
        search_svc=None,
        formatter=citation_formatter,
    )

    @app.get("/")
    async def root_health() -> dict[str, str]:
        return {"status": "ok", "service": "ronzzdoi"}

    register_doi_redirect(app)
    return app


@pytest.fixture
def public_client(public_app: FastAPI) -> Iterator[TestClient]:
    """Return a TestClient bound to the public app."""
    with TestClient(public_app) as c:
        yield c


@pytest.fixture
def full_app(
    auth_db,
    doi_crud_svc,
    citation_formatter,
) -> FastAPI:
    """Build a FastAPI app with BOTH internal and public routes (full mode).

    This is equivalent to ``create_app(mode="full")``.
    """
    from ronzzdoi.server.auth_routes import mount_auth_routes
    from ronzzdoi.server.citation_routes import mount_citation_routes
    from ronzzdoi.server.command_routes import mount_command_routes
    from ronzzdoi.server.doi_routes import mount_doi_routes
    from ronzzdoi.server.search_routes import mount_search_routes

    auth = Lighterauth(auth_db, keyonly=True)
    init_auth_deps(auth)

    app = FastAPI(title="ronzzdoi-full-test", version="0.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Internal routes
    mount_auth_routes(app, auth_db)
    mount_command_routes(app)
    mount_doi_routes(app, doi_svc=doi_crud_svc)
    mount_citation_routes(app, citation_formatter)

    @app.get("/api/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    # Public routes
    mount_public_routes(
        app,
        doi_svc=doi_crud_svc,
        search_svc=None,
        formatter=citation_formatter,
    )

    @app.get("/")
    async def root_health() -> dict[str, str]:
        return {"status": "ok", "service": "ronzzdoi"}

    register_doi_redirect(app)
    return app


@pytest.fixture
def full_client(full_app: FastAPI) -> Iterator[TestClient]:
    """Return a TestClient bound to the full (internal+public) app."""
    with TestClient(full_app) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _seed_book(doi_crud_svc: Any) -> dict[str, Any]:
    """Create and return a minimal book DOI for testing."""
    return doi_crud_svc.assign(
        target_url="https://example.com/book",
        doi_type="book",
        title="Public Test Book",
        metadata={
            "authors": [{"given": "Jane", "family": "Doe"}],
            "title": "Public Test Book",
            "publisher": "Test Press",
            "year": 2024,
        },
    )


# ═══════════════════════════════════════════════════════════════════════
# Public Health
# ═══════════════════════════════════════════════════════════════════════


class TestPublicHealth:
    """``GET /public/v1/health`` — public health check."""

    def test_health_no_auth(self, public_client: TestClient) -> None:
        """Health endpoint works without auth."""
        resp = public_client.get("/public/v1/health")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"

    def test_root_health_no_auth(self, public_client: TestClient) -> None:
        """Root health endpoint works without auth."""
        resp = public_client.get("/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════
# Public DOI Resolve
# ═══════════════════════════════════════════════════════════════════════


class TestPublicDOIResolve:
    """``GET /public/v1/doi/{doi}`` — public DOI resolution."""

    def test_resolve_no_auth(
        self, public_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """Resolve DOI without auth header → succeeds."""
        book = _seed_book(doi_crud_svc)
        resp = public_client.get(f"/public/v1/doi/{book['doi']}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["doi"] == book["doi"]
        assert data["title"] == "Public Test Book"

    def test_public_response_fields(
        self, public_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """Public response excludes internal fields.

        Should NOT contain: status, redirect_history, deleted_at, updated_at.
        """
        book = _seed_book(doi_crud_svc)
        resp = public_client.get(f"/public/v1/doi/{book['doi']}")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Should have these public fields
        assert "doi" in data
        assert "target_url" in data
        assert "title" in data
        assert "doi_type" in data
        assert "metadata" in data
        assert "created_at" in data

        # Should NOT have these internal fields
        assert "status" not in data, "status must not be exposed"
        assert "redirect_history" not in data, "redirect_history must not be exposed"
        assert "deleted_at" not in data, "deleted_at must not be exposed"
        assert "updated_at" not in data, "updated_at must not be exposed"

    def test_nonexistent_doi(self, public_client: TestClient) -> None:
        """Non-existent DOI → 404."""
        resp = public_client.get("/public/v1/doi/10.ronzz/0000000000000000")
        assert resp.status_code == 404, resp.text

    def test_invalid_doi_format(self, public_client: TestClient) -> None:
        """Invalid DOI format → 400 (caught by service)."""
        # An empty/invalid path that doesn't match the prefix
        resp = public_client.get("/public/v1/doi//")
        assert resp.status_code in (400, 404), resp.text


# ═══════════════════════════════════════════════════════════════════════
# Public Search
# ═══════════════════════════════════════════════════════════════════════


class TestPublicSearch:
    """``GET /public/v1/search`` — public DOI search."""

    def test_search_no_auth(
        self, public_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """Search without auth → succeeds."""
        _seed_book(doi_crud_svc)
        resp = public_client.get("/public/v1/search?q=Public")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1

    def test_search_limit_capped(
        self, public_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """Search ``limit`` param is silently capped at 50."""
        # Create a few DOIs to search through
        for i in range(5):
            doi_crud_svc.assign(
                target_url=f"https://example.com/{i}",
                doi_type="external",
                title=f"Cap Test {i}",
                metadata={},
            )

        resp = public_client.get("/public/v1/search?q=Cap&limit=100")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["limit"] == 50, f"Expected cap at 50, got {data['limit']}"

    def test_search_with_type_filter(
        self, public_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """Search with ``doi_type`` filter."""
        doi_crud_svc.assign(
            target_url="https://example.com/webpage",
            doi_type="webpage",
            title="Webpage Search Test",
            metadata={},
        )
        resp = public_client.get(
            "/public/v1/search?q=Search&doi_type=webpage"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert all(item["doi_type"] == "webpage" for item in data["items"])

    def test_search_public_fields(
        self, public_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """Search results exclude internal fields."""
        _seed_book(doi_crud_svc)
        resp = public_client.get("/public/v1/search?q=Public")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        for item in data["items"]:
            assert "status" not in item
            assert "redirect_history" not in item
            assert "deleted_at" not in item
            assert "updated_at" not in item


# ═══════════════════════════════════════════════════════════════════════
# Public Citation
# ═══════════════════════════════════════════════════════════════════════


class TestPublicCitation:
    """``GET /public/v1/citation`` — public citation formatting."""

    def test_citation_no_auth(
        self, public_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """Citation without auth → succeeds."""
        book = _seed_book(doi_crud_svc)
        resp = public_client.get(
            f"/public/v1/citation?doi={book['doi']}&style=apa"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["style"] == "apa"
        assert "citation" in data

    def test_citation_nonexistent_doi(
        self, public_client: TestClient
    ) -> None:
        """Non-existent DOI citation → 404."""
        resp = public_client.get(
            "/public/v1/citation?doi=10.ronzz/nonexistent&style=apa"
        )
        assert resp.status_code == 404, resp.text

    def test_citation_unsupported_style(
        self, public_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """Unknown style → 400."""
        book = _seed_book(doi_crud_svc)
        resp = public_client.get(
            f"/public/v1/citation?doi={book['doi']}&style=unknown_xyz"
        )
        assert resp.status_code == 400, resp.text


# ═══════════════════════════════════════════════════════════════════════
# Rate Limiting
# ═══════════════════════════════════════════════════════════════════════


class TestRateLimiting:
    """Rate-limiting on public endpoints."""

    def test_rate_limit_exceeded(
        self,
        monkeypatch: pytest.MonkeyPatch,
        auth_db,
        doi_crud_svc,
        citation_formatter,
    ) -> None:
        """After exceeding the limit → 429."""
        # Set a very low rate limit so we can trigger it in a single test
        monkeypatch.setenv("RONZZDOI_PUBLIC_RATE_LIMIT_DOI", "1/minute")

        # Build a fresh app so the limiter reads the env var at request time
        auth = Lighterauth(auth_db, keyonly=True)
        init_auth_deps(auth)

        app = FastAPI(title="ronzzdoi-ratelimit-test", version="0.0.0")
        mount_public_routes(
            app,
            doi_svc=doi_crud_svc,
            search_svc=None,
            formatter=citation_formatter,
        )

        with TestClient(app) as client:
            book = _seed_book(doi_crud_svc)

            # First request should succeed (1/minute limit)
            resp1 = client.get(f"/public/v1/doi/{book['doi']}")
            assert resp1.status_code == 200, resp1.text

            # Second request should be rate-limited
            resp2 = client.get(f"/public/v1/doi/{book['doi']}")
            assert resp2.status_code == 429, (
                f"Expected 429, got {resp2.status_code}: {resp2.text}"
            )
            data = resp2.json()
            # slowapi returns "error" by default; some versions use "detail"
            assert "error" in data or "detail" in data, data


# ═══════════════════════════════════════════════════════════════════════
# Auth isolation (full mode)
# ═══════════════════════════════════════════════════════════════════════


class TestAuthIsolation:
    """Internal endpoints still require auth, even in full mode."""

    def test_internal_endpoint_requires_auth(
        self, full_client: TestClient
    ) -> None:
        """GET /api/v1/doi/{doi} without auth → 401."""
        resp = full_client.get("/api/v1/doi/10.ronzz/some-doi")
        assert resp.status_code == 401, resp.text

    def test_public_endpoint_no_auth(
        self, full_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """In full mode, public endpoints still work without auth."""
        book = _seed_book(doi_crud_svc)
        resp = full_client.get(f"/public/v1/doi/{book['doi']}")
        assert resp.status_code == 200, resp.text

    def test_internal_health_no_auth(
        self, full_client: TestClient
    ) -> None:
        """Internal health endpoint also works without auth (no auth dep)."""
        resp = full_client.get("/api/health")
        assert resp.status_code == 200, resp.text

    def test_doi_redirect_still_public(
        self, full_client: TestClient, doi_crud_svc: Any
    ) -> None:
        """The DOI redirect (``/{doi}``) remains public."""
        book = doi_crud_svc.assign(
            target_url="https://example.com/redirect-test",
            doi_type="external",
            title="Redirect Test",
            metadata={},
        )
        resp = full_client.get(f"/{book['doi']}", follow_redirects=False)
        assert resp.status_code == 302, resp.text
        assert resp.headers.get("location") == "https://example.com/redirect-test"


# ═══════════════════════════════════════════════════════════════════════
# Public-only mode (no internal routes)
# ═══════════════════════════════════════════════════════════════════════


class TestPublicOnlyMode:
    """When running in ``public`` mode, internal endpoints are unavailable."""

    def test_internal_endpoint_not_found(
        self, public_client: TestClient
    ) -> None:
        """Internal endpoints return 404 in public mode."""
        resp = public_client.get("/api/v1/doi/10.ronzz/test")
        assert resp.status_code == 404, resp.text

    def test_internal_health_not_found(
        self, public_client: TestClient
    ) -> None:
        """Internal health endpoint is 404 in public mode."""
        resp = public_client.get("/api/health")
        assert resp.status_code == 404, resp.text
