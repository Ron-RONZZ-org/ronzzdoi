"""Snippet subcommands for the ronzzdoi CLI.

Handles ``ronzzdoi snippet assign|resolve|modify|delete|embed``.

Snippets are embeddable content fragments (text quotations, code blocks,
KaTeX math).  ``--type`` selects the content kind, mirroring the GUI's
Text/Code/Math toggle.  ``embed`` generates the copy-paste HTML embed tag
(an ``<iframe>`` pointing at the public-web embed page).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from typing import Any

from ronzzdoi.cli.client import RonzzdoiClient
from ronzzdoi.snippet.constants import CONTENT_KINDS, SUGGESTED_LANGUAGES

DOI_PREFIX = "10.ronzz"

DEFAULT_EMBED_BASE = "https://doi.ronzz.org/embed"
"""Default base URL for the public-web embed page (env: RONZZDOI_EMBED_BASE)."""


def _normalize_doi(doi: str) -> str:
    """Prepend ``10.ronzz/`` if the user provided just a suffix."""
    if not doi.startswith("10."):
        return f"{DOI_PREFIX}/{doi}"
    return doi


def _print_snippet(record: dict[str, Any]) -> None:
    """Print a snippet record in a human-readable format."""
    print(f"Snippet:  {record.get('doi', '?')}")
    print(f"  Title:      {record.get('title', '')}")
    print(f"  Kind:       {record.get('content_kind', '?')}")
    if record.get("language"):
        print(f"  Language:   {record.get('language')}")
    if record.get("source_doi"):
        print(f"  Source:     {record.get('source_doi')}")
    if record.get("page_start") or record.get("page_end"):
        print(
            f"  Pages:      {record.get('page_start', '')}-{record.get('page_end', '')}"
        )
    print(f"  Status:     {record.get('status', '?')}")
    print(f"  Created:    {record.get('created_at', '?')}")
    print(f"  Updated:    {record.get('updated_at', '?')}")
    print("  Content:")
    for line in (record.get("content") or "").splitlines():
        print(f"    {line}")


def register_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``snippet`` subcommand tree."""
    snippet_parser = subparsers.add_parser(
        "snippet",
        help="Manage embeddable snippets",
        description="Assign, resolve, modify, and delete snippets "
        "(text quotations, code, KaTeX math).",
    )
    snippet_sub = snippet_parser.add_subparsers(dest="snippet_command", required=True)

    # ── snippet assign ──────────────────────────────────────────────────────
    assign_parser = snippet_sub.add_parser(
        "assign",
        help="Assign a new snippet",
        description="Assign a new snippet DOI. Requires permission: edit.",
    )
    assign_parser.add_argument(
        "--type",
        dest="content_kind",
        required=True,
        choices=CONTENT_KINDS,
        help="Content kind: text (quotation), code, or math (KaTeX)",
    )
    assign_parser.add_argument(
        "--content",
        required=True,
        help="The snippet content (quotation text, code, or KaTeX source)",
    )
    assign_parser.add_argument("--title", default="", help="Human-readable title")
    assign_parser.add_argument(
        "--language",
        default="",
        help=f"Code language hint (code only). Common: {', '.join(SUGGESTED_LANGUAGES[:8])}…",
    )
    assign_parser.add_argument(
        "--source-doi",
        default="",
        help="Optional source DOI the snippet quotes from (must exist)",
    )
    assign_parser.add_argument(
        "--page-start", default="", help="Source page start (text only)"
    )
    assign_parser.add_argument(
        "--page-end", default="", help="Source page end (text only)"
    )
    assign_parser.set_defaults(func=_cmd_assign)

    # ── snippet resolve ─────────────────────────────────────────────────────
    resolve_parser = snippet_sub.add_parser(
        "resolve",
        help="Resolve a snippet",
        description="Resolve a snippet DOI and print its content. Requires permission: read_only.",
    )
    resolve_parser.add_argument("doi", help="DOI to resolve (e.g. 10.ronzz/abc123)")
    resolve_parser.set_defaults(func=_cmd_resolve)

    # ── snippet modify ──────────────────────────────────────────────────────
    modify_parser = snippet_sub.add_parser(
        "modify",
        help="Modify a snippet",
        description="Update a snippet's content or attribution. Requires permission: edit.",
    )
    modify_parser.add_argument("doi", help="DOI to modify")
    modify_parser.add_argument(
        "--type", dest="content_kind", choices=CONTENT_KINDS, help="New content kind"
    )
    modify_parser.add_argument("--content", help="New content")
    modify_parser.add_argument("--title", help="New title")
    modify_parser.add_argument("--language", help="New language hint ('' clears)")
    modify_parser.add_argument("--source-doi", help="New source DOI ('' clears)")
    modify_parser.add_argument("--page-start", help="New page start")
    modify_parser.add_argument("--page-end", help="New page end")
    modify_parser.set_defaults(func=_cmd_modify)

    # ── snippet delete ──────────────────────────────────────────────────────
    delete_parser = snippet_sub.add_parser(
        "delete",
        help="Tombstone a snippet",
        description="Soft-delete (tombstone) a snippet. Requires permission: edit.",
    )
    delete_parser.add_argument("doi", help="DOI to delete")
    delete_parser.set_defaults(func=_cmd_delete)

    # ── snippet embed ───────────────────────────────────────────────────────
    embed_parser = snippet_sub.add_parser(
        "embed",
        help="Generate an HTML embed tag for a snippet",
        description="Print a copy-paste <iframe> embed tag for a snippet DOI. "
        "Requires permission: read_only.",
    )
    embed_parser.add_argument("doi", help="DOI to embed (e.g. 10.ronzz/abc123)")
    embed_parser.add_argument(
        "--width", default="640", help="iframe width in px (default: 640)"
    )
    embed_parser.add_argument(
        "--height", default="240", help="iframe height in px (default: 240)"
    )
    embed_parser.add_argument(
        "--url-only",
        action="store_true",
        help="Print only the embed URL (for JS-based embeds)",
    )
    embed_parser.add_argument(
        "--base",
        default=os.environ.get("RONZZDOI_EMBED_BASE", DEFAULT_EMBED_BASE),
        help="Embed base URL (default: %(default)s, env: RONZZDOI_EMBED_BASE)",
    )
    embed_parser.set_defaults(func=_cmd_embed)


# ── Command implementations ────────────────────────────────────────────────


def _cmd_assign(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``snippet assign``."""
    body: dict[str, Any] = {
        "content_kind": args.content_kind,
        "content": args.content,
        "title": args.title,
        "language": args.language,
        "page_start": args.page_start,
        "page_end": args.page_end,
    }
    if args.source_doi:
        body["source_doi"] = _normalize_doi(args.source_doi)

    result = client.post("/api/v1/snippet", json=body)

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    print(f"Snippet assigned: {result.get('doi', '?')}")
    print(f"  Title:   {result.get('title', '')}")
    print(f"  Kind:    {result.get('content_kind', '?')}")
    if result.get("language"):
        print(f"  Language: {result.get('language')}")
    if result.get("source_doi"):
        print(f"  Source:  {result.get('source_doi')}")
    print(f"  Content: {result.get('content', '')}")


def _cmd_resolve(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``snippet resolve``."""
    doi = _normalize_doi(args.doi)
    result = client.get(f"/api/v1/snippet/{doi}", params={"include_redirects": "true"})

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    _print_snippet(result)


def _cmd_modify(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``snippet modify``."""
    doi = _normalize_doi(args.doi)
    body: dict[str, Any] = {}
    if args.content_kind is not None:
        body["content_kind"] = args.content_kind
    if args.content is not None:
        body["content"] = args.content
    if args.title is not None:
        body["title"] = args.title
    if args.language is not None:
        body["language"] = args.language
    if args.source_doi is not None:
        body["source_doi"] = _normalize_doi(args.source_doi) if args.source_doi else ""
    if args.page_start is not None:
        body["page_start"] = args.page_start
    if args.page_end is not None:
        body["page_end"] = args.page_end

    if not body:
        print(
            "No changes specified. Use --content, --type, --title, --language, "
            "--source-doi, --page-start, or --page-end."
        )
        sys.exit(1)

    result = client.put(f"/api/v1/snippet/{doi}", json=body)

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    print(f"Snippet modified: {result.get('doi', '?')}")
    _print_snippet(result)


def _cmd_delete(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``snippet delete``."""
    doi = _normalize_doi(args.doi)
    client.delete(f"/api/v1/snippet/{doi}")
    print(f"Snippet '{doi}' deleted (tombstoned).")


def _cmd_embed(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``snippet embed`` — print a copy-paste embed tag.

    Resolves the DOI to fetch its title (used as the iframe ``title``
    attribute), then prints either the embed URL (``--url-only``) or a
    ready-to-paste ``<iframe>`` tag pointing at the public-web embed page.
    """
    doi = _normalize_doi(args.doi)
    result = client.get(f"/api/v1/snippet/{doi}", params={"include_redirects": "true"})

    embed_url = f"{args.base.rstrip('/')}/{doi}"

    if getattr(args, "url_only", False):
        print(embed_url)
        return

    title = html.escape(
        (result.get("title") or f"Snippet: {doi}").strip(),
        quote=True,
    )
    iframe = (
        f'<iframe src="{embed_url}" title="{title}" '
        f'width="{html.escape(str(args.width), quote=True)}" '
        f'height="{html.escape(str(args.height), quote=True)}" '
        f'loading="lazy" style="border:0;border-radius:8px" '
        f'referrerpolicy="no-referrer" allowfullscreen></iframe>'
    )
    print(iframe)
