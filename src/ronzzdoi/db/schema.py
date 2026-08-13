"""SQL schema definitions and migration list for ronzzdoi.

The initial migration (version 1) creates all core tables, indexes, and
FTS5 virtual tables with content-sync triggers.

To upgrade an existing database, add new entries to ``MIGRATIONS``::

    MIGRATIONS = [
        (1, V1),
        (2, "ALTER TABLE dois ADD COLUMN language TEXT DEFAULT 'en'"),
    ]
"""

from __future__ import annotations

V1 = """
-- ═══════════════════════════════════════════════════════════════════
-- Version 1 — v0.1.0 initial schema (aligned with citation spec #4)
-- ═══════════════════════════════════════════════════════════════════

-- Core DOI table
-- Citation data lives in metadata_json (per doc_type schema).
-- Entity DOIs (person, abstract_entity, country) have target_url=NULL.
CREATE TABLE IF NOT EXISTS dois (
    doi           TEXT PRIMARY KEY,
    target_url    TEXT,
    title         TEXT DEFAULT '',
    doi_type      TEXT NOT NULL DEFAULT 'external',
    metadata_json TEXT DEFAULT '{}'
                  CHECK (json_valid(metadata_json)),
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    deleted_at    TEXT
);

-- Redirect history (track URL changes for a DOI)
CREATE TABLE IF NOT EXISTS redirects (
    redirect_id   TEXT PRIMARY KEY,
    doi           TEXT NOT NULL REFERENCES dois(doi) ON DELETE CASCADE,
    old_url       TEXT NOT NULL,
    note          TEXT DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- FTS5 virtual table (external content on dois)
-- Content is synced via triggers below; no separate storage.
CREATE VIRTUAL TABLE IF NOT EXISTS dois_fts USING fts5(
    doi, title, metadata_json,
    content='dois',
    content_rowid='rowid'
);

-- FTS5 sync triggers — keep dois_fts in sync with dois
CREATE TRIGGER IF NOT EXISTS dois_fts_insert
AFTER INSERT ON dois BEGIN
    INSERT INTO dois_fts(rowid, doi, title, metadata_json)
    VALUES (new.rowid, new.doi, new.title, new.metadata_json);
END;

CREATE TRIGGER IF NOT EXISTS dois_fts_delete
AFTER DELETE ON dois BEGIN
    INSERT INTO dois_fts(dois_fts, rowid, doi, title, metadata_json)
    VALUES ('delete', old.rowid, old.doi, old.title, old.metadata_json);
END;

CREATE TRIGGER IF NOT EXISTS dois_fts_update
AFTER UPDATE ON dois BEGIN
    INSERT INTO dois_fts(dois_fts, rowid, doi, title, metadata_json)
    VALUES ('delete', old.rowid, old.doi, old.title, old.metadata_json);
    INSERT INTO dois_fts(rowid, doi, title, metadata_json)
    VALUES (new.rowid, new.doi, new.title, new.metadata_json);
END;

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_redirects_doi       ON redirects(doi);
CREATE INDEX IF NOT EXISTS idx_dois_deleted_at     ON dois(deleted_at);
CREATE INDEX IF NOT EXISTS idx_dois_created_at     ON dois(created_at);
"""

V2 = """
-- ═══════════════════════════════════════════════════════════════════
-- Version 2 — embeddable snippets (quotations, code, KaTeX math)
-- ═══════════════════════════════════════════════════════════════════

-- Snippet content lives in its own table, separate from citation
-- metadata.  Each snippet is a DOI (dois.doi_type='snippet',
-- target_url=NULL) with a parallel row here carrying the content.
CREATE TABLE IF NOT EXISTS snippets (
    doi          TEXT PRIMARY KEY REFERENCES dois(doi) ON DELETE CASCADE,
    content_kind TEXT NOT NULL CHECK (content_kind IN ('text','code','math')),
    content      TEXT NOT NULL,
    language     TEXT DEFAULT '',
    source_doi   TEXT REFERENCES dois(doi),
    page_start   TEXT DEFAULT '',
    page_end     TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    deleted_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_snippets_source_doi ON snippets(source_doi);
CREATE INDEX IF NOT EXISTS idx_snippets_deleted_at ON snippets(deleted_at);

-- FTS5 virtual table (external content on snippets) — unified search:
-- snippet content is findable through the same search box as DOIs.
CREATE VIRTUAL TABLE IF NOT EXISTS snippets_fts USING fts5(
    doi, content, language,
    content='snippets',
    content_rowid='rowid'
);

-- FTS5 sync triggers — keep snippets_fts in sync with snippets
CREATE TRIGGER IF NOT EXISTS snippets_fts_insert
AFTER INSERT ON snippets BEGIN
    INSERT INTO snippets_fts(rowid, doi, content, language)
    VALUES (new.rowid, new.doi, new.content, new.language);
END;

CREATE TRIGGER IF NOT EXISTS snippets_fts_delete
AFTER DELETE ON snippets BEGIN
    INSERT INTO snippets_fts(snippets_fts, rowid, doi, content, language)
    VALUES ('delete', old.rowid, old.doi, old.content, old.language);
END;

CREATE TRIGGER IF NOT EXISTS snippets_fts_update
AFTER UPDATE ON snippets BEGIN
    INSERT INTO snippets_fts(snippets_fts, rowid, doi, content, language)
    VALUES ('delete', old.rowid, old.doi, old.content, old.language);
    INSERT INTO snippets_fts(rowid, doi, content, language)
    VALUES (new.rowid, new.doi, new.content, new.language);
END;
"""


MIGRATIONS: list[tuple[int, str]] = [
    (1, V1),
    (2, V2),
]
"""Ordered list of ``(version, SQL)`` tuples for :meth:`LighterDB.migrate`.

Add new migrations by appending to this list:
``MIGRATIONS.append((2, \"ALTER TABLE ...\"))``
"""
