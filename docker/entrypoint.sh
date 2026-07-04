#!/bin/sh
set -e

if [ -z "${SECOND_PASS_USERDATA_DIR:-}" ]; then
    echo "SECOND_PASS_USERDATA_DIR must be set." >&2
    exit 1
fi

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

    if [ ! -w "$dir" ]; then
        echo "Required userdata directory is not writable: $dir" >&2
        exit 1
    fi
done

echo "Starting Second Pass Library with userdata at $SECOND_PASS_USERDATA_DIR as uid=$(id -u) gid=$(id -g)"

python manage.py check --deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn secondpass.wsgi:application --bind 0.0.0.0:8000
