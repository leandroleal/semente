#!/usr/bin/env bash
# Check that app domains are engine-free (no direct agno imports).
# Run from an app root (has domain/) or the semente repo root (has examples/).
set -euo pipefail

hits=$(grep -rE "^\s*(from|import)\s+agno" domain/ examples/ 2>/dev/null || true)

if [ -n "$hits" ]; then
  echo "✖ agno imports found in domain/examples:"
  echo "$hits"
  exit 1
fi

echo "✓ domain is engine-free"
