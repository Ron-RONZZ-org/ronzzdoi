"""Snippet module — embeddable content fragments (quotations, code, math).

Each snippet is a DOI (persistent identity) with a parallel ``snippets``
row carrying the content.  Snippets are separate from the citation
module: citations format academic reference text, snippets are the
embeddable content itself.

Public API::

    from ronzzdoi.snippet import SnippetService
    from ronzzdoi.snippet.constants import CONTENT_KINDS
    from ronzzdoi.snippet.schema import SnippetAssignRequest
"""

from __future__ import annotations

from ronzzdoi.snippet.constants import CONTENT_KINDS, SUGGESTED_LANGUAGES
from ronzzdoi.snippet.exceptions import (
    SnippetError,
    SnippetInvalidError,
    SnippetNotFoundError,
    SnippetSourceNotFoundError,
)
from ronzzdoi.snippet.schema import (
    SnippetAssignRequest,
    SnippetModifyRequest,
    SnippetResponse,
)
from ronzzdoi.snippet.service import SnippetService

__all__ = [
    "CONTENT_KINDS",
    "SUGGESTED_LANGUAGES",
    "SnippetAssignRequest",
    "SnippetError",
    "SnippetInvalidError",
    "SnippetModifyRequest",
    "SnippetNotFoundError",
    "SnippetResponse",
    "SnippetService",
    "SnippetSourceNotFoundError",
]
