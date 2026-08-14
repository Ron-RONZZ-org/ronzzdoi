# AGENTS-doi.md — DOI Module

## Module Overview

The DOI module (`src/ronzzdoi/doi/`) implements the core ronzzDOI lifecycle:
identifier generation, assignment, resolution, modification with soft redirect,
tombstone deletion, paginated listing, and merging.

## DOI Format

```
10.ronzz/<uuid4-hex>
```

- `10` — DOI directory indicator (DOI namespace, per Handbook)
- `ronzz` — registrant code for ronzz.org
- `<uuid4-hex>` — 32-character lowercase UUID4 hex (no dashes)

Total length: 41 characters.

## File Layout

```
src/ronzzdoi/doi/
├── __init__.py         # Public API exports
├── constants.py        # DOI_PREFIX, UUID4_HEX_LENGTH, regex patterns, validators
├── exceptions.py       # DOI-specific exception hierarchy
├── schema.py           # Pydantic models (DOIAssignRequest, DOIResponse, etc.)
└── service.py          # DOIService — core lifecycle management
```

## DOIService API

| Method | Description | Returns |
|--------|-------------|---------|
| `assign(url, **metadata)` | Create new DOI | dict (DOI record) |
| `resolve(doi)` | Look up by DOI (prefix matching) | dict or None |
| `modify(doi, **changes)` | Update fields, soft redirect on URL change | dict |
| `delete_doi(doi)` | Tombstone (set `deleted_at` in-place) | bool |
| `merge_dois(src, tgt)` | Merge source DOI into target | dict |
| `list_dois(limit, offset)` | Paginated listing (active only by default) | list[dict] |

## Key Behaviors

1. **Opaque identifier**: The DOI string carries no semantic meaning. All metadata
   (`doi_type`, `title`, `metadata_json`, etc.) is stored in database columns.
2. **Soft redirect**: When `target_url` changes, the old URL is recorded in the
   `redirects` table with a timestamp. Resolution includes the full redirect history.
3. **Tombstone deletion**: Deleting a DOI sets `deleted_at` but keeps the row,
   so resolution can return a 404-with-explanation rather than a bare 410.
4. **Prefix resolution**: `resolve()` and `modify()` accept short prefixes (LIKE
   matching). Ambiguous prefixes raise `DOIAmbiguousError` with the matching records.
5. **`doi_type` is free-text**: No enum validation — any string accepted and stored as-is.

## Exceptions

| Exception | Inherits From | Raised When |
|-----------|---------------|-------------|
| `DOIError` | `LighterError` | Base DOI error |
| `DOINotFoundError` | `DOIError` | DOI doesn't exist (or tombstoned) |
| `DOIExistsError` | `DOIError` | UUID collision (astronomically rare) |
| `DOIInvalidError` | `DOIError` | DOI format validation fails |
| `DOIAmbiguousError` | `DOIError` | Prefix matches multiple records |

## Server Response Layer (`server/doi_routes.py`)

`_record_to_response()` adds API-consumer conveniences on top of the
service records:

- **`resolve_url`** — when called with `base_url` (from `request.base_url`),
  a browser-resolvable URL `{base}/{doi}` is included (used by the GUI to
  link result tabs to the public web).
- **Multilingual titles** — a `title` stored as JSON text (`{"en": "…",
  "fr": "…"}`) is deserialized to a dict in API responses (idempotent for
  plain strings).  The same language-map form applies to **any pure-text
  metadata field** (e.g. a film's `title` or `studio`) — values inside
  `metadata_json` may be language maps, and citation styles render the
  **primary language** (the map's FIRST key; default `en`, settable per
  field in the GUI — e.g. `fr` for a French-original song title).
- **`content_kind`** — passed through on unified-search hits so the GUI can
  render snippet results distinctly.
- `GET /api/v1/doi/schemas` — serves the citation doc-type field schemas
  (`DOC_TYPE_SCHEMAS`) to drive the GUI's guided assign form.

## Dependencies

- **Requires**: `lightercore` (LighterDB, CRUDService)
- **Depends on schema**: `dois` and `redirects` tables (defined in DB module)
- **Imported by**: CLI module, Server module, Citation module

## API Response Shape

- **`resolve_url`**: DOI responses (`doi_routes._record_to_response` and the
  command endpoint's `_inject_resolve_url`) include a browser-resolvable URL
  (`<request base url>/<doi>`) so the GUI can copy/click a DOI that actually
  redirects when typed in a browser.
- **`GET /api/v1/doi/types`**: returns the supported `doi_type` values
  (citation `DOC_TYPES` + `ENTITY_TYPES` + `external`) and the per-type
  metadata field schemas from `citation.schemas.DOC_TYPE_SCHEMAS` **and
  `ENTITY_SCHEMAS`**, used by the GUI assign/modify form for its type
  dropdown and guided metadata input.  Entity types (person,
  abstract_entity, country) have guided schemas so no raw-JSON entry is
  needed.
- **`!doi assign` without a URL**: the URL is optional — entity DOIs
  (person, abstract_entity, country) are assigned with `target_url=NULL`.
  A bare `!doi assign` (no args) still returns the interactive form.
- **CLI `doi assign --metadata <json>`**: passes type-specific metadata as
  JSON, including language maps for pure-text fields, e.g.
  `--metadata '{"title": {"en": "...", "fr": "..."}}'`.
