"""Service classes for ronzzdoi — DOIService, RedirectService.

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

    Provides ``search_fts()`` for FTS5 full-text search and
    ``search_semantic()`` for vector search (via lightersearch, if
    installed).  Embeddings are automatically synced on create/update
    and removed on delete.
    """

    _vec_available: bool = False
    """Set to ``True`` by :meth:`_probe_lightersearch` if sqlite-vec loaded."""

    def __init__(self, db: LighterDB) -> None:
        super().__init__(db, table="dois", pk_column="doi")
        self._probe_lightersearch()

    # ── Lightersearch probe ────────────────────────────────────────────

    def _probe_lightersearch(self) -> None:
        """Check if lightersearch is available for semantic search.

        Sets ``self._vec_available`` so :meth:`search` can
        decide at runtime whether to use vec0 or fall back to FTS5.
        """
        try:
            from lightersearch.vec import available as vec_available

            self._vec_available = vec_available(self.db)
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
        return self._search_fts(query, limit, include_snippet=False)

    def search_fts_with_snippet(
        self, query: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Full-text search with a highlighted ``snippet`` field.

        Uses SQLite FTS5's built-in ``snippet()`` function to extract
        the best-matching excerpt from the ``title`` column.

        Args:
            query: FTS5 query string.
            limit: Maximum number of results.

        Returns:
            List of DOI dicts with an extra ``snippet`` key containing an
            HTML-highlighted excerpt (``<mark>...</mark>``), or ``None``
            for each result if the query is empty.
        """
        return self._search_fts(query, limit, include_snippet=True)

    def _search_fts(
        self, query: str, limit: int = 20, include_snippet: bool = False
    ) -> list[dict[str, Any]]:
        """Internal FTS5 search implementation.

        Args:
            query: FTS5 query string.
            limit: Maximum number of results.
            include_snippet: If ``True``, include an FTS5 ``snippet()``
                excerpt in each result dict under the ``snippet`` key.

        Returns:
            List of DOI dicts matching the query, ordered by relevance.
        """
        if not query.strip():
            return []
        snippet_col = (
            ", snippet(dois_fts, 1, '<mark>', '</mark>', '…', 64) AS snippet"
            if include_snippet
            else ""
        )
        sql = f"""
            SELECT d.*{snippet_col}
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
            try:
                return self._search_semantic(query, limit)
            except Exception:
                pass
        return self.search_fts(query, limit)

    def _search_semantic(
        self, query: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Semantic search via lightersearch.

        Returns:
            List of DOI dicts with ``_distance`` metadata, or empty
            list if embedding generation fails.
        """
        try:
            from lightersearch.search import search_dois

            return search_dois(self.db, query, limit=limit)
        except (ImportError, Exception):
            return []

    # ── Hooks for lightersearch ────────────────────────────────────────

    def _post_create(self, data: dict[str, Any], result: dict[str, Any]) -> None:
        """Post-create hook — generates embedding if lightersearch available."""
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

        Constructs a text blob from the DOI's title and metadata,
        then generates an embedding via lightersearch and stores it
        in the ``vec_dois`` table.

        Failures are logged at WARNING level (not raised) so that
        embedding errors do not block the create/update flow.
        """
        doi_entry = self.get(doi)
        if not doi_entry:
            return

        text = " ".join(
            filter(None, [
                doi_entry.get("title", ""),
                doi_entry.get("metadata_json", "{}"),
            ])
        )
        if not text.strip():
            return

        # Fetch the SQLite rowid (not returned by SELECT *)
        row = self.db.execute_one(
            f"SELECT rowid FROM {self.table} WHERE {self._pk_column} = ?",
            (doi,),
        )
        if not row:
            return

        try:
            from lightersearch.embed import embed_single, vector_to_bytes
            from lightersearch.vec import insert_vector

            vec = embed_single(text)
            vec_bytes = vector_to_bytes(vec)
            insert_vector(self.db, rowid=row["rowid"], vector=vec_bytes)
        except Exception:
            import logging

            logging.getLogger("ronzzdoi.db").warning(
                "Failed to sync embedding for DOI %s", doi, exc_info=True
            )

    def _remove_embedding(self, doi: str) -> None:
        """Remove the embedding for *doi*.

        Failures are logged at WARNING level (not raised).
        """
        row = self.db.execute_one(
            f"SELECT rowid FROM {self.table} WHERE {self._pk_column} = ?",
            (doi,),
        )
        if not row:
            return

        try:
            from lightersearch.vec import delete_vector

            delete_vector(self.db, rowid=row["rowid"])
        except Exception:
            import logging

            logging.getLogger("ronzzdoi.db").warning(
                "Failed to remove embedding for DOI %s", doi, exc_info=True
            )


class RedirectService(CRUDService):
    """Redirect history service.

    Thin wrapper around CRUDService with ``table="redirects"``.
    """

    def __init__(self, db: LighterDB) -> None:
        super().__init__(db, table="redirects", pk_column="redirect_id")
