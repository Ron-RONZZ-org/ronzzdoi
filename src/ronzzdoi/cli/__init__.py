"""CLI entry point for ronzzdoi.

Provides the ``ronzzdoi`` command with auth, doi, citation, and search
subcommands.  Every authenticated request requires an API key, passed via
``--api-key`` or the ``RONZZDOI_API_KEY`` environment variable.

Usage::

    ronzzdoi --api-key <key> doi assign https://example.com --title "Example"
    ronzzdoi --server http://localhost:8000 auth api_key list
    ronzzdoi search "quantum computing" --mode semantic
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from ronzzdoi.cli.client import (
    AccessDeniedError,
    AuthenticationError,
    ClientError,
    ConnectionError_,
    RonzzdoiClient,
    ServerError,
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="ronzzdoi",
        description="In-house DOI & citation management system at ronzz.org",
    )

    # ── Global options ─────────────────────────────────────────────────────
    parser.add_argument(
        "--server",
        default=os.environ.get("RONZZDOI_SERVER", "https://doi.ronzz.org:8001"),
        help="ronzzdoi server URL (default: https://doi.ronzz.org:8001, "
        "env: RONZZDOI_SERVER)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("RONZZDOI_API_KEY", ""),
        help="API key for authentication (env: RONZZDOI_API_KEY)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output raw JSON for machine readability",
    )

    # ── Subcommands ────────────────────────────────────────────────────────
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Import and register subcommand parsers
    from ronzzdoi.cli.auth import register_subparser as register_auth
    from ronzzdoi.cli.citation import register_subparser as register_citation
    from ronzzdoi.cli.doi import register_subparser as register_doi
    from ronzzdoi.cli.search import register_subparser as register_search

    register_auth(subparsers)
    register_doi(subparsers)
    register_citation(subparsers)
    register_search(subparsers)

    return parser


def _print_error(msg: str) -> None:
    """Print an error message to stderr in red."""
    sys.stderr.write(f"\033[91mError: {msg}\033[0m\n")


def _check_api_key(api_key: str) -> None:
    """Exit with an error if no API key is configured."""
    if not api_key:
        _print_error(
            "No API key provided. Use --api-key <key> or "
            "set the RONZZDOI_API_KEY environment variable."
        )
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    # Validate API key is present
    _check_api_key(args.api_key)

    # Build the client
    client = RonzzdoiClient(server_url=args.server, api_key=args.api_key)

    # Dispatch to the subcommand handler
    try:
        args.func(args, client)
    except AuthenticationError:
        _print_error(
            "Authentication failed. Check your API key."
        )
        sys.exit(1)
    except AccessDeniedError as exc:
        _print_error(
            f"Permission denied. Your API key requires higher permission. "
            f"({exc})"
        )
        sys.exit(1)
    except ConnectionError_ as exc:
        _print_error(str(exc))
        sys.exit(1)
    except ServerError as exc:
        _print_error(f"Server error: {exc}")
        sys.exit(1)
    except ClientError as exc:
        _print_error(str(exc))
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)


def _entry_point() -> Any:
    """Wrapper for ``pyproject.toml`` entry point (returns None on success)."""
    main()
    return None


if __name__ == "__main__":
    main()
