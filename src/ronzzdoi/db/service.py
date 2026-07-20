"""Service classes for ronzzdoi — DOIService, CitationService, RedirectService.

Each class extends :class:`lightercore.crud.CRUDService` with
domain-specific overrides for primary-key handling, search, and
side-effect hooks.

Usage::

    from ronzzdoi.db.service import DOIService

    doi_svc = DOIService(db)
    doi = doi_svc.create({"doi": "10.ronzz/books/2024/smith", "target_url": "..."})
    results = doi_svc.search_fts("smith")
"""

from __future__ import annotations

from typing import Any

from lightercore.crud import CRUDService
from lightercore.db import LighterDB
from lightercore.exceptions import DataError


class DOIService(CRUDService):
    """DOI management service.

    Overrides ``create()`` to require an explicit ``doi`` value
    (no auto-generated UUID fallback) and ``get()`` to use exact match
    instead of prefix matching.

    Provides ``search_fts()`` for FTS5 full-text search and optional
    lightersearch integration via the ``_post_*`` hooks.
    """

    _vec_available: bool = False
    """Set to ``True`` by :meth:`_probe_lightersearch` if sqlite-vec loaded."""

    def __init__(self, db: LighterDB) -> None:
        super().__init__(db, table="dois", pk_column="doi")
        self._probe_lightersearch()

    # ── Lightersearch probe ────────────────────────────────────────────

    def _probe_lightersearch(self) -> None:
        """Check if sqlite-vec is available for semantic search.

        Sets ``self._vec_available`` so :meth:`search_semantic` can
        decide at runtime whether to use vec0 or fall back to FTS5.
        """
        try:
            import sqlite_vec  # noqa: F401

            self._vec_available = True
        except ImportError:
            self._vec_available = False

    # ── Create override ────────────────────────────────────────────────

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a DOI.

        Raises:
            DataError: If ``data`` does not contain a ``doi`` key.
        """
        if "doi" not in data:
            raise DataError(
                "doi is required for DOI creation. "
                "Use a DOI in the format 10.ronzz/<prefix>/<suffix>."
            )
        data.setdefault("doi_type", "external")
        return super().create(data)

    # ── Get override (exact match) ─────────────────────────────────────

    def get(self, pk: str) -> dict[str, Any] | None:
        """Get a DOI by exact ``doi`` match.

        Unlike the base :meth:`CRUDService.get`, this uses ``= ?``
        instead of ``LIKE ?`` with prefix matching — DOIs are exact
        identifiers per the DOI Handbook.
        """
        return self.db.execute_one(
            f"SELECT * FROM {self.table} WHERE {self._pk_column} = ?",
            (pk,),
        )

    # ── Search ─────────────────────────────────────────────────────────

    def search_fts(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Full-text search across DOI metadata via FTS5.

        Args:
            query: FTS5 query string (supports FTS5 syntax like
                ``"exact phrase"``, ``prefix*``, ``NEAR``, etc.).
            limit: Maximum number of results.

        Returns:
            List of DOI dicts matching the query, ordered by relevance.
        """
        if not query.strip():
            return []
        sql = """
            SELECT d.*
            FROM dois d
            JOIN dois_fts f ON d.rowid = f.rowid
            WHERE dois_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        return self.db.execute(sql, (query, limit))

    def search(
        self,
        query: str,
        mode: str = "fts",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Unified search — FTS5 or semantic (if available).

        Args:
            query: Search query string.
            mode: ``"fts"`` for FTS5, ``"semantic"`` for vector search
                (falls back to FTS5 if lightersearch is unavailable).
            limit: Maximum number of results.

        Returns:
            List of DOI dicts matching the query.
        """
        if mode == "semantic" and self._vec_available:
            return self._search_semantic(query, limit)
        return self.search_fts(query, limit)

    def _search_semantic(
        self, query: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Semantic search via sqlite-vec (lightersearch).

        Falls back to FTS5 if embedding generation fails.
        """
        # Stub — full implementation requires lightersearch which is
        # created as a separate repo.  For now, returns FTS5 results.
        return self.search_fts(query, limit)

    # ── Hooks for lightersearch ────────────────────────────────────────

    def _post_create(self, data: dict[str, Any], result: dict[str, Any]) -> None:
        """Post-create hook — triggers embedding if lightersearch available."""
        if self._vec_available:
            self._sync_embedding(result["doi"])

    def _post_update(
        self,
        pk: str,
        old_data: dict[str, Any] | None,
        new_data: dict[str, Any],
    ) -> None:
        """Post-update hook — refreshes embedding."""
        if self._vec_available:
            self._sync_embedding(pk)

    def _post_delete(self, pk: str, data: dict[str, Any] | None) -> None:
        """Post-delete hook — removes embedding."""
        if self._vec_available:
            self._remove_embedding(pk)

    def _sync_embedding(self, doi: str) -> None:
        """Generate or update an embedding for *doi*.

        No-op until lightersearch is available.
        """

    def _remove_embedding(self, doi: str) -> None:
        """Remove the embedding for *doi*.

        No-op until lightersearch is available.
        """


class CitationService(CRUDService):
    """Citation management service.

    Thin wrapper around CRUDService with ``table="citations"``.
    """

    def __init__(self, db: LighterDB) -> None:
        super().__init__(db, table="citations", pk_column="citation_id")


class RedirectService(CRUDService):
    """Redirect history service.

    Thin wrapper around CRUDService with ``table="redirects"``.
    """

    def __init__(self, db: LighterDB) -> None:
        super().__init__(db, table="redirects", pk_column="redirect_id")
