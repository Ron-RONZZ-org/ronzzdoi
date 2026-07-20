"""DOI core module — assign, resolve, redirect, and manage ronzzDOIs.

Handles the core DOI lifecycle:
- Generation and assignment of persistent identifiers (``10.ronzz/<uuid>``)
- URL resolution and redirect
- Soft redirect on URL changes (history preserved in ``redirects`` table)
- Tombstone deletion (row kept with ``deleted_at`` for 404-with-explanation)
- Paginated listing of DOIs
"""

from __future__ import annotations

from ronzzdoi.doi.constants import (
    DOI_PATTERN,
    DOI_PREFIX,
    DOI_PREFIX_PATTERN,
    UUID4_HEX_LENGTH,
    is_doi_prefix,
    is_valid_doi,
)
from ronzzdoi.doi.exceptions import (
    DOIAmbiguousError,
    DOIError,
    DOIExistsError,
    DOIInvalidError,
    DOINotFoundError,
)
from ronzzdoi.doi.schema import (
    DOIAssignRequest,
    DOIModifyRequest,
    DOIResolveResponse,
    DOIResponse,
    RedirectRecord,
)
from ronzzdoi.doi.service import DOIService

__all__ = [
    # Service
    "DOIService",
    # Exceptions
    "DOIError",
    "DOINotFoundError",
    "DOIExistsError",
    "DOIInvalidError",
    "DOIAmbiguousError",
    # Schema
    "DOIAssignRequest",
    "DOIModifyRequest",
    "DOIResponse",
    "DOIResolveResponse",
    "RedirectRecord",
    # Constants & validators
    "DOI_PREFIX",
    "UUID4_HEX_LENGTH",
    "DOI_PATTERN",
    "DOI_PREFIX_PATTERN",
    "is_valid_doi",
    "is_doi_prefix",
]
