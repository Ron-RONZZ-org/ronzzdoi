"""Snippet content-kind constants and validation helpers.

Snippets are embeddable content fragments hosted by ronzzdoi: text
quotations, code blocks, and KaTeX math.  The ``content_kind`` field
drives both the CLI/GUI input UX and the embed rendering.
"""

from __future__ import annotations

# ── Content kinds ─────────────────────────────────────────────────────────

CONTENT_KINDS: tuple[str, ...] = ("text", "code", "math")
"""Supported snippet content kinds.

- ``text`` — quotation from a book/document (optionally with source_doi
  + page range attribution).
- ``code`` — code snippet with a ``language`` hint for highlighting.
- ``math`` — KaTeX math source (rendered server-side at embed time).
"""

# Common code languages offered as suggestions in the GUI/CLI.  Not
# exhaustive — ``language`` is a free-text hint.
SUGGESTED_LANGUAGES: tuple[str, ...] = (
    "python",
    "javascript",
    "typescript",
    "bash",
    "sql",
    "rust",
    "go",
    "c",
    "cpp",
    "java",
    "html",
    "css",
    "json",
    "yaml",
    "markdown",
    "latex",
)


def is_valid_content_kind(kind: str) -> bool:
    """Return True if *kind* is a supported content kind."""
    return kind in CONTENT_KINDS


def normalize_content_kind(kind: str) -> str:
    """Return *kind* lowercased and stripped, or raise ValueError.

    Raises:
        ValueError: If *kind* is not one of :data:`CONTENT_KINDS`.
    """
    normalized = kind.strip().lower()
    if not is_valid_content_kind(normalized):
        raise ValueError(
            f"Invalid content kind '{kind}'. "
            f"Must be one of: {', '.join(CONTENT_KINDS)}."
        )
    return normalized


__all__ = [
    "CONTENT_KINDS",
    "SUGGESTED_LANGUAGES",
    "is_valid_content_kind",
    "normalize_content_kind",
]
