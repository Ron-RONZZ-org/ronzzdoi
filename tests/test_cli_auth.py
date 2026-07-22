"""Tests for CLI auth subcommands.

All tests use ``httpx.MockTransport`` — no real server needed.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from ronzzdoi.cli.auth import _cmd_create, _cmd_list, _cmd_revoke, _cmd_update
from ronzzdoi.cli.client import RonzzdoiClient


def _make_args(**overrides: Any) -> Any:
    """Create a simple namespace for testing command handlers."""
    defaults = {
        "json_output": False,
    }
    defaults.update(overrides)
    return type("Args", (), defaults)()


def _mock_client(handler) -> RonzzdoiClient:
    """Create a RonzzdoiClient with the given MockTransport handler."""
    transport = httpx.MockTransport(handler)
    return RonzzdoiClient(api_key="test-admin-key", client=httpx.Client(transport=transport))


# ── create ─────────────────────────────────────────────────────────────────


def test_create_api_key(capsys: pytest.CaptureFixture) -> None:
    """auth api_key create sends POST with name and permission."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["name"] == "my-key"
        assert body["permission"] == "edit"
        return httpx.Response(201, json={
            "id": "ak_new_001",
            "name": "my-key",
            "key": "la_raw_secret_key_here",
            "prefix": "la_",
            "permission": "edit",
            "created_at": "2026-01-01T00:00:00+00:00",
        })

    client = _mock_client(handler)
    args = _make_args(name="my-key", permission="edit", expires_at=None)
    _cmd_create(args, client)
    captured = capsys.readouterr()
    assert "my-key" in captured.out
    assert "la_raw_secret_key_here" in captured.out
    assert "edit" in captured.out
    assert "⚠" in captured.out


def test_create_api_key_json(capsys: pytest.CaptureFixture) -> None:
    """auth api_key create with --json outputs raw JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "ak_001", "name": "json-key"})

    client = _mock_client(handler)
    args = _make_args(name="json-key", permission="read_only", expires_at=None, json_output=True)
    _cmd_create(args, client)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["id"] == "ak_001"


# ── list ───────────────────────────────────────────────────────────────────


def test_list_api_keys(capsys: pytest.CaptureFixture) -> None:
    """auth api_key list returns formatted table."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[
            {"id": "ak_001", "name": "key-1", "permission": "admin", "prefix": "la_",
             "expires_at": None, "created_at": "2026-01-01T00:00:00+00:00"},
            {"id": "ak_002", "name": "key-2", "permission": "read_only", "prefix": "la_",
             "expires_at": "2027-01-01T00:00:00+00:00", "created_at": "2026-06-01T00:00:00+00:00"},
        ])

    client = _mock_client(handler)
    args = _make_args(include_expired=False)
    _cmd_list(args, client)
    captured = capsys.readouterr()
    assert "ak_001" in captured.out
    assert "key-1" in captured.out
    assert "admin" in captured.out
    assert "ak_002" in captured.out
    assert "key-2" in captured.out


def test_list_api_keys_empty(capsys: pytest.CaptureFixture) -> None:
    """auth api_key list with no keys shows message."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _mock_client(handler)
    args = _make_args(include_expired=False)
    _cmd_list(args, client)
    captured = capsys.readouterr()
    assert "No API keys found" in captured.out


def test_list_api_keys_json(capsys: pytest.CaptureFixture) -> None:
    """auth api_key list --json outputs raw JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": "ak_001"}])

    client = _mock_client(handler)
    args = _make_args(include_expired=False, json_output=True)
    _cmd_list(args, client)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data[0]["id"] == "ak_001"


# ── update ─────────────────────────────────────────────────────────────────


def test_update_api_key(capsys: pytest.CaptureFixture) -> None:
    """auth api_key update sends PATCH with updated fields."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        body = json.loads(request.content)
        assert body["name"] == "renamed"
        return httpx.Response(200, json={
            "id": "ak_001",
            "name": "renamed",
            "permission": "edit",
        })

    client = _mock_client(handler)
    args = _make_args(key_id="ak_001", name="renamed", permission=None, expires_at=None)
    _cmd_update(args, client)
    captured = capsys.readouterr()
    assert "renamed" in captured.out
    assert "ak_001" in captured.out


def test_update_api_key_permission(capsys: pytest.CaptureFixture) -> None:
    """auth api_key update changes permission."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["permission"] == "admin"
        return httpx.Response(200, json={
            "id": "ak_001", "name": "test", "permission": "admin",
        })

    client = _mock_client(handler)
    args = _make_args(key_id="ak_001", name=None, permission="admin", expires_at=None)
    _cmd_update(args, client)
    captured = capsys.readouterr()
    assert "admin" in captured.out


# ── revoke ─────────────────────────────────────────────────────────────────


def test_revoke_api_key(capsys: pytest.CaptureFixture) -> None:
    """auth api_key revoke sends DELETE."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(204)

    client = _mock_client(handler)
    args = _make_args(key_id="ak_001")
    _cmd_revoke(args, client)
    captured = capsys.readouterr()
    assert "ak_001" in captured.out
    assert "revoked" in captured.out
