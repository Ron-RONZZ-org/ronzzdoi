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

## Dependencies

- **Requires**: `lightercore` (LighterDB, CRUDService)
- **Depends on schema**: `dois` and `redirects` tables (defined in DB module)
- **Imported by**: CLI module, Server module, Citation module
