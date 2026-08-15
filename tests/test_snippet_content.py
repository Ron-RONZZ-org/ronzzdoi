"""Tests for snippet content normalization (transport-markup stripping).

Covers the pure helpers in ``ronzzdoi.snippet.content``: math delimiter
stripping, code fence/backtick stripping, and the rule that text content
is stored verbatim (markdown/HTML is rendered at display time, not
stripped at write time).
"""

from __future__ import annotations

import pytest

from ronzzdoi.snippet.content import (
    normalize_content,
    strip_code_fences,
    strip_math_delimiters,
)

# ── strip_math_delimiters ─────────────────────────────────────────────────


class TestStripMathDelimiters:
    def test_display_mode_dollars(self):
        assert strip_math_delimiters("$$E = mc^2$$") == "E = mc^2"

    def test_inline_dollars(self):
        assert strip_math_delimiters(r"$x^2 + 1$") == r"x^2 + 1"

    def test_surrounding_whitespace(self):
        assert strip_math_delimiters("  $$ \\frac{a}{b} $$  ") == r"\frac{a}{b}"

    def test_bare_latex_unchanged(self):
        assert strip_math_delimiters(r"\frac{a}{b}") == r"\frac{a}{b}"

    def test_math_with_newlines(self):
        assert strip_math_delimiters("$$\na\nb\n$$") == "a\nb"

    def test_only_delimiters_yields_empty(self):
        assert strip_math_delimiters("$$") == ""
        assert strip_math_delimiters("$") == ""


# ── strip_code_fences ─────────────────────────────────────────────────────


class TestStripCodeFences:
    def test_fence_with_language(self):
        content = "```python\nprint('hi')\n```"
        assert strip_code_fences(content) == "print('hi')"

    def test_fence_without_language(self):
        content = "```\nprint('hi')\n```"
        assert strip_code_fences(content) == "print('hi')"

    def test_fence_no_trailing_newline(self):
        content = "```python\nprint('hi')```"
        assert strip_code_fences(content) == "print('hi')"

    def test_inline_backticks(self):
        assert strip_code_fences("`print(1)`") == "print(1)"

    def test_bare_code_unchanged(self):
        assert strip_code_fences("print('hi')") == "print('hi')"

    def test_indented_code_inside_fence(self):
        content = "```python\n    indented = True\n```"
        assert strip_code_fences(content) == "indented = True"

    def test_code_containing_backticks(self):
        content = '```\nmsg = "``` not a fence"\n```'
        assert strip_code_fences(content) == 'msg = "``` not a fence"'

    def test_unclosed_fence_unchanged(self):
        content = "```python\nprint('hi')"
        assert strip_code_fences(content) == content

    def test_only_fences_yields_empty(self):
        assert strip_code_fences("```\n```") == ""


# ── normalize_content dispatcher ──────────────────────────────────────────


class TestNormalizeContent:
    def test_math_kind(self):
        assert normalize_content("math", "$$x^2$$") == "x^2"

    def test_code_kind(self):
        assert normalize_content("code", "```python\nprint(1)\n```") == "print(1)"

    def test_text_kind_stored_verbatim(self):
        """Markdown/HTML text is NOT stripped — it is rendered at display time."""
        markdown = "**bold** quote — see [the book](https://x)"
        assert normalize_content("text", markdown) == markdown

    def test_text_html_stored_verbatim(self):
        assert normalize_content("text", "<p>A <b>wise</b> quote</p>") == (
            "<p>A <b>wise</b> quote</p>"
        )

    def test_kind_case_insensitive(self):
        assert normalize_content("MATH", "$$y$$") == "y"

    def test_invalid_kind_raises(self):
        with pytest.raises(ValueError, match="content kind"):
            normalize_content("image", "data")
