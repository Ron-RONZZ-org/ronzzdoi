# DB Module — AGENTS-db

## Overview

The DB module (`src/ronzzdoi/db/`) is the data foundation for ronzzdoi. It provides:

- **Schema definitions** — SQLite tables for DOIs, citations, redirects, plus FTS5 full-text search
- **Migration engine** — forward-only schema versioning via `LighterDB.migrate()` (from lightercore)
- **Service classes** — `DOIService`, `CitationService`, `RedirectService` extending lightercore's `CRUDService`
- **Application lifecycle** — `init_db()` / `get_db()` for FastAPI startup

## Source Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | `init_db()` factory, `get_db()` singleton, public API exports |
| `schema.py` | `V1` SQL script + `MIGRATIONS` ordered list |
| `service.py` | `DOIService`, `CitationService`, `RedirectService` |

## Key Design Decisions

### FTS5 via SQL triggers (not app-level hooks)

The `dois_fts` virtual table is declared as `content='dois'` (external content). Three triggers (`AFTER INSERT`, `AFTER DELETE`, `AFTER UPDATE`) keep the FTS index in sync. This ensures search consistency regardless of whether writes happen through the service layer or direct SQL.

### DOI PK: exact match, not prefix

`DOIService.get()` overrides `CRUDService.get()` to use `= ?` instead of `LIKE ?` — DOIs are exact identifiers per the DOI Handbook and prefix matching could return the wrong DOI.

### DOI creation requires explicit `doi` value

`DOIService.create()` raises `DataError` if no `doi` key is provided, preventing the CRUDService fallback that would silently generate a UUID as the DOI.

### Lightersearch integration point

`DOIService` probes for `sqlite-vec` on init and sets `self._vec_available`. The `_post_create`/`_post_update`/`_post_delete` hooks call `_sync_embedding()` / `_remove_embedding()` when vec is available. The actual embedding logic will be implemented when the `lightersearch` repo is created.

## Schema (v1)

```
dois (doi PK, target_url, title, creator, doi_type, metadata_json, created_at, updated_at, deleted_at)
  │
  ├── citations (citation_id PK, doi FK→dois, doc_type, fields_json, created_at, updated_at)
  │
  └── redirects (redirect_id PK, doi FK→dois, old_url, note, created_at, updated_at)
```

## Adding a Migration

```python
# In src/ronzzdoi/db/schema.py
MIGRATIONS.append((2, "ALTER TABLE dois ADD COLUMN language TEXT DEFAULT 'en'"))
```

## Testing

```bash
PYTHONPATH=src python -m pytest tests/test_db.py -v
```

The test suite uses a fresh in-memory database per test (via `tmp_path` fixture). All 26 tests cover schema creation, CRUD operations, FTS5 search, foreign key enforcement, and CHECK constraints.
