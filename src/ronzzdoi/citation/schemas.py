"""Doc-type field schemas for citation metadata validation.

Defines the required and optional fields for each supported ``doc_type``
(``doi_type`` on the DOI record).  The CitationFormatter uses these
schemas to validate DOI metadata and to know which fields to read
when formatting.

Usage::

    from ronzzdoi.citation.schemas import DOC_TYPES, validate_metadata

    errors = validate_metadata("book", {"authors": [...], "title": "..."})
    assert "book" in DOC_TYPES
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Field definition ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FieldDef:
    """Definition of a single metadata field for a doc_type.

    Attributes:
        required: If True, the field must be present in metadata_json.
        types: Accepted Python types for the field value.
        description: Human-readable description.
    """

    required: bool = False
    types: tuple[type, ...] = (str,)
    description: str = ""


# ── Supported doc_type names ────────────────────────────────────────────────

DOC_TYPES: list[str] = [
    # External
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
    # Media
    "film",
    "podcast",
    "song",
    "media",
    # Internal (ronzz.org)
    "circulaire",
    "rulebook",
    "document",
]

ENTITY_TYPES: list[str] = [
    "person",
    "abstract_entity",
    "country",
]


# ── Doc-type field schemas ──────────────────────────────────────────────────

# fmt: off

DOC_TYPE_SCHEMAS: dict[str, dict[str, FieldDef]] = {
    # ── External ────────────────────────────────────────────────────────
    "book": {
        "authors": FieldDef(required=True, types=(list,), description="List of {person_doi: str}"),
        "title":   FieldDef(required=True, types=(str,),  description="Full book title"),
        "publisher": FieldDef(required=True, types=(str,), description="Publishing house"),
        "year":    FieldDef(required=True, types=(int, str), description="Publication year"),
        "isbn":    FieldDef(required=False, types=(str,), description="ISBN-13 or ISBN-10"),
        "edition": FieldDef(required=False, types=(str,), description="Edition string (e.g. '2nd ed.')"),
    },
    "bookSection": {
        "authors":  FieldDef(required=True, types=(list,), description="List of {person_doi: str}"),
        "title":    FieldDef(required=True, types=(str,),  description="Section/chapter title"),
        "book_doi": FieldDef(required=True, types=(str,),  description="DOI of the parent book"),
        "pages":    FieldDef(required=False, types=(str,), description="Page range (e.g. '45-67')"),
    },
    "scientificPaper": {
        "authors":      FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "title":        FieldDef(required=True,  types=(str,),  description="Paper title"),
        "publication":  FieldDef(required=True,  types=(str,),  description="Journal/proceedings name"),
        "year":         FieldDef(required=True,  types=(int, str), description="Publication year"),
        "subtype":      FieldDef(required=True,  types=(str,),  description="journal-article | preprint | thesis"),
        "volume":       FieldDef(required=False, types=(str,),  description="Journal volume"),
        "issue":        FieldDef(required=False, types=(str,),  description="Journal issue/number"),
        "pages":        FieldDef(required=False, types=(str,),  description="Page range"),
        "doi":          FieldDef(required=False, types=(str,),  description="External DOI"),
        "archive":      FieldDef(required=False, types=(str,),  description="Archive/identifier (e.g. arXiv:2401.12345)"),
    },
    "conferencePaper": {
        "authors":        FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "title":          FieldDef(required=True,  types=(str,),  description="Paper title"),
        "conference_name": FieldDef(required=True,  types=(str,),  description="Conference name"),
        "date":           FieldDef(required=True,  types=(str,),  description="Conference date"),
        "location":       FieldDef(required=False, types=(str,),  description="Conference location"),
    },
    "presentation": {
        "presenters": FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "title":      FieldDef(required=True,  types=(str,),  description="Presentation title"),
        "event_name": FieldDef(required=True,  types=(str,),  description="Event name"),
        "date":       FieldDef(required=True,  types=(str,),  description="Presentation date"),
        "url":        FieldDef(required=False, types=(str,),  description="Recording/slides URL"),
    },
    "report": {
        "authors":       FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "title":         FieldDef(required=True,  types=(str,),  description="Report title"),
        "institution":   FieldDef(required=True,  types=(str,),  description="Institution name"),
        "year":          FieldDef(required=True,  types=(int, str), description="Publication year"),
        "report_number": FieldDef(required=False, types=(str,),  description="Report number"),
        "url":           FieldDef(required=False, types=(str,),  description="Report URL"),
    },
    "dataset": {
        "title":    FieldDef(required=True,  types=(list, str), description="Dataset title"),
        "creators": FieldDef(required=True,  types=(list,),     description="List of {person_doi: str}"),
        "repository": FieldDef(required=True,  types=(str,),    description="Repository name"),
        "year":     FieldDef(required=True,  types=(int, str), description="Publication year"),
        "doi":      FieldDef(required=False, types=(str,),     description="External DOI"),
        "version":  FieldDef(required=False, types=(str,),     description="Dataset version"),
    },
    "webpage": {
        "authors":         FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "title":           FieldDef(required=True,  types=(str,),  description="Page title"),
        "website_name":    FieldDef(required=True,  types=(str,),  description="Website name"),
        "url":             FieldDef(required=True,  types=(str,),  description="Page URL"),
        "access_date":     FieldDef(required=True,  types=(str,),  description="Date accessed (ISO date)"),
        "publication_date": FieldDef(required=False, types=(str,), description="Original publication date"),
    },
    "magazineArticle": {
        "authors":       FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "title":         FieldDef(required=True,  types=(str,),  description="Article title"),
        "magazine_name": FieldDef(required=True,  types=(str,),  description="Magazine name"),
        "year":          FieldDef(required=True,  types=(int, str), description="Publication year"),
        "volume":        FieldDef(required=False, types=(str,),  description="Volume"),
        "issue":         FieldDef(required=False, types=(str,),  description="Issue/number"),
        "pages":         FieldDef(required=False, types=(str,),  description="Page range"),
        "url":           FieldDef(required=False, types=(str,),  description="Article URL"),
    },
    "newspaperArticle": {
        "authors":         FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "title":           FieldDef(required=True,  types=(str,),  description="Article title"),
        "newspaper_name":  FieldDef(required=True,  types=(str,),  description="Newspaper name"),
        "date":            FieldDef(required=True,  types=(str,),  description="Publication date (ISO date)"),
        "section":         FieldDef(required=False, types=(str,),  description="Newspaper section"),
        "url":             FieldDef(required=False, types=(str,),  description="Article URL"),
    },
    # ── Media ───────────────────────────────────────────────────────────
    "film": {
        "title":     FieldDef(required=True,  types=(str,),  description="Film title"),
        "directors": FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "year":      FieldDef(required=True,  types=(int, str), description="Release year"),
        "studio":    FieldDef(required=True,  types=(str,),  description="Production studio"),
        "duration":  FieldDef(required=False, types=(int, str), description="Duration in minutes"),
    },
    "podcast": {
        "title":          FieldDef(required=True,  types=(str,),  description="Episode title"),
        "hosts":          FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "podcast_name":   FieldDef(required=True,  types=(str,),  description="Podcast series name"),
        "publisher":      FieldDef(required=True,  types=(str,),  description="Publisher/network"),
        "date":           FieldDef(required=True,  types=(str,),  description="Publication date (ISO date)"),
        "episode_title":  FieldDef(required=False, types=(str,),  description="Episode subtitle"),
        "episode_number": FieldDef(required=False, types=(int, str), description="Episode number"),
        "url":            FieldDef(required=False, types=(str,),  description="Episode URL"),
    },
    "song": {
        "title":    FieldDef(required=True,  types=(str,),  description="Song title"),
        "artists":  FieldDef(required=True,  types=(list,), description="List of {person_doi: str}"),
        "label":    FieldDef(required=True,  types=(str,),  description="Record label"),
        "year":     FieldDef(required=True,  types=(int, str), description="Release year"),
        "album":    FieldDef(required=False, types=(str,),  description="Album name"),
        "duration": FieldDef(required=False, types=(int, str), description="Duration in seconds"),
    },
    "media": {
        "title":   FieldDef(required=True,  types=(list, str), description="Media title"),
        "creator": FieldDef(required=True,  types=(list, str), description="Creator(s)"),
        "format":  FieldDef(required=True,  types=(str,),      description="Media format (audio/video/image)"),
        "url":     FieldDef(required=False, types=(str,),      description="Media URL"),
    },
    # ── Internal (ronzz.org) ────────────────────────────────────────────
    "circulaire": {
        "circulaire_number":   FieldDef(required=True,  types=(str,), description="Circulaire number (e.g. '2025-001')"),
        "title":               FieldDef(required=True,  types=(str,), description="Circulaire title"),
        "issuing_authority_doi": FieldDef(required=True,  types=(str,), description="DOI of issuing person/entity"),
        "date":                FieldDef(required=True,  types=(str,), description="Issue date (ISO date)"),
        "url":                 FieldDef(required=False, types=(str,), description="Circulaire URL"),
    },
    "rulebook": {
        "title":               FieldDef(required=True,  types=(str,), description="Rulebook title"),
        "version":             FieldDef(required=True,  types=(str,), description="Version string"),
        "issuing_authority_doi": FieldDef(required=True,  types=(str,), description="DOI of issuing person/entity"),
        "date":                FieldDef(required=True,  types=(str,), description="Publication date (ISO date)"),
        "url":                 FieldDef(required=False, types=(str,), description="Rulebook URL"),
    },
    "document": {
        "title":       FieldDef(required=True,  types=(str,),  description="Document title"),
        "date":        FieldDef(required=True,  types=(str,),  description="Document date (ISO date)"),
        "authors":     FieldDef(required=False, types=(list,), description="List of {person_doi: str}"),
        "description": FieldDef(required=False, types=(str,),  description="Document description"),
    },
}

# fmt: on


# ── Public helpers ──────────────────────────────────────────────────────────


def validate_metadata(
    doi_type: str,
    metadata: dict[str, Any],
) -> list[str]:
    """Validate *metadata* fields against the ``doi_type`` schema.

    Args:
        doi_type: The ``doi_type`` value from the DOI record.
                  Must be one of ``DOC_TYPES`` or ``ENTITY_TYPES``.
        metadata: The deserialized ``metadata_json`` dict.

    Returns:
        List of missing required field names.  Empty list means valid.
        Entity types (person, abstract_entity, country) always return
        an empty list (they have no citation-relevant required fields).
    """
    if doi_type in ENTITY_TYPES:
        return []
    schema = DOC_TYPE_SCHEMAS.get(doi_type)
    if schema is None:
        return [f"unknown doc_type: {doi_type}"]
    missing: list[str] = []
    for field_name, field_def in schema.items():
        if field_def.required and field_name not in metadata:
            missing.append(field_name)
    return missing
