#!/bin/sh
set -e

PYTHON="${PYTHON:-python}"
export DJANGO_DEBUG="${DJANGO_DEBUG:-1}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1,[::1]}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR/.."

"$PYTHON" manage.py migrate --noinput
exec "$PYTHON" manage.py runserver "$@"
