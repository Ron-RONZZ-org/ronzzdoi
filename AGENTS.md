# AGENTS.md — Root Project Rules for ronzzdoi

> Current project stage: boilerplate. Do NOT write schema migrations. Everything is subjected to change.

This is the canonical, repo-wide instruction file for AI agents working on **ronzzdoi**.

## Hierarchical Context Model

Agents **must** follow this rule:

> When working inside a directory, load the nearest `AGENTS.md` file and merge it with parent `AGENTS.md` files up to root.  
> Local rules override global rules.

Context resolution order (highest priority first):
1. `AGENTS-[module].md` in module directories — module-specific context
2. `AGENTS.md` in current working directory (if present)
3. Root `AGENTS.md` — global project rules

---

## Project Overview

**ronzzdoi** is the in-house DOI (Digital Object Identifier) and citation management system at ronzz.org. It provides:

- **Persistent identifier assignment** — ronzzDOIs for external resources (books, films, webpages, conference transcripts, presentations) and internal documents (circulaire, rulebook, generic documents, media files)
- **Resolution & redirect** — HTTP redirects from `doi.ronzz.org/<id>` to the target resource, with soft redirect on metadata changes
- **Citation management** — add citations for various document types, auto-generate detailed-view pages, export in multiple styles (APA, Vancouver, MLA, Chicago, BibTeX)
- **Keyword search** — search across DOI metadata and citations (v0.1.0)
- **Semantic web federation** — native support for accepting semantic queries (v0.2.0+)

### Design Constraints

- **Public-oriented.** No secret-protection mechanism. Not for secrets.
- Extends the lighter ecosystem (lightercore for shared infrastructure, lighterbird patterns for CLI/GUI).
- AUTH functionalities borrowed from midiverse.

### Related Projects

| Project | Location | Relation |
|---------|----------|----------|
| **lightercore** | `../lightercore` | Shared core library (DB, paths, exceptions, CRUD, backup, LLM) |
| **lighterbird** | `../lighterbird` | Reference for CLI/GUI/LLM-UI interaction patterns |
| **midiverse** | `../midiverse` (clone into kodo/) | AUTH code reference |

### Disk Locations (absolute paths)

All sibling repos live under `/home/rongzhou/kodo/autish/`:

| Project | Absolute path |
|---------|--------------|
| **ronzzdoi** | `/home/rongzhou/kodo/autish/ronzzdoi/` — this repo |
| **lightercore** | `/home/rongzhou/kodo/autish/lightercore/` |
| **lighterbird** | `/home/rongzhou/kodo/autish/lighterbird/` |
| **midiverse** | `/home/rongzhou/kodo/autish/midiverse/` |

Relative references in this file (e.g., `../lightercore`) resolve correctly because all repos share the same parent directory.

---

## Language and Naming Conventions

- **Source code**: English (variable names, comments, docstrings)
- **User-facing strings**: English first
- **CLI command names**: English, singular form (`doi`, `citation`, `search`)
- **URL paths, route names**: lowercase with hyphens (`/api/v1/doi/resolve`)
- **Database columns**: English names throughout
- **DOI format**: `10.ronzz/<suffix>` — opaque identifier, no semantic encoding (per DOI Handbook); entity exceptions: `10.ronzz/country/<ISO>`

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | Python 3.11+ | Ecosystem, lightercore compatibility |
| Backend framework | FastAPI + uvicorn | Lightweight, async, auto-docs |
| Frontend editor | Svelte 5 SPA | Consistent with lighter ecosystem |
| Frontend build | Vite | Fast dev, static export possible |
| Database | SQLite (WAL mode) | Embedded, zero-config, sufficient |
| Static pages | (To be decided) | Detailed-view page generation |
| Package manager | `uv` (development) | Fast, modern, reproducible |
| Build system | Hatchling | PEP 517 compliant, simple |
| Async HTTP | httpx | Consistent with lightercore |

---

## Dependency Management

This project uses **uv** for development:

| Operation | Command |
|-----------|---------|
| Install project + lightercore in dev mode | `uv pip install -e "../lightercore" -e .` |
| Install dev deps | `uv pip install -e ".[dev]"` |
| Run tests | `uv run pytest tests/` |
| Add dependency | `uv add <pkg>` |

**Note:** [lightercore](../lightercore) is a sibling package — clone it alongside ronzzdoi and install with `-e ../lightercore` before installing ronzzdoi.

---

## Source Tree Structure

```
ronzzdoi/
├── AGENTS.md                    # This file — global project rules
├── README.md
├── LICENSE                      # AGPL-3.0
├── pyproject.toml
├── .gitignore
├── docs/                        # Documentation
├── scripts/                     # Dev tooling: dev CLI, seed data
├── src/
│   └── ronzzdoi/                # Main Python package
│       ├── __init__.py
│       ├── cli/                 # CLI commands
│       ├── doi/                 # DOI core: assign, resolve, redirect, delete
│       ├── citation/            # Citation management (Zotero-like)
│       ├── db/                  # SQLite models & migrations
│       ├── server/              # FastAPI API server
│       ├── auth/                # Auth (from midiverse)
│       └── static/              # Static page generation
├── tests/                       # Test suite
└── web/                         # Svelte 5 editor client (TBD)
    └── src/lib/
```

---

## Coding Conventions

1. **No file > 500 lines.** Split by functional unit.
2. **Type hints on all public functions.** Use `from __future__ import annotations`.
3. **Docstrings on all public functions.** Google-style or reStructuredText.
4. **Tests required for all modules.** `pytest` with `tmp_path` isolation for DB tests.
5. **Extend lightercore** — do not duplicate functionality that exists in lightercore.
6. **SQLite in WAL mode.** Use `pragma journal_mode=wal` on connection.
7. **Error messages include actionable suggestions.**
8. **Async where it matters.** FastAPI routes are async; CLI commands can be sync.

---

## Three Interaction Worlds: CLI / GUI / LLM

Following the lighterbird pattern, ronzzdoi operations are accessible through multiple interfaces:

| Operation | Best Interface | Why |
|-----------|---------------|-----|
| DOI assignment | CLI or GUI | Few params |
| DOI resolution | CLI or GUI (redirect) | Simple lookup |
| Citation management | GUI (primary), CLI (secondary) | Complex forms |
| Search | CLI or GUI | Keyword params |
| Batch operations | CLI | Scriptable |
| System admin | CLI | Deterministic |

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new user-facing feature
- `fix:` — bug fix
- `docs:` — documentation only
- `chore:` — tooling, config, CI
- `test:` — test additions/fixes
- `refactor:` — code restructuring with no behavior change
- `doi:` — DOI module changes
- `citation:` — citation module changes
- `db:` — database schema or migration changes
- `auth:` — authentication module changes
- `server:` — API server changes
- `cli:` — CLI command changes
- `web:` — frontend-only changes (Svelte)

---

## Testing Requirements

| Aspect | Convention |
|--------|-----------|
| Framework | pytest |
| Run all tests | `uv run pytest tests/` |
| Run single test file | `uv run pytest tests/test_foo.py -v` |
| Test directory | `tests/` |

### Principles

1. **Test via the public API wherever possible.** Prefer integration tests over isolated unit tests.
2. **Test through the user-facing interface** (CLI commands, API endpoints).
3. **Every bug fix must include a test** that would have caught the regression.

### Running Tests from Git Worktrees

When running tests in a git worktree (created by `worktreeCreate` or `git worktree add`),
the worktree does **not** have its own `.venv` — it shares the main checkout's virtual
environment. The project provides a convenience script that auto-detects this:

```bash
./scripts/test.sh [pytest-args...]
```

This script:
1. Detects if the current directory is inside a git worktree via
   `git rev-parse --is-inside-work-tree`.
2. If yes, finds the **main checkout's** `.venv` via `git rev-parse --git-common-dir`
   and uses that Python interpreter, with `PYTHONPATH=<worktree-root>/src` to pick up
   the worktree's code (the main checkout's editable install `.pth` file still points
   to the parent `src/`, so `PYTHONPATH` must override it).
3. If in the main checkout, runs `python -m pytest` directly (assumes `.venv` is active).

**Example** — run DOI tests from a worktree:
```bash
./scripts/test.sh tests/test_doi_service.py -x -v
```

**Manual invocation** (equivalent to what the script does for a worktree):
```bash
PYTHONPATH=src /path/to/main/checkout/.venv/bin/python -m pytest tests/...
```

---

## What to Avoid

- **Do not import from lighterbird or semantika.** lightercore is the shared dependency.
- **Do not store secrets.** ronzzdoi is public-oriented — no secret-protection mechanism.
- **Do not add heavy frameworks** (Django, SQLAlchemy, Celery).
- **Do not hardcode paths.** Extend lightercore's path resolution.

---

## Module-Level AGENTS Files

| Module | AGENTS File | Documentation |
|--------|-------------|---------------|
| DOI | `docs/AGENTS-doi.md` | `docs/man/doi.md` |
| Citation | `docs/AGENTS-citation.md` | `docs/man/citation.md` |
| DB | `docs/AGENTS-db.md` | `docs/man/db.md` |
| Server | `docs/AGENTS-server.md` | `docs/man/server.md` |
| Auth | `docs/AGENTS-auth.md` | `docs/man/auth.md` |
| CLI | `docs/AGENTS-cli.md` | `docs/man/cli.md` |

Current status: DB module ✓ (implemented), DOI module ✓ (implemented), Citation module ✓ (implemented). Other modules are placeholders.

---

## Dependencies and Inheritance Map

```
Root AGENTS.md (global rules)
    │
    ├── docs/AGENTS-doi.md
    ├── docs/AGENTS-citation.md
    ├── docs/AGENTS-db.md
    ├── docs/AGENTS-server.md
    ├── docs/AGENTS-auth.md
    └── docs/AGENTS-cli.md
```

Local rules override global rules. Module-level files focus on domain-specific behavior, constraints, and invariants.
