# ronzzdoi — In-house DOI & Citation Management

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

**ronzzdoi** is the in-house DOI (Digital Object Identifier) and citation management system at ronzz.org. It provides persistent identifiers for external resources (books, films, webpages) and internal documents (circulaire, rulebook, media files), with a citation formatting engine inspired by Zotero and native semantic web federation support.

Part of the [lighter ecosystem](https://github.com/Ron-RONZZ-org).

## Features (v0.1.0)

- **DOI assignment** — generate and assign persistent ronzzDOIs. Entity DOIs (person, abstract_entity, country) have no `target_url`.
- **DOI format** — identifiers follow the pattern `10.ronzz/<suffix>` (opaque by default; country DOIs use `10.ronzz/country/<ISO>` as documented exception)
- **Resolution & redirect** — HTTP redirect from `doi.ronzz.org/10.ronzz/<id>` to target URL with soft redirect support
- **Citation formatting** — read DOI metadata (`doi_type` + `metadata_json`) and produce styled citations in APA, Vancouver, or JSON format
- **17 doc_types** — book, bookSection, scientificPaper, conferencePaper, presentation, report, dataset, webpage, magazineArticle, newspaperArticle, film, podcast, song, media, circulaire, rulebook, document
- **Person/entity resolution** — authors reference person DOIs; formatters resolve names at format time with per-call caching
- **FTS5 full-text search** — search across DOI metadata via SQLite FTS5
- **Semantic search** (v0.2.0) — vector search via sqlite-vec + fastembed (optional `lightersearch` dependency)
- **CLI & Svelte 5 GUI** — dual interfaces following lighterbird patterns

## Planned (v0.2.0)

- Semantic web federation support with SPARQL query acceptance
- Linked data integration

## Architecture

ronzzdoi extends [lightercore](https://github.com/Ron-RONZZ-org/lightercore) for shared infrastructure (`LighterDB`, `CRUDService`, paths, exceptions) and uses [lightersearch](https://github.com/Ron-RONZZ-org/lightersearch) for optional semantic search. Interaction patterns follow [lighterbird](https://github.com/Ron-RONZZ-org/lighterbird).

```
                    ┌─────────────┐
                    │  ronzzdoi   │
                    │  (FastAPI)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │   CLI   │  │   GUI   │  │   LLM   │
        │ (!cmd)  │  │ (Svelte)│  │(natural) │
        └──────────┘ └──────────┘ └──────────┘
              │            │            │
              └────────────┼────────────┘
                           ▼
                    ┌─────────────┐
                    │ lightercore │
                    │ (DB, paths, │
                    │  CRUD, etc) │
                    └─────────────┘
```

## Authentication

ronzzdoi uses **key-only authentication** — no passwords or login forms. Every API request requires an `Authorization: Bearer <key>` header. Keys have three permission tiers:

| Tier | Read ops | Write ops | Auth mgmt |
|------|----------|-----------|-----------|
| `read_only` | ✅ | ❌ | ❌ |
| `edit` | ✅ | ✅ | ❌ |
| `admin` | ✅ | ✅ | ✅ |

## Quick Start

### Prerequisites

Sibling repos required alongside `ronzzdoi/`:

```bash
ls ../lightercore ../lighterauth   # must exist
```

### Install

```bash
uv pip install -e "../lightercore" -e "../lighterauth" -e ".[dev]"
```

### Start dev server with seed data

```bash
ronzzdoi-dev --seed
```

This creates an admin API key, a read-only API key, and **8 sample DOIs** (external, book, webpage, film, person, country, circulaire, rulebook), then starts the servers — internal API on `http://127.0.0.1:8011`, public API on `http://127.0.0.1:8012`. Copy the admin key from the output — it's shown only once.

### Use the CLI

Open another terminal:

```bash
export RONZZDOI_API_KEY="la_a_abc123..."   # the admin key from above

ronzzdoi help
ronzzdoi doi search
ronzzdoi doi search quantum  # matches seeded "Quantum Computing" webpage
ronzzdoi doi assign https://example.com --title "My Example" --type external
ronzzdoi auth api_key list
ronzzdoi auth api_key create --name "CI key" --permission edit --owner "CI pipeline"
```

### Use the GUI

```bash
cd web && npm install && npm run dev
```

Open `http://127.0.0.1:6025` in your browser, paste your API key, then type `!help`, `!doi search`, etc.

## Testing

### Backend unit + integration tests

```bash
# Run all tests (352+ backend tests)
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_doi_service.py -v
```

### Frontend component tests

```bash
cd web && npm run test
# 19 tests across 2 test files (parser, commandExecutor)
```

### E2E browser smoke test (requires both servers running)

```bash
# Terminal 1: start backend
ronzzdoi-dev

# Terminal 2: start frontend
cd web && npm run dev

# Terminal 3: run smoke test
CHROME_PATH=$(npx playwright install --list 2>/dev/null | grep chromium | head -1 | awk '{print $2}') \
  node tests/e2e_gui_smoke.mjs
```

The E2E test opens the GUI in headless Chromium, types `!help`, `!doi assign`, `!doi search`, `!citation show`, asserts tabs open with content, and fails on any JS console error.

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/

# Start dev servers (internal API on 8011, public API on 8012)
ronzzdoi-dev

# Start dev servers with seed data (creates API keys automatically)
ronzzdoi-dev --seed
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).
