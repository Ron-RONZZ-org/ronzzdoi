# ronzzdoi — In-house DOI & Citation Management

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

**ronzzdoi** is the in-house DOI (Digital Object Identifier) and citation management system at ronzz.org. It provides persistent identifiers for external resources (books, films, webpages) and internal documents (circulaire, rulebook, media files), with citation management inspired by Zotero and native semantic web federation support.

Part of the [lighter ecosystem](https://github.com/Ron-RONZZ-org).

## Features (v0.1.0)

- **DOI assignment** — generate and assign persistent ronzzDOIs
- **DOI format** — identifiers follow the pattern `10.ronzz/<uuid4-hex>` per DOI Handbook
- **Resolution & redirect** — HTTP redirect from `doi.ronzz.org/10.ronzz/<uuid>` to target URL
- **Soft redirect** — update target URL with historical redirect preserved
- **Citation management** — add citations for multiple document types (book, webpage, conference transcript, presentation, circulaire, rulebook, document, media file)
- **Auto-generated detailed-view pages** — persistent citation landing pages
- **Multi-style export** — APA, Vancouver, MLA, Chicago, BibTeX, JSON
- **Keyword search** — search across DOI metadata and citations
- **CLI & Svelte 5 GUI** — dual interfaces following lighterbird patterns

## Planned (v0.2.0)

- Semantic web federation support with SPARQL query acceptance
- Linked data integration

## Architecture

ronzzdoi extends [lightercore](https://github.com/Ron-RONZZ-org/lightercore) for shared infrastructure (database, paths, exceptions) and follows the interaction patterns established by [lighterbird](https://github.com/Ron-RONZZ-org/lighterbird).

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

## Quick Start

```bash
# Prerequisites: lightercore checked out alongside ronzzdoi
git clone https://github.com/Ron-RONZZ-org/ronzzdoi.git
cd ronzzdoi

# Install with uv (recommended)
uv pip install -e "../lightercore" -e .

# Or with pip
pip install -e ../lightercore -e .
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/

# Start dev server
uv run ronzzdoi-dev
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).
