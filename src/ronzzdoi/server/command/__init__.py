"""Command dispatch module — maps ``!xxx`` tokens to handler functions.

Following lighterbird's pattern: user types ``!auth api_key update ...``
in the homepage input box, the frontend sends tokens to
``POST /api/v1/command``, and this module dispatches to the registered
handler.

Usage::

    from ronzzdoi.server.command import get_command_tree, dispatch

    result = dispatch(["auth", "api_key", "list"], {})
    # → {"type": "list", "title": "API Keys", "data": [...]}
"""

from __future__ import annotations

from ronzzdoi.server.command.registry import (
    command,
    dispatch,
    get_command_tree,
    register_module,
)

# Import handlers to register them
from ronzzdoi.server.command import handlers  # noqa: F401

__all__ = [
    "command",
    "dispatch",
    "get_command_tree",
    "register_module",
]
