"""Citation subcommands for the ronzzdoi CLI.

Handles ``ronzzdoi citation show|styles``.
"""

from __future__ import annotations

import argparse
import json

from ronzzdoi.cli.client import RonzzdoiClient


def register_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``citation`` subcommand tree."""
    citation_parser = subparsers.add_parser(
        "citation",
        help="Manage citations",
        description="Show citations and list available styles. Requires permission: read_only.",
    )
    citation_sub = citation_parser.add_subparsers(dest="citation_command", required=True)

    # ── citation show ──────────────────────────────────────────────────────
    show_parser = citation_sub.add_parser(
        "show",
        help="Show a formatted citation",
        description="Format a citation for the given DOI. Requires permission: read_only.",
    )
    show_parser.add_argument("doi", help="DOI to cite (prefix optional)")
    show_parser.add_argument(
        "--style",
        default="apa",
        choices=["apa", "vancouver", "mla", "chicago", "bibtex", "json"],
        help="Citation style (default: apa)",
    )
    show_parser.set_defaults(func=_cmd_show)

    # ── citation styles ────────────────────────────────────────────────────
    styles_parser = citation_sub.add_parser(
        "styles",
        help="List available citation styles",
        description="List all available citation styles for a DOI. Requires permission: read_only.",
    )
    styles_parser.add_argument("doi", help="DOI to check styles for (prefix optional)")
    styles_parser.set_defaults(func=_cmd_styles)


# ── Command implementations ────────────────────────────────────────────────


def _cmd_show(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``citation show``."""
    result = client.get("/api/v1/citation", params={"doi": args.doi, "style": args.style})

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    print(result.get("citation", "(no citation text)"))


def _cmd_styles(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``citation styles``."""
    result = client.get("/api/v1/citation", params={"doi": args.doi})
    styles = result.get("styles", [])

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    if not styles:
        print(f"No styles available for DOI '{args.doi}'.")
        return

    print(f"Available styles for {result.get('doi', args.doi)}:")
    for style in styles:
        print(f"  - {style}")
