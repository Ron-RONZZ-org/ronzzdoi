# AGENTS-snippet.md — Snippet Module

## Module Overview

The snippet module (`src/ronzzdoi/snippet/`) manages **embeddable content
fragments**: text quotations, code snippets, and KaTeX math. Each snippet is a
DOI — the `dois` row provides the persistent identity (`doi_type='snippet'`,
`target_url=NULL`) and a parallel `snippets` row carries the content.

**Snippets are NOT citations.** The citation module (`ronzzdoi.citation`)
formats academic reference text (APA/Vancouver/JSON); snippets are the
embeddable content itself. The only shared machinery is the DOI identity,
resolution, and search infrastructure. `CitationFormatter.format()` explicitly
rejects `doi_type='snippet'` records.

## Files

```
src/ronzzdoi/snippet/
├── __init__.py         # Public API exports
├── constants.py        # CONTENT_KINDS (text/code/math), SUGGESTED_LANGUAGES
├── exceptions.py       # SnippetError hierarchy
├── schema.py           # SnippetAssignRequest, SnippetModifyRequest, SnippetResponse
└── service.py          # SnippetService — two-table lifecycle management
```

## Content Kinds

| Kind | Meaning | Extra fields |
|------|---------|--------------|
| `text` | Quotation from a book/document | `source_doi`, `page_start`, `page_end` |
| `code` | Code snippet | `language` (highlighting hint) |
| `math` | KaTeX math source | — |

`content_kind` is validated by a DB CHECK constraint
(`content_kind IN ('text','code','math')`) and by `normalize_content_kind()`.

## SnippetService API

A snippet spans two tables, written atomically in a single transaction:

| Method | Description |
|--------|-------------|
| `assign(content_kind, content, **kw)` | Create `dois` row + `snippets` row atomically |
| `resolve(doi, include_redirects=True)` | Resolve DOI (prefix matching), merge snippet row if present |
| `modify(doi, **changes)` | Update snippet fields; `""` clears a field (e.g. `source_doi`) |
| `delete(doi)` | Tombstone BOTH rows (`deleted_at`) in one transaction |

Key invariants:

1. **Atomicity** — `assign()` inserts `dois` + `snippets` rows in one
   `db.transaction()`; a crash never leaves a snippet-DOI without content.
   `DOIService.create()` must NOT be nested inside another transaction
   (sqlite3 forbids nested `BEGIN`).
2. **Source validation** — `source_doi` must reference an existing, active
   (non-tombstoned) DOI. Missing/tombstoned → `SnippetSourceNotFoundError`.
3. **Missing DOI → `DOINotFoundError`** (reused from the DOI module); a DOI
   that exists but has no snippet row → `SnippetNotFoundError`.
4. **Tombstone** — `delete()` sets `deleted_at` on both rows; resolution
   returns `status='tombstone'`.

## Unified Search

Snippet content is searchable through the SAME search box as DOIs:

- `snippets_fts` is an FTS5 external-content table on `snippets`, synced by
  triggers (same pattern as `dois_fts`).
- `DBDOIService._search_fts()` (in `db/service.py`) runs the MATCH query
  against **both** `dois_fts` and `snippets_fts`, merges results by DOI
  (dedup, cap at `limit`). Snippet hits carry an extra `content_kind` key so
  the frontend can render them distinctly.
- `_record_to_response()` (doi_routes) and `_record_to_public()`
  (public_routes) pass `content_kind` through when present.

## API Surface

| Endpoint | Permission | Notes |
|----------|-----------|-------|
| `POST /api/v1/snippet` | edit | assign (201) |
| `GET /api/v1/snippet/{doi:path}` | read_only | resolve + snippet fields |
| `PUT /api/v1/snippet/{doi:path}` | edit | modify |
| `DELETE /api/v1/snippet/{doi:path}` | edit | tombstone (204) |
| `GET /public/v1/snippet/{doi:path}` | none | public content for embeds (rate-limited) |

The public endpoint returns 410 for tombstoned snippets and 404 for
non-snippet DOIs. Citation formatting of snippet DOIs returns a 400
(guarded in `CitationFormatter.format()`).

## CLI

```
ronzzdoi snippet assign --type {text,code,math} --content "..." \
    [--title ... --language ... --source-doi ... --page-start ... --page-end ...]
ronzzdoi snippet resolve <doi>
ronzzdoi snippet modify <doi> [--content ... --type ... --source-doi ...]
ronzzdoi snippet delete <doi>
ronzzdoi snippet embed <doi> [--width 640 --height 240] [--url-only] [--base URL]
```

`--type` selects the content kind (mirrors the GUI toggle).
`embed` prints a copy-paste `<iframe>` tag pointing at the public-web
embed page (`https://doi.ronzz.org/embed/<doi>` by default, overridable
via `--base` or the `RONZZDOI_EMBED_BASE` env var).  `--url-only`
prints just the embed URL for JS-based embeds.

## GUI

`!snippet assign` opens a form (`FormTab` case `snippet-assign`) with a
**segmented Text/Code/Math toggle** that conditionally shows:

- `code` → language field
- `text` → source DOI + page start/end fields

`!snippet assign` and `!snippet resolve` return the `snippet` tab type,
rendered by `SnippetTab.svelte` with a **Copy Embed** button that copies
the iframe tag to the clipboard.  The embed base URL can be overridden
for development via `localStorage["ronzzdoi_embed_base"]`.

The command tree is backend-driven — `!snippet resolve|modify|delete` get
autocomplete automatically from the registered `@command` decorators.

## Tests

- `tests/test_snippet_service.py` — service lifecycle + unified search
- `tests/test_snippet_routes.py` — HTTP routes, permissions, public endpoint
- `tests/test_cli_snippet.py` — CLI embed/assign/resolve (MockTransport)
- `tests/test_db.py::TestSchema` — snippets table/triggers/indexes + CHECK
- `tests/e2e_gui_smoke.mjs` — GUI toggle, snippet tab, Copy Embed clipboard

Run: `./scripts/test.sh tests/test_snippet_service.py tests/test_snippet_routes.py tests/test_cli_snippet.py -v`

## Embed Rendering (ronzzdoi-public-web)

The `ronzzdoi-public-web` repo renders snippet DOIs and serves the embed
fragments:

- `QuotationView.astro` — detail-page rendering (content + attribution +
  copyable embed tag via the `EmbedCode` Svelte island)
- `src/pages/embed/[...doi].astro` — the iframe fragment page
  (`/embed/10.ronzz/<suffix>`), standalone (no site chrome, no scripts),
  with `?theme=dark`, `?cite=0`, `?title=` options
- `src/lib/snippetEmbed.ts` — shared server-side rendering:
  - text → HTML-escaped `blockquote` (XSS-safe by construction)
  - code → shiki syntax highlighting (server-side, escaped)
  - math → KaTeX `renderToString`, falling back to escaped source on error
- Headers: `Cross-Origin-Resource-Policy: cross-origin`,
  `Content-Security-Policy: default-src 'none'; …`, and
  `Cache-Control: public, max-age=60, s-maxage=300` so edits propagate to
  embeds within ~5 minutes.
- nginx: the `/embed/` location replaces the global `X-Frame-Options:
  DENY` with `Content-Security-Policy: frame-ancestors *` (framing is
  governed by CSP instead).

The embed data comes from `GET /public/v1/snippet/{doi}`.

## Production Access

Snippets are created against the **write** API, `https://doi-admin.ronzz.org`
(key-protected, see root AGENTS.md → Deployment):

```bash
export RONZZDOI_SERVER=https://doi-admin.ronzz.org
export RONZZDOI_API_KEY=<admin key>
ronzzdoi snippet assign --type code --content "print('hi')" --language python
```

The resulting DOI is served publicly without a key:
`https://doi.ronzz.org/embed/10.ronzz/<suffix>`.
