"""Tests for the citation module — CitationFormatter, schemas, styles.

Tests use a real SQLite database and DOIService (not mocked) to verify
that the full pipeline — DOI assign → CitationFormatter.format() —
works correctly for all supported doc_types and styles.
"""

from __future__ import annotations

import json

import pytest

from ronzzdoi.citation import CitationFormatter, DOC_TYPES, validate_metadata
from ronzzdoi.citation.schemas import ENTITY_TYPES
from ronzzdoi.citation.styles import available_styles
from ronzzdoi.doi.exceptions import DOINotFoundError

# ── Schema ──────────────────────────────────────────────────────────────────

DOI_SCHEMA = {
    "dois": """
        CREATE TABLE dois (
            doi           TEXT PRIMARY KEY,
            target_url    TEXT,
            title         TEXT DEFAULT '',
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


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    """Create a temporary SQLite database with DOI schema."""
    from lightercore.db import LighterDB

    db_path = tmp_path / "test_citation.db"
    ldb = LighterDB(db_path)
    ldb.init_schema(DOI_SCHEMA)
    yield ldb
    ldb.close()


@pytest.fixture
def doi_svc(db):
    """Create a DOIService bound to the temp database."""
    from ronzzdoi.doi.service import DOIService

    return DOIService(db)


@pytest.fixture
def formatter(doi_svc):
    """Create a CitationFormatter bound to the DOI service."""
    return CitationFormatter(doi_svc)


@pytest.fixture
def person_doi(doi_svc):
    """Create a person DOI for use in author references."""
    result = doi_svc.assign(
        doi_type="person",
        title="Ada Lovelace",
        metadata={
            "first_name": "Ada",
            "middle_names": [],
            "last_name": "Lovelace",
            "aliases": ["Augusta Ada King"],
        },
    )
    return result["doi"]


@pytest.fixture
def author_doi(doi_svc):
    """Create another person DOI for co-author testing."""
    result = doi_svc.assign(
        doi_type="person",
        title="Charles Babbage",
        metadata={
            "first_name": "Charles",
            "middle_names": [],
            "last_name": "Babbage",
        },
    )
    return result["doi"]


# ── available_styles() ─────────────────────────────────────────────────────


class TestAvailableStyles:
    def test_styles_list(self):
        """available_styles returns expected styles."""
        styles = available_styles()
        assert "apa" in styles
        assert "vancouver" in styles
        assert "json" in styles

    def test_formatter_styles(self, formatter):
        """CitationFormatter.available_styles() mirrors the styles module."""
        assert formatter.available_styles() == available_styles()


# ── DOC_TYPES and DOC_TYPE_SCHEMAS ─────────────────────────────────────────


class TestDocTypes:
    def test_doc_types_contains_all_expected(self):
        """DOC_TYPES lists all 16 supported document types."""
        expected = [
            "book",
            "bookSection",
            "scientificPaper",
            "conferencePaper",
            "presentation",
            "report",
            "dataset",
            "webpage",
            "magazineArticle",
            "newspaperArticle",
            "film",
            "podcast",
            "song",
            "media",
            "circulaire",
            "rulebook",
            "document",
        ]
        for dt in expected:
            assert dt in DOC_TYPES, f"Missing doc_type: {dt}"

    def test_entity_types_not_in_doc_types(self):
        """Entity types are separate from citation doc_types."""
        for et in ENTITY_TYPES:
            assert et not in DOC_TYPES

    def test_validate_metadata_passes_valid(self):
        """validate_metadata returns empty list for valid metadata."""
        errors = validate_metadata("book", {
            "authors": [{"person_doi": "10.ronzz/abc"}],
            "title": "Test",
            "publisher": "TestPub",
            "year": 2024,
        })
        assert errors == []

    def test_validate_metadata_missing_required(self):
        """validate_metadata returns missing field names."""
        errors = validate_metadata("book", {"title": "Test"})
        assert "authors" in errors
        assert "publisher" in errors
        assert "year" in errors

    def test_validate_metadata_entity_types_pass(self):
        """Entity types always pass validation (no citation fields)."""
        for et in ENTITY_TYPES:
            errors = validate_metadata(et, {})
            assert errors == [], f"Entity type {et} should not require fields"

    def test_validate_metadata_unknown_type(self):
        """Unknown doc_type returns an error message."""
        errors = validate_metadata("unknown_type", {})
        assert len(errors) == 1
        assert "unknown" in errors[0]


# ── APA style ──────────────────────────────────────────────────────────────


class TestAPA:
    def test_book(self, formatter, doi_svc, person_doi):
        """APA book citation."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Test Book",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "The Analytical Engine",
                "publisher": "Academic Press",
                "year": 2024,
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Lovelace, A." in result
        assert "The Analytical Engine" in result
        assert "Academic Press" in result
        assert "(2024)" in result

    def test_book_with_edition(self, formatter, doi_svc, person_doi):
        """APA book citation with edition."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Test Book",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "Calculus",
                "publisher": "Math Press",
                "year": 2023,
                "edition": "3rd ed.",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "3rd ed." in result

    def test_scientific_paper_journal(self, formatter, doi_svc, person_doi):
        """APA scientific paper (journal article)."""
        doi = doi_svc.assign(
            doi_type="scientificPaper",
            title="Test Paper",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "A Breakthrough in Computing",
                "publication": "Journal of Computing",
                "year": 2024,
                "subtype": "journal-article",
                "volume": "12",
                "issue": "3",
                "pages": "45-67",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Lovelace, A." in result
        assert "A Breakthrough in Computing" in result
        assert "Journal of Computing" in result
        assert "*12*" in result or "12" in result
        assert "45-67" in result

    def test_scientific_paper_preprint(self, formatter, doi_svc, person_doi):
        """APA scientific paper (preprint)."""
        doi = doi_svc.assign(
            doi_type="scientificPaper",
            title="Test Preprint",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "Preprint Results",
                "publication": "arXiv",
                "year": 2024,
                "subtype": "preprint",
                "archive": "arXiv:2401.12345",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Preprint Results" in result
        assert "arXiv:2401.12345" in result

    def test_scientific_paper_thesis(self, formatter, doi_svc, person_doi):
        """APA scientific paper (thesis)."""
        doi = doi_svc.assign(
            doi_type="scientificPaper",
            title="PhD Thesis",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "My Dissertation",
                "publication": "University of X",
                "year": 2024,
                "subtype": "thesis",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Doctoral dissertation" in result
        assert "University of X" in result

    def test_webpage(self, formatter, doi_svc, person_doi):
        """APA webpage citation."""
        doi = doi_svc.assign(
            doi_type="webpage",
            title="Test Page",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "History of Computing",
                "website_name": "Computing History Org",
                "url": "https://example.com/history",
                "access_date": "2024-03-15",
                "publication_date": "2023-06-01",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Lovelace, A." in result
        assert "History of Computing" in result
        assert "Computing History Org" in result
        assert "Retrieved" in result
        assert "https://example.com/history" in result

    def test_circulaire(self, formatter, doi_svc, person_doi):
        """APA circulaire citation with issuing_authority resolution."""
        doi = doi_svc.assign(
            doi_type="circulaire",
            title="Test Circulaire",
            metadata={
                "circulaire_number": "2025-001",
                "title": "Annual Budget Directive",
                "issuing_authority_doi": person_doi,
                "date": "2025-03-15",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Lovelace, A." in result
        assert "Annual Budget Directive" in result
        assert "Circulaire No. 2025-001" in result
        assert "2025" in result

    def test_rulebook(self, formatter, doi_svc, author_doi):
        """APA rulebook citation."""
        doi = doi_svc.assign(
            doi_type="rulebook",
            title="Staff Rules",
            metadata={
                "title": "Staff Rules and Procedures",
                "version": "2.1",
                "issuing_authority_doi": author_doi,
                "date": "2024-01-01",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Babbage, C." in result
        assert "Staff Rules and Procedures" in result
        assert "Version 2.1" in result

    def test_film(self, formatter, doi_svc, person_doi):
        """APA film citation."""
        doi = doi_svc.assign(
            doi_type="film",
            title="Test Film",
            metadata={
                "title": "The Great Film",
                "directors": [{"person_doi": person_doi}],
                "year": 2024,
                "studio": "Big Studio",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "The Great Film" in result
        assert "Film" in result
        assert "Big Studio" in result

    def test_two_authors(self, formatter, doi_svc, person_doi, author_doi):
        """APA with two authors uses &."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Co-authored Book",
            metadata={
                "authors": [
                    {"person_doi": person_doi},
                    {"person_doi": author_doi},
                ],
                "title": "Collaborative Work",
                "publisher": "Joint Press",
                "year": 2024,
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Lovelace, A." in result
        assert "Babbage, C." in result
        assert "&" in result

    def test_entity_doi_not_citable(self, formatter, doi_svc):
        """Entity DOIs return a descriptive message, not a citation."""
        doi = doi_svc.assign(
            doi_type="person",
            title="Test Person",
            metadata={"first_name": "Test", "last_name": "User"},
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "not a citable resource" in result
        assert "Test User" in result

    def test_nonexistent_doi(self, formatter):
        """Formatting non-existent DOI raises DOINotFoundError."""
        with pytest.raises(DOINotFoundError):
            formatter.format("10.ronzz/00000000000000000000000000000000", style="apa")

    def test_invalid_style(self, formatter, doi_svc):
        """Unknown style raises ValueError."""
        doi = doi_svc.assign(doi_type="book", title="Test", metadata={
            "authors": [{"person_doi": "10.ronzz/abc"}],
            "title": "Test", "publisher": "TP", "year": 2024,
        })["doi"]
        with pytest.raises(ValueError, match="Unsupported citation style"):
            formatter.format(doi, style="mla")

    def test_dataset(self, formatter, doi_svc, person_doi):
        """APA dataset citation."""
        doi = doi_svc.assign(
            doi_type="dataset",
            title="Test Dataset",
            metadata={
                "creators": [{"person_doi": person_doi}],
                "title": "Research Data 2024",
                "repository": "Zenodo",
                "year": 2024,
                "version": "1.0",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Research Data 2024" in result
        assert "Zenodo" in result
        assert "Data set" in result
        assert "Version 1.0" in result

    def test_newspaper_article(self, formatter, doi_svc, person_doi):
        """APA newspaper article citation."""
        doi = doi_svc.assign(
            doi_type="newspaperArticle",
            title="News Test",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "Breaking News",
                "newspaper_name": "The Daily Times",
                "date": "2024-06-15",
                "section": "A1",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Breaking News" in result
        assert "The Daily Times" in result


# ── Vancouver style ────────────────────────────────────────────────────────


class TestVancouver:
    def test_book(self, formatter, doi_svc, person_doi):
        """Vancouver book citation."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Test Book",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "Medical Textbook",
                "publisher": "Health Press",
                "year": 2024,
            },
        )["doi"]
        result = formatter.format(doi, style="vancouver")
        assert "Lovelace A" in result  # Vancouver: no comma, no period after initial
        assert "Medical Textbook" in result
        assert "Health Press" in result
        assert "2024" in result

    def test_scientific_paper_journal(self, formatter, doi_svc, person_doi):
        """Vancouver journal article."""
        doi = doi_svc.assign(
            doi_type="scientificPaper",
            title="Test Paper",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "Clinical Study",
                "publication": "J Med Res",
                "year": 2024,
                "subtype": "journal-article",
                "volume": "15",
                "issue": "2",
                "pages": "100-10",
            },
        )["doi"]
        result = formatter.format(doi, style="vancouver")
        assert "Clinical Study" in result
        assert "J Med Res" in result


# ── JSON style ─────────────────────────────────────────────────────────────


class TestJSON:
    def test_json_output(self, formatter, doi_svc, person_doi):
        """JSON style returns a JSON string with citation metadata."""
        doi = doi_svc.assign(
            doi_type="book",
            title="JSON Test",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "JSON Book",
                "publisher": "JSON Press",
                "year": 2024,
            },
        )["doi"]
        result = formatter.format(doi, style="json")
        data = json.loads(result)
        assert data["doi_type"] == "book"
        assert data["title"] == "JSON Book"
        assert "metadata" in data
        assert data["metadata"]["publisher"] == "JSON Press"

    def test_json_includes_resolved_names(self, formatter, doi_svc, person_doi):
        """JSON output includes resolved author names."""
        doi = doi_svc.assign(
            doi_type="book",
            title="JSON Authored",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "Authored Book",
                "publisher": "AP",
                "year": 2024,
            },
        )["doi"]
        result = formatter.format(doi, style="json")
        data = json.loads(result)
        assert "resolved_authors" in data
        assert "Lovelace, Ada" in data["resolved_authors"][0]


# ── validate_doi_metadata() ────────────────────────────────────────────────


class TestValidateDOIMetadata:
    def test_valid_doi(self, formatter, doi_svc, person_doi):
        """validate_doi_metadata returns empty list for valid DOI metadata."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Valid Book",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "Valid Book",
                "publisher": "VP",
                "year": 2024,
            },
        )["doi"]
        errors = formatter.validate_doi_metadata(doi)
        assert errors == []

    def test_missing_fields(self, formatter, doi_svc):
        """validate_doi_metadata returns missing field names."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Incomplete Book",
            metadata={"title": "Incomplete"},
        )["doi"]
        errors = formatter.validate_doi_metadata(doi)
        assert "authors" in errors
        assert "publisher" in errors
        assert "year" in errors

    def test_nonexistent_doi(self, formatter):
        """validate_doi_metadata raises DOINotFoundError for missing DOI."""
        with pytest.raises(DOINotFoundError):
            formatter.validate_doi_metadata("10.ronzz/nonexistent")

    def test_entity_doi_no_errors(self, formatter, doi_svc):
        """validate_doi_metadata returns empty for entity DOIs."""
        doi = doi_svc.assign(
            doi_type="person",
            title="Test Entity",
            metadata={"first_name": "Test", "last_name": "Entity"},
        )["doi"]
        errors = formatter.validate_doi_metadata(doi)
        assert errors == []


# ── Cross-reference resolution ─────────────────────────────────────────────


class TestCrossRefResolution:
    def test_book_section_with_book_doi(self, formatter, doi_svc, person_doi, author_doi):
        """bookSection resolves book_doi and includes parent book title."""
        # Create the parent book
        book_doi = doi_svc.assign(
            doi_type="book",
            title="Parent Book",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "The Parent Book",
                "publisher": "Big Press",
                "year": 2023,
            },
        )["doi"]

        # Create the book section referencing the parent
        section_doi = doi_svc.assign(
            doi_type="bookSection",
            title="Chapter 1",
            metadata={
                "authors": [{"person_doi": author_doi}],
                "title": "Introduction",
                "book_doi": book_doi,
                "pages": "1-20",
            },
        )["doi"]

        result = formatter.format(section_doi, style="apa")
        assert "Babbage, C." in result
        assert "Introduction" in result
        assert "Parent Book" in result
        assert "1-20" in result

    def test_circulaire_with_entity_authority(self, formatter, doi_svc, person_doi):
        """circulaire resolves issuing_authority_doi to person name."""
        doi = doi_svc.assign(
            doi_type="circulaire",
            title="Directive",
            metadata={
                "circulaire_number": "2024-042",
                "title": "Security Directive",
                "issuing_authority_doi": person_doi,
                "date": "2024-09-01",
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Lovelace, A." in result
        assert "Security Directive" in result


# ── Edge cases ─────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_metadata(self, formatter, doi_svc):
        """A DOI with empty metadata still formats (graceful fallback)."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Empty",
            metadata={},
        )["doi"]
        result = formatter.format(doi, style="apa")
        # Should not crash — returns fallback text
        assert result is not None

    def test_tombstoned_doi(self, formatter, doi_svc, person_doi):
        """Tombstoned DOI can still be formatted (record is resolvable)."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Gone",
            metadata={
                "authors": [{"person_doi": person_doi}],
                "title": "Deleted Book",
                "publisher": "DP",
                "year": 2020,
            },
        )["doi"]
        from ronzzdoi.doi.service import DOIService as DS
        # Tombstone via the DOI service
        doi_svc.delete_doi(doi)
        # Should still format — the record is resolvable with deleted_at set
        result = formatter.format(doi, style="apa")
        assert "Deleted Book" in result

    def test_inline_authors(self, formatter, doi_svc):
        """Inline authors (``given``/``family`` without ``person_doi``) format correctly."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Inline Authors",
            metadata={
                "authors": [
                    {"given": "John", "family": "Smith"},
                    {"given": "Alice", "family": "Johnson"},
                ],
                "title": "Inline Authors Test",
                "publisher": "Test Press",
                "year": 2024,
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Smith, J." in result
        assert "Johnson, A." in result
        assert "Inline Authors Test" in result

    def test_inline_author_single(self, formatter, doi_svc):
        """Single inline author formats correctly (``1 author`` code path)."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Single Author",
            metadata={
                "authors": [{"given": "Jane", "family": "Doe"}],
                "title": "Single Author Book",
                "publisher": "SP Press",
                "year": 2024,
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Doe, J." in result

    def test_inline_author_mixed_person_doi_and_inline(self, formatter, doi_svc, person_doi):
        """Mixed author list: person_doi refs + inline authors."""
        doi = doi_svc.assign(
            doi_type="book",
            title="Mixed Authors",
            metadata={
                "authors": [
                    {"person_doi": person_doi},
                    {"given": "Bob", "family": "Builder"},
                ],
                "title": "Mixed Authors Book",
                "publisher": "MP Press",
                "year": 2024,
            },
        )["doi"]
        result = formatter.format(doi, style="apa")
        assert "Lovelace, A." in result
        assert "Builder, B." in result
