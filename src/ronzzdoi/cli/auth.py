"""Auth subcommands for the ronzzdoi CLI.

Handles ``ronzzdoi auth api_key create|list|update|revoke``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ronzzdoi.cli.client import RonzzdoiClient


def register_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``auth`` subcommand tree."""
    auth_parser = subparsers.add_parser(
        "auth",
        help="Manage API keys and authentication",
        description="Manage API keys. Requires admin permission.",
    )
    auth_sub = auth_parser.add_subparsers(dest="auth_command", required=True)

    # ── auth api_key ───────────────────────────────────────────────────────
    api_key_parser = auth_sub.add_parser(
        "api_key",
        help="Manage API keys",
        description="Manage API keys. Requires admin permission.",
    )
    api_key_sub = api_key_parser.add_subparsers(dest="api_key_command", required=True)

    # ── auth api_key create ────────────────────────────────────────────────
    create_parser = api_key_sub.add_parser(
        "create",
        help="Create a new API key",
        description="Generate a new API key. The raw key is shown **only once**.",
    )
    create_parser.add_argument("--name", required=True, help="Human-readable name for the key")
    create_parser.add_argument(
        "--permission",
        choices=["read_only", "edit", "admin"],
        default="read_only",
        help="Permission level (default: read_only)",
    )
    create_parser.add_argument(
        "--owner",
        help="Free-text owner label (e.g. 'CI pipeline', 'Alice')",
    )
    create_parser.add_argument(
        "--expires-at",
        help="Expiration date (ISO 8601), e.g. 2027-01-01T00:00:00+00:00",
    )
    create_parser.set_defaults(func=_cmd_create)

    # ── auth api_key list ──────────────────────────────────────────────────
    list_parser = api_key_sub.add_parser(
        "list",
        help="List API keys",
        description="List all API keys (optionally including expired ones).",
    )
    list_parser.add_argument(
        "--include-expired",
        action="store_true",
        help="Include expired and revoked keys",
    )
    list_parser.set_defaults(func=_cmd_list)

    # ── auth api_key update ────────────────────────────────────────────────
    update_parser = api_key_sub.add_parser(
        "update",
        help="Update an API key",
        description="Update an existing API key's name, permission, and/or expiry.",
    )
    update_parser.add_argument("key_id", help="ID of the API key to update")
    update_parser.add_argument("--name", help="New name for the key")
    update_parser.add_argument(
        "--permission",
        choices=["read_only", "edit", "admin"],
        help="New permission level",
    )
    update_parser.add_argument(
        "--expires-at",
        help="New expiration date (ISO 8601) or 'null' to clear",
    )
    update_parser.set_defaults(func=_cmd_update)

    # ── auth api_key revoke ────────────────────────────────────────────────
    revoke_parser = api_key_sub.add_parser(
        "revoke",
        help="Revoke an API key",
        description="Permanently revoke (delete) an API key.",
    )
    revoke_parser.add_argument("key_id", help="ID of the API key to revoke")
    revoke_parser.set_defaults(func=_cmd_revoke)


# ── Command implementations ────────────────────────────────────────────────


def _cmd_create(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``auth api_key create``."""
    body: dict[str, Any] = {"name": args.name, "permission": args.permission}
    owner = getattr(args, "owner", None)
    if owner:
        body["owner"] = owner
    if args.expires_at:
        body["expires_at"] = args.expires_at

    result = client.post("/api/v1/auth/keys", json=body)

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2))
        return

    print("API key created:")
    print(f"  ID:         {result.get('id', '?')}")
    print(f"  Name:       {result.get('name', '?')}")
    print(f"  Permission: {result.get('permission', '?')}")
    print(f"  Owner:      {result.get('owner', '-')}")
    print(f"  Key:        {result.get('key', '?')}")
    print(f"  Prefix:     {result.get('prefix', '?')}")
    if expires := result.get("expires_at"):
        print(f"  Expires at: {expires}")
    print()
    print("⚠  Store this key securely — it will not be shown again.")


def _cmd_list(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``auth api_key list``."""
    params = {}
    if args.include_expired:
        params["include_expired"] = "true"

    result = client.get("/api/v1/auth/keys", params=params)

    # The server returns a list directly
    keys = result if isinstance(result, list) else result.get("items", [])

    if getattr(args, "json_output", False):
        print(json.dumps(keys, indent=2, default=str))
        return

    if not keys:
        print("No API keys found.")
        return

    print(f"{'ID':<30} {'Name':<18} {'Permission':<10} {'Owner':<18} {'Prefix':<10} {'Expires':<22} {'Created':<22}")
    print("-" * 130)
    for key in keys:
        print(
            f"{key.get('id', '?'):<30} "
            f"{key.get('name', '?'):<18} "
            f"{key.get('permission', '?'):<10} "
            f"{(key.get('owner') or '-'):<18} "
            f"{key.get('prefix', '?'):<10} "
            f"{(key.get('expires_at') or '-'):<22} "
            f"{(key.get('created_at') or '-'):<22}"
        )


def _cmd_update(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``auth api_key update``."""
    body: dict[str, Any] = {}
    if args.name is not None:
        body["name"] = args.name
    if args.permission is not None:
        body["permission"] = args.permission
    if args.expires_at is not None:
        body["expires_at"] = None if args.expires_at.lower() == "null" else args.expires_at

    if not body:
        print("No changes specified. Use --name, --permission, or --expires-at.")
        sys.exit(1)

    result = client.patch(f"/api/v1/auth/keys/{args.key_id}", json=body)

    if getattr(args, "json_output", False):
        print(json.dumps(result, indent=2, default=str))
        return

    print("API key updated:")
    print(f"  ID:         {result.get('id', '?')}")
    print(f"  Name:       {result.get('name', '?')}")
    print(f"  Permission: {result.get('permission', '?')}")
    if expires := result.get("expires_at"):
        print(f"  Expires at: {expires}")


def _cmd_revoke(args: argparse.Namespace, client: RonzzdoiClient) -> None:
    """Handle ``auth api_key revoke``."""
    client.delete(f"/api/v1/auth/keys/{args.key_id}")
    print(f"API key '{args.key_id}' revoked.")
