"""Auth command handlers — ``!auth api_key list|create|update|delete``.

Registered via the ``@command`` decorator at import time.
Lazily resolves ``_auth_db`` from ``auth_routes`` at dispatch time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lighterauth.api_key import generate_api_key, lookup_api_keys

from ronzzdoi.auth.config import ALL_PERMISSIONS
from ronzzdoi.server.command.handlers import check_permission
from ronzzdoi.server.command.registry import command
from ronzzdoi.server import auth_routes as _auth_routes


def _ensure_db() -> None:
    """Raise if auth DB is not initialised."""
    if _auth_routes._auth_db is None:
        raise RuntimeError("Auth database not initialised. Call mount_auth_routes() during startup.")


# ── auth.api_key.list ───────────────────────────────────────────────────


@command("auth.api_key.list", description="List all API keys")
def auth_api_key_list(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List API keys. Use ``--include-expired`` to show expired keys.

    Usage::

        !auth api_key list [--include-expired]
    """
    perm = check_permission(user, "admin")
    if perm:
        return perm

    _ensure_db()
    include_expired = "include-expired" in flags

    rows = lookup_api_keys(
        _auth_routes._auth_db,  # type: ignore[arg-type]
        include_expired=include_expired,
    )

    keys = [
        {
            "id": r["id"],
            "name": r["name"],
            "prefix": r["prefix"],
            "permission": r["permission"],
            "expires_at": r.get("expires_at") or "",
            "last_used_at": r.get("last_used_at") or "",
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]

    return {
        "type": "list",
        "title": "API Keys",
        "data": {"keys": keys, "total": len(keys)},
    }


# ── auth.api_key.create ─────────────────────────────────────────────────


@command("auth.api_key.create", description="Create a new API key")
def auth_api_key_create(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new API key. Raw key is shown only once.

    Usage::

        !auth api_key create --name <name> --permission read_only|edit|admin [--expires-at <iso>]
    """
    perm = check_permission(user, "admin")
    if perm:
        return perm

    name = flags.get("name", "")
    permission = flags.get("permission", "")

    if not name:
        return {
            "type": "form",
            "title": "Create API Key",
            "data": {
                "form": "auth-key-create",
                "initialData": {
                    "name": flags.get("name", ""),
                    "permission": flags.get("permission", ""),
                    "expires_at": flags.get("expires-at", ""),
                },
            },
        }

    if not permission or permission not in ALL_PERMISSIONS:
        return {
            "type": "error",
            "title": "Invalid Permission",
            "data": {
                "message": f"Permission must be one of: {', '.join(ALL_PERMISSIONS)}",
            },
        }

    _ensure_db()

    raw_key, prefix, hashed_key = generate_api_key()
    key_id = _auth_routes._generate_id()
    now_iso = datetime.now(timezone.utc).isoformat()
    expires_at = flags.get("expires-at") or flags.get("expires_at", "")

    _auth_routes._auth_db.execute(  # type: ignore[union-attr]
        "INSERT INTO api_keys (id, name, key, prefix, permission, expires_at, "
        "created_at, updated_at, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            key_id,
            name,
            hashed_key,
            prefix,
            permission,
            expires_at if expires_at else None,
            now_iso,
            now_iso,
            user["id"] if user else None,
        ),
    )

    return {
        "type": "success",
        "title": "API Key Created",
        "data": {
            "raw_key": raw_key,
            "id": key_id,
            "name": name,
            "prefix": prefix,
            "permission": permission,
            "message": (
                f"API key '{name}' created with {permission} permissions.\n"
                f"Raw key (copy now, will not be shown again):\n{raw_key}"
            ),
        },
    }


# ── auth.api_key.update ─────────────────────────────────────────────────


@command("auth.api_key.update", description="Update an API key")
def auth_api_key_update(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update an API key's name, permission, or expiry.

    Usage::

        !auth api_key update <id> [--name ... --permission ... --expires-at ...]
    """
    perm = check_permission(user, "admin")
    if perm:
        return perm

    key_id = positionals[0] if positionals else flags.get("id", "")
    if not key_id:
        return {
            "type": "form",
            "title": "Update API Key",
            "data": {
                "form": "auth-key-update",
                "initialData": {
                    "key_id": flags.get("id", ""),
                    "name": flags.get("name", ""),
                    "permission": flags.get("permission", ""),
                    "expires_at": flags.get("expires-at", "") or flags.get("expires_at", ""),
                },
            },
        }

    _ensure_db()

    # Verify key exists
    row = _auth_routes._auth_db.execute_one("SELECT * FROM api_keys WHERE id = ?", (key_id,))  # type: ignore[union-attr]
    if row is None:
        return {
            "type": "error",
            "title": "Not Found",
            "data": {"message": f"API key not found: {key_id}"},
        }

    # Build updates
    updates: dict[str, str | None] = {}
    if "name" in flags:
        updates["name"] = flags["name"]
    if "permission" in flags:
        perm_val = flags["permission"]
        if perm_val not in ALL_PERMISSIONS:
            return {
                "type": "error",
                "title": "Invalid Permission",
                "data": {
                    "message": f"Permission must be one of: {', '.join(ALL_PERMISSIONS)}",
                },
            }
        updates["permission"] = perm_val
    if "expires-at" in flags or "expires_at" in flags:
        val = flags.get("expires-at") or flags.get("expires_at", "")
        updates["expires_at"] = val if val else None

    if not updates:
        return {
            "type": "success",
            "title": "No Changes",
            "data": {"message": "No fields to update."},
        }

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clauses = [f"{k} = ?" for k in updates]
    values = [updates[k] for k in updates] + [key_id]

    _auth_routes._auth_db.execute(  # type: ignore[union-attr]
        f"UPDATE api_keys SET {', '.join(set_clauses)} WHERE id = ?",
        values,
    )

    # Re-read and return
    updated = _auth_routes._auth_db.execute_one("SELECT * FROM api_keys WHERE id = ?", (key_id,))  # type: ignore[union-attr]
    if updated is None:
        return {
            "type": "error",
            "title": "Update Failed",
            "data": {"message": "Failed to read updated API key."},
        }

    return {
        "type": "success",
        "title": "API Key Updated",
        "data": {
            "id": updated["id"],
            "name": updated["name"],
            "prefix": updated["prefix"],
            "permission": updated["permission"],
            "expires_at": updated.get("expires_at") or "",
            "message": f"API key '{updated['name']}' updated.",
        },
    }


# ── auth.api_key.delete ─────────────────────────────────────────────────


@command("auth.api_key.delete", description="Revoke (delete) an API key")
def auth_api_key_delete(
    flags: dict[str, str],
    positionals: list[str],
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Revoke an API key by ID.

    Usage::

        !auth api_key delete <id>
    """
    perm = check_permission(user, "admin")
    if perm:
        return perm

    key_id = positionals[0] if positionals else flags.get("id", "")
    if not key_id:
        return {
            "type": "error",
            "title": "Missing Key ID",
            "data": {"message": "Usage: !auth api_key delete <id>"},
        }

    _ensure_db()

    row = _auth_routes._auth_db.execute_one("SELECT id, name FROM api_keys WHERE id = ?", (key_id,))  # type: ignore[union-attr]
    if row is None:
        return {
            "type": "error",
            "title": "Not Found",
            "data": {"message": f"API key not found: {key_id}"},
        }

    _auth_routes._auth_db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))  # type: ignore[union-attr]

    return {
        "type": "success",
        "title": "API Key Deleted",
        "data": {
            "id": key_id,
            "message": f"API key '{row['name']}' ({key_id}) has been revoked.",
        },
    }
