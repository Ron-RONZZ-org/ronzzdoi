"""Search subcommand for the ronzzdoi CLI.

Handles ``ronzzdoi search``.
"""

from __future__ import annotations

import argparse
import json

from ronzzdoi.cli.client import RonzzdoiClient


def register_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``search`` subcommand."""
    search_parser = subparsers.add_parser(
        "search",
        help="Search across DOI metadata",
        description="Full-text or semantic search across DOI records. Requires permission: read_only.",
    )
    search_parser.add_argument("query", help="Search query string")
    search_parser.add_argument(
        "--mode",
        choices=["fts", "semantic"],
        default="fts",
        help="Search mode: fts (FTS5 full-text) or semantic (vector search). Default: fts",
    )
    search_parser.set_defaults(func=_cmd_search)


def _cmd_search(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``search``."""
    result = client.get("/api/v1/search", params={"q": args.query, "mode": args.mode})
    items = result.get("items", [])

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    if not items:
        print(f"No results for '{args.query}'.")
        return

    print(f"Results for '{args.query}' (mode: {result.get('mode', args.mode)}):")
    print()
    for i, item in enumerate(items, 1):
        print(f"{i}. {item.get('title', '(no title)')}")
        print(f"   DOI:  {item.get('doi', '?')}")
        print(f"   URL:  {item.get('target_url', '(none)')}")
        print(f"   Type: {item.get('doi_type', '?')}")
        print()
    print(f"Total: {result.get('total', len(items))}")
