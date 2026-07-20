"""DOI-specific exception hierarchy.

All exceptions inherit from :class:`DOIError`, which itself inherits from
:class:`lightercore.exceptions.LighterbirdError` so that client code can
catch a single base class for all domain errors in the lighter ecosystem.

Usage::

    from ronzzdoi.doi.exceptions import DOINotFoundError, DOIAmbiguousError

    try:
        service.resolve("10.ronzz/abc123")
    except DOINotFoundError:
        print("DOI not found")
    except DOIAmbiguousError as e:
        print(f"Multiple matches: {e.matches}")
"""

from __future__ import annotations

from lightercore.exceptions import AmbiguousIDError, LighterbirdError


class DOIError(LighterbirdError):
    """Base exception for all DOI-related errors."""


class DOINotFoundError(DOIError):
    """Raised when a requested DOI does not exist.

    Also raised for tombstoned DOIs so the caller can distinguish
    "never existed" from "exists but deleted" via the *tombstoned* flag.

    Attributes:
        doi: The requested DOI string.
        tombstoned: True if the DOI was deleted (tombstoned) rather than
            never existing.
    """

    def __init__(self, doi: str, *, tombstoned: bool = False) -> None:
        self.doi = doi
        self.tombstoned = tombstoned
        msg = (
            f"DOI '{doi}' has been deleted (tombstoned)."
            if tombstoned
            else f"DOI '{doi}' not found."
        )
        super().__init__(msg)


class DOIExistsError(DOIError):
    """Raised when attempting to create a DOI that already exists.

    With UUID-based generation this is extremely unlikely, but acts as a
    safety net against external ID collisions.
    """

    def __init__(self, doi: str) -> None:
        self.doi = doi
        super().__init__(f"DOI '{doi}' already exists.")


class DOIInvalidError(DOIError):
    """Raised when a DOI string does not match the expected format.

    Attributes:
        doi: The invalid DOI string.
        reason: Description of why it's invalid.
    """

    def __init__(self, doi: str, reason: str = "") -> None:
        self.doi = doi
        msg = f"Invalid DOI '{doi}'."
        if reason:
            msg += f" {reason}"
        super().__init__(msg)


class DOIAmbiguousError(DOIError):
    """Raised when a DOI prefix matches multiple entries.

    Useful for CLI interaction — the caller can present the matches
    to the user for disambiguation.

    Attributes:
        matches: List of matching DOI record dicts.
    """

    def __init__(self, message: str, matches: list[dict] | None = None) -> None:
        super().__init__(message)
        self.matches: list[dict] = matches or []


# Re-export from lightercore for convenience
__all__ = [
    "DOIError",
    "DOINotFoundError",
    "DOIExistsError",
    "DOIInvalidError",
    "DOIAmbiguousError",
]
