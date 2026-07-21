"""Tests for ronzzdoi's DB module — schema, services, search."""

from __future__ import annotations

import sqlite3

import pytest

from lightercore.db import LighterDB
from lightercore.exceptions import DataError

from ronzzdoi.db.schema import MIGRATIONS
from ronzzdoi.db.service import DOIService, RedirectService


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
def red_svc(db):
    return RedirectService(db)


# ── Schema tests ──────────────────────────────────────────────────────


class TestSchema:
    """Verify all tables and indexes are created correctly."""

    def test_all_tables_exist(self, db):
        tables = [
            "dois", "redirects", "dois_fts",
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
            "metadata_json": '{"author": "John Smith"}',
        })
        doi_svc.create({
            "doi": "10.ronzz/books/2024/jones",
            "target_url": "https://example.com/jones",
            "title": "Data Science with Python",
            "metadata_json": '{"author": "Alice Jones"}',
        })

        results = doi_svc.search_fts("python")
        assert len(results) >= 2  # both match "Python" in title

        results = doi_svc.search_fts("Data")
        assert len(results) >= 1

    def test_search_fts_empty_query(self, doi_svc):
        """Empty query returns empty list, not all rows."""
        assert doi_svc.search_fts("") == []
        assert doi_svc.search_fts("   ") == []

    def test_search_fts_exact_phrase(self, doi_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/test",
            "target_url": "https://example.com/test",
            "title": "Machine Learning for Beginners",
        })

        results = doi_svc.search_fts('"Machine Learning"')
        assert len(results) >= 1

    def test_search_fts_prefix(self, doi_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/test",
            "target_url": "https://example.com/test",
            "title": "Machine Learning Fundamentals",
        })

        results = doi_svc.search_fts("Machine*")
        assert len(results) >= 1

    def test_unified_search_defaults_to_fts(self, doi_svc):
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/smith",
            "title": "Python Programming",
        })

        results = doi_svc.search("python")
        assert len(results) >= 1

    def test_unified_search_semantic_fallback(self, doi_svc):
        """Semantic search falls back to FTS5 when vec not available."""
        doi_svc.create({
            "doi": "10.ronzz/books/2024/smith",
            "target_url": "https://example.com/smith",
            "title": "Python Programming",
        })

        # lightersearch not installed, so semantic should fall back to FTS5
        results = doi_svc.search("python", mode="semantic")
        assert len(results) >= 1


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
    def test_metadata_json_check(self, db):
        """metadata_json CHECK rejects non-JSON."""
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO dois (doi, target_url, metadata_json, created_at, updated_at) "
                "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
                ("10.ronzz/test/badjson", "https://x.com", "not-json"),
            )


# ── Lightersearch wiring tests ───────────────────────────────────────


class TestLightersearchWiring:
    """Tests for the lightersearch integration in DOIService.

    These tests verify that DOIService correctly probes, calls into,
    and falls back from lightersearch.  They use mocking to avoid
    requiring a full sqlite-vec + fastembed stack.
    """

    def test_probe_detects_lightersearch(self, db, mocker):
        """_probe_lightersearch sets _vec_available=True when lightersearch responds."""
        mock_available = mocker.patch("lightersearch.vec.available", return_value=True)
        svc = DOIService(db)
        assert svc._vec_available is True
        mock_available.assert_called_once_with(db)

    def test_probe_false_when_lightersearch_unavailable(self, db, mocker):
        """_probe_lightersearch sets _vec_available=False when lightersearch is missing."""
        mocker.patch("lightersearch.vec.available", side_effect=ImportError("no module"))
        svc = DOIService(db)
        assert svc._vec_available is False

    def test_probe_false_when_vec_not_loaded(self, db, mocker):
        """_probe_lightersearch sets _vec_available=False when vec.available returns False."""
        mocker.patch("lightersearch.vec.available", return_value=False)
        svc = DOIService(db)
        assert svc._vec_available is False

    def test_sync_embedding_calls_embed_and_insert(self, db, mocker):
        """_sync_embedding generates embedding and inserts into vec0 table."""
        # Create DOI first WITHOUT vec enabled (to avoid _post_create triggering)
        mocker.patch("lightersearch.vec.available", return_value=False)
        svc = DOIService(db)
        svc.create({
            "doi": "10.ronzz/test/sync",
            "target_url": "https://example.com",
            "title": "Test Title",
            "metadata_json": '{"author": "Test Creator"}',
        })

        # Now enable vec and set up mocks for the sync call
        svc._vec_available = True
        mock_embed = mocker.patch("lightersearch.embed.embed_single")
        mock_embed.return_value = __import__("numpy").array([0.1] * 384, dtype="float32")

        mock_to_bytes = mocker.patch("lightersearch.embed.vector_to_bytes")
        mock_to_bytes.return_value = b"fakevec"

        mock_insert = mocker.patch("lightersearch.vec.insert_vector")
        mock_insert.return_value = True

        svc._sync_embedding("10.ronzz/test/sync")

        # Should have been called with the title+metadata text
        call_text = mock_embed.call_args[0][0]
        assert "Test Title" in call_text

        mock_insert.assert_called_once()
        assert mock_insert.call_args[1]["vector"] == b"fakevec"

    def test_sync_embedding_noop_for_missing_doi(self, db, mocker):
        """_sync_embedding does nothing for a non-existent DOI."""
        mocker.patch("lightersearch.vec.available", return_value=True)
        svc = DOIService(db)
        svc._vec_available = True

        mock_embed = mocker.patch("lightersearch.embed.embed_single")
        svc._sync_embedding("10.ronzz/doesnotexist")
        mock_embed.assert_not_called()

    def test_sync_embedding_logs_on_failure(self, db, mocker):
        """_sync_embedding logs warning on failure, does not raise."""
        mocker.patch("lightersearch.vec.available", return_value=True)
        svc = DOIService(db)
        svc._vec_available = True

        svc.create({
            "doi": "10.ronzz/test/fail",
            "target_url": "https://example.com",
            "title": "Test",
        })

        mocker.patch("lightersearch.embed.embed_single", side_effect=RuntimeError("model fail"))
        mock_log = mocker.patch("logging.Logger.warning")

        # Should not raise
        svc._sync_embedding("10.ronzz/test/fail")
        mock_log.assert_called()

    def test_remove_embedding_calls_delete(self, db, mocker):
        """_remove_embedding calls delete_vector."""
        # Create DOI first WITHOUT vec enabled
        mocker.patch("lightersearch.vec.available", return_value=False)
        svc = DOIService(db)
        svc.create({
            "doi": "10.ronzz/test/rm",
            "target_url": "https://example.com",
        })

        # Now enable vec and set up mocks
        svc._vec_available = True
        mock_delete = mocker.patch("lightersearch.vec.delete_vector")
        svc._remove_embedding("10.ronzz/test/rm")
        mock_delete.assert_called_once()

    def test_remove_embedding_noop_for_missing_doi(self, db, mocker):
        """_remove_embedding does nothing for a non-existent DOI."""
        mocker.patch("lightersearch.vec.available", return_value=True)
        svc = DOIService(db)
        svc._vec_available = True

        mock_delete = mocker.patch("lightersearch.vec.delete_vector")
        svc._remove_embedding("10.ronzz/doesnotexist")
        mock_delete.assert_not_called()

    def test_search_semantic_delegates_to_lightersearch(self, db, mocker):
        """_search_semantic calls lightersearch.search.search_dois when available."""
        mocker.patch("lightersearch.vec.available", return_value=True)
        svc = DOIService(db)
        svc._vec_available = True

        mock_search = mocker.patch("lightersearch.search.search_dois")
        mock_search.return_value = [{"doi": "10.ronzz/result"}]

        results = svc._search_semantic("machine learning", limit=5)
        assert len(results) == 1
        assert results[0]["doi"] == "10.ronzz/result"
        mock_search.assert_called_once_with(db, "machine learning", limit=5)

    def test_search_semantic_returns_empty_on_error(self, db, mocker):
        """_search_semantic returns empty list when lightersearch.search fails."""
        mocker.patch("lightersearch.vec.available", return_value=True)
        svc = DOIService(db)
        svc._vec_available = True

        mocker.patch("lightersearch.search.search_dois", side_effect=RuntimeError("search fail"))
        results = svc._search_semantic("test")
        assert results == []

    def test_search_semantic_fallback_when_vec_not_available(self, db, mocker):
        """search(mode='semantic') falls back to FTS5 when vec not available."""
        mocker.patch("lightersearch.vec.available", return_value=False)
        svc = DOIService(db)

        svc.create({
            "doi": "10.ronzz/test/fallback",
            "target_url": "https://example.com",
            "title": "Python Programming",
        })

        # vec not available → should use FTS5
        mock_fts = mocker.spy(svc, "search_fts")
        results = svc.search("python", mode="semantic")
        assert len(results) >= 1
        mock_fts.assert_called_once()

    def test_post_create_triggers_sync(self, db, mocker):
        """_post_create calls _sync_embedding when vec is available."""
        mocker.patch("lightersearch.vec.available", return_value=True)
        svc = DOIService(db)
        svc._vec_available = True

        mock_sync = mocker.patch.object(svc, "_sync_embedding")
        svc._post_create(
            {"doi": "10.ronzz/test/pc"},
            {"doi": "10.ronzz/test/pc"},
        )
        mock_sync.assert_called_once_with("10.ronzz/test/pc")

    def test_post_update_triggers_sync(self, db, mocker):
        """_post_update calls _sync_embedding when vec is available."""
        mocker.patch("lightersearch.vec.available", return_value=True)
        svc = DOIService(db)
        svc._vec_available = True

        mock_sync = mocker.patch.object(svc, "_sync_embedding")
        svc._post_update("10.ronzz/test/pu", None, {})
        mock_sync.assert_called_once_with("10.ronzz/test/pu")

    def test_post_delete_triggers_remove(self, db, mocker):
        """_post_delete calls _remove_embedding when vec is available."""
        mocker.patch("lightersearch.vec.available", return_value=True)
        svc = DOIService(db)
        svc._vec_available = True

        mock_remove = mocker.patch.object(svc, "_remove_embedding")
        svc._post_delete("10.ronzz/test/pd", None)
        mock_remove.assert_called_once_with("10.ronzz/test/pd")

    def test_post_hooks_noop_without_vec(self, db, mocker):
        """Post hooks do nothing when vec is not available."""
        mocker.patch("lightersearch.vec.available", return_value=False)
        svc = DOIService(db)
        assert svc._vec_available is False

        mock_sync = mocker.patch.object(svc, "_sync_embedding")
        mock_rm = mocker.patch.object(svc, "_remove_embedding")

        svc._post_create({"doi": "x"}, {"doi": "x"})
        svc._post_update("x", None, {})
        svc._post_delete("x", None)

        mock_sync.assert_not_called()
        mock_rm.assert_not_called()


# ── init_db() integration test ───────────────────────────────────────


class TestInitDB:
    def test_init_db_creates_database(self, tmp_path, mocker):
        """init_db() creates a database file and returns all services."""
        # Mock paths to use tmpdir
        mock_data_dir = tmp_path / "data"
        mock_data_dir.mkdir()
        mocker.patch("ronzzdoi.db.data_dir", return_value=mock_data_dir)
        mocker.patch("ronzzdoi.db.ensure_dirs")
        mocker.patch("ronzzdoi.db.set_app_name")

        from ronzzdoi.db import init_db

        db, doi_svc, red_svc = init_db("test_ronzzdoi")

        assert (mock_data_dir / "ronzzdoi.db").exists()
        assert db.table_exists("dois")
        assert not db.table_exists("citations")
        assert db.table_exists("redirects")
        assert isinstance(doi_svc, DOIService)
        assert isinstance(red_svc, RedirectService)

    def test_init_db_creates_vec_table_when_lightersearch_available(self, tmp_path, mocker):
        """init_db() creates vec_dois when lightersearch is installed."""
        mock_data_dir = tmp_path / "data"
        mock_data_dir.mkdir()
        mocker.patch("ronzzdoi.db.data_dir", return_value=mock_data_dir)
        mocker.patch("ronzzdoi.db.ensure_dirs")
        mocker.patch("ronzzdoi.db.set_app_name")

        # Ensure _after_connect runs (lightersearch is installed in this env)
        from ronzzdoi.db import init_db

        db, doi_svc, red_svc = init_db("test_ronzzdoi_vec")

        # vec_dois should exist only if sqlite-vec extension loaded
        from lightersearch.vec import available as vec_available

        if vec_available(db):
            assert db.table_exists("vec_dois")

    def test_get_db_singleton(self, tmp_path, mocker):
        """get_db() returns the same instances on second call."""
        mock_data_dir = tmp_path / "data"
        mock_data_dir.mkdir()
        mocker.patch("ronzzdoi.db.data_dir", return_value=mock_data_dir)
        mocker.patch("ronzzdoi.db.ensure_dirs")
        mocker.patch("ronzzdoi.db.set_app_name")

        from ronzzdoi.db import get_db, _db_state

        _db_state.clear()

        db1, doi1, red1 = get_db("test_singleton")
        db2, doi2, red2 = get_db("test_singleton")

        assert db1 is db2
        assert doi1 is doi2
        assert red1 is red2
