# AGENTS-citation.md — Citation Module

## Overview

The citation module provides a **formatting-only** service (`CitationFormatter`) that reads DOI metadata and returns styled citation text. No separate citation storage — the DOI's `doi_type` + `metadata_json` are the citation source.

## Architecture

```
CitationFormatter(doi_service)
├── format(doi, style) -> str           # formatted citation string
├── available_styles() -> [str]         # ["apa", "vancouver", "json"]
└── validate_doi_metadata(doi) -> [str] # missing required fields
```

## Files

| File | Purpose |
|------|---------|
| `formatter.py` | `CitationFormatter` class — resolves DOIs, delegates to style formatters, caches person/entity lookups per call |
| `styles.py` | Style formatters (`format_apa`, `format_vancouver`, `format_json`) and helpers for name/authority resolution |
| `schemas.py` | `DOC_TYPE_SCHEMAS` — required/optional fields for all 17 doc_types; `validate_metadata()` function |

## Doc Types (17 total)

**External (10):** book, bookSection, scientificPaper, conferencePaper, presentation, report, dataset, webpage, magazineArticle, newspaperArticle

**Media (4):** film, podcast, song, media

**Internal (3):** circulaire, rulebook, document

**Entity types (3, not citable):** person, abstract_entity, country

## Citation Source

The citation data lives in the DOI record's `metadata_json` column. The `doi_type` field determines the format. Authors and issuing authorities are person/entity DOIs resolved at format time via `DOIService.resolve()`.

## Styles

| Style | Function | Notes |
|-------|----------|-------|
| `apa` | `format_apa()` | APA 7th edition. Author names: `Last, F.` |
| `vancouver` | `format_vancouver()` | Vancouver style. Author names: `Last F` |
| `json` | `format_json()` | JSON blob with resolved names |

## Resolution Cache

Person/entity DOIs (`person_doi`, `issuing_authority_doi`, `book_doi`) are resolved via `DOIService.resolve()` and cached in a per-`format()` call dict to avoid N+1 lookups.

## Schema Dependencies

- `dois` table: `target_url` is nullable (NULL for entity DOIs)
- `doi_type` is free-text (no CHECK constraint)
- No `citations` table (no separate citation storage)
- No `creator` column on `dois`
