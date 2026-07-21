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
