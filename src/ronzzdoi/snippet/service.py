"""SnippetService — embeddable snippet lifecycle management.

Snippets are content fragments hosted by ronzzdoi (text quotations,
code blocks, KaTeX math).  Each snippet is a DOI — the ``dois`` row
provides the persistent identity (``doi_type='snippet'``,
``target_url=NULL``) and a parallel ``snippets`` row carries the
content.  The two rows are written atomically in a single transaction.

Usage::

    from ronzzdoi.snippet.service import SnippetService

    svc = SnippetService(db, doi_svc)
    record = svc.assign("text", "To be or not to be…",
                        source_doi="10.ronzz/hamlet", page_start="p. 12")
    resolved = svc.resolve(record["doi"])
"""

from __future__ import annotations

from typing import Any

from lightercore.crud import now
from lightercore.db import LighterDB

from ronzzdoi.doi.exceptions import DOINotFoundError
from ronzzdoi.doi.service import DOIService
from ronzzdoi.snippet.constants import normalize_content_kind
from ronzzdoi.snippet.exceptions import (
    SnippetInvalidError,
    SnippetNotFoundError,
    SnippetSourceNotFoundError,
)


class SnippetService:
    """Manage the full lifecycle of embeddable snippets.

    A snippet spans two tables: ``dois`` (identity + timestamps) and
    ``snippets`` (content).  All mutations keep them in sync within a
    single transaction.

    Args:
        db: A :class:`lightercore.db.LighterDB` instance.
        doi_svc: A :class:`ronzzdoi.doi.service.DOIService` instance
            used for DOI resolution and identity generation.  Defaults
            to a fresh instance bound to *db*.
    """

    def __init__(self, db: LighterDB, doi_svc: DOIService | None = None) -> None:
        self._db = db
        self._doi_svc = doi_svc or DOIService(db)

    # ── Public API ──────────────────────────────────────────────────────────

    def assign(
        self,
        content_kind: str,
        content: str,
        *,
        title: str = "",
        language: str = "",
        source_doi: str | None = None,
        page_start: str = "",
        page_end: str = "",
    ) -> dict[str, Any]:
        """Assign a new snippet DOI.

        Creates the ``dois`` row (``doi_type='snippet'``) and the
        ``snippets`` row atomically in a single transaction.

        Args:
            content_kind: ``"text"``, ``"code"``, or ``"math"``.
            content: The snippet content.  Must be non-empty.
            title: Human-readable title.
            language: Code language hint (code snippets only).
            source_doi: Optional source DOI (must exist and be active).
            page_start: Source page start (text quotations).
            page_end: Source page end (text quotations).

        Returns:
            The merged snippet record (DOI fields + snippet fields).

        Raises:
            SnippetInvalidError: If *content_kind* is invalid or *content*
                is empty.
            SnippetSourceNotFoundError: If *source_doi* does not exist or
                is tombstoned.
        """
        try:
            kind = normalize_content_kind(content_kind)
        except ValueError as exc:
            raise SnippetInvalidError(str(exc)) from exc

        if not content or not content.strip():
            raise SnippetInvalidError("content must be non-empty.")

        source = self._validate_source(source_doi) if source_doi else None

        ts = now()
        doi = DOIService.generate_doi()

        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO dois (doi, target_url, title, doi_type, metadata_json, "
                "created_at, updated_at) "
                "VALUES (?, NULL, ?, 'snippet', '{}', ?, ?)",
                (doi, title, ts, ts),
            )
            conn.execute(
                "INSERT INTO snippets (doi, content_kind, content, language, "
                "source_doi, page_start, page_end, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doi, kind, content, language, source, page_start, page_end, ts, ts),
            )

        return self._fetch_record(doi)

    def resolve(
        self,
        doi: str,
        *,
        include_redirects: bool = True,
    ) -> dict[str, Any] | None:
        """Resolve a DOI to its record, attaching snippet content if present.

        Delegates to :meth:`DOIService.resolve` (prefix matching).  If the
        resolved DOI has a ``snippets`` row, its fields are merged into
        the record.  Non-snippet DOIs resolve normally (no snippet keys).

        Args:
            doi: Full DOI or prefix to resolve.
            include_redirects: Passed through to ``DOIService.resolve``.

        Returns:
            The record dict (with ``content_kind``/``content``/… when the
            DOI is a snippet), or ``None`` if no match is found.

        Raises:
            DOIAmbiguousError: If *doi* is an ambiguous prefix.
        """
        record = self._doi_svc.resolve(doi, include_redirects=include_redirects)
        if record is None:
            return None
        return self._merge_snippet_row(record)

    def modify(
        self,
        doi: str,
        *,
        content: str | None = None,
        content_kind: str | None = None,
        title: str | None = None,
        language: str | None = None,
        source_doi: str | None = None,
        page_start: str | None = None,
        page_end: str | None = None,
    ) -> dict[str, Any]:
        """Modify an existing snippet.

        Only provided fields are updated.  Pass ``""`` to clear a field
        (e.g. ``source_doi="", language=""``).  ``content_kind`` and
        ``content`` are validated when provided.

        Args:
            doi: Full DOI or prefix of the snippet to modify.
            content: New content.
            content_kind: New content kind (``text``/``code``/``math``).
            title: New title (written to the ``dois`` row).
            language: New language hint.
            source_doi: New source DOI, or ``""`` to clear.
            page_start: New page start.
            page_end: New page end.

        Returns:
            The updated snippet record.

        Raises:
            DOINotFoundError: If the DOI does not exist.
            SnippetNotFoundError: If the DOI exists but is not a snippet.
            SnippetInvalidError: If a provided field fails validation.
            SnippetSourceNotFoundError: If the new *source_doi* is invalid.
            DOIAmbiguousError: If the prefix is ambiguous.
        """
        record = self._doi_svc._resolve_exact(doi)
        if record is None:
            raise DOINotFoundError(doi)

        snippet = self._get_snippet_row(record["doi"])
        if snippet is None:
            raise SnippetNotFoundError(record["doi"])

        updates: dict[str, Any] = {}
        if content is not None:
            if not content.strip():
                raise SnippetInvalidError("content must be non-empty.")
            updates["content"] = content
        if content_kind is not None:
            try:
                updates["content_kind"] = normalize_content_kind(content_kind)
            except ValueError as exc:
                raise SnippetInvalidError(str(exc)) from exc
        if language is not None:
            updates["language"] = language
        if page_start is not None:
            updates["page_start"] = page_start
        if page_end is not None:
            updates["page_end"] = page_end
        if source_doi is not None:
            if source_doi.strip():
                updates["source_doi"] = self._validate_source(source_doi)
            else:
                updates["source_doi"] = None

        if not updates and title is None:
            return self._fetch_record(record["doi"])

        ts = now()
        with self._db.transaction() as conn:
            if updates:
                set_clauses = [f"{k} = ?" for k in updates]
                values = [updates[k] for k in updates]
                conn.execute(
                    f"UPDATE snippets SET {', '.join(set_clauses)}, updated_at = ? "
                    "WHERE doi = ?",
                    (*values, ts, record["doi"]),
                )
            if title is not None:
                conn.execute(
                    "UPDATE dois SET title = ?, updated_at = ? WHERE doi = ?",
                    (title, ts, record["doi"]),
                )

        return self._fetch_record(record["doi"])

    def delete(self, doi: str) -> bool:
        """Tombstone a snippet by setting ``deleted_at`` on both rows.

        The rows are NOT removed — ``deleted_at`` is set so resolution
        can report a tombstone.

        Args:
            doi: Full DOI or prefix of the snippet to delete.

        Returns:
            ``True`` if the snippet was tombstoned, ``False`` if the DOI
            does not exist.

        Raises:
            SnippetNotFoundError: If the DOI exists but is not a snippet.
            DOIAmbiguousError: If the prefix is ambiguous.
        """
        record = self._doi_svc._resolve_exact(doi)
        if record is None:
            return False
        if self._get_snippet_row(record["doi"]) is None:
            raise SnippetNotFoundError(record["doi"])

        ts = now()
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE dois SET deleted_at = ?, updated_at = ? WHERE doi = ?",
                (ts, ts, record["doi"]),
            )
            conn.execute(
                "UPDATE snippets SET deleted_at = ?, updated_at = ? WHERE doi = ?",
                (ts, ts, record["doi"]),
            )
        return True

    # ── Internal helpers ────────────────────────────────────────────────────

    def enrich(self, record: dict[str, Any]) -> dict[str, Any]:
        """Attach snippet content fields to a resolved DOI record.

        Records returned by DOI listing/search carry no snippet content;
        this merges the ``snippets`` row when the record is a snippet
        (determined by ``doi_type == 'snippet'``).  Non-snippet records
        are returned unchanged.

        Args:
            record: A DOI record dict from :class:`DOIService`.

        Returns:
            The record with ``content_kind``/``content``/``language``/
            ``source_doi``/``page_start``/``page_end`` merged when the
            DOI is a snippet.
        """
        if record.get("doi_type") != "snippet":
            return record
        return self._merge_snippet_row(record)

    def _validate_source(self, source_doi: str) -> str:
        """Return *source_doi* if it references an active DOI.

        Raises:
            SnippetSourceNotFoundError: If the DOI does not exist or is
                tombstoned.
        """
        row = self._db.execute_one(
            "SELECT doi FROM dois WHERE doi = ? AND deleted_at IS NULL",
            (source_doi,),
        )
        if row is None:
            raise SnippetSourceNotFoundError(source_doi)
        return source_doi

    def _get_snippet_row(self, doi: str) -> dict[str, Any] | None:
        """Fetch the raw ``snippets`` row for *doi*, or None."""
        return self._db.execute_one(
            "SELECT * FROM snippets WHERE doi = ?",
            (doi,),
        )

    def _fetch_record(self, doi: str) -> dict[str, Any]:
        """Fetch and merge the DOI + snippet records for *doi*.

        Raises:
            DOINotFoundError: If the DOI row vanished (should not happen
                inside a healthy flow).
        """
        record = self._doi_svc.resolve(doi, include_redirects=False)
        if record is None:
            raise DOINotFoundError(doi)
        return self._merge_snippet_row(record)

    def _merge_snippet_row(self, record: dict[str, Any]) -> dict[str, Any]:
        """Merge the ``snippets`` row into a resolved DOI record.

        When the DOI is a snippet, adds ``content_kind``, ``content``,
        ``language``, ``source_doi``, ``page_start``, ``page_end`` to the
        record (in place) and returns it.
        """
        row = self._get_snippet_row(record["doi"])
        if row is None:
            return record
        for key in (
            "content_kind",
            "content",
            "language",
            "source_doi",
            "page_start",
            "page_end",
        ):
            record[key] = row[key]
        return record


__all__ = ["SnippetService"]
