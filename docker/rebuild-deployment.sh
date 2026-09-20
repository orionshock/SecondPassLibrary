#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE="$SCRIPT_DIR/compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Compose file not found: $COMPOSE_FILE" >&2
    exit 1
fi

cd "$REPOSITORY_ROOT"

if ! VERSION=$(git describe --tags --always --dirty); then
    echo "Could not derive the image version from Git." >&2
    exit 1
fi
if ! RELEASE_DATE=$(git log -1 --format=%cs); then
    echo "Could not derive the image release date from Git." >&2
    exit 1
fi
if [ -z "$VERSION" ] || [ -z "$RELEASE_DATE" ]; then
    echo "Git returned empty release metadata; refusing to build." >&2
    exit 1
fi

echo "Stopping Second Pass Library..."
docker compose -f "$COMPOSE_FILE" --profile discovery down

echo "Building Second Pass Library $VERSION ($RELEASE_DATE)..."
docker compose -f "$COMPOSE_FILE" build \
    --build-arg "SERVER_VERSION=$VERSION" \
    --build-arg "SERVER_RELEASE_DATE=$RELEASE_DATE"
docker compose -f "$COMPOSE_FILE" --profile discovery up -d
