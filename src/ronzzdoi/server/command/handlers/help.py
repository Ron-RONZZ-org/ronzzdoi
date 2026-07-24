"""Command handler for ``!help``.

Shows available commands by listing the registry descriptions.
"""

from __future__ import annotations

from typing import Any

from ronzzdoi.server.command.registry import command, get_descriptions


@command("help", description="Show available commands")
def show_help(flags: dict[str, str], positionals: list[str], user: dict[str, Any] | None = None) -> dict[str, Any]:
    """!help [command]

    Returns the list of registered command definitions.
    If a search term is given, filter to matching commands.
    """
    descs = get_descriptions()

    # Build canonical paths from dot-separated keys
    lines = []
    for path, description in descs.items():
        canonical = "!" + path.replace(".", " ")
        if positionals:
            query = " ".join(positionals).lower()
            if query not in canonical.lower():
                continue
        lines.append({"name": canonical[1:], "description": description})

    return {
        "type": "help",
        "title": "Available Commands",
        "data": lines,
    }
