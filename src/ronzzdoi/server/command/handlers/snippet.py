"""Snippet command handlers — ``!snippet add|view|search|modify|delete``.

Registered via the ``@command`` decorator at import time.
Lazily resolves the service instance from ``snippet_routes`` at dispatch
time, which is guaranteed to be initialized before any command is
dispatched.
"""

from __future__ import annotations

from typing import Any

import ronzzdoi.server.doi_routes as _doi_routes
from ronzzdoi.doi.exceptions import DOIAmbiguousError, DOINotFoundError
from ronzzdoi.server.command.handlers import check_permission
from ronzzdoi.server.command.registry import command
from ronzzdoi.server.snippet_routes import (
    _get_snippet_svc,
    _record_to_snippet_response,
)
from ronzzdoi.snippet.exceptions import (
    SnippetInvalidError,
    SnippetNotFoundError,
    SnippetSourceNotFoundError,
)

DOI_PREFIX = "10.ronzz"


def _normalize_doi_ref(ref: str) -> str:
    """Normalize a full link, DOI, or bare suffix to a canonical DOI.

    Accepts:
        - ``https://doi.ronzz.org/10.ronzz/<suffix>`` (full resolvable link)
        - ``10.ronzz/<suffix>`` (canonical DOI)
        - ``<suffix>`` (bare suffix, prefix added)

    Args:
        ref: The raw user input (link or DOI).

    Returns:
        The canonical DOI ``10.ronzz/<suffix>``.
    """
    ref = ref.strip()
    if ref.startswith(("http://", "https://")):
        # Strip scheme + origin, keep the path (which starts with the DOI)
        path = ref.split("//", 1)[1]
        path = path.split("/", 1)[1] if "/" in path else ""
        if not path.startswith(DOI_PREFIX + "/"):
            raise ValueError(
                f"Link '{ref}' does not contain a ronzzDOI (expected {DOI_PREFIX}/…)."
            )
        return path
    if ref.startswith(DOI_PREFIX + "/"):
        return ref
    if ref.startswith(DOI_PREFIX):
        return f"{DOI_PREFIX}/{ref.split('/', 1)[1] if '/' in ref else ref}"
    return f"{DOI_PREFIX}/{ref}"


def _svc_or_error() -> tuple[Any, dict[str, Any] | None]:
    """Return the snippet service, or an error response if not mounted.

    Returns:
        ``(svc, None)`` on success, ``(None, error_dict)`` when the
        snippet service is unavailable.
    """
    try:
        return _get_snippet_svc(), None
    except RuntimeError:
        return None, {
            "type": "error",
            "title": "Unavailable",
            "data": {"message": "Snippet service is not available on this server."},
        }


def _snippet_record(doi: str, include_status: bool = True) -> dict[str, Any] | None:
    """Resolve *doi* to a snippet record, or return None if not a snippet.

    Args:
        doi: Canonical DOI to resolve.
        include_status: Include ``status``/``redirect_history`` in the record.

    Returns:
        The snippet record, or ``None`` if the DOI is not a snippet.
    """
    svc, error = _svc_or_error()
    if error:
        return None
    record = svc.resolve(doi, include_redirects=True)
    if record is None:
        return None
    if record.get("content_kind") is None:
        return None
    return _record_to_snippet_response(record, include_status=include_status)


# ── snippet.add ─────────────────────────────────────────────────────────


@command("snippet.add", description="Add a new snippet (text/code/math)")
def snippet_add(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add a new embeddable snippet.

    Usage::

        !snippet add --type code --content "print('hi')" [--title ... --language python]
        !snippet add  (opens the interactive form with a Text/Code/Math toggle)

    Missing ``--type`` or ``--content`` → returns ``form`` response.

    Content is normalized on save: ``$$``/``$`` are stripped for math and
    ``` / `` ` `` for code.  Text content is stored verbatim as
    markdown/HTML and rendered to rich HTML at display time (see
    :mod:`ronzzdoi.snippet.content`).
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    content_kind = flags.get("type", "")
    content = flags.get("content", "")

    if not content_kind or not content:
        return {
            "type": "form",
            "title": "Add Snippet",
            "data": {
                "form": "snippet-add",
                "initialData": {
                    "type": flags.get("type", "text"),
                    "content": content,
                    "title": flags.get("title", ""),
                    "language": flags.get("language", ""),
                    "source_doi": flags.get("source_doi", ""),
                    "page_start": flags.get("page_start", ""),
                    "page_end": flags.get("page_end", ""),
                },
            },
        }

    svc, error = _svc_or_error()
    if error:
        return error

    try:
        result = svc.assign(
            content_kind=content_kind,
            content=content,
            title=flags.get("title", ""),
            language=flags.get("language", ""),
            source_doi=flags.get("source_doi") or None,
            page_start=flags.get("page_start", ""),
            page_end=flags.get("page_end", ""),
        )
    except SnippetInvalidError as exc:
        return {
            "type": "error",
            "title": "Invalid Snippet",
            "data": {"message": str(exc)},
        }
    except SnippetSourceNotFoundError as exc:
        return {
            "type": "error",
            "title": "Source Not Found",
            "data": {"message": str(exc)},
        }

    return {
        "type": "snippet",
        "title": f"Snippet: {result['doi']}",
        "data": _record_to_snippet_response(result),
    }


# ── snippet.view ────────────────────────────────────────────────────────


@command("snippet.view", description="View a snippet by link or DOI")
def snippet_view(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """View a snippet and return its content.

    Accepts a full resolvable link or just the DOI::

        !snippet view <doi>
        !snippet view https://doi.ronzz.org/10.ronzz/<suffix>
    """
    perm = check_permission(user, "read_only")
    if perm:
        return perm

    ref = positionals[0] if positionals else flags.get("doi", "")
    if not ref:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {"message": "Usage: !snippet view <doi or link>"},
        }

    try:
        doi = _normalize_doi_ref(ref)
    except ValueError as exc:
        return {"type": "error", "title": "Invalid DOI", "data": {"message": str(exc)}}

    svc, error = _svc_or_error()
    if error:
        return error

    try:
        record = svc.resolve(doi, include_redirects=True)
    except DOIAmbiguousError as exc:
        return {
            "type": "error",
            "title": "Ambiguous DOI",
            "data": {"message": str(exc)},
        }

    if record is None:
        return {
            "type": "error",
            "title": "Not Found",
            "data": {"message": f"DOI '{doi}' not found."},
        }
    if record.get("content_kind") is None:
        return {
            "type": "error",
            "title": "Not a Snippet",
            "data": {
                "message": f"DOI '{record['doi']}' is not a snippet.",
            },
        }

    return {
        "type": "snippet",
        "title": f"Snippet: {record['doi']}",
        "data": _record_to_snippet_response(record, include_status=True),
    }


# ── snippet.search ──────────────────────────────────────────────────────


@command("snippet.search", description="Search snippets by query")
def snippet_search(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Search snippets. Empty query lists all snippets.

    Reuses the DOI search machinery (FTS across ``dois_fts`` +
    ``snippets_fts``) restricted to ``doi_type='snippet'`` records.

    Usage::

        !snippet search <query> [--limit 20 --offset 0]
        !snippet search  (lists all snippets)
    """
    perm = check_permission(user, "read_only")
    if perm:
        return perm

    query = " ".join(positionals) if positionals else flags.get("query", "")
    limit = int(flags.get("limit", "20"))
    offset = int(flags.get("offset", "0"))

    doi_svc = _doi_routes._get_doi_svc()
    search_svc = _doi_routes._search_svc
    svc, _ = _svc_or_error()

    if query:
        results: list[dict[str, Any]] = []
        if search_svc is not None:
            try:
                results = search_svc.search_fts(query, limit=limit)
            except Exception:
                # FTS5 rejects some syntaxes (e.g. hyphens in "foo-bar" are
                # parsed as column refs) — degrade to the LIKE fallback.
                results = []
        if not results:
            # Fallback: basic text filter across snippet fields
            all_snippets = doi_svc.list_dois(limit=1000, doi_type="snippet")
            q_lower = query.lower()
            results = [
                r
                for r in all_snippets
                if q_lower in r.get("doi", "").lower()
                or q_lower in r.get("title", "").lower()
            ][:limit]
        results = [r for r in results if r.get("doi_type") == "snippet"]
    else:
        results = doi_svc.list_dois(limit=limit, offset=offset, doi_type="snippet")

    items = []
    for record in results:
        enriched = svc.enrich(record) if svc is not None else record
        items.append(_record_to_snippet_response(enriched))

    return {
        "type": "snippet-list",
        "title": f"Snippet Search{' - ' + query if query else ''}",
        "data": {
            "results": items,
            "total": len(items),
            "query": query,
            "limit": limit,
            "offset": offset,
        },
    }


# ── snippet.modify ──────────────────────────────────────────────────────


@command("snippet.modify", description="Modify an existing snippet")
def snippet_modify(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update snippet content or attribution. All flags optional.

    With a DOI/link and NO change flags, opens the edit form prefilled
    with the current record (shortcut for the view tab's Edit button).

    Usage::

        !snippet modify <doi or link>
        !snippet modify <doi> [--content ... --type ... --source-doi ... --title ...]
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    ref = positionals[0] if positionals else flags.get("doi", "")
    if not ref:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {
                "message": "Usage: !snippet modify <doi> [--content ... --type ...]"
            },
        }

    try:
        doi = _normalize_doi_ref(ref)
    except ValueError as exc:
        return {"type": "error", "title": "Invalid DOI", "data": {"message": str(exc)}}

    # No change flags → edit form prefilled from the current record.
    change_keys = (
        "content",
        "type",
        "title",
        "language",
        "source_doi",
        "page_start",
        "page_end",
    )
    if not any(flags.get(k) for k in change_keys):
        record = _snippet_record(doi, include_status=False)
        if record is None:
            return {
                "type": "error",
                "title": "Not Found",
                "data": {"message": f"DOI '{doi}' is not a snippet."},
            }
        return {
            "type": "form",
            "title": f"Edit Snippet: {record['doi']}",
            "data": {
                "form": "snippet-edit",
                "initialData": {
                    "doi": record["doi"],
                    "type": record.get("content_kind", "text"),
                    "content": record.get("content", ""),
                    "title": record.get("title", ""),
                    "language": record.get("language", ""),
                    "source_doi": record.get("source_doi") or "",
                    "page_start": record.get("page_start", ""),
                    "page_end": record.get("page_end", ""),
                },
            },
        }

    svc, error = _svc_or_error()
    if error:
        return error

    try:
        result = svc.modify(
            doi,
            content=flags.get("content"),
            content_kind=flags.get("type"),
            title=flags.get("title"),
            language=flags.get("language"),
            source_doi=flags.get("source_doi"),
            page_start=flags.get("page_start"),
            page_end=flags.get("page_end"),
        )
    except DOINotFoundError as exc:
        return {"type": "error", "title": "Not Found", "data": {"message": str(exc)}}
    except SnippetNotFoundError as exc:
        return {
            "type": "error",
            "title": "Not a Snippet",
            "data": {"message": str(exc)},
        }
    except DOIAmbiguousError as exc:
        return {
            "type": "error",
            "title": "Ambiguous DOI",
            "data": {"message": str(exc)},
        }
    except SnippetInvalidError as exc:
        return {
            "type": "error",
            "title": "Invalid Snippet",
            "data": {"message": str(exc)},
        }
    except SnippetSourceNotFoundError as exc:
        return {
            "type": "error",
            "title": "Source Not Found",
            "data": {"message": str(exc)},
        }

    return {
        "type": "snippet",
        "title": f"Snippet: {result['doi']}",
        "data": _record_to_snippet_response(result, include_status=True),
    }


# ── snippet.delete ──────────────────────────────────────────────────────


@command("snippet.delete", description="Tombstone a snippet (soft-delete)")
def snippet_delete(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tombstone a snippet.

    Usage::

        !snippet delete <doi or link>
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    ref = positionals[0] if positionals else flags.get("doi", "")
    if not ref:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {"message": "Usage: !snippet delete <doi>"},
        }

    try:
        doi = _normalize_doi_ref(ref)
    except ValueError as exc:
        return {"type": "error", "title": "Invalid DOI", "data": {"message": str(exc)}}

    svc, error = _svc_or_error()
    if error:
        return error

    try:
        deleted = svc.delete(doi)
    except DOIAmbiguousError as exc:
        return {
            "type": "error",
            "title": "Ambiguous DOI",
            "data": {"message": str(exc)},
        }
    except SnippetNotFoundError as exc:
        return {
            "type": "error",
            "title": "Not a Snippet",
            "data": {"message": str(exc)},
        }

    if not deleted:
        return {
            "type": "error",
            "title": "Not Found",
            "data": {"message": f"DOI '{doi}' not found."},
        }

    return {
        "type": "success",
        "title": f"Tombstoned: {doi}",
        "data": {"message": f"Snippet '{doi}' has been tombstoned.", "doi": doi},
    }
