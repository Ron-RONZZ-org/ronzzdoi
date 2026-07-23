"""Dev CLI entry point for ronzzdoi.

Provides ``ronzzdoi-dev`` command which starts both internal (auth-protected)
and public (rate-limited) API servers as separate processes, mirroring
production setup.

Usage::

    ronzzdoi-dev --seed
    ronzzdoi-dev --data-dir /tmp/ronzzdoi-dev --seed
    ronzzdoi-dev --port-int 8011 --port-pub 8012
"""

from __future__ import annotations

import argparse
import multiprocessing
import signal
import sys
from typing import NoReturn


def _run_server(mode: str, host: str, port: int, data_dir: str | None) -> NoReturn:
    """Start a single uvicorn server process.

    Args:
        mode: ``"internal"`` or ``"public"``.
        host: Bind address.
        port: Bind port.
        data_dir: Data directory path or ``None`` for XDG default.
    """
    from ronzzdoi.server.app import create_app
    import uvicorn

    app = create_app(data_dir=data_dir, mode=mode)
    uvicorn.run(app, host=host, port=port)


def dev_main() -> None:
    """Development server entry point.

    Starts both internal (auth-protected) and public (rate-limited) API
    servers as separate child processes.
    """
    parser = argparse.ArgumentParser(prog="ronzzdoi-dev", description="ronzzdoi development server")
    parser.add_argument(
        "--port-int",
        type=int,
        default=8011,
        help="Internal API server port (default: 8011)",
    )
    parser.add_argument(
        "--port-pub",
        type=int,
        default=8012,
        help="Public API server port (default: 8012)",
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
        help="Seed the database with an admin key and a read-only key for development",
    )

    args = parser.parse_args()

    # Seed if requested (writes DB directly — no server needed)
    if args.seed:
        _seed_keys(args.data_dir)
        _seed_dois()

    # Start both server processes
    processes: list[multiprocessing.Process] = []
    try:
        import uvicorn  # noqa: F401 — verify available before spawning

        proc_int = multiprocessing.Process(
            target=_run_server,
            args=("internal", args.host, args.port_int, args.data_dir),
            daemon=True,
        )
        proc_int.start()
        processes.append(proc_int)

        proc_pub = multiprocessing.Process(
            target=_run_server,
            args=("public", args.host, args.port_pub, args.data_dir),
            daemon=True,
        )
        proc_pub.start()
        processes.append(proc_pub)

        print(f"ronzzdoi dev server started:")
        print(f"  Internal API:  http://{args.host}:{args.port_int}  (auth-protected)")
        print(f"  Public API:    http://{args.host}:{args.port_pub}  (rate-limited, no auth)")
        print(f"  API docs:      http://{args.host}:{args.port_int}/api/docs")
        print()
        print("Press Ctrl+C to stop both servers.")

        # Wait for either process to exit, then terminate the other
        while True:
            for p in processes:
                p.join(timeout=0.5)
                if not p.is_alive():
                    print(
                        f"\n  Server process exited unexpectedly (exit code {p.exitcode}).",
                        file=sys.stderr,
                    )
                    _terminate_all(processes)
                    sys.exit(1)

    except ImportError:
        print("uvicorn is required. Install with: uv pip install uvicorn", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down both servers...")
        _terminate_all(processes)
        sys.exit(0)


def _terminate_all(processes: list[multiprocessing.Process]) -> None:
    """Terminate all server processes."""
    for p in processes:
        if p.is_alive():
            p.terminate()
            p.join(timeout=3)
            if p.is_alive():
                p.kill()
                p.join(timeout=1)


def _seed_keys(data_dir: str | None) -> None:
    """Seed API keys for development (key-only auth, no users).

    Creates:
    - An admin API key (permission: admin, owner: "dev-admin")
    - A read-only API key (permission: read_only, owner: "dev-read-only")
    """
    from lighterauth.api_key import generate_api_key
    from lighterauth.keyonly import init_keyonly_schema
    from lightercore.db import LighterDB

    from ronzzdoi.auth.config import resolve_auth_db_path

    db_path = resolve_auth_db_path(data_dir)
    db = LighterDB(str(db_path))
    init_keyonly_schema(db)

    # Check if keys already exist
    existing = db.execute_one("SELECT id FROM api_keys LIMIT 1")
    if existing:
        print("Seed data already exists, skipping.")
        return

    import secrets
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    # Create admin API key
    raw_admin, prefix_admin, hashed_admin = generate_api_key()
    db.execute(
        "INSERT INTO api_keys (id, name, key, prefix, permission, owner, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "ak_seed_admin_" + secrets.token_hex(8),
            "dev-admin",
            hashed_admin,
            prefix_admin,
            "admin",
            "dev-admin",
            now,
            now,
        ),
    )

    # Create read-only API key
    raw_ro, prefix_ro, hashed_ro = generate_api_key()
    db.execute(
        "INSERT INTO api_keys (id, name, key, prefix, permission, owner, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "ak_seed_ro_" + secrets.token_hex(8),
            "dev-read-only",
            hashed_ro,
            prefix_ro,
            "read_only",
            "dev-read-only",
            now,
            now,
        ),
    )

    print(f"Seed data created:")
    print(f"  Admin API key:      {raw_admin}  (owner: dev-admin)")
    print(f"  Read-only API key:  {raw_ro}  (owner: dev-read-only)")
    print()
    print("⚠  Store keys securely — they will not be shown again.")
    print("   Use the --owner flag on `ronzzdoi auth api_key create` to")
    print("   label keys (e.g. '--owner \"Alice\"' or '--owner \"CI pipeline\"').")


def _seed_dois() -> None:
    """Seed sample DOIs of various types for development/testing.

    Creates DOIs of each major type: external, book, webpage, film,
    person, country, circulaire, rulebook.
    """
    from ronzzdoi.db import init_db
    from ronzzdoi.doi.service import DOIService

    doi_service = DOIService(init_db()[0])

    # Check if DOIs already exist
    existing = doi_service.list_dois(limit=1)
    if existing:
        print("DOI seed data already exists, skipping.")
        return

    sample_dois = [
        {
            "target_url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
            "doi_type": "external",
            "title": "Python (programming language) — Wikipedia",
            "metadata": {},
        },
        {
            "target_url": "https://example.com/clean-code",
            "doi_type": "book",
            "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
            "metadata": {
                "author": [{"name": "Robert C. Martin", "type": "person"}],
                "publisher": "Prentice Hall",
                "year": 2008,
                "isbn": "978-0132350884",
            },
        },
        {
            "target_url": "https://example.com/quantum-computing-article",
            "doi_type": "webpage",
            "title": "Quantum Computing: A Gentle Introduction",
            "metadata": {
                "author": [{"name": "Scott Aaronson", "type": "person"}],
                "site_name": "Shtetl-Optimized",
                "published_date": "2025-03-15",
            },
        },
        {
            "target_url": "https://example.com/inception",
            "doi_type": "film",
            "title": "Inception (2010)",
            "metadata": {
                "director": {"name": "Christopher Nolan", "type": "person"},
                "year": 2010,
                "duration_minutes": 148,
            },
        },
        {
            "target_url": "https://ronzz.org/people/alice-dubois",
            "doi_type": "person",
            "title": "Alice Dubois — Research Scientist",
            "metadata": {
                "full_name": "Alice Dubois",
                "affiliation": "CNRS",
                "orcid": "0000-0002-1825-0097",
            },
        },
        {
            "doi_type": "country",
            "title": "France",
            "metadata": {
                "iso_code": "FR",
                "capital": "Paris",
                "languages": ["French"],
            },
        },
        {
            "target_url": "https://example.com/circulaire-2025-01",
            "doi_type": "circulaire",
            "title": "Circulaire relative à l'organisation des services",
            "metadata": {
                "reference": "CIRC-2025-001",
                "authority": "Ministère de l'Intérieur",
                "date": "2025-01-15",
            },
        },
        {
            "target_url": "https://example.com/rulebook-data-protection",
            "doi_type": "rulebook",
            "title": "Règlement intérieur — Protection des données",
            "metadata": {
                "reference": "RI-DATA-2024",
                "effective_date": "2024-06-01",
                "jurisdiction": "France",
            },
        },
    ]

    count = 0
    for entry in sample_dois:
        try:
            doi_service.assign(
                target_url=entry.get("target_url"),
                doi_type=entry["doi_type"],
                title=entry["title"],
                metadata=entry["metadata"],
            )
            count += 1
        except Exception as exc:
            print(f"  Warning: failed to seed DOI '{entry['title']}': {exc}")

    print(f"Seeded {count} sample DOIs of various types.")
    print("  Try: ronzzdoi doi search")
    print("  Try: ronzzdoi doi resolve <doi>")
