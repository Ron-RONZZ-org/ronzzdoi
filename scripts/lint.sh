#!/usr/bin/env bash
# Worktree-aware ruff wrapper for lefthook pre-commit hooks.
#
# lefthook runs `uv run ruff`, which fails inside a git worktree: uv tries
# to sync the project environment and resolves the sibling dependencies
# (../lighterauth, ../lightercore) relative to the worktree, where those
# paths do not exist.  This script resolves the MAIN checkout's `.venv`
# (via `git rev-parse --git-common-dir`, mirroring smart-test.sh) and runs
# its ruff binary directly — the same ruff the main checkout would use.
#
# Usage:  scripts/lint.sh {check|format} [ruff-args...]
#
# Example:
#   scripts/lint.sh check --force-exclude {staged_files}
#   scripts/lint.sh format --check --force-exclude {staged_files}

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── Resolve main checkout paths (for worktree support) ──────────────────
MAIN_DIR=""
if git -C "$ROOT" rev-parse --is-inside-work-tree 2>/dev/null | grep -q true; then
    GIT_COMMON_DIR=$(cd "$ROOT" && git rev-parse --git-common-dir 2>/dev/null || true)
    if [ -n "$GIT_COMMON_DIR" ]; then
        MAIN_DIR=$(cd "$GIT_COMMON_DIR/.." && pwd 2>/dev/null || true)
    fi
fi

# ── Locate a ruff binary ────────────────────────────────────────────────
find_ruff() {
    # Prefer the main checkout's venv (worktree-safe), then a local venv.
    if [ -n "$MAIN_DIR" ] && [ -x "$MAIN_DIR/.venv/bin/ruff" ]; then
        printf '%s' "$MAIN_DIR/.venv/bin/ruff"
        return 0
    fi
    if [ -x "$ROOT/.venv/bin/ruff" ]; then
        printf '%s' "$ROOT/.venv/bin/ruff"
        return 0
    fi
    if command -v ruff >/dev/null 2>&1; then
        printf '%s' "$(command -v ruff)"
        return 0
    fi
    return 1
}

RUFF_BIN="$(find_ruff || true)"
if [ -z "$RUFF_BIN" ]; then
    echo "scripts/lint.sh: ruff not found. Run 'uv pip install -e \".[dev]\"' in the main checkout." >&2
    exit 1
fi

# ── Dispatch ─────────────────────────────────────────────────────────────
CMD="${1:-check}"
shift || true

case "$CMD" in
    check)
        exec "$RUFF_BIN" check --force-exclude "$@"
        ;;
    format)
        exec "$RUFF_BIN" format --check --force-exclude "$@"
        ;;
    *)
        echo "scripts/lint.sh: unknown command '$CMD' (expected: check|format)" >&2
        exit 2
        ;;
esac
