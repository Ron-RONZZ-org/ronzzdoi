"""Tests for the command dispatch infrastructure.

Tests the registry, dispatch, and tree-building logic in isolation
(no HTTP layer, no database).
"""

from __future__ import annotations

import pytest

from ronzzdoi.server.command.models import CommandRequest
from ronzzdoi.server.command.registry import (
    CommandAmbiguousError,
    CommandNotFoundError,
    _handlers,
    _descriptions,
    _tree_cache,
    command,
    dispatch,
    get_command_tree,
    register_module,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _clean_registry() -> None:
    """Clear all registered handlers (for test isolation)."""
    _handlers.clear()
    _descriptions.clear()
    global _tree_cache
    _tree_cache = None


_MOCK_USER = {"id": "test-user-001", "role": "user", "auth_method": "api_key"}


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Reset the registry before and after each test."""
    _clean_registry()
    yield
    _clean_registry()


# ── Test: @command decorator ────────────────────────────────────────────


class TestCommandDecorator:
    """``@command()`` decorator registers handlers correctly."""

    def test_register_single(self) -> None:
        """A single @command registers one handler."""

        @command("test.hello", description="Say hello")
        def _handler(
            flags: dict[str, str],
            positionals: list[str],
            user: dict | None = None,
        ) -> dict:
            return {"type": "success", "title": "Hello", "data": {"msg": "world"}}

        assert "test.hello" in _handlers
        assert _descriptions.get("test.hello") == "Say hello"

    def test_register_multiple(self) -> None:
        """Multiple @command decorators register independently."""

        @command("a.b", description="AB")
        def _ab(flags, positionals, user=None):  # type: ignore
            return {"type": "detail", "title": "AB", "data": {}}

        @command("a.c", description="AC")
        def _ac(flags, positionals, user=None):  # type: ignore
            return {"type": "detail", "title": "AC", "data": {}}

        assert "a.b" in _handlers
        assert "a.c" in _handlers
        assert _descriptions.get("a.b") == "AB"
        assert _descriptions.get("a.c") == "AC"

    def test_no_description(self) -> None:
        """@command without description does not add to _descriptions."""

        @command("test.noop")
        def _noop(flags, positionals, user=None):  # type: ignore
            return {"type": "success", "title": "OK", "data": None}

        assert "test.noop" in _handlers
        assert "test.noop" not in _descriptions


# ── Test: register_module ───────────────────────────────────────────────


class TestRegisterModule:
    """``register_module()`` registers handlers from a dict."""

    def test_basic(self) -> None:
        register_module({
            "mod.a": (lambda f, p, u=None: {"type": "detail", "title": "A", "data": {}}, "Module A"),
            "mod.b": (lambda f, p, u=None: {"type": "detail", "title": "B", "data": {}}, "Module B"),
        })
        assert "mod.a" in _handlers
        assert "mod.b" in _handlers
        assert _descriptions.get("mod.a") == "Module A"


# ── Test: dispatch ──────────────────────────────────────────────────────


class TestDispatch:
    """``dispatch()`` routes commands to the correct handler and passes user."""

    def test_exact_match(self) -> None:
        @command("auth.api_key.list", description="List keys")
        def _list(flags, positionals, user=None):  # type: ignore
            return {"type": "list", "title": "Keys", "data": [1, 2, 3]}

        result = dispatch(["auth", "api_key", "list"], {}, _MOCK_USER)
        assert result["type"] == "list"
        assert result["data"] == [1, 2, 3]

    def test_passes_positionals(self) -> None:
        """Positional tokens after the command path are passed to the handler."""

        @command("doi.resolve", description="Resolve a DOI")
        def _resolve(flags, positionals, user=None):  # type: ignore
            return {"type": "detail", "title": "Resolved", "data": {"doi": positionals[0]}}

        result = dispatch(["doi", "resolve", "10.ronzz/abc123"], {}, _MOCK_USER)
        assert result["data"]["doi"] == "10.ronzz/abc123"

    def test_passes_multiple_positionals(self) -> None:
        """Multiple positional args are passed correctly."""

        @command("doi.merge", description="Merge DOIs")
        def _merge(flags, positionals, user=None):  # type: ignore
            return {
                "type": "detail",
                "title": "Merged",
                "data": {"source": positionals[0], "target": positionals[1]},
            }

        result = dispatch(["doi", "merge", "10.ronzz/src", "10.ronzz/tgt"], {}, _MOCK_USER)
        assert result["data"]["source"] == "10.ronzz/src"
        assert result["data"]["target"] == "10.ronzz/tgt"

    def test_empty_positionals_for_no_args(self) -> None:
        """Handler receives empty list when no positional args."""

        @command("doi.list", description="List DOIs")
        def _list(flags, positionals, user=None):  # type: ignore
            return {"type": "list", "title": "DOIs", "data": {"pos_len": len(positionals)}}

        result = dispatch(["doi", "list"], {}, _MOCK_USER)
        assert result["data"]["pos_len"] == 0

    def test_passes_user_context(self) -> None:
        """Handler receives the authenticated user dict."""

        @command("test.whoami", description="Who am I")
        def _whoami(flags, positionals, user=None):  # type: ignore
            return {"type": "detail", "title": "User", "data": {"id": user["id"] if user else None}}

        result = dispatch(["test", "whoami"], {}, _MOCK_USER)
        assert result["data"]["id"] == "test-user-001"

        # Without user
        result = dispatch(["test", "whoami"], {}, None)
        assert result["data"]["id"] is None

    def test_passes_flags(self) -> None:
        @command("test.flags", description="Flag test")
        def _flags(flags, positionals, user=None):  # type: ignore
            return {"type": "detail", "title": "Flags", "data": flags}

        result = dispatch(
            ["test", "flags"], {"include-expired": "", "limit": "10"}, _MOCK_USER,
        )
        assert result["data"] == {"include-expired": "", "limit": "10"}

    def test_not_found(self) -> None:
        """Unregistered command raises CommandNotFoundError."""
        with pytest.raises(CommandNotFoundError, match="Unknown command"):
            dispatch(["does", "not", "exist"], {}, _MOCK_USER)

    def test_not_found_message(self) -> None:
        """Error message suggests !help."""
        with pytest.raises(CommandNotFoundError, match="!help"):
            dispatch(["unknown"], {}, _MOCK_USER)

    def test_ambiguous(self) -> None:
        """Partial match with multiple subcommands raises CommandAmbiguousError."""

        @command("auth.api_key.list", description="List")
        def _list(flags, positionals, user=None):  # type: ignore
            return {"type": "list", "title": "Keys", "data": []}

        @command("auth.api_key.create", description="Create")
        def _create(flags, positionals, user=None):  # type: ignore
            return {"type": "form", "title": "Create Key", "data": {}}

        with pytest.raises(CommandAmbiguousError) as exc_info:
            dispatch(["auth", "api_key"], {}, _MOCK_USER)
        msg = str(exc_info.value)
        assert "auth.api_key.list" in msg
        assert "auth.api_key.create" in msg

    def test_no_tokens(self) -> None:
        """Empty tokens raises CommandNotFoundError."""
        with pytest.raises(CommandNotFoundError, match="No command tokens"):
            dispatch([], {}, _MOCK_USER)


# ── Test: get_command_tree ──────────────────────────────────────────────


class TestCommandTree:
    """``get_command_tree()`` builds a nested tree from registered handlers."""

    def test_empty(self) -> None:
        """No handlers → empty tree."""
        assert get_command_tree() == []

    def test_single_handler(self) -> None:
        @command("auth.api_key.list", description="List API keys")
        def _list(flags, positionals, user=None):  # type: ignore
            pass

        tree = get_command_tree()
        assert len(tree) == 1
        assert tree[0]["name"] == "auth"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["name"] == "api_key"
        assert len(tree[0]["children"][0]["children"]) == 1
        leaf = tree[0]["children"][0]["children"][0]
        assert leaf["name"] == "list"
        assert leaf["description"] == "List API keys"
        assert "children" not in leaf or leaf["children"] is None

    def test_multiple_groups(self) -> None:
        @command("auth.api_key.list", description="List keys")
        def _list(flags, positionals, user=None):  # type: ignore
            pass

        @command("doi.assign", description="Assign a DOI")
        def _assign(flags, positionals, user=None):  # type: ignore
            pass

        tree = get_command_tree()
        names = [n["name"] for n in tree]
        assert "auth" in names
        assert "doi" in names

    def test_cache(self) -> None:
        """Tree is cached and rebuilt on new registration."""
        @command("first.cmd", description="First")
        def _f(flags, positionals, user=None):  # type: ignore
            pass

        tree1 = get_command_tree()
        assert len(tree1) == 1

        @command("second.cmd", description="Second")
        def _s(flags, positionals, user=None):  # type: ignore
            pass

        tree2 = get_command_tree()
        assert len(tree2) == 2


# ── Test: CommandRequest model ──────────────────────────────────────────


class TestCommandRequest:
    """Pydantic model validation for command requests."""

    def test_minimal(self) -> None:
        req = CommandRequest(tokens=["auth", "list"])
        assert req.tokens == ["auth", "list"]
        assert req.flags == {}
        assert req.raw_input == ""

    def test_full(self) -> None:
        req = CommandRequest(
            tokens=["doi", "assign"],
            flags={"target_url": "https://example.com"},
            raw_input='!doi assign --target_url "https://example.com"',
        )
        assert req.tokens == ["doi", "assign"]
        assert req.flags == {"target_url": "https://example.com"}
        assert req.raw_input.startswith("!doi")
