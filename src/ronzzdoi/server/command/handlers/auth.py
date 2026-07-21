"""``!auth`` command handlers — API key management.

Provides the ``!auth api_key`` subcommand tree:

- ``!auth api_key list`` — list API keys
- ``!auth api_key create`` — create a new API key
- ``!auth api_key update`` — update an existing API key
- ``!auth api_key delete`` — revoke an API key
"""

from __future__ import annotations

from typing import Any

from lighterauth.api_key import generate_api_key, lookup_api_keys

from ronzzdoi.auth.config import ALL_PERMISSIONS
from ronzzdoi.server.command.registry import command

# ── Module-level DB reference (set by mount_command_routes) ────────────

_auth_db: Any = None


def set_auth_db(db: Any) -> None:
    """Set the auth database reference for command handlers.

    Called during server startup from ``mount_command_routes``.
    """
    global _auth_db
    _auth_db = db


def _ensure_db() -> None:
    """Raise if the auth database has not been initialised."""
    if _auth_db is None:
        raise RuntimeError("Auth database not initialised. Call set_auth_db() during startup.")


# ── Helpers ─────────────────────────────────────────────────────────────


def _get_admin_user() -> dict[str, Any] | None:
    """Return the first admin user found, or ``None``."""
    _ensure_db()
    rows = _auth_db.execute(
        "SELECT * FROM users WHERE role = 'administrator' LIMIT 1",
    )
    return rows[0] if rows else None


def _parse_dt(value: str | None) -> str | None:
    """Return the value as-is if present (ISO string), else None."""
    if value is None:
        return None
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


# ── !auth api_key list ───────────────────────────────────────────────────


@command("auth.api_key.list", description="List all API keys")
def _auth_api_key_list(flags: dict[str, str]) -> dict[str, Any]:
    """List all API keys (optionally including expired/revoked ones).

    Flags:
        --include-expired: Include expired and revoked keys.
    """
    _ensure_db()
    include_expired = "include-expired" in flags or "include_expired" in flags

    rows = lookup_api_keys(
        _auth_db,
        include_expired=include_expired,
    )

    keys = [
        {
            "id": r["id"],
            "name": r["name"],
            "prefix": r["prefix"],
            "permission": r["permission"],
            "expires_at": _parse_dt(r.get("expires_at")),
            "last_used_at": _parse_dt(r.get("last_used_at")),
            "created_at": _parse_dt(r["created_at"]),
        }
        for r in rows
    ]

    return {
        "type": "list",
        "title": "API Keys",
        "data": keys,
        "id_key": "auth-api-key-list",
    }


# ── !auth api_key create ─────────────────────────────────────────────────


@command("auth.api_key.create", description="Create a new API key")
def _auth_api_key_create(flags: dict[str, str]) -> dict[str, Any]:
    """Create a new API key.

    Flags:
        --name: Human-readable name (required).
        --permission: ``read_only`` or ``full_access`` (default: ``read_only``).
        --expires-at: ISO 8601 expiration date (optional).
    """
    _ensure_db()

    name = flags.get("name") or flags.get("n")
    if not name:
        return {
            "type": "form",
            "title": "Create API Key",
            "data": {
                "fields": [
                    {
                        "name": "name",
                        "label": "Key Name",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "name": "permission",
                        "label": "Permission",
                        "type": "select",
                        "options": ["read_only", "full_access"],
                        "default": "read_only",
                    },
                    {
                        "name": "expires_at",
                        "label": "Expires At (ISO 8601, optional)",
                        "type": "text",
                    },
                ],
            },
            "id_key": "auth-api-key-create",
        }

    permission = flags.get("permission", "read_only")
    if permission not in ALL_PERMISSIONS:
        return {
            "type": "error",
            "title": "Invalid Permission",
            "data": {
                "message": f"Invalid permission '{permission}'. "
                f"Must be one of: {ALL_PERMISSIONS}",
            },
        }

    expires_at = flags.get("expires-at") or flags.get("expires_at")

    admin = _get_admin_user()
    if admin is None:
        return {
            "type": "error",
            "title": "No Admin User",
            "data": {"message": "No administrator user found. Seed the database first."},
        }

    # Generate the key pair
    raw_key, prefix, hashed_key = generate_api_key()

    import secrets
    from datetime import datetime, timezone

    key_id = "ak_" + secrets.token_hex(12)
    now = datetime.now(timezone.utc).isoformat()

    _auth_db.execute(
        "INSERT INTO api_keys (id, name, key, prefix, permission, expires_at, "
        "created_at, updated_at, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            key_id,
            name,
            hashed_key,
            prefix,
            permission,
            expires_at,
            now,
            now,
            admin["id"],
        ),
    )

    return {
        "type": "success",
        "title": "API Key Created",
        "data": {
            "message": f"API key '{name}' created successfully.",
            "key": raw_key,
            "warning": "Save this key now — it will not be shown again.",
        },
        "id_key": "auth-api-key-create",
    }


# ── !auth api_key update ─────────────────────────────────────────────────


@command("auth.api_key.update", description="Update an existing API key")
def _auth_api_key_update(flags: dict[str, str]) -> dict[str, Any]:
    """Update an existing API key's name, permission, and/or expiry.

    Flags:
        --id: Key ID to update.  If omitted, uses --name to find the key.
        --name: New name for the key (or current name to identify by).
        --permission: ``read_only`` or ``full_access``.
        --expires-at: ISO 8601 expiration date, or ``clear`` to remove.
    """
    _ensure_db()

    key_id = flags.get("id")
    name_filter = flags.get("name") or flags.get("n")

    if not key_id and not name_filter:
        # Show all keys for the user to pick one
        return _auth_api_key_list(flags)

    # Resolve key ID from name if not provided
    if not key_id and name_filter:
        keys = lookup_api_keys(_auth_db, include_expired=True)
        matching = [k for k in keys if k["name"] == name_filter]
        if len(matching) == 0:
            return {
                "type": "error",
                "title": "Key Not Found",
                "data": {
                    "message": f"No API key found with name '{name_filter}'.",
                },
            }
        if len(matching) > 1:
            return {
                "type": "error",
                "title": "Multiple Keys",
                "data": {
                    "message": f"Multiple keys found with name '{name_filter}'. "
                    f"Use --id to specify which one.\n"
                    f"Matching IDs: {', '.join(k['id'] for k in matching)}",
                },
            }
        key_id = matching[0]["id"]

    # Fetch current record
    row = _auth_db.execute_one("SELECT * FROM api_keys WHERE id = ?", (key_id,))
    if row is None:
        return {
            "type": "error",
            "title": "Key Not Found",
            "data": {"message": f"API key not found: {key_id}"},
        }

    # Determine what to update
    updates: dict[str, str | None] = {}
    new_name = flags.get("newname") or flags.get("new-name") or flags.get("name")
    if new_name and new_name != row["name"]:
        updates["name"] = new_name

    permission = flags.get("permission")
    if permission:
        if permission not in ALL_PERMISSIONS:
            return {
                "type": "error",
                "title": "Invalid Permission",
                "data": {
                    "message": f"Invalid permission '{permission}'. "
                    f"Must be one of: {ALL_PERMISSIONS}",
                },
            }
        updates["permission"] = permission

    expires_at = flags.get("expires-at") or flags.get("expires_at")
    if "expires-at" in flags or "expires_at" in flags:
        updates["expires_at"] = expires_at if expires_at != "clear" else None

    if not updates:
        # No changes — show current key info
        return {
            "type": "detail",
            "title": f"API Key: {row['name']}",
            "data": {
                "id": row["id"],
                "name": row["name"],
                "prefix": row["prefix"],
                "permission": row["permission"],
                "expires_at": _parse_dt(row.get("expires_at")),
                "created_at": _parse_dt(row["created_at"]),
                "message": "No changes specified. "
                "Use --name, --permission, or --expires-at to update.",
            },
            "id_key": f"auth-api-key-{key_id}",
        }

    from datetime import datetime, timezone

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    set_clauses = [f"{k} = ?" for k in updates]
    values = [updates[k] for k in updates] + [key_id]

    _auth_db.execute(
        f"UPDATE api_keys SET {', '.join(set_clauses)} WHERE id = ?",
        values,
    )

    # Re-read and return
    updated = _auth_db.execute_one("SELECT * FROM api_keys WHERE id = ?", (key_id,))
    if updated is None:
        return {
            "type": "error",
            "title": "Update Failed",
            "data": {"message": "Failed to read updated API key."},
        }

    return {
        "type": "detail",
        "title": f"API Key: {updated['name']}",
        "data": {
            "id": updated["id"],
            "name": updated["name"],
            "prefix": updated["prefix"],
            "permission": updated["permission"],
            "expires_at": _parse_dt(updated.get("expires_at")),
            "created_at": _parse_dt(updated["created_at"]),
            "updated_at": _parse_dt(updated["updated_at"]),
            "message": "API key updated successfully.",
        },
        "id_key": f"auth-api-key-{key_id}",
    }


# ── !auth api_key delete ─────────────────────────────────────────────────


@command("auth.api_key.delete", description="Revoke an API key")
def _auth_api_key_delete(flags: dict[str, str]) -> dict[str, Any]:
    """Revoke (delete) an API key by ID or name.

    Flags:
        --id: Key ID to delete.
        --name: Key name to delete (first match).
    """
    _ensure_db()

    key_id = flags.get("id")
    name_filter = flags.get("name") or flags.get("n")

    if not key_id and name_filter:
        keys = lookup_api_keys(_auth_db, include_expired=True)
        matching = [k for k in keys if k["name"] == name_filter]
        if matching:
            key_id = matching[0]["id"]

    if not key_id:
        return _auth_api_key_list(flags)

    row = _auth_db.execute_one("SELECT id, name FROM api_keys WHERE id = ?", (key_id,))
    if row is None:
        return {
            "type": "error",
            "title": "Key Not Found",
            "data": {"message": f"API key not found: {key_id}"},
        }

    key_name = row["name"]
    _auth_db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))

    return {
        "type": "success",
        "title": "API Key Revoked",
        "data": {"message": f"API key '{key_name}' revoked successfully."},
        "id_key": f"auth-api-key-delete-{key_id}",
    }
