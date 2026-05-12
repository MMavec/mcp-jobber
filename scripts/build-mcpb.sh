#!/usr/bin/env bash
# Build an MCPB bundle (mcp-jobber.mcpb) for Claude Desktop / Smithery upload.
#
# It stages manifest.json + the package + all its dependencies under build/mcpb/
# (MCPB requires Python deps to be bundled, not pip-installed at runtime), then
# packs it. Uses the official `@anthropic-ai/mcpb` CLI if `npx` is available
# (it validates the manifest); otherwise falls back to plain `zip`.
#
# Usage:  bash scripts/build-mcpb.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/mcpb"
OUT="$ROOT/mcp-jobber.mcpb"
PY="${PYTHON:-python3}"

echo ">> staging into $BUILD"
rm -rf "$BUILD" "$OUT"
mkdir -p "$BUILD/server/lib"
cp "$ROOT/manifest.json" "$BUILD/manifest.json"
cp "$ROOT/README.md" "$BUILD/README.md"
cp "$ROOT/LICENSE" "$BUILD/LICENSE"

echo ">> installing mcp-jobber + dependencies into the bundle"
"$PY" -m pip install --quiet --upgrade --target "$BUILD/server/lib" "$ROOT"
# Trim noise that the host doesn't need.
find "$BUILD/server/lib" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$BUILD/server/lib" -name "*.dist-info" -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo ">> packing"
if command -v npx >/dev/null 2>&1; then
  ( cd "$BUILD" && npx -y @anthropic-ai/mcpb pack . "$OUT" )
else
  echo "   (npx not found; using zip — install Node for manifest validation)"
  ( cd "$BUILD" && zip -qr "$OUT" . )
fi

echo ">> done: $OUT"
echo "   Note: dependencies are vendored, so if any pull in a compiled extension"
echo "   (cffi/cryptography), this bundle is specific to the OS + Python version that"
echo "   built it. Build it on the platform you'll run it on, or build one per platform."
echo "   - Claude Desktop: double-click it, or Settings -> Extensions -> Install."
echo "   - Smithery: upload it at https://smithery.ai/new (MCPB bundle option)."
