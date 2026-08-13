"""Snippet command handlers — ``!snippet assign|resolve|modify|delete``.

Registered via the ``@command`` decorator at import time.
Lazily resolves the service instance from ``snippet_routes`` at dispatch
time, which is guaranteed to be initialized before any command is
dispatched.
"""

from __future__ import annotations

from typing import Any

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


# ── snippet.assign ─────────────────────────────────────────────────────


@command("snippet.assign", description="Assign a new snippet (text/code/math)")
def snippet_assign(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assign a new embeddable snippet.

    Usage::

        !snippet assign --type code --content "print('hi')" [--title ... --language python]
        !snippet assign  (opens the interactive form with a Text/Code/Math toggle)

    Missing ``--type`` or ``--content`` → returns ``form`` response.
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    content_kind = flags.get("type", "")
    content = flags.get("content", "")

    if not content_kind or not content:
        return {
            "type": "form",
            "title": "Assign Snippet",
            "data": {
                "form": "snippet-assign",
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


# ── snippet.resolve ────────────────────────────────────────────────────


@command("snippet.resolve", description="Resolve a snippet to its content")
def snippet_resolve(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a snippet DOI and return its content.

    Usage::

        !snippet resolve <doi>
    """
    perm = check_permission(user, "read_only")
    if perm:
        return perm

    doi = positionals[0] if positionals else flags.get("doi", "")
    if not doi:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {"message": "Usage: !snippet resolve <doi>"},
        }

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

    return {
        "type": "snippet",
        "title": f"Snippet: {record['doi']}",
        "data": _record_to_snippet_response(record, include_status=True),
    }


# ── snippet.modify ─────────────────────────────────────────────────────


@command("snippet.modify", description="Modify an existing snippet")
def snippet_modify(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update snippet content or attribution. All flags optional.

    Usage::

        !snippet modify <doi> [--content ... --type ... --source-doi ... --title ...]
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    doi = positionals[0] if positionals else flags.get("doi", "")
    if not doi:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {
                "message": "Usage: !snippet modify <doi> [--content ... --type ...]"
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
        "type": "detail",
        "title": f"Modified: {result['doi']}",
        "data": _record_to_snippet_response(result, include_status=True),
    }


# ── snippet.delete ─────────────────────────────────────────────────────


@command("snippet.delete", description="Tombstone a snippet (soft-delete)")
def snippet_delete(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tombstone a snippet.

    Usage::

        !snippet delete <doi>
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    doi = positionals[0] if positionals else flags.get("doi", "")
    if not doi:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {"message": "Usage: !snippet delete <doi>"},
        }

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
