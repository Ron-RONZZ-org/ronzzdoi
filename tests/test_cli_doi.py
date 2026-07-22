"""Tests for CLI doi subcommands.

All tests use ``httpx.MockTransport`` — no real server needed.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from ronzzdoi.cli.client import RonzzdoiClient
from ronzzdoi.cli.doi import (
    _cmd_assign,
    _cmd_delete,
    _cmd_list,
    _cmd_merge,
    _cmd_modify,
    _cmd_resolve,
    _normalize_doi,
)


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
    """Full DOI is not modified."""
    assert _normalize_doi("10.ronzz/abc123") == "10.ronzz/abc123"


def test_normalize_doi_suffix() -> None:
    """Suffix-only DOI gets prefixed."""
    assert _normalize_doi("abc123") == "10.ronzz/abc123"


def test_normalize_doi_country() -> None:
    """Country DOI with prefix is not modified."""
    assert _normalize_doi("10.ronzz/country/FR") == "10.ronzz/country/FR"


# ── assign ─────────────────────────────────────────────────────────────────


def test_assign_with_url(capsys: pytest.CaptureFixture) -> None:
    """doi assign sends POST with target_url."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["target_url"] == "https://example.com"
        assert body["doi_type"] == "webpage"
        assert body["title"] == "Example"
        return httpx.Response(201, json={
            "doi": "10.ronzz/new-uuid",
            "target_url": "https://example.com",
            "doi_type": "webpage",
            "title": "Example",
        })

    client = _mock_client(handler)
    args = _make_args(url="https://example.com", doi_type="webpage", title="Example")
    _cmd_assign(args, client)
    captured = capsys.readouterr()
    assert "10.ronzz/new-uuid" in captured.out
    assert "https://example.com" in captured.out
    assert "webpage" in captured.out


def test_assign_entity_doi(capsys: pytest.CaptureFixture) -> None:
    """doi assign without URL for entity DOIs."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "target_url" not in body
        return httpx.Response(201, json={
            "doi": "10.ronzz/person-uuid",
            "target_url": None,
            "doi_type": "person",
            "title": "John Doe",
        })

    client = _mock_client(handler)
    args = _make_args(url=None, doi_type="person", title="John Doe")
    _cmd_assign(args, client)
    captured = capsys.readouterr()
    assert "person-uuid" in captured.out


def test_assign_json(capsys: pytest.CaptureFixture) -> None:
    """doi assign --json outputs raw JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"doi": "10.ronzz/uuid", "target_url": "https://ex.com"})

    client = _mock_client(handler)
    args = _make_args(url="https://ex.com", doi_type="external", title="", json_output=True)
    _cmd_assign(args, client)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["doi"] == "10.ronzz/uuid"


# ── resolve ────────────────────────────────────────────────────────────────


def test_resolve(capsys: pytest.CaptureFixture) -> None:
    """doi resolve sends GET and shows metadata."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v1/doi/" in str(request.url)
        return httpx.Response(200, json={
            "doi": "10.ronzz/abc123",
            "target_url": "https://example.com",
            "title": "Example",
            "doi_type": "webpage",
            "status": "active",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "redirect_history": [],
        })

    client = _mock_client(handler)
    args = _make_args(doi="10.ronzz/abc123")
    _cmd_resolve(args, client)
    captured = capsys.readouterr()
    assert "10.ronzz/abc123" in captured.out
    assert "https://example.com" in captured.out
    assert "active" in captured.out


def test_resolve_with_redirect_history(capsys: pytest.CaptureFixture) -> None:
    """doi resolve shows redirect history."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "doi": "10.ronzz/abc",
            "target_url": "https://new.example.com",
            "title": "Test",
            "doi_type": "webpage",
            "status": "active",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "redirect_history": [
                {"old_url": "https://old.example.com", "note": "Moved", "created_at": "2026-03-01T00:00:00+00:00"},
            ],
        })

    client = _mock_client(handler)
    args = _make_args(doi="10.ronzz/abc")
    _cmd_resolve(args, client)
    captured = capsys.readouterr()
    assert "https://old.example.com" in captured.out
    assert "Moved" in captured.out
    assert "1 entries" in captured.out


def test_resolve_suffix(capsys: pytest.CaptureFixture) -> None:
    """doi resolve normalizes suffix DOI."""

    def handler(request: httpx.Request) -> httpx.Response:
        # The request path should contain the normalized DOI
        assert "10.ronzz/abc" in str(request.url)
        return httpx.Response(200, json={"doi": "10.ronzz/abc", "status": "active"})

    client = _mock_client(handler)
    args = _make_args(doi="abc")  # just suffix
    _cmd_resolve(args, client)
    captured = capsys.readouterr()
    assert "10.ronzz/abc" in captured.out


# ── modify ─────────────────────────────────────────────────────────────────


def test_modify_url(capsys: pytest.CaptureFixture) -> None:
    """doi modify sends PUT with new URL."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        body = json.loads(request.content)
        assert body["target_url"] == "https://new.example.com"
        return httpx.Response(200, json={
            "doi": "10.ronzz/abc",
            "target_url": "https://new.example.com",
            "title": "Test",
            "doi_type": "webpage",
        })

    client = _mock_client(handler)
    args = _make_args(doi="10.ronzz/abc", target_url="https://new.example.com",
                      title=None, doi_type=None, redirect_note="")
    _cmd_modify(args, client)
    captured = capsys.readouterr()
    assert "https://new.example.com" in captured.out


def test_modify_all_fields(capsys: pytest.CaptureFixture) -> None:
    """doi modify sends all fields."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["title"] == "New Title"
        assert body["doi_type"] == "book"
        assert body["redirect_note"] == "Moved to new server"
        return httpx.Response(200, json={
            "doi": "10.ronzz/abc", "title": "New Title", "doi_type": "book",
        })

    client = _mock_client(handler)
    args = _make_args(doi="10.ronzz/abc", target_url=None, title="New Title",
                      doi_type="book", redirect_note="Moved to new server")
    _cmd_modify(args, client)
    captured = capsys.readouterr()
    assert "New Title" in captured.out


# ── delete ─────────────────────────────────────────────────────────────────


def test_delete(capsys: pytest.CaptureFixture) -> None:
    """doi delete sends DELETE."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(204)

    client = _mock_client(handler)
    args = _make_args(doi="10.ronzz/abc123")
    _cmd_delete(args, client)
    captured = capsys.readouterr()
    assert "deleted" in captured.out


# ── list ───────────────────────────────────────────────────────────────────


def test_list_dois(capsys: pytest.CaptureFixture) -> None:
    """doi list returns formatted table."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "items": [
                {"doi": "10.ronzz/aaa", "doi_type": "webpage", "title": "Site A", "deleted_at": None},
                {"doi": "10.ronzz/bbb", "doi_type": "book", "title": "Book B", "deleted_at": "2026-06-01T00:00:00+00:00"},
            ],
            "total": 2,
        })

    client = _mock_client(handler)
    args = _make_args(doi_type="", include_deleted=False)
    _cmd_list(args, client)
    captured = capsys.readouterr()
    assert "10.ronzz/aaa" in captured.out
    assert "10.ronzz/bbb" in captured.out
    assert "active" in captured.out
    assert "tombstone" in captured.out


def test_list_dois_empty(capsys: pytest.CaptureFixture) -> None:
    """doi list with no results shows message."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [], "total": 0})

    client = _mock_client(handler)
    args = _make_args(doi_type="", include_deleted=False)
    _cmd_list(args, client)
    captured = capsys.readouterr()
    assert "No DOIs found" in captured.out


# ── merge ──────────────────────────────────────────────────────────────────


def test_merge_force(capsys: pytest.CaptureFixture) -> None:
    """doi merge --force sends POST without confirmation."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"doi": "10.ronzz/src", "status": "active"})
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["source_doi"] == "10.ronzz/src"
        return httpx.Response(200, json={"doi": "10.ronzz/tgt", "target_url": "https://tgt.com", "title": "Target", "doi_type": "webpage"})

    client = _mock_client(handler)
    args = _make_args(source_doi="10.ronzz/src", target_doi="10.ronzz/tgt",
                      preview=False, force=True)
    _cmd_merge(args, client)
    captured = capsys.readouterr()
    assert "Merge complete" in captured.out


def test_merge_preview(capsys: pytest.CaptureFixture) -> None:
    """doi merge --preview shows records without executing."""

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"doi": "10.ronzz/src" if "src" in str(request.url) else "10.ronzz/tgt", "status": "active"})

    client = _mock_client(handler)
    args = _make_args(source_doi="src", target_doi="tgt",
                      preview=True, force=False)
    _cmd_merge(args, client)
    captured = capsys.readouterr()
    assert "Preview" in captured.out
    assert call_count == 2  # Two GETs, no POST
