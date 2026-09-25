#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${SECOND_PASS_COMPOSE_FILE:-$REPOSITORY_ROOT/docker/compose.yml}
IMAGE_REPOSITORY=${SECOND_PASS_IMAGE_REPOSITORY:-git.zcaprica.duckdns.org/orionshock/secondpasslibrary}
HEALTH_TIMEOUT=${SECOND_PASS_HEALTH_TIMEOUT:-180}

usage() {
    echo "Usage: $0 <image-tag|full-image-reference>" >&2
    echo "Example: $0 sha-0123456789abcdef" >&2
}

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
    usage
    exit 2
fi
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Compose file not found: $COMPOSE_FILE" >&2
    exit 1
fi

case "$1" in
    */*) IMAGE_REFERENCE=$1 ;;
    *) IMAGE_REFERENCE=$IMAGE_REPOSITORY:$1 ;;
esac
case "$IMAGE_REFERENCE" in
    *:main|*:latest)
        echo "Refusing mutable deployment tag: $IMAGE_REFERENCE" >&2
        echo "Deploy an immutable sha-* tag, release tag, or digest." >&2
        exit 2
        ;;
esac

if [ -n "${SECOND_PASS_REGISTRY_USERNAME:-}" ] || [ -n "${SECOND_PASS_REGISTRY_TOKEN_FILE:-}" ]; then
    if [ -z "${SECOND_PASS_REGISTRY_USERNAME:-}" ] || [ -z "${SECOND_PASS_REGISTRY_TOKEN_FILE:-}" ]; then
        echo "Set both SECOND_PASS_REGISTRY_USERNAME and SECOND_PASS_REGISTRY_TOKEN_FILE." >&2
        exit 2
    fi
    if [ ! -r "$SECOND_PASS_REGISTRY_TOKEN_FILE" ]; then
        echo "Registry token file is not readable: $SECOND_PASS_REGISTRY_TOKEN_FILE" >&2
        exit 1
    fi
    REGISTRY_HOST=${IMAGE_REFERENCE%%/*}
    docker login "$REGISTRY_HOST" \
        --username "$SECOND_PASS_REGISTRY_USERNAME" \
        --password-stdin < "$SECOND_PASS_REGISTRY_TOKEN_FILE"
fi

export SECOND_PASS_IMAGE=$IMAGE_REFERENCE
compose() {
    docker compose -f "$COMPOSE_FILE" --profile discovery "$@"
}

echo "Pulling $IMAGE_REFERENCE..."
compose pull server worker

echo "Stopping the current Second Pass Library deployment..."
compose down

echo "Starting the replacement deployment..."
compose up -d --no-build

server_id=$(compose ps -q server)
if [ -z "$server_id" ]; then
    echo "The server container was not created." >&2
    exit 1
fi

deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
while :; do
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$server_id")
    if [ "$health" = healthy ]; then
        break
    fi
    if [ "$health" = unhealthy ] || [ "$(date +%s)" -ge "$deadline" ]; then
        echo "Server health did not become healthy (status: $health)." >&2
        compose ps >&2
        compose logs --tail 100 server >&2
        exit 1
    fi
    sleep 3
done

for service in worker discovery; do
    container_id=$(compose ps -q "$service")
    if [ -z "$container_id" ] || [ "$(docker inspect --format '{{.State.Status}}' "$container_id")" != running ]; then
        echo "$service is not running." >&2
        compose ps >&2
        compose logs --tail 100 "$service" >&2
        exit 1
    fi
done

echo "Deployment is healthy."
compose ps
docker inspect --format 'server image id: {{.Image}}' "$server_id"
docker exec "$server_id" python -c \
    'from secondpass.version import SERVER_RELEASE_DATE, SERVER_VERSION; print(f"Second Pass Library {SERVER_VERSION} ({SERVER_RELEASE_DATE})")'
