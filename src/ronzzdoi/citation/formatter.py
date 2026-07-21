"""CitationFormatter — reads DOI metadata and returns styled citation text.

No CRUD — purely a formatting service.  The DOI's ``doi_type`` +
``metadata_json`` are the citation source.
"""

from __future__ import annotations

from typing import Any

from ronzzdoi.citation.schemas import DOC_TYPE_SCHEMAS, DOC_TYPES, ENTITY_TYPES, validate_metadata
from ronzzdoi.citation.styles import STYLES, available_styles as _available_styles
from ronzzdoi.doi.exceptions import DOINotFoundError
from ronzzdoi.db.service import DOIService


class CitationFormatter:
    """Format DOI records as styled citations.

    Reads metadata from the DOI service and delegates to style-specific
    formatters.  Referenced DOIs (person, abstract_entity, book) are
    resolved on-the-fly and cached per ``format()`` call.

    Usage::

        formatter = CitationFormatter(doi_service)
        apa = formatter.format("10.ronzz/abc...", style="apa")
        print(formatter.available_styles())  # ["apa", "vancouver", "json"]
    """

    def __init__(self, doi_service: DOIService) -> None:
        """Initialize the formatter.

        Args:
            doi_service: A :class:`ronzzdoi.db.service.DOIService` instance
                         for reading DOI records.
        """
        self._doi = doi_service
        self._cache: dict[str, dict[str, Any]] = {}

    # ── Public API ──────────────────────────────────────────────────────────

    def format(self, doi: str, style: str = "apa") -> str:
        """Format a citation for the given DOI in the requested style.

        Args:
            doi: Full DOI (``10.ronzz/...``) or prefix to resolve.
            style: Citation style name (see :meth:`available_styles`).

        Returns:
            Formatted citation string.

        Raises:
            DOINotFoundError: If the DOI does not exist.
            ValueError: If *style* is not a supported style.
        """
        record = self._resolve(doi)
        if record is None:
            raise DOINotFoundError(doi)

        formatter = STYLES.get(style)
        if formatter is None:
            raise ValueError(
                f"Unsupported citation style '{style}'. "
                f"Available styles: {', '.join(self.available_styles())}"
            )

        # Fresh per-call cache for resolving referenced DOIs
        self._cache = {}
        try:
            return formatter(record, resolve=self._resolve)
        finally:
            self._cache.clear()

    @staticmethod
    def available_styles() -> list[str]:
        """Return the list of supported citation style names.

        Returns:
            ``["apa", "vancouver", "json"]``
        """
        return _available_styles()

    def validate_doi_metadata(self, doi: str) -> list[str]:
        """Validate that the DOI's metadata has all required fields.

        Args:
            doi: Full DOI or prefix to resolve and validate.

        Returns:
            List of missing required field names.  Empty list means valid.
            Entity DOIs (person, abstract_entity, country) always return
            an empty list.

        Raises:
            DOINotFoundError: If the DOI does not exist.
        """
        record = self._resolve(doi)
        if record is None:
            raise DOINotFoundError(doi)

        doi_type = record.get("doi_type", "external")
        metadata = record.get("metadata", {})
        return validate_metadata(doi_type, metadata)

    # ── Internal helpers ────────────────────────────────────────────────────

    def _resolve(self, doi: str) -> dict[str, Any] | None:
        """Resolve a DOI, using per-call cache.

        If the DOI is already cached in the current ``format()`` call,
        returns the cached record.  Otherwise resolves via ``DOIService``
        and caches the result.
        """
        if not doi:
            return None
        if doi in self._cache:
            return self._cache[doi]

        record = self._doi.resolve(doi)
        if record is not None:
            self._cache[doi] = record
        return record
