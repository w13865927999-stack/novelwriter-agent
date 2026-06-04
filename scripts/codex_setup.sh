#!/usr/bin/env bash
set -euo pipefail

# Optional setup script for Codex Cloud environments.
# The smoke test itself works without these dependencies in mock mode, but
# installing requirements lets Codex exercise real OpenAI-compatible calls when
# environment variables are configured.

if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
else
  echo "Python was not found. Codex universal images normally include Python." >&2
  exit 1
fi

"$python_bin" -m pip install --upgrade pip
"$python_bin" -m pip install -r requirements.txt

