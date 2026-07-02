#!/bin/sh
set -e

PYTHON="${PYTHON:-python}"
BIND="${BIND:-0.0.0.0:8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
export DJANGO_DEBUG=0
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR/.."

"$PYTHON" manage.py migrate --noinput
"$PYTHON" manage.py collectstatic --noinput

set -- secondpass.wsgi:application \
    --bind "$BIND" \
    --workers "$WEB_CONCURRENCY"

if [ -n "${GUNICORN_CONFIG:-}" ]; then
    set -- "$@" --config "$GUNICORN_CONFIG"
fi

exec "$PYTHON" -m gunicorn "$@"
