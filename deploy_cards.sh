#!/usr/bin/env bash
# deploy_cards.sh - Copy custom Lovelace cards to config/www
#
# Usage:
#   ./deploy_cards.sh                     # defaults to /homeassistant/www
#   ./deploy_cards.sh /path/to/config     # explicit config root

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CARDS_DIR="$SCRIPT_DIR/custom_cards"

CONFIG_DIR="${1:-/homeassistant}"
WWW_DIR="$CONFIG_DIR/www"

if [ ! -d "$WWW_DIR" ]; then
    echo "Creating $WWW_DIR ..."
    mkdir -p "$WWW_DIR"
fi

echo "Copying cards from $CARDS_DIR -> $WWW_DIR"
cp "$CARDS_DIR"/*.js "$WWW_DIR/"

echo ""
echo "Done. Files in $WWW_DIR:"
ls -1 "$WWW_DIR"/*.js 2>/dev/null || echo "  (none found)"
