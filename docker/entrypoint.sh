#!/bin/sh
set -e

export SECOND_PASS_ENABLE_WHITENOISE=1
export SECOND_PASS_USERDATA_DIR=/app/userdata

for dir in \
    "$SECOND_PASS_USERDATA_DIR" \
    "$SECOND_PASS_USERDATA_DIR/db" \
    "$SECOND_PASS_USERDATA_DIR/media" \
    "$SECOND_PASS_USERDATA_DIR/imports"
do
    if ! mkdir -p "$dir"; then
        echo "Could not create required userdata directory: $dir" >&2
        exit 1
    fi

    if ! chown secondpass:secondpass "$dir"; then
        echo "Could not set required userdata directory ownership: $dir" >&2
        exit 1
    fi

    if ! gosu secondpass test -w "$dir"; then
        echo "Required userdata directory is not writable: $dir" >&2
        exit 1
    fi
done

echo "Starting Second Pass Library as uid=$(gosu secondpass id -u) gid=$(gosu secondpass id -g)"

gosu secondpass python manage.py check --deploy
gosu secondpass python manage.py migrate --noinput

exec gosu secondpass python -m uvicorn secondpass.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --no-proxy-headers \
    --no-access-log
