"""Tests for the DOI service layer — DOIService.

Tests all operations through the public API (assign, resolve, modify,
delete_doi, list_dois) using an isolated SQLite temp database.
"""

from __future__ import annotations

import json
import re

import pytest

from ronzzdoi.doi.constants import DOI_PATTERN, is_valid_doi, is_doi_prefix
from ronzzdoi.doi.exceptions import DOIAmbiguousError, DOINotFoundError
from ronzzdoi.doi.service import DOIService

# ── Schema ──────────────────────────────────────────────────────────────────

DOI_SCHEMA = {
    "dois": """
        CREATE TABLE dois (
            doi           TEXT PRIMARY KEY,
            target_url    TEXT NOT NULL,
            title         TEXT DEFAULT '',
            creator       TEXT DEFAULT '',
            doi_type      TEXT NOT NULL DEFAULT 'external',
            metadata_json TEXT DEFAULT '{}',
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            deleted_at    TEXT
        )
    """,
    "redirects": """
        CREATE TABLE redirects (
            redirect_id TEXT PRIMARY KEY,
            doi         TEXT NOT NULL REFERENCES dois(doi) ON DELETE CASCADE,
            old_url     TEXT NOT NULL,
            note        TEXT DEFAULT '',
            created_at  TEXT NOT NULL
        )
    """,
}

DOI_FORMAT_RE = re.compile(r"^10\.ronzz/[0-9a-f]{32}$")


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    """Create a temporary SQLite database with DOI schema."""
    from lightercore.db import LighterDB

    db_path = tmp_path / "test_ronzzdoi.db"
    ldb = LighterDB(db_path)
    ldb.init_schema(DOI_SCHEMA)
    yield ldb
    ldb.close()


@pytest.fixture
def svc(db):
    """Create a DOIService bound to the temp database."""
    return DOIService(db)


# ── assign() ────────────────────────────────────────────────────────────────


class TestAssign:
    def test_assign_minimal(self, svc):
        """Assign with only target_url."""
        result = svc.assign("https://example.com")
        assert result["target_url"] == "https://example.com"
        assert DOI_FORMAT_RE.match(result["doi"])
        assert result["title"] == ""
        assert result["creator"] == ""
        assert result["doi_type"] == "external"
        assert result["metadata"] == {}
        assert result["created_at"]
        assert result["updated_at"]
        assert result["deleted_at"] is None

    def test_assign_full(self, svc):
        """Assign with all optional fields."""
        result = svc.assign(
            "https://example.org/doc",
            doi_type="circulaire",
            title="Annual Report 2025",
            creator="Rong Zhou",
            metadata={"lang": "en", "pages": 42},
        )
        assert result["target_url"] == "https://example.org/doc"
        assert result["doi_type"] == "circulaire"
        assert result["title"] == "Annual Report 2025"
        assert result["creator"] == "Rong Zhou"
        assert result["metadata"] == {"lang": "en", "pages": 42}
        assert DOI_FORMAT_RE.match(result["doi"])

    def test_assign_unique_dois(self, svc):
        """Each assign generates a unique DOI."""
        r1 = svc.assign("https://a.com")
        r2 = svc.assign("https://b.com")
        assert r1["doi"] != r2["doi"]

    def test_assign_generates_valid_format(self, svc):
        """Generated DOI matches 10.ronzz/<32-hex> format."""
        result = svc.assign("https://example.com")
        assert DOI_PATTERN.match(result["doi"])

    def test_doi_length(self, svc):
        """DOI string is 41 characters (10.ronzz/ + 32 hex)."""
        result = svc.assign("https://example.com")
        assert len(result["doi"]) == 41

    def test_assign_stores_in_db(self, svc):
        """Assigned DOI is queryable from the database."""
        result = svc.assign("https://example.com")
        row = svc.db.execute_one("SELECT * FROM dois WHERE doi = ?", (result["doi"],))
        assert row is not None
        assert row["target_url"] == "https://example.com"

    def test_assign_with_empty_metadata(self, svc):
        """Empty metadata dict is stored as empty object."""
        result = svc.assign("https://example.com", metadata={})
        assert result["metadata"] == {}

    def test_assign_with_none_metadata(self, svc):
        """None metadata is stored as empty object."""
        result = svc.assign("https://example.com", metadata=None)
        assert result["metadata"] == {}


# ── resolve() ───────────────────────────────────────────────────────────────


class TestResolve:
    def test_resolve_by_full_doi(self, svc):
        """Resolve by complete DOI string."""
        created = svc.assign("https://example.com", title="Test", metadata={"key": "val"})
        resolved = svc.resolve(created["doi"])
        assert resolved is not None
        assert resolved["doi"] == created["doi"]
        assert resolved["target_url"] == "https://example.com"
        assert resolved["title"] == "Test"
        assert resolved["metadata"] == {"key": "val"}
        assert resolved["status"] == "active"

    def test_resolve_by_prefix(self, svc):
        """Resolve by DOI prefix (short unique prefix)."""
        created = svc.assign("https://example.com")
        prefix = created["doi"][:20]  # first 20 chars: unique prefix
        resolved = svc.resolve(prefix)
        assert resolved is not None
        assert resolved["doi"] == created["doi"]

    def test_resolve_not_found(self, svc):
        """Non-existent DOI returns None."""
        assert svc.resolve("10.ronzz/00000000000000000000000000000000") is None

    def test_resolve_nonexistent_prefix(self, svc):
        """Non-existent DOI prefix returns None."""
        assert svc.resolve("10.ronzz/nonexistent") is None

    def test_resolve_ambiguous_prefix(self, svc):
        """Ambiguous prefix raises DOIAmbiguousError."""
        svc.assign("https://a.com")
        svc.assign("https://b.com")
        # Both DOIs start with "10.ronzz/" — this should raise
        with pytest.raises(DOIAmbiguousError) as exc:
            svc.resolve("10.ronzz/")
        assert "matches" in str(exc.value)

    def test_resolve_returns_redirect_history(self, svc):
        """Resolution includes redirect_history list."""
        created = svc.assign("https://original.com")
        resolved = svc.resolve(created["doi"])
        assert isinstance(resolved, dict)
        assert "redirect_history" in resolved
        assert isinstance(resolved["redirect_history"], list)

    def test_resolve_tombstoned_doi(self, svc):
        """Tombstoned DOI is still resolvable (returns record with deleted_at)."""
        created = svc.assign("https://example.com")
        svc.delete_doi(created["doi"])
        resolved = svc.resolve(created["doi"])
        assert resolved is not None
        assert resolved["deleted_at"] is not None
        assert resolved["status"] == "tombstone"

    def test_resolve_exact_match_preferred(self, svc):
        """When exact match exists, it takes priority over prefix match."""
        a = svc.assign("https://a.com")  # doi: 10.ronzz/abc...
        b = svc.assign("https://b.com")  # doi: 10.ronzz/def...
        # Exact match by full DOI should work
        resolved = svc.resolve(a["doi"])
        assert resolved is not None
        assert resolved["doi"] == a["doi"]


# ── modify() ────────────────────────────────────────────────────────────────


class TestModify:
    def test_modify_url(self, svc):
        """Changing target_url updates it and creates redirect record."""
        created = svc.assign("https://original.com")
        updated = svc.modify(created["doi"], target_url="https://new.com")
        assert updated["target_url"] == "https://new.com"
        # Verify redirect was recorded
        redirects = svc._get_redirect_history(created["doi"])
        assert len(redirects) == 1
        assert redirects[0]["old_url"] == "https://original.com"

    def test_modify_multiple_url_changes(self, svc):
        """Multiple modifications create multiple redirect entries."""
        created = svc.assign("https://v1.com")
        svc.modify(created["doi"], target_url="https://v2.com")
        svc.modify(created["doi"], target_url="https://v3.com")
        redirects = svc._get_redirect_history(created["doi"])
        assert len(redirects) == 2
        assert redirects[0]["old_url"] == "https://v1.com"
        assert redirects[1]["old_url"] == "https://v2.com"

    def test_modify_title(self, svc):
        """Changing title preserves other fields."""
        created = svc.assign("https://example.com", title="Old Title")
        updated = svc.modify(created["doi"], title="New Title")
        assert updated["title"] == "New Title"
        assert updated["target_url"] == "https://example.com"  # unchanged

    def test_modify_creator(self, svc):
        """Changing creator works."""
        created = svc.assign("https://example.com", creator="Alice")
        updated = svc.modify(created["doi"], creator="Bob")
        assert updated["creator"] == "Bob"

    def test_modify_doi_type(self, svc):
        """Changing doi_type works (free-text)."""
        created = svc.assign("https://example.com", doi_type="book")
        updated = svc.modify(created["doi"], doi_type="webpage")
        assert updated["doi_type"] == "webpage"

    def test_modify_metadata(self, svc):
        """Changing metadata replaces the entire metadata dict."""
        created = svc.assign("https://example.com", metadata={"key": "old"})
        updated = svc.modify(created["doi"], metadata={"key": "new", "extra": True})
        assert updated["metadata"] == {"key": "new", "extra": True}

    def test_modify_nonexistent(self, svc):
        """Modifying non-existent DOI raises DOINotFoundError."""
        with pytest.raises(DOINotFoundError):
            svc.modify("10.ronzz/00000000000000000000000000000000", title="Nope")

    def test_modify_no_changes(self, svc):
        """Modify with no changes returns existing record."""
        created = svc.assign("https://example.com", title="Same")
        updated = svc.modify(created["doi"])
        assert updated["doi"] == created["doi"]
        assert updated["title"] == "Same"

    def test_modify_preserves_created_at(self, svc):
        """created_at should remain unchanged after modify."""
        created = svc.assign("https://example.com")
        import time
        time.sleep(0.01)
        updated = svc.modify(created["doi"], title="Updated")
        assert updated["created_at"] == created["created_at"]
        assert updated["updated_at"] > created["updated_at"]

    def test_modify_redirect_note(self, svc):
        """Custom redirect note is stored."""
        created = svc.assign("https://original.com")
        svc.modify(created["doi"], target_url="https://new.com", redirect_note="Server migration")
        redirects = svc._get_redirect_history(created["doi"])
        assert redirects[0]["note"] == "Server migration"


# ── delete_doi() ────────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_sets_deleted_at(self, svc):
        """delete_doi sets deleted_at timestamp without removing row."""
        created = svc.assign("https://example.com")
        assert svc.delete_doi(created["doi"]) is True
        row = svc.db.execute_one("SELECT * FROM dois WHERE doi = ?", (created["doi"],))
        assert row is not None  # row still exists
        assert row["deleted_at"] is not None  # tombstoned

    def test_delete_not_found(self, svc):
        """Deleting non-existent DOI returns False."""
        assert svc.delete_doi("10.ronzz/00000000000000000000000000000000") is False

    def test_delete_twice_idempotent(self, svc):
        """Deleting an already-tombstoned DOI returns True (still exists)."""
        created = svc.assign("https://example.com")
        assert svc.delete_doi(created["doi"]) is True
        assert svc.delete_doi(created["doi"]) is True  # second delete succeeds
        row = svc.db.execute_one("SELECT * FROM dois WHERE doi = ?", (created["doi"],))
        assert row["deleted_at"] is not None

    def test_delete_by_prefix(self, svc):
        """Delete by unique prefix works."""
        created = svc.assign("https://example.com")
        prefix = created["doi"][:20]
        assert svc.delete_doi(prefix) is True
        row = svc.db.execute_one("SELECT * FROM dois WHERE doi = ?", (created["doi"],))
        assert row["deleted_at"] is not None


# ── list_dois() ─────────────────────────────────────────────────────────────


class TestList:
    def test_list_empty(self, svc):
        """Empty database returns empty list."""
        assert svc.list_dois() == []

    def test_list_returns_all_active(self, svc):
        """list_dois returns all active DOIs."""
        svc.assign("https://a.com")
        svc.assign("https://b.com")
        svc.assign("https://c.com")
        results = svc.list_dois()
        assert len(results) == 3

    def test_list_excludes_deleted(self, svc):
        """list_dois excludes tombstoned DOIs by default."""
        a = svc.assign("https://a.com")
        svc.assign("https://b.com")
        svc.delete_doi(a["doi"])
        results = svc.list_dois()
        assert len(results) == 1
        assert results[0]["doi"] != a["doi"]

    def test_list_include_deleted(self, svc):
        """list_dois with include_deleted=True includes tombstoned."""
        a = svc.assign("https://a.com")
        svc.assign("https://b.com")
        svc.delete_doi(a["doi"])
        results = svc.list_dois(include_deleted=True)
        assert len(results) == 2

    def test_list_pagination(self, svc):
        """list_dois supports limit and offset."""
        for i in range(5):
            svc.assign(f"https://example{i}.com")
        page1 = svc.list_dois(limit=2, offset=0)
        page2 = svc.list_dois(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        # Ensure pages don't overlap
        ids1 = {r["doi"] for r in page1}
        ids2 = {r["doi"] for r in page2}
        assert ids1.isdisjoint(ids2)

    def test_list_order(self, svc):
        """list_dois returns newest first."""
        r1 = svc.assign("https://first.com")
        r2 = svc.assign("https://second.com")
        r3 = svc.assign("https://third.com")
        results = svc.list_dois()
        assert results[0]["doi"] == r3["doi"]
        assert results[1]["doi"] == r2["doi"]
        assert results[2]["doi"] == r1["doi"]

    def test_list_limit(self, svc):
        """list_dois respects limit parameter."""
        for i in range(10):
            svc.assign(f"https://example{i}.com")
        assert len(svc.list_dois(limit=3)) == 3
        assert len(svc.list_dois(limit=0)) == 0


# ── Edge cases & integration ────────────────────────────────────────────────


class TestEdgeCases:
    def test_full_lifecycle(self, svc):
        """Full DOI lifecycle: assign → resolve → modify → resolve → delete → resolve."""
        # Assign
        created = svc.assign("https://start.com", title="Lifecycle Test")
        doi = created["doi"]

        # Resolve
        resolved = svc.resolve(doi)
        assert resolved["target_url"] == "https://start.com"
        assert resolved["status"] == "active"

        # Modify URL
        modified = svc.modify(doi, target_url="https://moved.com")
        assert modified["target_url"] == "https://moved.com"
        assert len(modified["redirect_history"]) == 1

        # Re-resolve
        resolved2 = svc.resolve(doi)
        assert resolved2["target_url"] == "https://moved.com"
        assert len(resolved2["redirect_history"]) == 1

        # Delete
        assert svc.delete_doi(doi) is True

        # Resolve tombstoned
        resolved3 = svc.resolve(doi)
        assert resolved3["deleted_at"] is not None
        assert resolved3["status"] == "tombstone"

    def test_multiple_dois_same_url(self, svc):
        """Multiple DOIs can point to the same URL."""
        a = svc.assign("https://example.com")
        b = svc.assign("https://example.com")
        assert a["doi"] != b["doi"]
        assert svc.resolve(a["doi"])["target_url"] == "https://example.com"
        assert svc.resolve(b["doi"])["target_url"] == "https://example.com"

    def test_redirect_chain_preserved(self, svc):
        """Modify chain creates full redirect history."""
        created = svc.assign("https://v1.com")
        svc.modify(created["doi"], target_url="https://v2.com")
        svc.modify(created["doi"], target_url="https://v3.com")
        resolved = svc.resolve(created["doi"])
        history = resolved["redirect_history"]
        assert len(history) == 2
        assert history[0]["old_url"] == "https://v1.com"
        assert history[1]["old_url"] == "https://v2.com"
        assert resolved["target_url"] == "https://v3.com"

    def test_generate_doi_static(self, svc):
        """generate_doi() produces valid format as a static method."""
        doi = DOIService.generate_doi()
        assert DOI_FORMAT_RE.match(doi)
        assert len(doi) == 41

    def test_resolve_after_tombstone_returns_metadata(self, svc):
        """Tombstoned DOI still returns all original metadata except redirect."""
        created = svc.assign(
            "https://example.com",
            title="Gone",
            creator="Alice",
            doi_type="report",
            metadata={"version": 1},
        )
        svc.delete_doi(created["doi"])
        resolved = svc.resolve(created["doi"])
        assert resolved["title"] == "Gone"
        assert resolved["creator"] == "Alice"
        assert resolved["doi_type"] == "report"
        assert resolved["metadata"] == {"version": 1}


# ── Constants/validators (do not need the DB) ──────────────────────────────


class TestDOIValidators:
    """Tests for is_valid_doi() and is_doi_prefix() in constants.py."""

    def test_is_valid_doi_accepts_proper_format(self):
        """Valid DOI returns True."""
        assert is_valid_doi("10.ronzz/0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d") is True

    def test_is_valid_doi_rejects_wrong_prefix(self):
        """Wrong registrant prefix returns False."""
        assert is_valid_doi("10.wrong/0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d") is False

    def test_is_valid_doi_rejects_short_suffix(self):
        """Too-short suffix returns False."""
        assert is_valid_doi("10.ronzz/abc123") is False

    def test_is_valid_doi_rejects_garbage(self):
        """Garbage string returns False."""
        assert is_valid_doi("not-a-doi") is False
        assert is_valid_doi("") is False

    def test_is_valid_doi_rejects_uppercase(self):
        """Uppercase hex in suffix returns False (must be lowercase)."""
        assert is_valid_doi("10.ronzz/0A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D") is False

    def test_is_doi_prefix_accepts_full_prefix(self):
        """Full prefix '10.ronzz/' returns True."""
        assert is_doi_prefix("10.ronzz/") is True

    def test_is_doi_prefix_accepts_prefix_with_suffix(self):
        """Prefix with partial suffix returns True."""
        assert is_doi_prefix("10.ronzz/abc123") is True

    def test_is_doi_prefix_rejects_wrong_prefix(self):
        """Wrong prefix returns False."""
        assert is_doi_prefix("10.wrong/") is False

    def test_is_doi_prefix_rejects_no_slash(self):
        """String without slash returns False."""
        assert is_doi_prefix("10.ronzz") is False

    def test_is_doi_prefix_rejects_garbage(self):
        """Garbage string returns False."""
        assert is_doi_prefix("nope") is False


# ── Edge cases for service methods ─────────────────────────────────────────


class TestAdditionalEdgeCases:
    """Additional edge cases discovered during test coverage audit."""

    def test_resolve_no_redirects(self, svc):
        """resolve() with include_redirects=False skips redirect history fetch."""
        created = svc.assign("https://example.com")
        resolved = svc.resolve(created["doi"], include_redirects=False)
        assert resolved["redirect_history"] == []

    def test_modify_same_url_no_redirect(self, svc):
        """Modify with same target_url does NOT create a redirect record."""
        created = svc.assign("https://example.com")
        svc.modify(created["doi"], target_url="https://example.com")
        redirects = svc._get_redirect_history(created["doi"])
        assert len(redirects) == 0

    def test_modify_partial_update_preserves_other_fields(self, svc):
        """Modifying only one field preserves all others."""
        created = svc.assign(
            "https://example.com",
            title="Original",
            creator="Alice",
            doi_type="book",
        )
        svc.modify(created["doi"], title="Updated")
        resolved = svc.resolve(created["doi"])
        assert resolved["title"] == "Updated"
        assert resolved["creator"] == "Alice"  # unchanged
        assert resolved["doi_type"] == "book"  # unchanged
