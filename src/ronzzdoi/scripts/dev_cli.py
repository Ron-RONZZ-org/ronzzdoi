"""Dev CLI entry point for ronzzdoi.

Provides ``ronzzdoi-dev`` command with options for mode, port, data
directory, and seed data.

Usage::

    ronzzdoi-dev --port 8080 --seed
    ronzzdoi-dev --data-dir /tmp/ronzzdoi-dev --seed
    ronzzdoi-dev --mode public --port 9000
"""

from __future__ import annotations

import argparse
import sys

from lighterauth.password import hash_password


def dev_main() -> None:
    """Development server entry point."""
    parser = argparse.ArgumentParser(prog="ronzzdoi-dev", description="ronzzdoi development server")
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Data directory path (default: XDG-compliant path)",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed the database with an admin user for development",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="full",
        choices=["full", "internal", "public"],
        help='Server mode: "full" (both internal+public, default), '
        '"internal" (auth-protected only), or "public" (rate-limited only)',
    )

    args = parser.parse_args()

    # Create the app
    try:
        from ronzzdoi.server.app import create_app

        app = create_app(data_dir=args.data_dir, mode=args.mode)
    except Exception as exc:
        print(f"Failed to create app: {exc}", file=sys.stderr)
        sys.exit(1)

    # Seed if requested
    if args.seed:
        _seed_data(args.data_dir)

    # Start uvicorn
    try:
        import uvicorn

        print(f"Starting ronzzdoi dev server (mode={args.mode}) on {args.host}:{args.port}")
        if args.mode in ("full", "internal"):
            print(f"API docs: http://{args.host}:{args.port}/api/docs")
        uvicorn.run(app, host=args.host, port=args.port)
    except ImportError:
        print("uvicorn is required. Install with: uv pip install uvicorn", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


def _seed_data(data_dir: str | None) -> None:
    """Seed the database with an admin user for development.

    Creates:
    - An admin user (admin@ronzz.org / admin123)
    - A full-access API key for the admin user
    - A read-only API key for the admin user

    Uses the same auth database path resolution as ``create_app``.
    """
    from lighterauth.api_key import generate_api_key
    from lighterauth.db import init_auth_schema
    from lightercore.db import LighterDB

    from ronzzdoi.auth.config import resolve_auth_db_path

    db_path = resolve_auth_db_path(data_dir)
    db = LighterDB(str(db_path))
    init_auth_schema(db)

    # Check if seed already exists
    existing = db.execute_one("SELECT id FROM users WHERE email = ?", ("admin@ronzz.org",))
    if existing:
        print("Seed data already exists, skipping.")
        return

    import secrets
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    # Create admin user (key-only auth; password is unused but schema-required)
    user_id = "user_dev_admin_001"
    _dummy = hash_password(secrets.token_urlsafe(32))
    db.execute(
        "INSERT INTO users (id, email, username, password, role, status, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, "admin@ronzz.org", "admin", _dummy, "administrator", "active", now, now),
    )

    # Create admin API key
    raw_admin, prefix_admin, hashed_admin = generate_api_key()
    db.execute(
        "INSERT INTO api_keys (id, name, key, prefix, permission, "
        "created_at, updated_at, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "ak_seed_admin_" + secrets.token_hex(8),
            "dev-admin",
            hashed_admin,
            prefix_admin,
            "admin",
            now,
            now,
            user_id,
        ),
    )

    # Create read-only API key
    raw_ro, prefix_ro, hashed_ro = generate_api_key()
    db.execute(
        "INSERT INTO api_keys (id, name, key, prefix, permission, "
        "created_at, updated_at, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "ak_seed_ro_" + secrets.token_hex(8),
            "dev-read-only",
            hashed_ro,
            prefix_ro,
            "read_only",
            now,
            now,
            user_id,
        ),
    )

    print(f"Seed data created:")
    print(f"  Admin user: admin@ronzz.org / admin123")
    print(f"  Admin API key: {raw_admin}")
    print(f"  Read-only API key:   {raw_ro}")
