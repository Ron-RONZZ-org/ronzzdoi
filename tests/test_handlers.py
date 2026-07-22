"""Tests for the command handler infrastructure.

Tests ``check_permission()`` in isolation (no HTTP layer, no database).
"""

from __future__ import annotations

import pytest

from ronzzdoi.server.command.handlers import check_permission


# ── Fixtures ─────────────────────────────────────────────────────────────

_MOCK_ADMIN = {"id": "admin-001", "api_key_permission": "admin"}
_MOCK_EDIT = {"id": "editor-001", "api_key_permission": "edit"}
_MOCK_READONLY = {"id": "reader-001", "api_key_permission": "read_only"}


# ── Tests: check_permission ──────────────────────────────────────────────


class TestCheckPermission:
    """``check_permission()`` validates user permission levels correctly."""

    def test_admin_allows_admin_action(self) -> None:
        """Admin can perform admin-level actions."""
        assert check_permission(_MOCK_ADMIN, "admin") is None

    def test_admin_allows_edit_action(self) -> None:
        """Admin can perform edit-level actions."""
        assert check_permission(_MOCK_ADMIN, "edit") is None

    def test_admin_allows_readonly_action(self) -> None:
        """Admin can perform read-only actions."""
        assert check_permission(_MOCK_ADMIN, "read_only") is None

    def test_edit_denies_admin_action(self) -> None:
        """Editor cannot perform admin-level actions — returns error."""
        result = check_permission(_MOCK_EDIT, "admin")
        assert result is not None
        assert result["type"] == "error"
        assert "Insufficient permissions" in result["data"]["message"]

    def test_edit_allows_edit_action(self) -> None:
        """Editor can perform edit-level actions."""
        assert check_permission(_MOCK_EDIT, "edit") is None

    def test_edit_allows_readonly_action(self) -> None:
        """Editor can perform read-only actions."""
        assert check_permission(_MOCK_EDIT, "read_only") is None

    def test_readonly_denies_admin_action(self) -> None:
        """Read-only user cannot perform admin actions."""
        result = check_permission(_MOCK_READONLY, "admin")
        assert result is not None
        assert "Insufficient permissions" in result["data"]["message"]

    def test_readonly_denies_edit_action(self) -> None:
        """Read-only user cannot perform edit actions."""
        result = check_permission(_MOCK_READONLY, "edit")
        assert result is not None
        assert "Insufficient permissions" in result["data"]["message"]

    def test_readonly_allows_readonly_action(self) -> None:
        """Read-only user can perform read-only actions."""
        assert check_permission(_MOCK_READONLY, "read_only") is None

    # ── Edge cases ─────────────────────────────────────────────────────

    def test_none_user_returns_auth_required(self) -> None:
        """No user → Authentication Required error."""
        result = check_permission(None, "read_only")
        assert result is not None
        assert result["type"] == "error"
        assert result["title"] == "Authentication Required"

    def test_user_missing_permission_key_returns_auth_required(self) -> None:
        """User without api_key_permission → Authentication Required."""
        result = check_permission({"id": "no-perm"}, "read_only")
        assert result is not None
        assert result["type"] == "error"
        assert "API key required" in result["data"]["message"]

    def test_unknown_min_permission_uses_default_zero(self) -> None:
        """Unknown min_permission defaults to 0, which everyone passes."""
        assert check_permission(_MOCK_READONLY, "unknown_perm") is None

    def test_unknown_user_permission_treated_as_lowest(self) -> None:
        """Unknown user permission level defaults to -1 → denied for anything above."""
        user = {"id": "test", "api_key_permission": "superadmin"}
        result = check_permission(user, "read_only")
        assert result is not None
        assert "Insufficient permissions" in result["data"]["message"]

    def test_error_response_structure(self) -> None:
        """Error response has the expected shape for command display."""
        result = check_permission(_MOCK_READONLY, "admin")
        assert isinstance(result, dict)
        assert result["type"] == "error"
        assert "title" in result
        assert "data" in result
        assert "message" in result["data"]

    def test_success_returns_none(self) -> None:
        """Successful check returns None (not a dict)."""
        assert check_permission(_MOCK_ADMIN, "admin") is None
