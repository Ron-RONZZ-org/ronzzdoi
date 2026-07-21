"""Citation formatting engine for ronzzdoi.

Reads DOI metadata and returns styled citation text.  No separate citation
storage — the DOI's ``doi_type`` + ``metadata_json`` are the citation source.

See ``docs/AGENTS-citation.md`` for module-level rules and conventions.

Usage::

    from ronzzdoi.citation import CitationFormatter

    formatter = CitationFormatter(doi_service)
    apa = formatter.format("10.ronzz/<uuid>", style="apa")
    styles = formatter.available_styles()
"""

from __future__ import annotations

from ronzzdoi.citation.formatter import CitationFormatter
from ronzzdoi.citation.schemas import DOC_TYPE_SCHEMAS, DOC_TYPES, validate_metadata

__all__ = [
    "CitationFormatter",
    "DOC_TYPE_SCHEMAS",
    "DOC_TYPES",
    "validate_metadata",
]
