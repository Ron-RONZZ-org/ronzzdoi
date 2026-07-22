"""Citation command handlers — ``!citation show|styles``.

Registered via the ``@command`` decorator at import time.
Lazily resolves the formatter from ``citation_routes`` at dispatch time.
"""

from __future__ import annotations

from typing import Any

from ronzzdoi.doi.exceptions import DOINotFoundError
from ronzzdoi.server.command.handlers import check_permission
from ronzzdoi.server.command.registry import command
from ronzzdoi.server.citation_routes import _get_formatter


# ── citation.show ───────────────────────────────────────────────────────


@command("citation.show", description="Show formatted citation for a DOI")
def citation_show(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render a citation in the requested style.

    Usage::

        !citation show <doi> [--style apa]
    """
    perm = check_permission(user, "read_only")
    if perm:
        return perm

    doi = positionals[0] if positionals else flags.get("doi", "")
    if not doi:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {"message": "Usage: !citation show <doi> [--style apa]"},
        }

    style = flags.get("style", "apa")
    formatter = _get_formatter()

    try:
        text = formatter.format(doi, style=style)
    except DOINotFoundError as exc:
        return {"type": "error", "title": "Not Found", "data": {"message": str(exc)}}
    except ValueError as exc:
        return {
            "type": "error",
            "title": "Invalid Style",
            "data": {"message": str(exc)},
        }

    return {
        "type": "detail",
        "title": f"Citation ({style.upper()}): {doi}",
        "data": {
            "doi": doi,
            "style": style,
            "citation": text,
        },
    }


# ── citation.styles ─────────────────────────────────────────────────────


@command("citation.styles", description="List available citation styles for a DOI")
def citation_styles(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List which citation styles are available for a DOI.

    Usage::

        !citation styles <doi>
    """
    perm = check_permission(user, "read_only")
    if perm:
        return perm

    doi = positionals[0] if positionals else flags.get("doi", "")
    if not doi:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {"message": "Usage: !citation styles <doi>"},
        }

    formatter = _get_formatter()

    try:
        # Resolve the DOI to validate it exists
        from ronzzdoi.doi.exceptions import DOINotFoundError as DOIErr
        from ronzzdoi.server.doi_routes import _get_doi_svc

        svc = _get_doi_svc()
        record = svc.resolve(doi)
        if record is None:
            return {
                "type": "error",
                "title": "Not Found",
                "data": {"message": f"DOI '{doi}' not found."},
            }
    except DOIErr as exc:
        return {"type": "error", "title": "Not Found", "data": {"message": str(exc)}}

    styles = formatter.available_styles()
    doi_type = record.get("doi_type", "external")

    return {
        "type": "detail",
        "title": f"Styles: {doi}",
        "data": {
            "doi": doi,
            "doi_type": doi_type,
            "styles": styles,
            "message": f"Available styles for '{doi}' (type: {doi_type}): {', '.join(styles)}",
        },
    }
