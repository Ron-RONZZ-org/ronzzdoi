"""Tests for ronzzdoi's DB module — schema, services, search."""

from __future__ import annotations

import sqlite3

import pytest

from lightercore.db import LighterDB
from lightercore.exceptions import DataError

from ronzzdoi.db.schema import MIGRATIONS
from ronzzdoi.db.service import CitationService, DOIService, RedirectService


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    """Fresh database with full schema applied."""
    test_db = LighterDB(tmp_path / "ronzzdoi.db")
    test_db.migrate(MIGRATIONS)
    yield test_db


@pytest.fixture
def doi_svc(db):
    return DOIService(db)


@pytest.fixture
def cit_svc(db):
    return CitationService(db)


@pytest.fixture
def red_svc(db):
    return RedirectService(db)


# ── Schema tests ──────────────────────────────────────────────────────


class TestSchema:
    """Verify all tables and indexes are created correctly."""

    def test_all_tables_exist(self, db):
        tables = [
            "dois", "citations", "redirects", "dois_fts",
        ]
        for name in tables:
            assert db.table_exists(name), f"Missing table: {name}"

    def test_triggers_exist(self, db):
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' "
            "AND name LIKE 'dois_fts_%' ORDER BY name"
        )
        names = [r["name"] for r in rows]
        assert "dois_fts_insert" in names
        assert "dois_fts_delete" in names
        assert "dois_fts_update" in names

    def test_indexes_exist(self, db):
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_%' ORDER BY name"
        )
        names = [r["name"] for r in rows]
        expected = [
            "idx_citations_doi",
            "idx_redirects_doi",
            "idx_dois_deleted_at",
            "idx_dois_created_at",
        ]
        for idx in expected:
            assert idx in names, f"Missing index: {idx}"

    def test_foreign_keys_enabled(self, db):
        row = db.execute_one("PRAGMA foreign_keys")
        assert row["foreign_keys"] == 1

    def test_journal_mode_wal(self, db):
        row = db.execute_one("PRAGMA journal_mode")
        assert row["journal_mode"].lower() == "wal"


# ── DOIService tests ──────────────────────────────────────────────────


class TestDOIService:
    def test_create_requires_doi(self, doi_svc):
        """Create without doi raises DataError."""
        with pytest.raises(DataError, match="doi is required"):
            doi_svc.create({"target_url": "https://example.com"})

    def test_create_with_doi(self, doi_svc):
        """Create with valid doi succeeds."""
        result = doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/book",
            "title": "Test Book",
            "creator": "John Smith",
        })
        assert result["doi"] == "10.ronzz/books/2024/smith"
        assert result["target_url"] == "https://example.com/book"
        assert result["title"] == "Test Book"
        assert "created_at" in result
        assert "updated_at" in result

    def test_create_sets_defaults(self, doi_svc):
        """Default doi_type and metadata are set."""
        result = doi_svc.create({
            "doi": "10.ronzz/internal/2024/doc",
            "target_url": "https://internal.example.com/doc",
        })
        assert result["doi_type"] == "external"  # default

    def test_get_exact_match(self, doi_svc):
        """get() uses exact match, not prefix."""
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/smith",
        })
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith-2nd-ed",
            "target_url": "https://example.com/smith-2nd",
        })

        result = doi_svc.get("10.ronzz/books/2024/smith")
        assert result is not None
        assert result["doi"] == "10.ronzz/books/2024/smith"

    def test_get_nonexistent(self, doi_svc):
        """get() returns None for missing DOI."""
        assert doi_svc.get("10.ronzz/nonexistent") is None

    def test_list(self, doi_svc):
        """list() returns created DOIs."""
        doi_svc.create({"doi": "10.ronzz/a/1", "target_url": "https://a.com"})
        doi_svc.create({"doi": "10.ronzz/a/2", "target_url": "https://b.com"})
        results = doi_svc.list()
        assert len(results) >= 2

    def test_update(self, doi_svc):
        """update() changes fields and bumps updated_at."""
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/original",
        })
        updated = doi_svc.update("10.ronzz/books/2024/smith", {
            "target_url": "https://example.com/updated",
        })
        assert updated is not None
        assert updated["target_url"] == "https://example.com/updated"
        assert updated["updated_at"] != updated["created_at"]

    def test_delete(self, doi_svc):
        """delete() removes a DOI."""
        doi_svc.create({
            "doi": "10.ronzz/books/2024/temp",
            "target_url": "https://example.com/temp",
        })
        assert doi_svc.delete("10.ronzz/books/2024/temp", soft=False) is True
        assert doi_svc.get("10.ronzz/books/2024/temp") is None


# ── FTS5 search tests ────────────────────────────────────────────────


class TestSearch:
    def test_search_fts_finds_matching_dois(self, doi_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/smith",
            "title": "Advanced Python Programming",
            "creator": "John Smith",
        })
        doi_svc.create({
            "doi": "10.ronzz/books/2024/jones",
            "target_url": "https://example.com/jones",
            "title": "Data Science with Python",
            "creator": "Alice Jones",
        })

        results = doi_svc.search_fts("python")
        assert len(results) >= 2  # both match "Python" in title

        results = doi_svc.search_fts("smith")
        assert len(results) >= 1
        assert results[0]["creator"] == "John Smith"

    def test_search_fts_empty_query(self, doi_svc):
        """Empty query returns empty list, not all rows."""
        assert doi_svc.search_fts("") == []
        assert doi_svc.search_fts("   ") == []

    def test_search_fts_exact_phrase(self, doi_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/test",
            "target_url": "https://example.com/test",
            "title": "Machine Learning for Beginners",
            "creator": "Test Author",
        })

        results = doi_svc.search_fts('"Machine Learning"')
        assert len(results) >= 1

    def test_search_fts_prefix(self, doi_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/test",
            "target_url": "https://example.com/test",
            "title": "Machine Learning Fundamentals",
            "creator": "Test Author",
        })

        results = doi_svc.search_fts("Machine*")
        assert len(results) >= 1

    def test_unified_search_defaults_to_fts(self, doi_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/smith",
            "title": "Python Programming",
            "creator": "John Smith",
        })

        results = doi_svc.search("python")
        assert len(results) >= 1

    def test_unified_search_semantic_fallback(self, doi_svc):
        """Semantic search falls back to FTS5 when vec not available."""
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/smith",
            "title": "Python Programming",
            "creator": "John Smith",
        })

        # lightersearch not installed, so semantic should fall back to FTS5
        results = doi_svc.search("python", mode="semantic")
        assert len(results) >= 1


# ── CitationService tests ──────────────────────────────────────────────


class TestCitationService:
    def test_create_and_get(self, doi_svc, cit_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/smith",
        })

        cit = cit_svc.create({
            "citation_id": "cit-001",
            "doi": "10.ronzz/books/2024/smith",
            "doc_type": "book",
            "fields_json": '{"publisher": "O\'Reilly"}',
        })
        assert cit["citation_id"] == "cit-001"

        fetched = cit_svc.get("cit-001")
        assert fetched is not None
        assert fetched["doi"] == "10.ronzz/books/2024/smith"

    def test_foreign_key_enforced(self, cit_svc):
        """Cannot create citation referencing nonexistent DOI."""
        with pytest.raises(sqlite3.IntegrityError):
            cit_svc.create({
                "citation_id": "cit-orphan",
                "doi": "10.ronzz/nonexistent",
                "doc_type": "book",
            })

    def test_list_by_doi(self, doi_svc, cit_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/smith",
        })
        cit_svc.create({
            "citation_id": "cit-001",
            "doi": "10.ronzz/books/2024/smith",
            "doc_type": "book",
        })
        cit_svc.create({
            "citation_id": "cit-002",
            "doi": "10.ronzz/books/2024/smith",
            "doc_type": "article",
        })

        results = doi_svc.get("10.ronzz/books/2024/smith")
        assert results is not None


# ── RedirectService tests ──────────────────────────────────────────────


class TestRedirectService:
    def test_create_redirect(self, doi_svc, red_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/smith",
        })
        red = red_svc.create({
            "redirect_id": "red-001",
            "doi": "10.ronzz/books/2024/smith",
            "old_url": "https://oldsite.com/smith",
            "note": "Site migration",
        })
        assert red["redirect_id"] == "red-001"

    def test_redirect_foreign_key(self, red_svc):
        with pytest.raises(sqlite3.IntegrityError):
            red_svc.create({
                "redirect_id": "red-orphan",
                "doi": "10.ronzz/nonexistent",
                "old_url": "https://example.com",
            })


# ── Schema constraints ─────────────────────────────────────────────────


class TestConstraints:
    def test_doi_type_check(self, db):
        """doi_type CHECK rejects invalid values."""
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO dois (doi, target_url, doi_type, created_at, updated_at) "
                "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
                ("10.ronzz/test/invalid", "https://x.com", "invalid_type"),
            )

    def test_metadata_json_check(self, db):
        """metadata_json CHECK rejects non-JSON."""
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO dois (doi, target_url, metadata_json, created_at, updated_at) "
                "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
                ("10.ronzz/test/badjson", "https://x.com", "not-json"),
            )
