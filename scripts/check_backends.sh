#!/usr/bin/env bash
# Smoke test: every registered backend imports and builds the echo domain.
set -euo pipefail

cd "$(dirname "$0")/.."

for engine in agno adk pi; do
  echo "--- engine: $engine ---"
  APP_ENV=development GOOGLE_API_KEY=dummy-key SEMENTE_ENGINE="$engine" \
    .venv/bin/python -c "
from semente.backends.registry import get_backend
b = get_backend('$engine')
print('backend:', b.name)
" || { echo "✖ $engine backend failed"; exit 1; }
done

echo "✓ all backends import"
