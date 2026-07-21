"""DOI format constants.

Defines the canonical ronzzDOI format and validation helpers.

Format::

    10.ronzz/<suffix>

Where:
    - ``10`` — DOI directory indicator (DOI namespace)
    - ``ronzz`` — registrant code for ronzz.org
    - ``<suffix>`` — free-form (no semantic encoding per DOI Handbook).

Entity DOIs use non-opaque suffixes as documented exceptions:
``10.ronzz/country/<ISO_3166-1_alpha-2>``.
"""

from __future__ import annotations

import re

# ── DOI prefix ──────────────────────────────────────────────────────────────

DOI_PREFIX = "10.ronzz"

# ── Suffix parameters ───────────────────────────────────────────────────────

UUID4_HEX_LENGTH = 32

# ── Compiled regex for full DOI validation ──────────────────────────────────

DOI_PATTERN = re.compile(
    rf"^{re.escape(DOI_PREFIX)}/.+$",
)

DOI_PREFIX_PATTERN = re.compile(
    rf"^{re.escape(DOI_PREFIX)}/",
)


def is_valid_doi(doi: str) -> bool:
    """Return True if *doi* matches the canonical ronzzDOI format.

    Accepts any non-empty suffix after ``10.ronzz/`` per the
    DOI Handbook's opaque-identifier principle (with documented
    exceptions for country DOIs).
    """
    return DOI_PATTERN.match(doi) is not None


def is_doi_prefix(s: str) -> bool:
    """Return True if *s* looks like the start of a ronzzDOI.

    Accepts the full DOI prefix (``10.ronzz/``) or a prefix-plus-partial-suffix.
    """
    return DOI_PREFIX_PATTERN.match(s) is not None


__all__ = [
    "DOI_PREFIX",
    "UUID4_HEX_LENGTH",
    "DOI_PATTERN",
    "DOI_PREFIX_PATTERN",
    "is_valid_doi",
    "is_doi_prefix",
]
