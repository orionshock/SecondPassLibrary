#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE="$SCRIPT_DIR/compose.yml"
VERSION_FILE="$REPOSITORY_ROOT/backend/secondpass/version.py"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Compose file not found: $COMPOSE_FILE" >&2
    exit 1
fi

cd "$REPOSITORY_ROOT"

VERSION=$(git describe --tags --always --dirty)
RELEASE_DATE=$(git log -1 --format=%cs)
TEMP_VERSION_FILE=$(mktemp "$VERSION_FILE.XXXXXX")
trap 'rm -f "$TEMP_VERSION_FILE"' EXIT HUP INT TERM

echo "Stopping Second Pass Library..."
docker compose -f "$COMPOSE_FILE" down

ESCAPED_VERSION=$(printf '%s' "$VERSION" | sed 's/[\\"]/\\&/g')
printf 'SERVER_VERSION = "%s"\nSERVER_RELEASE_DATE = "%s"\n' \
    "$ESCAPED_VERSION" "$RELEASE_DATE" > "$TEMP_VERSION_FILE"
mv "$TEMP_VERSION_FILE" "$VERSION_FILE"
trap - EXIT HUP INT TERM

echo "Building Second Pass Library $VERSION ($RELEASE_DATE)..."
docker compose -f "$COMPOSE_FILE" up -d --build
