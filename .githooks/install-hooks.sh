#!/usr/bin/env bash
# Installs git hooks for openchronicle-mcp.
#
# - pre-commit: managed by the 'pre-commit' Python framework
#
# Usage: bash .githooks/install-hooks.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing hooks for openchronicle-mcp..."

# Find pre-commit: check PATH first, then .venv
PRE_COMMIT=""
if command -v pre-commit &>/dev/null; then
    PRE_COMMIT="pre-commit"
elif [ -f "$REPO_ROOT/.venv/Scripts/pre-commit.exe" ]; then
    PRE_COMMIT="$REPO_ROOT/.venv/Scripts/pre-commit.exe"
elif [ -f "$REPO_ROOT/.venv/bin/pre-commit" ]; then
    PRE_COMMIT="$REPO_ROOT/.venv/bin/pre-commit"
fi

if [ -n "$PRE_COMMIT" ]; then
    echo "  Installing pre-commit hooks..."
    "$PRE_COMMIT" install
else
    echo "  WARNING: 'pre-commit' not found in PATH or .venv."
    echo "           Run: pip install pre-commit && pre-commit install"
fi

echo "Done."
