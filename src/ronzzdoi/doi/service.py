"""DOIService — core DOI lifecycle management.

Provides ronzzDOI assignment, resolution, modification (with soft redirect),
tombstone deletion, and paginated listing.

Usage::

from lightercore.db import LighterDB
    from ronzzdoi.doi.service import DOIService

    db = LighterDB("/path/to/ronzzdoi.db")
    db.init_schema(SCHEMA)          # see ronzzdoi.db for schema
    service = DOIService(db)

    result = service.assign("https://example.com", title="My Resource")
    doi = result["doi"]
    resolved = service.resolve(doi)
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from lightercore.crud import CRUDService, now
from lightercore.db import LighterDB

from ronzzdoi.doi.constants import DOI_PREFIX, UUID4_HEX_LENGTH, is_valid_doi
from ronzzdoi.doi.exceptions import (
    DOIAmbiguousError,
    DOIInvalidError,
    DOINotFoundError,
)


class DOIService(CRUDService):
    """Manage the full lifecycle of ronzzDOIs.

    Extends :class:`lightercore.crud.CRUDService` with DOI-specific
    operations and overrides the generic ``create()`` to handle
    custom primary key generation.

    Args:
        db: A :class:`lightercore.db.LighterDB` instance.
    """

    def __init__(self, db: LighterDB) -> None:
        super().__init__(db, table="dois", pk_column="doi")

    # ── DOI generation ──────────────────────────────────────────────────────

    @staticmethod
    def generate_doi() -> str:
        """Generate a new ronzzDOI in the format ``10.ronzz/<uuid4-hex>``.

        Returns:
            A 45-character string (10 prefix + 1 slash + 32 hex + 1 separator...).
            Actually: ``10.ronzz/`` (9 chars) + 32 hex = 41 chars total.
        """
        suffix = uuid.uuid4().hex  # 32 lowercase hex chars, no dashes
        return f"{DOI_PREFIX}/{suffix}"

    # ── Hook overrides ──────────────────────────────────────────────────────

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new DOI record.

        Overrides :meth:`CRUDService.create` to use DOI-specific primary key
        generation when no ``doi`` key is provided.

        Args:
            data: Record data. If ``doi`` is omitted, a new DOI is auto-generated.

        Returns:
            The saved record dict including auto-generated timestamps.

        Raises:
            DOIExistsError: If a record with the same DOI already exists
                (extremely unlikely with UUID4, but guarded).
        """
        from lightercore.exceptions import DatabaseError

        ts = now()
        data = dict(data)
        data.setdefault("doi", self.generate_doi())
        # Validate DOI format for user-supplied DOIs
        if "doi" in data and not is_valid_doi(data["doi"]):
            raise DOIInvalidError(
                data["doi"],
                reason="DOI must start with '10.ronzz/' followed by a non-empty suffix.",
            )
        data.setdefault("created_at", ts)
        data["updated_at"] = ts

        columns = [k for k in data.keys() if not k.startswith("_")]
        values = [data[k] for k in columns]
        placeholders = ", ".join(["?"] * len(columns))

        try:
            with self.db.transaction() as conn:
                conn.execute(
                    f"INSERT INTO {self.table} ({', '.join(columns)}) VALUES ({placeholders})",
                    values,
                )
        except DatabaseError as exc:
            if "UNIQUE" in str(exc):
                from ronzzdoi.doi.exceptions import DOIExistsError

                raise DOIExistsError(data["doi"]) from exc
            raise

        result = data.copy()
        result.setdefault("deleted_at", None)
        self._post_create(data, result)
        return result

    # ── Public API ──────────────────────────────────────────────────────────

    def assign(
        self,
        target_url: str | None = None,
        *,
        doi_type: str = "external",
        title: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assign a new ronzzDOI.

        ``target_url`` is optional — entity DOIs (person, abstract_entity,
        country) set ``target_url=NULL``.  The ``doi_type`` field is
        free-text and stored as-is; citation doc_types (book, webpage, …)
        use their type name here.

        Args:
            target_url: The URL the DOI should resolve to.
                        ``None`` for entity DOIs.
            doi_type: Free-text type descriptor (default ``"external"``).
                      Use citation doc_type names (book, webpage, …) or
                      entity type names (person, abstract_entity, country).
            title: Human-readable title.
            metadata: Type-specific fields (serialized to JSON).  Required
                      keys depend on ``doi_type`` (see citation.schemas).

        Returns:
            The newly created DOI record.

        Raises:
            DOIInvalidError: If a user-supplied ``doi`` is malformed.
            DOIExistsError: If a UUID collision occurs (astronomically rare).
        """
        data: dict[str, Any] = {
            "doi_type": doi_type,
            "title": title,
            "metadata_json": json.dumps(metadata or {}),
        }
        if target_url is not None:
            data["target_url"] = target_url
        result = self.create(data)
        # Ensure target_url is always present in the response (nullable)
        result.setdefault("target_url", None)
        # Deserialize metadata_json to metadata for API consistency
        self._deserialize_record(result)
        return result

    def resolve(
        self,
        doi: str,
        *,
        include_redirects: bool = True,
    ) -> dict[str, Any] | None:
        """Resolve a DOI to its current record.

        Uses prefix matching (LIKE), so a short prefix will match the first
        record whose DOI starts with the given string.

        Args:
            doi: Full DOI or prefix to resolve.
            include_redirects: If True (default), fetch the redirect history.

        Returns:
            The DOI record with ``metadata`` deserialized, or ``None`` if
            no match is found.  Tombstoned records are returned with
            ``deleted_at`` set; the caller should inspect it.

        Raises:
            DOIAmbiguousError: If *doi* is a prefix matching multiple records
                and the caller should disambiguate.
        """
        # Check for ambiguous prefix matches
        matches = self.find_by_pk_prefix(doi, limit=10)
        if not matches:
            return None
        if len(matches) > 1:
            # If exact match also exists among matches, it's not ambiguous
            exact = [m for m in matches if m["doi"] == doi]
            if not exact:
                raise DOIAmbiguousError(
                    f"DOI prefix '{doi}' matches {len(matches)} records. "
                    f"Provide a longer prefix or the full DOI.",
                    matches=matches,
                )

        record = matches[0]
        # Deserialize metadata and add status
        self._deserialize_record(record)
        record["status"] = "tombstone" if record.get("deleted_at") else "active"

        # Fetch redirect history if requested
        if include_redirects:
            record["redirect_history"] = self._get_redirect_history(record["doi"])
        else:
            record["redirect_history"] = []

        return record

    def modify(
        self,
        doi: str,
        *,
        target_url: str | None = None,
        title: str | None = None,
        doi_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        redirect_note: str = "",
    ) -> dict[str, Any]:
        """Modify an existing DOI record.

        If *target_url* changes, the old URL is recorded in the ``redirects``
        table for audit trail (soft redirect).

        Args:
            doi: Full DOI or prefix to modify.
            target_url: New target URL (triggers soft redirect if changed).
            title: New title.
            doi_type: New type descriptor.
            metadata: New metadata dict (replaces existing entirely).
            redirect_note: Optional note for the redirect entry.

        Returns:
            The updated DOI record with ``metadata`` deserialized.

        Raises:
            DOINotFoundError: If the DOI does not exist.
            DOIAmbiguousError: If the prefix matches multiple records.
        """
        old = self._resolve_exact(doi)
        if old is None:
            raise DOINotFoundError(doi)

        update_data: dict[str, Any] = {}

        # URL change → soft redirect
        if target_url is not None and target_url != old.get("target_url"):
            update_data["target_url"] = target_url
            old_url = old.get("target_url") or "(none)"
            self._record_redirect(old["doi"], old_url, redirect_note)

        if title is not None:
            update_data["title"] = title
        if doi_type is not None:
            update_data["doi_type"] = doi_type
        if metadata is not None:
            update_data["metadata_json"] = json.dumps(metadata)

        if not update_data:
            # Nothing changed — return the existing record with metadata
            # already deserialized by _resolve_exact
            result = dict(old)
            result.setdefault("status", "tombstone" if old.get("deleted_at") else "active")
            result.setdefault("redirect_history", [])
            return result

        update_data["updated_at"] = now()

        set_clauses = [f"{k} = ?" for k in update_data]
        values = [update_data[k] for k in update_data] + [old["doi"]]

        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE {self.table} SET {', '.join(set_clauses)} "
                f"WHERE {self._pk_column} = ?",
                values,
            )

        # Re-fetch and return
        updated = self.db.execute_one(
            f"SELECT * FROM {self.table} WHERE {self._pk_column} = ?",
            (old["doi"],),
        )
        if updated:
            self._deserialize_record(updated)
            updated["status"] = "tombstone" if updated.get("deleted_at") else "active"
            updated["redirect_history"] = self._get_redirect_history(old["doi"])
        return updated or old

    def delete_doi(self, doi: str) -> bool:
        """Tombstone a DOI by setting ``deleted_at`` in-place.

        The row is NOT removed from the database — ``deleted_at`` is set
        to the current timestamp so that resolution can return a tombstone
        message (404 with explanation) rather than a bare 410.

        Args:
            doi: Full DOI or prefix to tombstone.

        Returns:
            ``True`` if the DOI was tombstoned, ``False`` if not found.

        Raises:
            DOIAmbiguousError: If the prefix matches multiple records.
        """
        record = self._resolve_exact(doi)
        if record is None:
            return False

        ts = now()
        self.db.execute(
            f"UPDATE {self.table} SET deleted_at = ?, updated_at = ? "
            f"WHERE {self._pk_column} = ?",
            (ts, ts, record["doi"]),
        )
        self._post_delete(record["doi"], record)
        return True

    def list_dois(
        self,
        limit: int = 100,
        offset: int = 0,
        *,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """List DOI records with pagination.

        By default only active (non-tombstoned) DOIs are returned.

        Args:
            limit: Maximum number of records (default 100).
            offset: Number of records to skip (default 0).
            include_deleted: If True, also return tombstoned DOIs.

        Returns:
            List of DOI record dicts.  The ``metadata_json`` field is kept
            as a raw string; callers should deserialize if needed.
        """
        if include_deleted:
            return self.db.execute(
                f"SELECT * FROM {self.table} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return self.db.execute(
            f"SELECT * FROM {self.table} WHERE deleted_at IS NULL "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    # ── Internal helpers ────────────────────────────────────────────────────

    def _resolve_exact(self, doi: str) -> dict[str, Any] | None:
        """Resolve a DOI to exactly one record.

        Unlike the public ``resolve()`` which uses prefix matching,
        this method prefers an exact match and only falls back to
        prefix matching if no exact match is found.  Raises
        ``DOIAmbiguousError`` if the prefix is ambiguous.

        Returns:
            The record with ``metadata`` deserialized, or ``None``.
        """
        # Try exact match first
        record = self.db.execute_one(
            f"SELECT * FROM {self.table} WHERE {self._pk_column} = ?",
            (doi,),
        )
        if record:
            self._deserialize_record(record)
            return record

        # Fall back to prefix matching
        matches = self.find_by_pk_prefix(doi, limit=10)
        if not matches:
            return None
        if len(matches) > 1:
            raise DOIAmbiguousError(
                f"DOI prefix '{doi}' matches {len(matches)} records. "
                f"Provide a longer prefix or the full DOI.",
                matches=matches,
            )
        record = matches[0]
        self._deserialize_record(record)
        return record

    def _get_redirect_history(self, doi: str) -> list[dict[str, str]]:
        """Return the redirect history for *doi*, oldest first."""
        return self.db.execute(
            "SELECT old_url, note, created_at "
            "FROM redirects WHERE doi = ? "
            "ORDER BY created_at ASC",
            (doi,),
        )

    def _record_redirect(self, doi: str, old_url: str, note: str = "") -> None:
        """Insert a redirect record for a URL change."""
        self.db.execute(
            "INSERT INTO redirects (redirect_id, doi, old_url, note, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), doi, old_url, note, now()),
        )

    @staticmethod
    def _deserialize_record(record: dict[str, Any]) -> None:
        """Deserialize ``metadata_json`` in-place to a ``metadata`` dict."""
        raw = record.pop("metadata_json", "{}")
        record["metadata"] = json.loads(raw) if isinstance(raw, str) else raw
