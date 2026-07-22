"""Tests for CLI citation subcommands.

All tests use ``httpx.MockTransport`` — no real server needed.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from ronzzdoi.cli.citation import _cmd_show, _cmd_styles
from ronzzdoi.cli.client import RonzzdoiClient


def _make_args(**overrides: Any) -> Any:
    defaults = {"json_output": False}
    defaults.update(overrides)
    return type("Args", (), defaults)()


def _mock_client(handler) -> RonzzdoiClient:
    transport = httpx.MockTransport(handler)
    return RonzzdoiClient(api_key="test-key", client=httpx.Client(transport=transport))


# ── show ───────────────────────────────────────────────────────────────────


def test_citation_show(capsys: pytest.CaptureFixture) -> None:
    """citation show returns formatted text."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "style=apa" in str(request.url)
        return httpx.Response(200, json={
            "doi": "10.ronzz/abc",
            "style": "apa",
            "citation": "Doe, J. (2026). *Example Title*. Publisher.",
        })

    client = _mock_client(handler)
    args = _make_args(doi="10.ronzz/abc", style="apa")
    _cmd_show(args, client)
    captured = capsys.readouterr()
    assert "Doe, J." in captured.out
    assert "Example Title" in captured.out


def test_citation_show_style_param(capsys: pytest.CaptureFixture) -> None:
    """citation show passes style parameter."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "style=vancouver" in str(request.url)
        return httpx.Response(200, json={
            "doi": "10.ronzz/abc",
            "style": "vancouver",
            "citation": "1. Doe J. Title. Publisher; 2026.",
        })

    client = _mock_client(handler)
    args = _make_args(doi="10.ronzz/abc", style="vancouver")
    _cmd_show(args, client)
    captured = capsys.readouterr()
    assert "Doe J." in captured.out


def test_citation_show_json(capsys: pytest.CaptureFixture) -> None:
    """citation show --json outputs raw JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"doi": "10.ronzz/abc", "style": "apa", "citation": "..."})

    client = _mock_client(handler)
    args = _make_args(doi="10.ronzz/abc", style="apa", json_output=True)
    _cmd_show(args, client)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["doi"] == "10.ronzz/abc"


# ── styles ─────────────────────────────────────────────────────────────────


def test_citation_styles(capsys: pytest.CaptureFixture) -> None:
    """citation styles returns list of styles."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "style" not in str(request.url)
        return httpx.Response(200, json={
            "doi": "10.ronzz/abc",
            "styles": ["apa", "vancouver", "mla", "chicago", "bibtex"],
        })

    client = _mock_client(handler)
    args = _make_args(doi="10.ronzz/abc")
    _cmd_styles(args, client)
    captured = capsys.readouterr()
    assert "apa" in captured.out
    assert "vancouver" in captured.out
    assert "bibtex" in captured.out


def test_citation_styles_json(capsys: pytest.CaptureFixture) -> None:
    """citation styles --json outputs raw JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"doi": "x", "styles": ["apa"]})

    client = _mock_client(handler)
    args = _make_args(doi="x", json_output=True)
    _cmd_styles(args, client)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["styles"] == ["apa"]
