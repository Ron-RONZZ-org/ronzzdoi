"""Snippet content normalization — input hygiene for ``!snippet add``.

Users paste snippet content from chat windows, editors, and web pages,
so the raw input is often wrapped in *transport markup*:

- ``math`` content usually arrives as ``$$E = mc^2$$`` or ``$x^2$`` —
  KaTeX wants the bare LaTeX source, not the delimiter wrappers.
- ``code`` content usually arrives inside a fenced block
  (`` ```python … ``` ``) or single backticks (`` `print(1)` ``).
- ``text`` content is **stored verbatim** — it is markdown/HTML source,
  not transport markup.  It is rendered to rich HTML at display time by
  the frontends (admin GUI and public-web embed), and the edit form
  shows the raw markdown the user pasted.

This module strips the transport wrappers for math/code at write time (in
:class:`ronzzdoi.snippet.service.SnippetService`).  All functions are pure
and dependency-free.
"""

from __future__ import annotations

import re

from ronzzdoi.snippet.constants import normalize_content_kind

# ── math: strip $ / $$ delimiters ─────────────────────────────────────────


def strip_math_delimiters(content: str) -> str:
    """Strip ``$$…$$`` / ``$…$`` wrappers from KaTeX source.

    Leading/trailing whitespace outside the delimiters is trimmed; a
    bare LaTeX string (no delimiters) is returned unchanged.

    Args:
        content: Raw math snippet content (possibly delimiter-wrapped).

    Returns:
        The unwrapped KaTeX source.
    """
    text = content.strip()
    if text.startswith("$$") and text.endswith("$$"):
        return text[2:-2].strip()
    if text.startswith("$") and text.endswith("$"):
        return text[1:-1].strip()
    return text


# ── code: strip ``` fences / ` backticks ─────────────────────────────────

# Fenced block: optional opening fence (with language hint), payload,
# closing fence.  The closing fence must be the last thing in the string.
_FENCE_RE = re.compile(r"^[\t ]*`{3,}[^\n]*\n(.*?)\n?[\t ]*`{3,}[\t ]*$", re.DOTALL)


def strip_code_fences(content: str) -> str:
    """Strip fenced-block or inline-backtick wrappers from code.

    Handles::

        ```python          ```            `print(1)`
        print(1)           print(1)
        ```                ```

    Content that is not delimited (or is an unclosed fence) is returned
    unchanged.  The language hint on an opening fence is dropped.

    Args:
        content: Raw code snippet content.

    Returns:
        The bare code.
    """
    text = content.strip()
    match = _FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    if (
        len(text) >= 2
        and text.startswith("`")
        and text.endswith("`")
        and not text.startswith("```")
    ):
        return text[1:-1].strip()
    return text


# ── dispatcher ────────────────────────────────────────────────────────────


def normalize_content(content_kind: str, content: str) -> str:
    """Normalize *content* for the given content kind.

    Applies the kind-specific transport-markup stripping:

    - ``math`` — strip ``$$`` / ``$`` delimiters
    - ``code`` — strip ``` fences / backticks
    - ``text`` — returned **verbatim** (markdown/HTML is rendered to
      rich HTML at display time, not at write time)

    Args:
        content_kind: One of :data:`CONTENT_KINDS` (case-insensitive).
        content: The raw snippet content.

    Returns:
        The normalized content.

    Raises:
        ValueError: If *content_kind* is not a supported kind.
    """
    kind = normalize_content_kind(content_kind)
    if kind == "math":
        return strip_math_delimiters(content)
    if kind == "code":
        return strip_code_fences(content)
    return content


__all__ = [
    "normalize_content",
    "strip_code_fences",
    "strip_math_delimiters",
]
