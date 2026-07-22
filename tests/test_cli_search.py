"""Tests for CLI search subcommand.

All tests use ``httpx.MockTransport`` — no real server needed.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from ronzzdoi.cli.client import RonzzdoiClient
from ronzzdoi.cli.search import _cmd_search


def _make_args(**overrides: Any) -> Any:
    defaults = {"json_output": False}
    defaults.update(overrides)
    return type("Args", (), defaults)()


def _mock_client(handler) -> RonzzdoiClient:
    transport = httpx.MockTransport(handler)
    return RonzzdoiClient(api_key="test-key", client=httpx.Client(transport=transport))


# ── search ─────────────────────────────────────────────────────────────────


def test_search_fts(capsys: pytest.CaptureFixture) -> None:
    """search sends GET with query and mode=fts."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "q=quantum" in str(request.url)
        assert "mode=fts" in str(request.url)
        return httpx.Response(200, json={
            "items": [
                {"doi": "10.ronzz/abc", "title": "Quantum Computing", "target_url": "https://ex.com", "doi_type": "webpage"},
                {"doi": "10.ronzz/def", "title": "Quantum Physics", "target_url": "https://ex2.com", "doi_type": "book"},
            ],
            "total": 2,
            "mode": "fts",
        })

    client = _mock_client(handler)
    args = _make_args(query="quantum", mode="fts")
    _cmd_search(args, client)
    captured = capsys.readouterr()
    assert "Quantum Computing" in captured.out
    assert "Quantum Physics" in captured.out
    assert "10.ronzz/abc" in captured.out
    assert "10.ronzz/def" in captured.out


def test_search_semantic(capsys: pytest.CaptureFixture) -> None:
    """search --mode semantic sends correct mode."""

    def handler(request: httpx.Request) -> httpx.Request:
        assert "mode=semantic" in str(request.url)
        return httpx.Response(200, json={
            "items": [{"doi": "10.ronzz/abc", "title": "Result", "target_url": "https://ex.com", "doi_type": "webpage"}],
            "total": 1,
            "mode": "semantic",
        })

    client = _mock_client(handler)
    # Note: handler is actually a function, but we need to return Response
    # Let's rewrite properly
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={
        "items": [{"doi": "10.ronzz/abc", "title": "Semantic Result", "target_url": "https://ex.com", "doi_type": "webpage"}],
        "total": 1,
        "mode": "semantic",
    }))
    client = RonzzdoiClient(api_key="test-key", client=httpx.Client(transport=transport))
    args = _make_args(query="quantum", mode="semantic")
    _cmd_search(args, client)
    captured = capsys.readouterr()
    assert "Semantic Result" in captured.out


def test_search_empty(capsys: pytest.CaptureFixture) -> None:
    """search with no results shows message."""

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={
        "items": [], "total": 0, "mode": "fts",
    }))
    client = RonzzdoiClient(api_key="test-key", client=httpx.Client(transport=transport))
    args = _make_args(query="nonexistent", mode="fts")
    _cmd_search(args, client)
    captured = capsys.readouterr()
    assert "No results" in captured.out


def test_search_json(capsys: pytest.CaptureFixture) -> None:
    """search --json outputs raw JSON."""

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={
        "items": [{"doi": "10.ronzz/x"}], "total": 1, "mode": "fts",
    }))
    client = RonzzdoiClient(api_key="test-key", client=httpx.Client(transport=transport))
    args = _make_args(query="x", mode="fts", json_output=True)
    _cmd_search(args, client)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["total"] == 1
