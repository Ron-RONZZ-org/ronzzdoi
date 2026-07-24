"""DOI command handlers — ``!doi assign|resolve|modify|merge|delete|search``.

Registered via the ``@command`` decorator at import time.
Lazily resolves the service instance from ``doi_routes`` at dispatch time,
which is guaranteed to be initialized before any command is dispatched.
"""

from __future__ import annotations

import json
from typing import Any

from ronzzdoi.doi.exceptions import DOIAmbiguousError, DOIExistsError, DOIInvalidError, DOINotFoundError
from ronzzdoi.server.command.handlers import check_permission
from ronzzdoi.server.command.registry import command
from ronzzdoi.server.doi_routes import _get_doi_svc, _record_to_response, _search_svc


# ── doi.assign ──────────────────────────────────────────────────────────


@command("doi.assign", description="Assign a new DOI")
def doi_assign(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assign a new ronzzDOI.

    Usage::

        !doi assign <url> [--title '{"en":"..."}' --type external --metadata '{}']

    Missing required params → returns ``form`` response.
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    # URL from positional arg or --url flag
    url = positionals[0] if positionals else flags.get("url", "")
    if not url:
        return {
            "type": "form",
            "title": "Assign DOI",
            "data": {
                "form": "doi-assign",
                "initialData": {
                    "url": flags.get("url", ""),
                    "title": flags.get("title", ""),
                    "doi_type": flags.get("type", ""),
                    "metadata": flags.get("metadata", ""),
                },
            },
        }

    # Parse optional fields
    title = flags.get("title", "")
    doi_type = flags.get("type", "external")
    metadata_raw = flags.get("metadata", "{}")
    try:
        metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else {}
    except json.JSONDecodeError:
        return {
            "type": "error",
            "title": "Invalid Metadata",
            "data": {"message": "Metadata must be valid JSON."},
        }

    try:
        svc = _get_doi_svc()
        result = svc.assign(
            target_url=url,
            doi_type=doi_type,
            title=title,
            metadata=metadata,
        )
    except DOIInvalidError as exc:
        return {"type": "error", "title": "Invalid DOI", "data": {"message": str(exc)}}
    except DOIExistsError as exc:
        return {"type": "error", "title": "DOI Exists", "data": {"message": str(exc)}}

    return {
        "type": "detail",
        "title": f"DOI: {result['doi']}",
        "data": _record_to_response(result),
    }


# ── doi.resolve ─────────────────────────────────────────────────────────


@command("doi.resolve", description="Resolve a DOI to its metadata")
def doi_resolve(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a DOI and return its metadata.

    Usage::

        !doi resolve <doi>
    """
    perm = check_permission(user, "read_only")
    if perm:
        return perm

    doi = positionals[0] if positionals else flags.get("doi", "")
    if not doi:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {"message": "Usage: !doi resolve <doi>"},
        }

    try:
        svc = _get_doi_svc()
        record = svc.resolve(doi, include_redirects=True)
    except DOIAmbiguousError as exc:
        return {"type": "error", "title": "Ambiguous DOI", "data": {"message": str(exc)}}

    if record is None:
        return {
            "type": "error",
            "title": "Not Found",
            "data": {"message": f"DOI '{doi}' not found."},
        }

    return {
        "type": "detail",
        "title": f"DOI: {record['doi']}",
        "data": _record_to_response(record, include_status=True),
    }


# ── doi.modify ──────────────────────────────────────────────────────────


@command("doi.modify", description="Modify an existing DOI")
def doi_modify(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update DOI metadata. All flags optional.

    Usage::

        !doi modify <doi> [--url ... --title '{"en":"..."}' --type ... --metadata '{}']
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    doi = positionals[0] if positionals else flags.get("doi", "")
    if not doi:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {"message": "Usage: !doi modify <doi> [--url ... --title ...]"},
        }

    # All fields optional
    target_url = flags.get("url")
    title = flags.get("title")
    doi_type = flags.get("type")

    metadata = None
    metadata_raw = flags.get("metadata")
    if metadata_raw:
        try:
            metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else {}
        except json.JSONDecodeError:
            return {
                "type": "error",
                "title": "Invalid Metadata",
                "data": {"message": "Metadata must be valid JSON."},
            }

    try:
        svc = _get_doi_svc()
        result = svc.modify(
            doi,
            target_url=target_url,
            title=title,
            doi_type=doi_type,
            metadata=metadata,
        )
    except DOINotFoundError as exc:
        return {"type": "error", "title": "Not Found", "data": {"message": str(exc)}}
    except DOIAmbiguousError as exc:
        return {"type": "error", "title": "Ambiguous DOI", "data": {"message": str(exc)}}

    return {
        "type": "detail",
        "title": f"Modified: {result['doi']}",
        "data": _record_to_response(result, include_status=True),
    }


# ── doi.merge ───────────────────────────────────────────────────────────


@command("doi.merge", description="Merge a source DOI into a target DOI")
def doi_merge(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge source DOI into target. Source is tombstoned.

    Usage::

        !doi merge <source-doi> <target-doi>
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    if len(positionals) < 2:
        return {
            "type": "error",
            "title": "Missing Arguments",
            "data": {"message": "Usage: !doi merge <source-doi> <target-doi>"},
        }

    source_doi = positionals[0]
    target_doi = positionals[1]

    try:
        svc = _get_doi_svc()
        result = svc.merge_dois(source_doi, target_doi)
    except DOINotFoundError as exc:
        return {"type": "error", "title": "Not Found", "data": {"message": str(exc)}}
    except DOIAmbiguousError as exc:
        return {"type": "error", "title": "Ambiguous DOI", "data": {"message": str(exc)}}

    return {
        "type": "detail",
        "title": f"Merged → {result['doi']}",
        "data": _record_to_response(result, include_status=True),
    }


# ── doi.delete ──────────────────────────────────────────────────────────


@command("doi.delete", description="Tombstone a DOI (soft-delete)")
def doi_delete(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tombstone a DOI.

    Usage::

        !doi delete <doi>
    """
    perm = check_permission(user, "edit")
    if perm:
        return perm

    doi = positionals[0] if positionals else flags.get("doi", "")
    if not doi:
        return {
            "type": "error",
            "title": "Missing DOI",
            "data": {"message": "Usage: !doi delete <doi>"},
        }

    try:
        svc = _get_doi_svc()
        deleted = svc.delete_doi(doi)
    except DOIAmbiguousError as exc:
        return {"type": "error", "title": "Ambiguous DOI", "data": {"message": str(exc)}}

    if not deleted:
        return {
            "type": "error",
            "title": "Not Found",
            "data": {"message": f"DOI '{doi}' not found."},
        }

    return {
        "type": "success",
        "title": f"Tombstoned: {doi}",
        "data": {"message": f"DOI '{doi}' has been tombstoned.", "doi": doi},
    }


# ── doi.search ──────────────────────────────────────────────────────────


@command("doi.search", description="Search DOIs by query")
def doi_search(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Search DOIs. Empty query lists all DOIs.

    Usage::

        !doi search <query> [--limit 20 --offset 0 --mode semantical]
        !doi search  (lists all DOIs)
    """
    perm = check_permission(user, "read_only")
    if perm:
        return perm

    query = " ".join(positionals) if positionals else flags.get("query", "")
    limit = int(flags.get("limit", "20"))
    offset = int(flags.get("offset", "0"))

    svc = _get_doi_svc()

    if query:
        if _search_svc is not None:
            results = _search_svc.search_fts(query, limit=limit)
        else:
            # Fallback: basic text filter via DOI service
            all_dois = svc.list_dois(limit=1000)
            q_lower = query.lower()
            results = [
                r for r in all_dois
                if q_lower in r.get("doi", "").lower()
                or q_lower in r.get("title", "").lower()
            ][:limit]
    else:
        results = svc.list_dois(limit=limit, offset=offset)

    items = [_record_to_response(r) for r in results]

    return {
        "type": "doi-list",
        "title": f"DOI Search{' - ' + query if query else ''}",
        "data": {
            "results": items,
            "total": len(items),
            "query": query,
            "limit": limit,
            "offset": offset,
        },
    }
