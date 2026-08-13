"""Snippet-specific exception hierarchy.

All exceptions inherit from :class:`SnippetError`, which itself inherits
from :class:`lightercore.exceptions.LighterError` so client code can
catch a single base class for all domain errors in the lighter ecosystem.

Missing DOIs raise :class:`ronzzdoi.doi.exceptions.DOINotFoundError` —
a snippet is a DOI, so DOI-level errors are reused for consistency.
"""

from __future__ import annotations

from lightercore.exceptions import LighterError


class SnippetError(LighterError):
    """Base exception for all snippet-related errors."""


class SnippetNotFoundError(SnippetError):
    """Raised when a DOI exists but has no snippet row.

    Unlike :class:`DOINotFoundError` (the DOI itself does not exist),
    this signals "the DOI is there but it is not a snippet".
    """

    def __init__(self, doi: str) -> None:
        self.doi = doi
        super().__init__(f"DOI '{doi}' exists but is not a snippet.")


class SnippetInvalidError(SnippetError):
    """Raised when snippet content/fields fail validation.

    Attributes:
        reason: Description of what failed validation.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Invalid snippet: {reason}")


class SnippetSourceNotFoundError(SnippetError):
    """Raised when a referenced source DOI does not exist or is tombstoned.

    Attributes:
        source_doi: The missing source DOI.
    """

    def __init__(self, source_doi: str) -> None:
        self.source_doi = source_doi
        super().__init__(
            f"Source DOI '{source_doi}' not found or tombstoned. "
            "Snippets can only reference active DOIs."
        )


__all__ = [
    "SnippetError",
    "SnippetInvalidError",
    "SnippetNotFoundError",
    "SnippetSourceNotFoundError",
]
