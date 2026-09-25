#!/bin/sh
set -eu

if [ "$#" -ne 3 ] || [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
    echo "Usage: $0 <image> <expected-version> <expected-release-date>" >&2
    exit 2
fi

IMAGE=$1
EXPECTED_VERSION=$2
EXPECTED_RELEASE_DATE=$3
SMOKE_ID=${SECOND_PASS_SMOKE_ID:-${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}}
SERVER_CONTAINER=secondpass-smoke-server-$SMOKE_ID
WORKER_CONTAINER=secondpass-smoke-worker-$SMOKE_ID
USERDATA_VOLUME=secondpass-smoke-userdata-$SMOKE_ID

cleanup() {
    docker rm -f "$WORKER_CONTAINER" "$SERVER_CONTAINER" >/dev/null 2>&1 || true
    docker volume rm "$USERDATA_VOLUME" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

docker volume create "$USERDATA_VOLUME" >/dev/null
docker run --detach --name "$SERVER_CONTAINER" \
    --volume "$USERDATA_VOLUME:/app/userdata" \
    --env DJANGO_SECRET_KEY=smoke-test-only-not-a-production-secret \
    --env DJANGO_ALLOWED_HOSTS=127.0.0.1 \
    "$IMAGE" >/dev/null

attempt=1
while [ "$attempt" -le 60 ]; do
    if docker exec "$SERVER_CONTAINER" python /app/docker/healthcheck.py \
        >/dev/null 2>&1; then
        break
    fi
    if [ "$attempt" -eq 60 ]; then
        echo "Server did not become healthy." >&2
        docker logs "$SERVER_CONTAINER" >&2
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep 2
done

docker exec \
    --env EXPECTED_VERSION="$EXPECTED_VERSION" \
    --env EXPECTED_RELEASE_DATE="$EXPECTED_RELEASE_DATE" \
    "$SERVER_CONTAINER" python -c \
    'import os; from secondpass.version import SERVER_RELEASE_DATE, SERVER_VERSION; assert SERVER_VERSION == os.environ["EXPECTED_VERSION"]; assert SERVER_RELEASE_DATE == os.environ["EXPECTED_RELEASE_DATE"]'

docker run --detach --name "$WORKER_CONTAINER" --network none \
    --volume "$USERDATA_VOLUME:/app/userdata" \
    --env DJANGO_SECRET_KEY=smoke-test-only-not-a-production-secret \
    --env DJANGO_ALLOWED_HOSTS=127.0.0.1 \
    "$IMAGE" worker >/dev/null
sleep 5
if [ "$(docker inspect --format '{{.State.Status}}' "$WORKER_CONTAINER")" != running ]; then
    echo "Worker did not remain running." >&2
    docker logs "$WORKER_CONTAINER" >&2
    exit 1
fi

echo "Production image smoke test passed: $IMAGE ($EXPECTED_VERSION, $EXPECTED_RELEASE_DATE)"
