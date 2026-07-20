"""Tests for ``src/ronzzdoi/auth/config.py`` — path resolution and constants."""

from __future__ import annotations

import os
from pathlib import Path

from ronzzdoi.auth.config import (
    ALL_PERMISSIONS,
    API_KEY_PREFIX,
    AUTH_HEADER_SCHEME,
    PERMISSION_FULL_ACCESS,
    PERMISSION_READ_ONLY,
    WRITE_PERMISSIONS,
    get_auth_config,
    resolve_auth_db_path,
)


class TestPermissionConstants:
    """Verify permission constants are consistent."""

    def test_read_only_value(self) -> None:
        assert PERMISSION_READ_ONLY == "read_only"

    def test_full_access_value(self) -> None:
        assert PERMISSION_FULL_ACCESS == "full_access"

    def test_write_permissions_only_full_access(self) -> None:
        """Only ``full_access`` grants write capability."""
        assert WRITE_PERMISSIONS == [PERMISSION_FULL_ACCESS]
        assert PERMISSION_READ_ONLY not in WRITE_PERMISSIONS

    def test_all_permissions_both(self) -> None:
        """All permissions includes both roles."""
        assert set(ALL_PERMISSIONS) == {PERMISSION_READ_ONLY, PERMISSION_FULL_ACCESS}


class TestHeaderConstants:
    """Verify auth header constants."""

    def test_scheme(self) -> None:
        assert AUTH_HEADER_SCHEME == "Bearer"

    def test_key_prefix(self) -> None:
        assert API_KEY_PREFIX == "la_"


class TestResolveAuthDbPath:
    """Tests for the ``resolve_auth_db_path()`` function."""

    def test_explicit_data_dir(self, tmp_path: Path) -> None:
        """Explicit ``data_dir`` produces ``{data_dir}/auth.db``."""
        result = resolve_auth_db_path(data_dir=tmp_path)
        assert result == tmp_path / "auth.db"
        assert result.parent == tmp_path
        assert result.parent.exists()  # mkdir was called

    def test_explicit_path_created(self, tmp_path: Path) -> None:
        """Directory is created if it does not exist."""
        nested = tmp_path / "nested" / "deep"
        result = resolve_auth_db_path(data_dir=nested)
        assert result == nested / "auth.db"
        assert nested.exists()

    def test_env_var_override(self, tmp_path: Path, monkeypatch) -> None:
        """``RONZZDOI_DATA_DIR`` env var is respected."""
        monkeypatch.setenv("RONZZDOI_DATA_DIR", str(tmp_path))
        result = resolve_auth_db_path()
        assert result == tmp_path / "auth.db"

    def test_env_var_override_vs_explicit(self, tmp_path: Path, monkeypatch) -> None:
        """Explicit ``data_dir`` takes precedence over env var."""
        monkeypatch.setenv("RONZZDOI_DATA_DIR", "/tmp/should-not-be-used")
        explicit = tmp_path / "my-data"
        result = resolve_auth_db_path(data_dir=explicit)
        assert result == explicit / "auth.db"
        assert explicit.exists()

    def test_default_fallback(self, monkeypatch) -> None:
        """Without explicit path or env var, falls back to XDG default."""
        # Ensure app name is set for path resolution
        from lightercore.paths import set_app_name

        set_app_name("ronzzdoi")
        monkeypatch.delenv("RONZZDOI_DATA_DIR", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        # The default should be under home/.local/share/ronzzdoi/auth.db
        result = resolve_auth_db_path()
        expected = Path.home() / ".local" / "share" / "ronzzdoi" / "auth.db"
        assert result == expected

    def test_data_dir_is_file_path(self, tmp_path: Path) -> None:
        """``data_dir`` pointing to a file is treated as a directory path.

        The function calls ``mkdir(parents=True)`` which will fail if an
        existing file is at that path.  We pass a path that doesn't exist
        to ensure it's created as a directory — no file conflict.
        """
        nonexistent = tmp_path / "nonexistent-dir"
        result = resolve_auth_db_path(data_dir=nonexistent)
        assert result == nonexistent / "auth.db"
        assert nonexistent.is_dir()


class TestGetAuthConfig:
    """Tests for the ``get_auth_config()`` function."""

    def test_no_secret(self, monkeypatch) -> None:
        """With no ``JWT_SECRET`` set, returns ``None``."""
        monkeypatch.delenv("JWT_SECRET", raising=False)
        config = get_auth_config()
        assert config == {"jwt_secret": None}

    def test_with_secret(self, monkeypatch) -> None:
        """With ``JWT_SECRET`` set, returns the value."""
        monkeypatch.setenv("JWT_SECRET", "my-super-secret-key-32bytes!")
        config = get_auth_config()
        assert config == {"jwt_secret": "my-super-secret-key-32bytes!"}
