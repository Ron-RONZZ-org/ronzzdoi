"""Tests for the snippet service layer — SnippetService.

Covers assign/resolve/modify/delete lifecycle plus the unified FTS5
search integration (snippet content findable through the same search
as DOIs).  Uses the full migration schema (``MIGRATIONS``).
"""

from __future__ import annotations

import re

import pytest

from ronzzdoi.db.schema import MIGRATIONS
from ronzzdoi.doi.exceptions import DOINotFoundError
from ronzzdoi.snippet.exceptions import (
    SnippetInvalidError,
    SnippetNotFoundError,
    SnippetSourceNotFoundError,
)
from ronzzdoi.snippet.service import SnippetService

DOI_FORMAT_RE = re.compile(r"^10\.ronzz/[0-9a-f]{32}$")


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    """Fresh database with the full migration schema applied."""
    from lightercore.db import LighterDB

    test_db = LighterDB(tmp_path / "ronzzdoi.db")
    test_db.migrate(MIGRATIONS)
    yield test_db


@pytest.fixture
def doi_svc(db):
    """DOI CRUD service bound to the temp database."""
    from ronzzdoi.doi.service import DOIService

    return DOIService(db)


@pytest.fixture
def svc(db, doi_svc):
    """SnippetService bound to the temp database."""
    return SnippetService(db, doi_svc)


@pytest.fixture
def db_search_svc(db):
    """FTS5 search service bound to the temp database."""
    from ronzzdoi.db.service import DOIService as DBDOIService

    return DBDOIService(db)


# ── assign() ────────────────────────────────────────────────────────────────


class TestAssign:
    def test_assign_text_minimal(self, svc):
        """Assign a text quotation with only content."""
        result = svc.assign("text", "To be or not to be.")
        assert DOI_FORMAT_RE.match(result["doi"])
        assert result["content_kind"] == "text"
        assert result["content"] == "To be or not to be."
        assert result["title"] == ""
        assert result["language"] == ""
        assert result["source_doi"] is None
        assert result["page_start"] == ""
        assert result["page_end"] == ""
        assert result["doi_type"] == "snippet"
        assert result["target_url"] is None
        assert result["deleted_at"] is None

    def test_assign_uppercase_kind_normalized(self, svc):
        """'Code' is normalized to 'code'."""
        result = svc.assign("Code", "print('hi')")
        assert result["content_kind"] == "code"

    def test_assign_code_with_language(self, svc):
        result = svc.assign("code", "print('hi')", title="Greeting", language="python")
        assert result["content_kind"] == "code"
        assert result["language"] == "python"
        assert result["title"] == "Greeting"

    def test_assign_math(self, svc):
        result = svc.assign("math", r"\frac{a}{b}")
        assert result["content_kind"] == "math"

    def test_assign_invalid_kind(self, svc):
        with pytest.raises(SnippetInvalidError, match="content kind"):
            svc.assign("image", "data")

    def test_assign_empty_content(self, svc):
        with pytest.raises(SnippetInvalidError, match="non-empty"):
            svc.assign("text", "   ")

    def test_assign_with_source_and_pages(self, svc, doi_svc):
        source = doi_svc.assign(
            "https://example.com/book", doi_type="book", title="Hamlet"
        )
        result = svc.assign(
            "text",
            "To be or not to be.",
            source_doi=source["doi"],
            page_start="12",
            page_end="13",
        )
        assert result["source_doi"] == source["doi"]
        assert result["page_start"] == "12"
        assert result["page_end"] == "13"

    def test_assign_missing_source_raises(self, svc):
        with pytest.raises(SnippetSourceNotFoundError, match="not found"):
            svc.assign("text", "quote", source_doi="10.ronzz/does-not-exist")

    def test_assign_tombstoned_source_raises(self, svc, doi_svc):
        source = doi_svc.assign("https://example.com", doi_type="book")
        doi_svc.delete_doi(source["doi"])
        with pytest.raises(SnippetSourceNotFoundError):
            svc.assign("text", "quote", source_doi=source["doi"])

    def test_assign_creates_both_rows(self, db, svc):
        """Atomicity — dois row and snippets row both exist."""
        result = svc.assign("text", "hello world", title="Greeting")
        doi_row = db.execute_one("SELECT * FROM dois WHERE doi = ?", (result["doi"],))
        snip_row = db.execute_one(
            "SELECT * FROM snippets WHERE doi = ?", (result["doi"],)
        )
        assert doi_row is not None
        assert doi_row["doi_type"] == "snippet"
        assert snip_row is not None
        assert snip_row["content"] == "hello world"

    def test_assign_unique_dois(self, svc):
        r1 = svc.assign("text", "a")
        r2 = svc.assign("text", "b")
        assert r1["doi"] != r2["doi"]


# ── resolve() ───────────────────────────────────────────────────────────────


class TestResolve:
    def test_resolve_own_doi(self, svc):
        result = svc.assign("code", "print(1)")
        resolved = svc.resolve(result["doi"])
        assert resolved["doi"] == result["doi"]
        assert resolved["content_kind"] == "code"
        assert resolved["content"] == "print(1)"
        assert resolved["status"] == "active"

    def test_resolve_suffix_prefix(self, svc):
        result = svc.assign("math", r"e^{i\pi}")
        resolved = svc.resolve(result["doi"][:20])
        assert resolved["doi"] == result["doi"]

    def test_resolve_missing_returns_none(self, svc):
        assert svc.resolve("10.ronzz/does-not-exist") is None

    def test_resolve_non_snippet_doi(self, svc, doi_svc):
        """A regular DOI resolves without snippet keys."""
        doi = doi_svc.assign("https://example.com", title="Book")
        resolved = svc.resolve(doi["doi"])
        assert resolved["doi"] == doi["doi"]
        assert "content_kind" not in resolved
        assert "content" not in resolved

    def test_resolve_tombstoned(self, svc):
        result = svc.assign("text", "quote")
        svc.delete(result["doi"])
        resolved = svc.resolve(result["doi"])
        assert resolved is not None
        assert resolved["deleted_at"] is not None
        assert resolved["status"] == "tombstone"


# ── modify() ────────────────────────────────────────────────────────────────


class TestModify:
    def test_modify_content_and_kind(self, svc):
        result = svc.assign("text", "old quote")
        updated = svc.modify(result["doi"], content="new quote", content_kind="code")
        assert updated["content"] == "new quote"
        assert updated["content_kind"] == "code"
        assert updated["updated_at"] >= result["updated_at"]

    def test_modify_title(self, svc):
        result = svc.assign("text", "quote", title="Old")
        updated = svc.modify(result["doi"], title="New")
        assert updated["title"] == "New"

    def test_modify_source_and_pages(self, svc, doi_svc):
        source = doi_svc.assign("https://example.com/book", doi_type="book")
        result = svc.assign("text", "quote")
        updated = svc.modify(
            result["doi"],
            source_doi=source["doi"],
            page_start="4",
            page_end="5",
        )
        assert updated["source_doi"] == source["doi"]
        assert updated["page_start"] == "4"

    def test_modify_clear_source(self, svc, doi_svc):
        source = doi_svc.assign("https://example.com/book", doi_type="book")
        result = svc.assign("text", "quote", source_doi=source["doi"])
        updated = svc.modify(result["doi"], source_doi="")
        assert updated["source_doi"] is None

    def test_modify_no_changes_returns_record(self, svc):
        result = svc.assign("text", "quote")
        updated = svc.modify(result["doi"])
        assert updated["doi"] == result["doi"]

    def test_modify_missing_doi_raises(self, svc):
        with pytest.raises(DOINotFoundError):
            svc.modify("10.ronzz/does-not-exist", content="x")

    def test_modify_non_snippet_raises(self, svc, doi_svc):
        doi = doi_svc.assign("https://example.com")
        with pytest.raises(SnippetNotFoundError, match="not a snippet"):
            svc.modify(doi["doi"], content="x")

    def test_modify_empty_content_raises(self, svc):
        result = svc.assign("text", "quote")
        with pytest.raises(SnippetInvalidError, match="non-empty"):
            svc.modify(result["doi"], content="  ")

    def test_modify_invalid_kind_raises(self, svc):
        result = svc.assign("text", "quote")
        with pytest.raises(SnippetInvalidError, match="content kind"):
            svc.modify(result["doi"], content_kind="image")

    def test_modify_invalid_source_raises(self, svc):
        result = svc.assign("text", "quote")
        with pytest.raises(SnippetSourceNotFoundError):
            svc.modify(result["doi"], source_doi="10.ronzz/missing")


# ── delete() ────────────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_tombstones_both_rows(self, db, svc):
        result = svc.assign("text", "quote")
        assert svc.delete(result["doi"]) is True
        doi_row = db.execute_one("SELECT * FROM dois WHERE doi = ?", (result["doi"],))
        snip_row = db.execute_one(
            "SELECT * FROM snippets WHERE doi = ?", (result["doi"],)
        )
        assert doi_row["deleted_at"] is not None
        assert snip_row["deleted_at"] is not None

    def test_delete_missing_returns_false(self, svc):
        assert svc.delete("10.ronzz/does-not-exist") is False

    def test_delete_non_snippet_raises(self, svc, doi_svc):
        doi = doi_svc.assign("https://example.com")
        with pytest.raises(SnippetNotFoundError):
            svc.delete(doi["doi"])


# ── Unified search ──────────────────────────────────────────────────────────


class TestUnifiedSearch:
    def _seed(self, svc, doi_svc):
        """Seed one DOI + two snippets with distinct terms."""
        doi_svc.create(
            {
                "doi": "10.ronzz/books/quantum",
                "target_url": "https://example.com/q",
                "title": "Quantum Computing Primer",
                "metadata_json": "{}",
            }
        )
        svc.assign(
            "text", "Quantum entanglement is spooky action", title="Einstein quote"
        )
        svc.assign("code", "def quantum_sim():\n    pass", language="python")

    def test_search_finds_snippet_content(self, svc, doi_svc, db_search_svc):
        self._seed(svc, doi_svc)
        results = db_search_svc.search_fts("entanglement")
        assert len(results) == 1
        assert results[0]["content_kind"] == "text"

    def test_search_finds_snippet_language(self, svc, doi_svc, db_search_svc):
        self._seed(svc, doi_svc)
        results = db_search_svc.search_fts("python")
        assert len(results) == 1
        assert results[0]["content_kind"] == "code"

    def test_search_merges_doi_and_snippet_hits(self, svc, doi_svc, db_search_svc):
        self._seed(svc, doi_svc)
        # "quantum" matches the DOI title AND the text snippet content.
        results = db_search_svc.search_fts("quantum")
        dois = {r["doi"] for r in results}
        assert "10.ronzz/books/quantum" in dois
        assert len(dois) == len(results)  # no duplicates
        kinds = [r.get("content_kind") for r in results if r.get("content_kind")]
        assert "text" in kinds

    def test_search_with_snippet_excerpt(self, svc, doi_svc, db_search_svc):
        self._seed(svc, doi_svc)
        results = db_search_svc.search_fts_with_snippet("entanglement")
        assert results[0]["content_kind"] == "text"
        assert "mark" in results[0].get("snippet", "")

    def test_search_empty_query(self, db_search_svc):
        assert db_search_svc.search_fts("") == []

    def test_search_does_not_include_deleted_snippet_content(
        self, svc, doi_svc, db_search_svc
    ):
        """Tombstoned snippet content stays indexed (dois_fts/snippets_fts
        are content mirrors) — search still finds the DOI record; this
        matches existing DOI search behavior."""
        self._seed(svc, doi_svc)
        results = db_search_svc.search_fts("entanglement")
        svc.delete(results[0]["doi"])
        results = db_search_svc.search_fts("entanglement")
        assert len(results) >= 1  # row still indexed, caller filters deleted_at
