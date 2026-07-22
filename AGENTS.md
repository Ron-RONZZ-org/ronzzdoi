# AGENTS.md — Root Project Rules for ronzzdoi

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
- **Citation formatting** — format DOI metadata into styled citations (APA, Vancouver, JSON). No separate citation storage — the DOI record is the source of truth
- **FTS5 full-text search** — search across DOI metadata via SQLite FTS5 (v0.1.0)
- **Public read-only API** — rate-limited public endpoints for DOI metadata, search, and citations (v0.1.0)
- **Key-only authentication** — no passwords, no user accounts. API keys with 3-tier permission model (read_only / edit / admin)
- **CLI & Svelte 5 GUI** — dual interfaces following lighterbird patterns
- **Semantic web federation** — native support for accepting semantic queries (v0.2.0+)

### Design Constraints

- **Public-oriented.** No secret-protection mechanism. Not for secrets.
- **Key-only auth.** No user accounts, passwords, JWT, or login forms.
- Extends the lighter ecosystem (lightercore for shared infrastructure, lighterauth for key-only auth, lighterbird patterns for CLI/GUI).

### Related Projects

| Project | Location | Relation |
|---------|----------|----------|
| **lightercore** | `../lightercore` | Shared core library (DB, paths, exceptions, CRUD, backup) |
| **lighterauth** | `../lighterauth` | Key-only auth model (api_keys with owner labels, no users) |
| **lighterbird** | `../lighterbird` | Reference for CLI/GUI/LLM-UI interaction patterns |

### Disk Locations (absolute paths)

All sibling repos live under `/home/rongzhou/kodo/autish/`:

| Project | Absolute path |
|---------|--------------|
| **ronzzdoi** | `/home/rongzhou/kodo/autish/ronzzdoi/` — this repo |
| **lightercore** | `/home/rongzhou/kodo/autish/lightercore/` |
| **lighterauth** | `/home/rongzhou/kodo/autish/lighterauth/` |
| **lighterbird** | `/home/rongzhou/kodo/autish/lighterbird/` |

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
| Auth | lighterauth (key-only) | API keys with owner labels, no users |
| Package manager | `uv` (development) | Fast, modern, reproducible |
| Build system | Hatchling | PEP 517 compliant, simple |
| Async HTTP | httpx | Consistent with lightercore |
| Rate limiting | slowapi | IP-based rate limiting for public endpoints |
| E2E testing | Playwright | Browser smoke tests |

---

## Dependency Management

This project uses **uv** for development:

| Operation | Command |
|-----------|---------|
| Install project + lightercore + lighterauth | `uv pip install -e "../lightercore" -e "../lighterauth" -e .` |
| Install dev deps | `uv pip install -e ".[dev]"` |
| Run tests | `uv run pytest tests/` |
| Add dependency | `uv add <pkg>` |

**Note:** [lightercore](../lightercore) and [lighterauth](../lighterauth) are sibling packages — clone them alongside ronzzdoi.

---

## Source Tree Structure

```
ronzzdoi/
├── AGENTS.md                    # This file — global project rules
├── README.md
├── LICENSE                      # AGPL-3.0
├── pyproject.toml
├── .gitignore
├── docs/                        # AGENTS modules documentation
├── scripts/                     # Dev tooling: test.sh
├── src/
│   └── ronzzdoi/                # Main Python package
│       ├── __init__.py
│       ├── cli/                 # CLI commands (doi, citation, search, auth)
│       ├── doi/                 # DOI core: assign, resolve, modify, tombstone, list, merge
│       ├── citation/            # Citation formatting (APA, Vancouver, JSON)
│       ├── db/                  # SQLite models, migrations, FTS5 service
│       ├── server/              # FastAPI API server (internal + public routes)
│       │   ├── command/         # !xxx command dispatch + handlers
│       │   └── handlers/        # Command handler implementations
│       ├── auth/                # Key-only auth wiring (lighterauth wrapper)
│       └── scripts/             # ronzzdoi-dev and ronzzdoi-server entry points
├── tests/                       # Test suite (pytest)
│   ├── conftest.py              # Shared fixtures (key-only auth)
│   ├── test_doi_service.py      # DOI service unit tests
│   ├── test_citation.py         # Citation formatting tests
│   ├── test_doi_routes.py       # DOI API endpoint tests
│   ├── test_public_routes.py    # Public API endpoint tests
│   ├── test_auth_routes.py      # Auth API endpoint tests
│   ├── test_auth_middleware.py  # Auth middleware tests
│   ├── test_auth_integration.py # End-to-end server tests
│   ├── test_cli_*.py            # CLI command tests
│   ├── test_command.py          # Command dispatch tests
│   ├── test_handlers.py         # Handler unit tests (check_permission)
│   ├── test_db.py               # DB module tests
│   └── e2e_gui_smoke.mjs        # Playwright E2E smoke test
└── web/                         # Svelte 5 SPA frontend
    └── src/
        ├── lib/
        │   ├── __tests__/       # Vitest component tests
        │   ├── ChatInput.svelte # Command input box
        │   ├── HomeTab.svelte   # Home tab with !xxx dispatch
        │   ├── TabView.svelte   # Tab-based result display
        │   ├── FormTab.svelte   # Interactive form rendering
        │   ├── DetailTab.svelte # Detail view for DOI records
        │   ├── ListTab.svelte   # List view for search results
        │   ├── api.js           # Auth-bearing fetch() wrapper
        │   └── command*.js      # Command engine, parser, executor
        └── App.svelte
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
| Citation show | GUI (primary), CLI (secondary) | Style selection |
| Search | CLI or GUI | Keyword params |
| Batch operations | CLI | Scriptable |
| Auth management | CLI | Deterministic, admin-only |
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
- `public:` — public API endpoint changes
- `web:` — frontend-only changes (Svelte)

---

## Testing Requirements

| Aspect | Convention |
|--------|-----------|
| Backend framework | pytest |
| Frontend framework | vitest |
| E2E framework | Playwright (.mjs in tests/) |
| Run all backend tests | `uv run pytest tests/` |
| Run single test file | `uv run pytest tests/test_foo.py -v` |
| Run frontend tests | `cd web && npm run test` |
| Run E2E smoke test | `node tests/e2e_gui_smoke.mjs` (servers must be running) |
| Test directory (backend) | `tests/` |
| Test directory (frontend) | `web/src/lib/__tests__/` |

### Principles

1. **Test via the public API wherever possible.** Prefer integration tests over isolated unit tests.
2. **Test through the user-facing interface** (CLI commands, API endpoints).
3. **Every bug fix must include a test** that would have caught the regression.
4. **E2E tests must check for console errors.** Any `pageerror` or `console.error` causes suite failure.

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

## Current Test Count

| Suite | Count | File |
|-------|-------|------|
| Backend pytest | 352 | All `tests/test_*.py` |
| Frontend vitest | 19 | `web/src/lib/__tests__/*.test.js` |
| E2E Playwright | 1 suite | `tests/e2e_gui_smoke.mjs` |

---

## What to Avoid

- **Do not import from lighterbird or semantika.** lightercore and lighterauth are the shared dependencies.
- **Do not store secrets.** ronzzdoi is public-oriented — no secret-protection mechanism.
- **Do not add heavy frameworks** (Django, SQLAlchemy, Celery).
- **Do not hardcode paths.** Extend lightercore's path resolution.
- **Do not add user/password auth.** Key-only is the model. No JWT, no sessions, no login forms.

---

## Module-Level AGENTS Files

| Module | AGENTS File | Status |
|--------|-------------|--------|
| DOI | `docs/AGENTS-doi.md` | ✅ Implemented |
| Citation | `docs/AGENTS-citation.md` | ✅ Implemented |
| DB | `docs/AGENTS-db.md` | ✅ Implemented |
| Server | (inline in AGENTS.md) | ✅ Implemented |
| Auth | (inline in AGENTS.md) | ✅ Implemented (key-only) |
| CLI | (inline in AGENTS.md) | ✅ Implemented |

---

## Dependencies and Inheritance Map

```
Root AGENTS.md (global rules)
    │
    ├── docs/AGENTS-doi.md
    ├── docs/AGENTS-citation.md
    └── docs/AGENTS-db.md
```

Local rules override global rules. Module-level files focus on domain-specific behavior, constraints, and invariants.
