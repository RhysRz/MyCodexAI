#!/usr/bin/env bash
set -euo pipefail

SOURCE=${1:-/srv/mycodexai}
DESTINATION=${2:-/var/backups/mycodexai}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

test -d "$SOURCE" || { echo "State directory not found: $SOURCE" >&2; exit 1; }
install -d -m 0700 "$DESTINATION"
tar --exclude='*.tmp' --exclude='node_modules' --exclude='__pycache__' -C "$(dirname "$SOURCE")" -czf "$DESTINATION/mycodexai-$STAMP.tar.gz" "$(basename "$SOURCE")"
sha256sum "$DESTINATION/mycodexai-$STAMP.tar.gz" > "$DESTINATION/mycodexai-$STAMP.tar.gz.sha256"
echo "Created $DESTINATION/mycodexai-$STAMP.tar.gz"
