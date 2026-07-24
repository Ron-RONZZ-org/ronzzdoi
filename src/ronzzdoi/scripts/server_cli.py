"""Production server CLI entry point for ronzzdoi.

Provides ``ronzzdoi-server`` command with options for mode, host, and port.
Defaults to ``--mode internal`` for production safety.

Usage::

    ronzzdoi-server                          # mode=internal, 127.0.0.1:8011
    ronzzdoi-server --mode public            # mode=public, 0.0.0.0:8012
    ronzzdoi-server --mode internal --port 9000
"""

from __future__ import annotations

import argparse
import sys


def server_main() -> None:
    """Production server entry point."""
    parser = argparse.ArgumentParser(
        prog="ronzzdoi-server",
        description="ronzzdoi API server (production)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="internal",
        choices=["internal", "public"],
        help='Server mode: "internal" (auth-protected, default) or "public" (rate-limited, no auth)',
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Bind address (default: 127.0.0.1 for internal, 0.0.0.0 for public)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port (default: 8011 for internal, 8012 for public)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Data directory path (default: XDG-compliant path)",
    )

    args = parser.parse_args()

    # Resolve defaults per mode
    mode = args.mode
    host = args.host or ("127.0.0.1" if mode == "internal" else "0.0.0.0")
    port = args.port or (8011 if mode == "internal" else 8012)

    # Create the app
    try:
        from ronzzdoi.server.app import create_app

        app = create_app(data_dir=args.data_dir, mode=mode)
    except Exception as exc:
        print(f"Failed to create app: {exc}", file=sys.stderr)
        sys.exit(1)

    # Start uvicorn
    try:
        import uvicorn

        print(f"Starting ronzzdoi server (mode={mode}) on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except ImportError:
        print("uvicorn is required. Install with: uv pip install uvicorn", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
