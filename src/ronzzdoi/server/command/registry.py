"""Command registry — decorators, dispatch, and tree building.

Follows lighterbird's pattern: handlers are registered via the ``@command``
decorator (or explicitly via ``register_module``).  The dispatch function
walks a prefix tree to find the matching handler.

Usage::

    @command("auth.api_key.list")
    def auth_api_key_list(_flags: dict[str, str]) -> dict:
        return {"type": "list", "title": "API Keys", "data": [...]}
"""

from __future__ import annotations

import functools
from typing import Any, Callable

# ── In-memory registry ──────────────────────────────────────────────────

_handlers: dict[str, Callable[[dict[str, str]], dict[str, Any]]] = {}
"""Maps dot-separated command paths (e.g. ``"auth.api_key.list"``) to handler functions."""

_descriptions: dict[str, str] = {}
"""Maps dot-separated command paths to human-readable descriptions."""


# ── Decorator ────────────────────────────────────────────────────────────


def command(
    path: str,
    *,
    description: str = "",
) -> Callable:
    """Register a command handler.

    Args:
        path: Dot-separated command path, e.g. ``"auth.api_key.list"``.
        description: Human-readable description for the command tree.

    Usage::

        @command("auth.api_key.list", description="List all API keys")
        def handler(flags):
            ...
    """

    def decorator(func: Callable) -> Callable:
        _handlers[path] = func
        if description:
            _descriptions[path] = description
        _invalidate_cache()

        @functools.wraps(func)
        def wrapper(flags: dict[str, str]) -> dict[str, Any]:
            return func(flags)

        return wrapper

    return decorator


# ── Module registration ─────────────────────────────────────────────────


def register_module(
    module_handlers: dict[str, tuple[Callable, str]],
) -> None:
    """Register multiple handlers from a module.

    Args:
        module_handlers: Mapping of ``path -> (handler_func, description)``.

    This is an alternative to the ``@command`` decorator for modules that
    prefer explicit registration.
    """
    for path, (func, desc) in module_handlers.items():
        _handlers[path] = func
        if desc:
            _descriptions[path] = desc
    _invalidate_cache()


# ── Dispatch ────────────────────────────────────────────────────────────


class CommandNotFoundError(ValueError):
    """Raised when no handler matches the given command path."""


class CommandAmbiguousError(ValueError):
    """Raised when the command prefix matches multiple possible commands."""


def dispatch(
    tokens: list[str],
    flags: dict[str, str],
) -> dict[str, Any]:
    """Dispatch a command to its registered handler.

    Args:
        tokens: Command tokens, e.g. ``["auth", "api_key", "list"]``.
        flags: Flag arguments parsed from the command line.

    Returns:
        A dict with ``type``, ``title``, ``data`` — the structured response
        that the frontend renders as a tab.

    Raises:
        CommandNotFoundError: If no handler matches the path.
        CommandAmbiguousError: If the prefix matches multiple commands
            (e.g. user typed ``!auth api_key`` without a subcommand).
    """
    if not tokens:
        raise CommandNotFoundError("No command tokens provided")

    # Build candidate paths: try the full path first, then walk parents
    candidate = ".".join(tokens)
    handler = _handlers.get(candidate)

    if handler is not None:
        return handler(flags)

    # Partial match: find all commands that start with the given prefix
    prefix = candidate + "."
    matches = {p: _descriptions.get(p, "") for p in _handlers if p.startswith(prefix)}

    if not matches:
        raise CommandNotFoundError(
            f"Unknown command: !{' '.join(tokens)}. "
            f"Type !help to see available commands."
        )

    if len(matches) == 1:
        # Auto-complete to the single match
        single_path = next(iter(matches))
        handler = _handlers[single_path]
        return handler(flags)

    # Multiple matches — show available subcommands
    raise CommandAmbiguousError(
        f"Ambiguous command: !{' '.join(tokens)}. "
        f"Available subcommands: {', '.join(sorted(matches.keys()))}. "
        f"Try one of: {', '.join('!' + p for p in sorted(matches.keys()))}",
    )


# ── Command tree ────────────────────────────────────────────────────────


def _build_tree() -> list[dict[str, Any]]:
    """Build a nested command tree from the registered handlers.

    Returns a list of dicts with ``name``, ``description``, and optionally
    ``children``.  This is served via ``GET /api/v1/command/tree`` for the
    frontend's autocomplete engine.
    """
    # Split all paths into parts and build a nested dict
    root: dict[str, dict[str, Any]] = {}

    for path, desc in _descriptions.items():
        parts = path.split(".")
        current = root
        for i, part in enumerate(parts):
            is_leaf = i == len(parts) - 1
            if part not in current:
                current[part] = {
                    "name": part,
                    "description": desc if is_leaf else "",
                    "children": {} if not is_leaf else None,
                }
            elif not is_leaf and current[part].get("children") is None:
                current[part]["children"] = {}
            elif is_leaf:
                current[part]["description"] = desc
            current = current[part].get("children") if not is_leaf else {}

    # Convert nested dict to sorted list-of-dicts
    def _node_to_dict(node: dict) -> dict:
        result: dict[str, Any] = {
            "name": node["name"],
            "description": node["description"],
        }
        if node.get("children"):
            result["children"] = [
                _node_to_dict(n)
                for n in sorted(node["children"].values(), key=lambda x: x["name"])
            ]
        return result

    return [
        _node_to_dict(n)
        for n in sorted(root.values(), key=lambda x: x["name"])
    ]


# Cached tree — invalidate on new registration
_tree_cache: list[dict[str, Any]] | None = None


def get_command_tree() -> list[dict[str, Any]]:
    """Return the cached command tree, rebuilding if stale."""
    global _tree_cache
    if _tree_cache is None:
        _tree_cache = _build_tree()
    return _tree_cache


# ── Invalidation ────────────────────────────────────────────────────────


def _invalidate_cache() -> None:
    """Clear the tree cache so it's rebuilt on next access."""
    global _tree_cache
    _tree_cache = None
