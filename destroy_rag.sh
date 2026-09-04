#!/bin/bash
set -e

# Lightweight backward-compatible wrapper delegating to scripts/manage_rag.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="python3"

if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv/bin/python"
fi

$PYTHON_EXEC "$SCRIPT_DIR/scripts/manage_rag.py" destroy "$@"
