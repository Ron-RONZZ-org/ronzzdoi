"""DOI subcommands for the ronzzdoi CLI.

Handles ``ronzzdoi doi assign|resolve|modify|delete|list|merge``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ronzzdoi.cli.client import RonzzdoiClient

DOI_PREFIX = "10.ronzz"


def _normalize_doi(doi: str) -> str:
    """Prepend ``10.ronzz/`` if the user provided just a suffix."""
    if not doi.startswith("10."):
        return f"{DOI_PREFIX}/{doi}"
    return doi


def register_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``doi`` subcommand tree."""
    doi_parser = subparsers.add_parser(
        "doi",
        help="Manage DOIs",
        description="Assign, resolve, modify, delete, list, and merge DOIs.",
    )
    doi_sub = doi_parser.add_subparsers(dest="doi_command", required=True)

    # ── doi assign ─────────────────────────────────────────────────────────
    assign_parser = doi_sub.add_parser(
        "assign",
        help="Assign a new ronzzDOI",
        description="Assign a new ronzzDOI. Requires permission: edit.",
    )
    assign_parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Target URL (omit for entity DOIs: person, abstract_entity, country)",
    )
    assign_parser.add_argument("--type", dest="doi_type", default="external", help="DOI type (default: external)")
    assign_parser.add_argument("--title", default="", help="Human-readable title")
    assign_parser.set_defaults(func=_cmd_assign)

    # ── doi resolve ────────────────────────────────────────────────────────
    resolve_parser = doi_sub.add_parser(
        "resolve",
        help="Resolve a ronzzDOI",
        description="Resolve a DOI and return its full metadata. Requires permission: read_only.",
    )
    resolve_parser.add_argument("doi", help="DOI to resolve (e.g. 10.ronzz/abc123)")
    resolve_parser.set_defaults(func=_cmd_resolve)

    # ── doi modify ─────────────────────────────────────────────────────────
    modify_parser = doi_sub.add_parser(
        "modify",
        help="Modify a ronzzDOI",
        description="Update a DOI's metadata. URL change triggers soft redirect. Requires permission: edit.",
    )
    modify_parser.add_argument("doi", help="DOI to modify")
    modify_parser.add_argument("--url", dest="target_url", help="New target URL")
    modify_parser.add_argument("--title", help="New title")
    modify_parser.add_argument("--type", dest="doi_type", help="New DOI type")
    modify_parser.add_argument("--redirect-note", default="", help="Note for the redirect entry")
    modify_parser.set_defaults(func=_cmd_modify)

    # ── doi delete ─────────────────────────────────────────────────────────
    delete_parser = doi_sub.add_parser(
        "delete",
        help="Tombstone a ronzzDOI",
        description="Soft-delete (tombstone) a DOI. Requires permission: edit.",
    )
    delete_parser.add_argument("doi", help="DOI to delete")
    delete_parser.set_defaults(func=_cmd_delete)

    # ── doi list ──────────────────────────────────────────────────────────
    list_parser = doi_sub.add_parser(
        "list",
        help="List DOIs",
        description="List DOI records with optional type filter. Requires permission: read_only.",
    )
    list_parser.add_argument("--type", dest="doi_type", default="", help="Filter by DOI type")
    list_parser.add_argument("--include-deleted", action="store_true", help="Include tombstoned DOIs")
    list_parser.set_defaults(func=_cmd_list)

    # ── doi merge ──────────────────────────────────────────────────────────
    merge_parser = doi_sub.add_parser(
        "merge",
        help="Merge two DOIs",
        description="Merge a source DOI into a target DOI. Requires permission: edit.",
    )
    merge_parser.add_argument("source_doi", help="Source DOI (will be tombstoned)")
    merge_parser.add_argument("target_doi", help="Target DOI (receives redirect history)")
    merge_parser.add_argument("--preview", action="store_true", help="Show affected records without executing")
    merge_parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    merge_parser.set_defaults(func=_cmd_merge)


# ── Command implementations ────────────────────────────────────────────────


def _cmd_assign(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``doi assign``."""
    body: dict[str, Any] = {
        "doi_type": args.doi_type,
        "title": args.title,
    }
    if args.url is not None:
        body["target_url"] = args.url

    result = client.post("/api/v1/doi", json=body)

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    print(f"DOI assigned: {result.get('doi', '?')}")
    print(f"  URL:   {result.get('target_url', '(none)')}")
    print(f"  Type:  {result.get('doi_type', '?')}")
    print(f"  Title: {result.get('title', '')}")


def _cmd_resolve(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``doi resolve``."""
    doi = _normalize_doi(args.doi)
    result = client.get(f"/api/v1/doi/{doi}", params={"include_redirects": "true"})

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    print(f"DOI:       {result.get('doi', '?')}")
    print(f"URL:       {result.get('target_url', '(none)')}")
    print(f"Title:     {result.get('title', '')}")
    print(f"Type:      {result.get('doi_type', '?')}")
    print(f"Status:    {result.get('status', '?')}")
    print(f"Created:   {result.get('created_at', '?')}")
    print(f"Updated:   {result.get('updated_at', '?')}")
    if deleted := result.get("deleted_at"):
        print(f"Deleted:   {deleted}")

    history = result.get("redirect_history", [])
    if history:
        print(f"\nRedirect history ({len(history)} entries):")
        for entry in history:
            note = f" — {entry.get('note', '')}" if entry.get("note") else ""
            print(f"  {entry.get('old_url', '?')}{note}")
    else:
        print("\nNo redirect history.")


def _cmd_modify(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``doi modify``."""
    doi = _normalize_doi(args.doi)
    body: dict[str, Any] = {}
    if args.target_url is not None:
        body["target_url"] = args.target_url
    if args.title is not None:
        body["title"] = args.title
    if args.doi_type is not None:
        body["doi_type"] = args.doi_type
    if args.redirect_note:
        body["redirect_note"] = args.redirect_note

    if not body:
        print("No changes specified. Use --url, --title, --type, or --redirect-note.")
        sys.exit(1)

    result = client.put(f"/api/v1/doi/{doi}", json=body)

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    print(f"DOI modified: {result.get('doi', '?')}")
    print(f"  URL:   {result.get('target_url', '(none)')}")
    print(f"  Title: {result.get('title', '')}")
    print(f"  Type:  {result.get('doi_type', '?')}")


def _cmd_delete(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``doi delete``."""
    doi = _normalize_doi(args.doi)
    client.delete(f"/api/v1/doi/{doi}")
    print(f"DOI '{doi}' deleted (tombstoned).")


def _cmd_list(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``doi list``."""
    params: dict[str, Any] = {}
    if args.doi_type:
        params["doi_type"] = args.doi_type
    if args.include_deleted:
        params["include_deleted"] = "true"

    result = client.get("/api/v1/doi", params=params)
    items = result.get("items", [])

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    if not items:
        print("No DOIs found.")
        return

    print(f"{'DOI':<45} {'Type':<20} {'Title':<40} {'Status':<10}")
    print("-" * 115)
    for item in items:
        status = "tombstone" if item.get("deleted_at") else "active"
        print(
            f"{item.get('doi', '?'):<45} "
            f"{item.get('doi_type', '?'):<20} "
            f"{item.get('title', ''):<40} "
            f"{status:<10}"
        )
    print(f"\nTotal: {result.get('total', len(items))}")


def _cmd_merge(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``doi merge``."""
    source = _normalize_doi(args.source_doi)
    target = _normalize_doi(args.target_doi)

    if args.preview:
        # Show records without executing
        src_result = client.get(f"/api/v1/doi/{source}")
        tgt_result = client.get(f"/api/v1/doi/{target}")

        if getattr(args, "json_output", False):
            print(json.dumps({"source": src_result, "target": tgt_result}, indent=2))
            return

        print("=== Preview: DOI Merge ===")
        print()
        print("--- Source ---")
        _print_doi_brief(src_result)
        print()
        print("--- Target ---")
        _print_doi_brief(tgt_result)
        print()
        print("Run without --preview to execute the merge, or add --force to skip confirmation.")
        return

    if not args.force:
        # Confirm with the user
        src_result = client.get(f"/api/v1/doi/{source}")
        tgt_result = client.get(f"/api/v1/doi/{target}")
        print("=== Confirm Merge ===")
        print()
        print("--- Source (will be tombstoned) ---")
        _print_doi_brief(src_result)
        print()
        print("--- Target (will receive redirect history) ---")
        _print_doi_brief(tgt_result)
        print()
        try:
            confirm = input("Proceed with merge? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nMerge cancelled.")
            sys.exit(1)
        if confirm != "y":
            print("Merge cancelled.")
            sys.exit(0)

    result = client.post("/api/v1/doi/merge", json={"source_doi": source, "target_doi": target})

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    print(f"Merge complete. Target DOI: {result.get('doi', '?')}")
    print(f"  URL:   {result.get('target_url', '(none)')}")
    print(f"  Title: {result.get('title', '')}")
    print(f"  Type:  {result.get('doi_type', '?')}")


def _print_doi_brief(record: dict[str, Any]) -> None:
    """Print a brief summary of a DOI record."""
    print(f"  DOI:       {record.get('doi', '?')}")
    print(f"  URL:       {record.get('target_url', '(none)')}")
    print(f"  Title:     {record.get('title', '')}")
    print(f"  Type:      {record.get('doi_type', '?')}")
    print(f"  Status:    {record.get('status', '?')}")
