#!/usr/bin/env bash
# T060: regenerate apps/web's typed view of harness-api's REST surface
# from its live OpenAPI schema - no hand-written request/response types.
#
# Requires a running harness-api (e.g. `uv run uvicorn harness_api.main:app --port 8001`).
# Run from the repo root:
#   ./scripts/generate-frontend-types.sh
set -euo pipefail

HARNESS_API_URL="${HARNESS_API_URL:-http://127.0.0.1:8001}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_FILE="$REPO_ROOT/apps/web/lib/harness-api/schema.d.ts"

mkdir -p "$(dirname "$OUT_FILE")"

npx --prefix "$REPO_ROOT/apps/web" openapi-typescript \
  "$HARNESS_API_URL/openapi.json" \
  -o "$OUT_FILE"

echo "Wrote $OUT_FILE"
