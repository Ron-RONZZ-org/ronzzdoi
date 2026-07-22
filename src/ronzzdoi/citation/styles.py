"""Citation formatting functions for APA, Vancouver, and JSON styles.

Each function takes a DOI record (with ``doi_type`` + ``metadata``) and a
resolver callable for looking up referenced DOIs (people, entities, books).

Person/entity lookup should be cached per format call by the caller.
"""

from __future__ import annotations

import json
from typing import Any, Callable

DOI_RESOLVER = Callable[[str], dict[str, Any] | None]
"""Signature for resolving a DOI to its record (with deserialized metadata)."""


# ── Name helpers ────────────────────────────────────────────────────────────


def _format_person_name_apa(person: dict[str, Any]) -> str:
    """Format a person DOI's metadata as ``Last, F.`` (APA style)."""
    meta = person.get("metadata", {})
    last = meta.get("last_name", "Unknown")
    first = meta.get("first_name", "")
    initial = f"{first[0]}." if first else ""
    return f"{last}, {initial}".strip()


def _format_person_name_vancouver(person: dict[str, Any]) -> str:
    """Format a person DOI's metadata as ``Last F`` (Vancouver style)."""
    meta = person.get("metadata", {})
    last = meta.get("last_name", "Unknown")
    first = meta.get("first_name", "")
    initial = first[0] if first else ""
    return f"{last} {initial}".strip()


def _resolve_author_list(
    authors: list[dict[str, str]],
    resolve: DOI_RESOLVER,
    formatter: Callable[[dict[str, Any]], str],
) -> list[str]:
    """Resolve author entries to formatted name strings.

    Supports two author formats:

    * **Person DOI reference** — ``{"person_doi": "10.ronzz/..."}``.
      The DOI is resolved and the full person record is passed to the
      *formatter*.
    * **Inline author** — ``{"given": "...", "family": "..."}`` (CSL JSON
      convention).  The inline data is wrapped in a pseudo-person record
      matching the person-DOI format so the *formatter* can handle it.
    """
    names: list[str] = []
    for ref in authors:
        doi = ref.get("person_doi", "")
        if doi:
            # Person DOI reference — resolve and format
            person = resolve(doi)
            if person:
                names.append(formatter(person))
            else:
                names.append("[unresolved person]")
        else:
            # Inline author (given/family keys, CSL JSON convention)
            given = ref.get("given", ref.get("first_name", ""))
            family = ref.get("family", ref.get("last_name", ""))
            if given or family:
                pseudo = {"metadata": {"last_name": family, "first_name": given}}
                names.append(formatter(pseudo))
            else:
                names.append("[unknown author]")
    return names


def _resolve_issuing_authority(
    doi: str,
    resolve: DOI_RESOLVER,
) -> str:
    """Resolve an ``issuing_authority_doi`` to a display string."""
    record = resolve(doi)
    if not record:
        return "[unresolved authority]"
    if record.get("doi_type") == "person":
        return _format_person_name_apa(record)
    # abstract_entity or fallback
    return record.get("metadata", {}).get("legal_name", "[unknown entity]")


# ── APA style ───────────────────────────────────────────────────────────────


def format_apa(record: dict[str, Any], *, resolve: DOI_RESOLVER) -> str:
    """Format a DOI record in APA 7th edition style.

    Args:
        record: DOI record with ``doi_type`` and ``metadata`` deserialized.
        resolve: Callable to resolve referenced DOIs.

    Returns:
        APA-formatted citation string.
    """
    doi_type = record.get("doi_type", "external")
    meta = record.get("metadata", {})
    _resolve = resolve  # local alias for closures

    # ── Entity DOIs are not directly citable ─────────────────────────
    if doi_type in ("person", "abstract_entity", "country"):
        return _format_entity_citation(doi_type, meta, _resolve)

    # ── Common author/date prefix ───────────────────────────────────
    authors_raw = meta.get("authors") or meta.get("presenters") or meta.get("creators") or meta.get("directors") or meta.get("hosts") or meta.get("artists") or []
    author_str = _format_author_list_apa(authors_raw, _resolve)
    year = meta.get("year", meta.get("date", "n.d."))[:4] if isinstance(meta.get("date"), str) else str(meta.get("year", "n.d."))

    # ── Dispatch by type ────────────────────────────────────────────
    if doi_type == "book":
        title = meta.get("title", "Untitled")
        publisher = meta.get("publisher", "Unknown Publisher")
        edition = meta.get("edition")
        ed_str = f" ({edition})" if edition else ""
        return f"{author_str} ({year}). *{title}*{ed_str}. {publisher}."

    if doi_type == "bookSection":
        title = meta.get("title", "Untitled")
        # Resolve the parent book
        book_doi = meta.get("book_doi", "")
        book_title = _resolve_book_title(book_doi, _resolve)
        pages = meta.get("pages", "")
        pages_str = f", pp. {pages}" if pages else ""
        return f"{author_str} ({year}). {title}. In *{book_title}*{pages_str}."

    if doi_type == "scientificPaper":
        title = meta.get("title", "Untitled")
        pub = meta.get("publication", "Unknown Journal")
        subtype = meta.get("subtype", "journal-article")
        if subtype == "journal-article":
            vol = meta.get("volume", "")
            iss = meta.get("issue", "")
            pages = meta.get("pages", "")
            vol_iss = f"*, {vol}" if vol else ""
            iss_str = f"({iss})" if iss else ""
            pages_str = f", {pages}" if pages else ""
            return f"{author_str} ({year}). {title}. *{pub}*{vol_iss}{iss_str}{pages_str}."
        elif subtype == "preprint":
            archive = meta.get("archive", "")
            arch_str = f" {archive}." if archive else "."
            return f"{author_str} ({year}). {title}. *{pub}*{arch_str}"
        elif subtype == "thesis":
            return f"{author_str} ({year}). {title} [Doctoral dissertation, {pub}]."

    if doi_type == "conferencePaper":
        conf = meta.get("conference_name", "Unknown Conference")
        loc = meta.get("location", "")
        loc_str = f", {loc}" if loc else ""
        return f"{author_str} ({year}). {title}. Paper presented at {conf}{loc_str}."

    if doi_type == "presentation":
        event = meta.get("event_name", "Unknown Event")
        return f"{author_str} ({year}). {title} [Presentation]. {event}."

    if doi_type == "report":
        title = meta.get("title", "Untitled")
        inst = meta.get("institution", "Unknown Institution")
        num = meta.get("report_number", "")
        num_str = f" (No. {num})" if num else ""
        return f"{author_str} ({year}). {title}{num_str}. {inst}."

    if doi_type == "dataset":
        title = meta.get("title", "Untitled")
        repo = meta.get("repository", "Unknown Repository")
        vers = meta.get("version", "")
        vers_str = f" (Version {vers})" if vers else ""
        return f"{author_str} ({year}). {title}{vers_str} [Data set]. {repo}."

    if doi_type == "webpage":
        title = meta.get("title", "Untitled")
        site = meta.get("website_name", "Unknown Website")
        url = meta.get("url", "")
        access = meta.get("access_date", "n.d.")
        return f"{author_str} ({year}). {title}. {site}. Retrieved {access}, from {url}"

    if doi_type == "magazineArticle":
        title = meta.get("title", "Untitled")
        mag = meta.get("magazine_name", "Unknown Magazine")
        vol = meta.get("volume", "")
        iss = meta.get("issue", "")
        pages = meta.get("pages", "")
        vol_iss = f", {vol}" if vol else ""
        iss_str = f"({iss})" if iss else ""
        pages_str = f", {pages}" if pages else ""
        return f"{author_str} ({year}). {title}. *{mag}*{vol_iss}{iss_str}{pages_str}."

    if doi_type == "newspaperArticle":
        title = meta.get("title", "Untitled")
        news = meta.get("newspaper_name", "Unknown Newspaper")
        date = meta.get("date", year) if year != "n.d." else "n.d."
        sec = meta.get("section", "")
        sec_str = f", p. {sec}" if sec else ""
        return f"{author_str} ({date}). {title}. *{news}*{sec_str}."

    if doi_type == "film":
        title = meta.get("title", "Untitled")
        studio = meta.get("studio", "Unknown Studio")
        return f"{author_str} ({year}). *{title}* [Film]. {studio}."

    if doi_type == "podcast":
        title = meta.get("title", "Untitled")
        pod = meta.get("podcast_name", "Unknown Podcast")
        pub = meta.get("publisher", "Unknown Publisher")
        ep_num = meta.get("episode_number", "")
        ep_str = f", No. {ep_num}" if ep_num else ""
        return f"{author_str} ({year}). {title}{ep_str} [Audio podcast episode]. {pod}. {pub}."

    if doi_type == "song":
        title = meta.get("title", "Untitled")
        label = meta.get("label", "Unknown Label")
        album = meta.get("album", "")
        album_str = f" On *{album}*" if album else ""
        return f"{author_str} ({year}). {title}{album_str} [Song]. {label}."

    if doi_type == "media":
        title = meta.get("title", "Untitled")
        fmt = meta.get("format", "media")
        return f"{author_str} ({year}). {title} [{fmt}]."

    # ── Internal types ────────────────────────────────────────────
    if doi_type == "circulaire":
        title = meta.get("title", "Untitled")
        circ_num = meta.get("circulaire_number", "")
        issuer_doi = meta.get("issuing_authority_doi", "")
        issuer = _resolve_issuing_authority(issuer_doi, _resolve) if issuer_doi else "Unknown Authority"
        date = meta.get("date", year) if year != "n.d." else "n.d."
        return f"{issuer} ({date}). *{title}* (Circulaire No. {circ_num})."

    if doi_type == "rulebook":
        title = meta.get("title", "Untitled")
        version = meta.get("version", "")
        issuer_doi = meta.get("issuing_authority_doi", "")
        issuer = _resolve_issuing_authority(issuer_doi, _resolve) if issuer_doi else "Unknown Authority"
        date = meta.get("date", year) if year != "n.d." else "n.d."
        vers_str = f" (Version {version})" if version else ""
        return f"{issuer} ({date}). *{title}*{vers_str}."

    if doi_type == "document":
        title = meta.get("title", "Untitled")
        date = meta.get("date", "n.d.")
        desc = meta.get("description", "")
        desc_str = f" ({desc})" if desc else ""
        return f"{author_str} ({date}). *{title}*{desc_str}."

    # Fallback for custom/doc_type not in schema
    return f"{author_str} ({year}). {meta.get('title', 'Untitled')}."


def _format_author_list_apa(
    authors_raw: list[dict[str, str]] | str,
    resolve: DOI_RESOLVER,
) -> str:
    """Format an author list in APA style."""
    if isinstance(authors_raw, str):
        return authors_raw  # plain text fallback
    if not authors_raw:
        return "Unknown"
    names = _resolve_author_list(authors_raw, resolve, _format_person_name_apa)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return ", ".join(names[:-1]) + f", & {names[-1]}"


def _format_entity_citation(doi_type: str, meta: dict[str, Any], resolve: DOI_RESOLVER) -> str:
    """Format an entity DOI as a plain label (not a citation)."""
    if doi_type == "person":
        name = f"{meta.get('first_name', '')} {meta.get('last_name', 'Unknown')}".strip()
        return f"{name} [Person DOI — not a citable resource]"
    if doi_type == "abstract_entity":
        return f"{meta.get('legal_name', 'Unknown Entity')} [Entity DOI — not a citable resource]"
    if doi_type == "country":
        return f"{meta.get('iso_code', 'Unknown')} [Country DOI — not a citable resource]"
    return "[Entity DOI — not a citable resource]"


def _resolve_book_title(book_doi: str, resolve: DOI_RESOLVER) -> str:
    """Resolve a book DOI and return its title."""
    if not book_doi:
        return "Unknown Book"
    book = resolve(book_doi)
    if not book:
        return "Unknown Book"
    return book.get("metadata", {}).get("title", "Untitled Book")


# ── Vancouver style ─────────────────────────────────────────────────────────


def format_vancouver(record: dict[str, Any], *, resolve: DOI_RESOLVER) -> str:
    """Format a DOI record in Vancouver style.

    Args:
        record: DOI record with ``doi_type`` and ``metadata`` deserialized.
        resolve: Callable to resolve referenced DOIs.

    Returns:
        Vancouver-formatted citation string.
    """
    doi_type = record.get("doi_type", "external")
    meta = record.get("metadata", {})
    _resolve = resolve

    if doi_type in ("person", "abstract_entity", "country"):
        return _format_entity_citation(doi_type, meta, _resolve)

    authors_raw = meta.get("authors") or meta.get("presenters") or meta.get("creators") or meta.get("directors") or meta.get("hosts") or meta.get("artists") or []
    author_str = _format_author_list_vancouver(authors_raw, _resolve)
    year = meta.get("year", meta.get("date", "n.d."))[:4] if isinstance(meta.get("date"), str) else str(meta.get("year", "n.d."))

    if doi_type == "book":
        title = meta.get("title", "Untitled")
        publisher = meta.get("publisher", "Unknown Publisher")
        edition = meta.get("edition")
        ed_str = f" ({edition})" if edition else ""
        return f"{author_str}. {title}{ed_str}. {publisher}; {year}."

    if doi_type == "scientificPaper":
        title = meta.get("title", "Untitled")
        pub = meta.get("publication", "Unknown Journal")
        subtype = meta.get("subtype", "journal-article")
        if subtype == "journal-article":
            vol = meta.get("volume", "")
            iss = meta.get("issue", "")
            pages = meta.get("pages", "")
            vol_iss = f"{vol}" if vol else ""
            iss_str = f"({iss})" if iss else ""
            pages_str = f":{pages}" if pages else ""
            return f"{author_str}. {title}. {pub}. {year};{vol_iss}{iss_str}{pages_str}."
        elif subtype == "preprint":
            archive = meta.get("archive", "")
            arch_str = f" {archive}." if archive else ""
            return f"{author_str}. {title}. {pub}. {year}{arch_str}"
        elif subtype == "thesis":
            return f"{author_str}. {title} [Doctoral dissertation]. {pub}; {year}."

    # For types not explicitly Vancouver-mapped, use APA-like format
    # with Vancouver name style
    return format_apa(record, resolve=resolve)


def _format_author_list_vancouver(
    authors_raw: list[dict[str, str]] | str,
    resolve: DOI_RESOLVER,
) -> str:
    """Format an author list in Vancouver style."""
    if isinstance(authors_raw, str):
        return authors_raw
    if not authors_raw:
        return "Unknown"
    names = _resolve_author_list(authors_raw, resolve, _format_person_name_vancouver)
    return ", ".join(names)


# ── JSON style ──────────────────────────────────────────────────────────────


def format_json(record: dict[str, Any], *, resolve: DOI_RESOLVER) -> str:
    """Format a DOI record as a JSON blob of citation metadata.

    Args:
        record: DOI record with ``doi_type`` and ``metadata`` deserialized.
        resolve: Callable to resolve referenced DOIs.

    Returns:
        JSON string of citation metadata.
    """
    doi_type = record.get("doi_type", "external")
    meta = record.get("metadata", {})

    citation_data: dict[str, Any] = {
        "doi": record.get("doi", ""),
        "doi_type": doi_type,
        "title": meta.get("title", ""),
        "metadata": meta,
    }

    # Resolve author/creator names for convenience
    for list_key in ("authors", "presenters", "creators", "directors", "hosts", "artists"):
        items = meta.get(list_key, [])
        if isinstance(items, list) and items:
            resolved_names: list[str] = []
            for ref in items:
                p_doi = ref.get("person_doi", "")
                if p_doi:
                    person = resolve(p_doi)
                    if person:
                        m = person.get("metadata", {})
                        name = f"{m.get('last_name', '')}, {m.get('first_name', '')}".strip().strip(",")
                        resolved_names.append(name or "[unknown]")
                    else:
                        resolved_names.append(p_doi)
                else:
                    resolved_names.append(str(ref))
            citation_data[f"resolved_{list_key}"] = resolved_names

    # Resolve issuing authority
    issuer_doi = meta.get("issuing_authority_doi", "")
    if issuer_doi:
        issuer = resolve(issuer_doi)
        if issuer:
            if issuer.get("doi_type") == "person":
                m = issuer.get("metadata", {})
                citation_data["resolved_issuing_authority"] = (
                    f"{m.get('last_name', '')}, {m.get('first_name', '')}"
                ).strip().strip(",")
            else:
                citation_data["resolved_issuing_authority"] = (
                    issuer.get("metadata", {}).get("legal_name", "")
                )

    return json.dumps(citation_data, indent=2, ensure_ascii=False)


# ── Style registry ──────────────────────────────────────────────────────────


STYLES: dict[str, Any] = {
    "apa": format_apa,
    "vancouver": format_vancouver,
    "json": format_json,
}
"""Mapping of style names to format functions."""


def available_styles() -> list[str]:
    """Return the list of supported citation style names."""
    return list(STYLES.keys())
