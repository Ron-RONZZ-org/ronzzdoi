"""Tests for CLI snippet subcommands — assign, embed, resolve.

All tests use ``httpx.MockTransport`` — no real server needed.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from ronzzdoi.cli.client import RonzzdoiClient
from ronzzdoi.cli.snippet import (
    DEFAULT_EMBED_BASE,
    _cmd_assign,
    _cmd_embed,
    _cmd_resolve,
    _normalize_doi,
)

SNIPPET_RESPONSE = {
    "doi": "10.ronzz/abc123def456",
    "title": "Hamlet soliloquy",
    "content_kind": "text",
    "content": "To be, or not to be",
    "language": "",
    "source_doi": "10.ronzz/book123",
    "page_start": "Act 3",
    "page_end": "",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
    "deleted_at": None,
    "status": "active",
}


def _make_args(**overrides: Any) -> Any:
    """Create a simple namespace for testing command handlers."""
    defaults = {"json_output": False}
    defaults.update(overrides)
    return type("Args", (), defaults)()


def _mock_client(handler) -> RonzzdoiClient:
    """Create a RonzzdoiClient with the given MockTransport handler."""
    transport = httpx.MockTransport(handler)
    return RonzzdoiClient(api_key="test-key", client=httpx.Client(transport=transport))


# ── _normalize_doi ─────────────────────────────────────────────────────────


def test_normalize_doi_full() -> None:
    assert _normalize_doi("10.ronzz/abc123") == "10.ronzz/abc123"


def test_normalize_doi_suffix() -> None:
    assert _normalize_doi("abc123") == "10.ronzz/abc123"


# ── embed ──────────────────────────────────────────────────────────────────


class TestEmbed:
    def test_embed_url_only(self, capsys: pytest.CaptureFixture) -> None:
        """--url-only prints just the embed URL."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SNIPPET_RESPONSE)

        args = _make_args(
            doi="abc123def456",
            width="640",
            height="240",
            base=DEFAULT_EMBED_BASE,
            url_only=True,
        )
        _cmd_embed(args, _mock_client(handler))
        out = capsys.readouterr().out.strip()
        assert out == f"{DEFAULT_EMBED_BASE}/10.ronzz/abc123def456"

    def test_embed_iframe_tag(self, capsys: pytest.CaptureFixture) -> None:
        """Default output is a copy-paste iframe tag."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SNIPPET_RESPONSE)

        args = _make_args(
            doi="10.ronzz/abc123def456",
            width="640",
            height="240",
            base=DEFAULT_EMBED_BASE,
            url_only=False,
        )
        _cmd_embed(args, _mock_client(handler))
        out = capsys.readouterr().out.strip()
        assert out.startswith(
            '<iframe src="https://doi.ronzz.org/embed/10.ronzz/abc123def456"'
        )
        assert 'title="Hamlet soliloquy"' in out
        assert 'width="640"' in out
        assert 'height="240"' in out
        assert 'loading="lazy"' in out

    def test_embed_escapes_title(self, capsys: pytest.CaptureFixture) -> None:
        """Titles with quotes/angle brackets are HTML-escaped."""

        def handler(request: httpx.Request) -> httpx.Response:
            body = dict(SNIPPET_RESPONSE)
            body["title"] = 'Quote "to be" <or not>'
            return httpx.Response(200, json=body)

        args = _make_args(
            doi="10.ronzz/abc",
            width="640",
            height="240",
            base=DEFAULT_EMBED_BASE,
            url_only=False,
        )
        _cmd_embed(args, _mock_client(handler))
        out = capsys.readouterr().out.strip()
        assert "&quot;to be&quot;" in out
        assert "&lt;or not&gt;" in out
        assert '" <' not in out.replace(
            "src=", ""
        )  # no raw angle brackets inside attrs

    def test_embed_custom_base(self, capsys: pytest.CaptureFixture) -> None:
        """--base overrides the embed URL prefix."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SNIPPET_RESPONSE)

        args = _make_args(
            doi="10.ronzz/abc",
            width="640",
            height="240",
            base="http://127.0.0.1:4321/embed/",
            url_only=True,
        )
        _cmd_embed(args, _mock_client(handler))
        out = capsys.readouterr().out.strip()
        # trailing slash in base is normalized
        assert out == "http://127.0.0.1:4321/embed/10.ronzz/abc"

    def test_embed_resolves_snippet(self, capsys: pytest.CaptureFixture) -> None:
        """embed fetches the snippet record for the title."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/snippet/10.ronzz/abc123"
            return httpx.Response(200, json=SNIPPET_RESPONSE)

        args = _make_args(
            doi="10.ronzz/abc123",
            width="640",
            height="240",
            base=DEFAULT_EMBED_BASE,
            url_only=False,
        )
        _cmd_embed(args, _mock_client(handler))
        out = capsys.readouterr().out.strip()
        assert "Hamlet soliloquy" in out


# ── assign ─────────────────────────────────────────────────────────────────


class TestAssign:
    def test_assign_sends_fields(self, capsys: pytest.CaptureFixture) -> None:
        """assign sends content_kind/content + optional fields."""

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            body = json.loads(request.content)
            assert body["content_kind"] == "text"
            assert body["content"] == "To be or not to be"
            assert body["source_doi"] == "10.ronzz/book123"
            assert body["page_start"] == "Act 3"
            return httpx.Response(201, json=SNIPPET_RESPONSE)

        args = _make_args(
            content_kind="text",
            content="To be or not to be",
            title="Hamlet soliloquy",
            language="",
            source_doi="book123",
            page_start="Act 3",
            page_end="",
        )
        _cmd_assign(args, _mock_client(handler))
        out = capsys.readouterr().out
        assert "Snippet assigned: 10.ronzz/abc123def456" in out


# ── resolve ────────────────────────────────────────────────────────────────


class TestResolve:
    def test_resolve_prints_content(self, capsys: pytest.CaptureFixture) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=SNIPPET_RESPONSE)

        args = _make_args(doi="10.ronzz/abc123")
        _cmd_resolve(args, _mock_client(handler))
        out = capsys.readouterr().out
        assert "Snippet:  10.ronzz/abc123def456" in out
        assert "To be, or not to be" in out
        assert "Source:     10.ronzz/book123" in out
