"""Tests for the CLI HTTP client (RonzzdoiClient).

All tests use ``httpx.MockTransport`` — no real server needed.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from ronzzdoi.cli.client import (
    AccessDeniedError,
    AuthenticationError,
    ClientError,
    ConnectionError_,
    RonzzdoiClient,
    ServerError,
)


def _mock_transport(response_body: dict[str, Any] | None = None, status_code: int = 200) -> httpx.MockTransport:
    """Create a MockTransport that returns a fixed JSON response."""
    response_data = httpx.Response(status_code, json=response_body or {})

    def handler(request: httpx.Request) -> httpx.Response:
        return response_data

    return httpx.MockTransport(handler)


def _error_transport(status_code: int, detail: str = "error") -> httpx.MockTransport:
    """Create a MockTransport that returns an error response."""
    return httpx.MockTransport(
        lambda req: httpx.Response(status_code, json={"detail": detail})
    )


# ── Auth header ────────────────────────────────────────────────────────────


def test_auth_header_sent() -> None:
    """Verify the API key is sent as Bearer token."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization", "")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = RonzzdoiClient(api_key="test-key-123", client=httpx.Client(transport=transport))
    client.get("/api/v1/doi")
    assert captured["auth"] == "Bearer test-key-123"


def test_auth_header_empty_key() -> None:
    """Verify no Authorization header when api_key is empty."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization", "")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = RonzzdoiClient(api_key="", client=httpx.Client(transport=transport))
    client.get("/api/v1/doi")
    assert captured["auth"] == ""


# ── Error translation ─────────────────────────────────────────────────────


def test_401_authentication_error() -> None:
    """401 raises AuthenticationError."""
    client = RonzzdoiClient(api_key="bad", client=httpx.Client(transport=_error_transport(401, "Invalid API key")))
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        client.get("/api/v1/doi")


def test_403_permission_error() -> None:
    """403 raises AccessDeniedError."""
    client = RonzzdoiClient(api_key="ro-key", client=httpx.Client(transport=_error_transport(403, "Insufficient permission")))
    with pytest.raises(AccessDeniedError, match="Insufficient permission"):
        client.get("/api/v1/doi")


def test_404_client_error() -> None:
    """404 raises ClientError."""
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=_error_transport(404, "Not found")))
    with pytest.raises(ClientError, match="Not found"):
        client.get("/api/v1/doi/nonexistent")


def test_409_client_error() -> None:
    """409 raises ClientError."""
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=_error_transport(409, "Conflict")))
    with pytest.raises(ClientError, match="Conflict"):
        client.post("/api/v1/doi", json={})


def test_422_client_error() -> None:
    """422 raises ClientError."""
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=_error_transport(422, "Invalid input")))
    with pytest.raises(ClientError, match="Invalid input"):
        client.post("/api/v1/doi", json={})


def test_500_server_error() -> None:
    """500 raises ServerError."""
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=_error_transport(500, "Internal error")))
    with pytest.raises(ServerError, match="Internal error"):
        client.get("/api/v1/doi")


# ── Connection errors ─────────────────────────────────────────────────────


def test_connection_refused() -> None:
    """ConnectionError_ when httpx cannot connect."""
    client = RonzzdoiClient(server_url="http://127.0.0.1:1", api_key="test")
    with pytest.raises(ConnectionError_, match="Could not connect to server"):
        client.get("/api/v1/doi")


# ── 204 No Content ────────────────────────────────────────────────────────


def test_204_returns_none() -> None:
    """204 response returns None."""
    transport = httpx.MockTransport(lambda req: httpx.Response(204))
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=transport))
    result = client.delete("/api/v1/doi/10.ronzz/abc")
    assert result is None


# ── Successful requests ────────────────────────────────────────────────────


def test_get_returns_json() -> None:
    """GET returns parsed JSON."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"doi": "10.ronzz/abc", "title": "Test"}))
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=transport))
    result = client.get("/api/v1/doi/10.ronzz/abc")
    assert result == {"doi": "10.ronzz/abc", "title": "Test"}


def test_post_returns_json() -> None:
    """POST returns parsed JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        data = json.loads(request.content)
        return httpx.Response(201, json={"doi": "10.ronzz/new", **data})

    transport = httpx.MockTransport(handler)
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=transport))
    result = client.post("/api/v1/doi", json={"target_url": "https://example.com"})
    assert result["doi"] == "10.ronzz/new"
    assert result["target_url"] == "https://example.com"


# ── PUT, PATCH, DELETE ─────────────────────────────────────────────────────


def test_put_request() -> None:
    """PUT sends data and returns result."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"doi": "10.ronzz/abc", "title": "Updated"}))
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=transport))
    result = client.put("/api/v1/doi/10.ronzz/abc", json={"title": "Updated"})
    assert result["title"] == "Updated"


def test_patch_request() -> None:
    """PATCH sends data and returns result."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "application/json" in request.headers.get("content-type", "")
        return httpx.Response(200, json={"id": "ak_001", "name": "renamed"})

    transport = httpx.MockTransport(handler)
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=transport))
    result = client.patch("/api/v1/auth/keys/ak_001", json={"name": "renamed"})
    assert result["name"] == "renamed"


def test_delete_request() -> None:
    """DELETE returns None for 204."""
    transport = httpx.MockTransport(lambda req: httpx.Response(204))
    client = RonzzdoiClient(api_key="test", client=httpx.Client(transport=transport))
    result = client.delete("/api/v1/doi/10.ronzz/abc")
    assert result is None


# ── ENV var fallback (server_url) ──────────────────────────────────────────


def test_default_server_url() -> None:
    """Default server URL is http://127.0.0.1:8000 (dev-friendly)."""
    client = RonzzdoiClient(api_key="test")
    assert client.server_url == "http://127.0.0.1:8000"


def test_custom_server_url() -> None:
    """Custom server URL is used."""
    client = RonzzdoiClient(server_url="http://localhost:9000", api_key="test")
    assert client.server_url == "http://localhost:9000"
