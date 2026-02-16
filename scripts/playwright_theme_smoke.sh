#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
BRANDS=(acme aurora meridian)

export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"

if [[ ! -x "$PWCLI" ]]; then
  echo "Playwright wrapper not found at $PWCLI"
  exit 1
fi

for brand in "${BRANDS[@]}"; do
  session="theme-${brand}"
  "$PWCLI" -s="$session" open "$BASE_URL/demo/preview-page/$brand"
  "$PWCLI" -s="$session" screenshot
  "$PWCLI" -s="$session" close
  echo "Captured preview screenshot for $brand"
done
