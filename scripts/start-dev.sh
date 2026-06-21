#!/bin/sh
set -e

PYTHON="${PYTHON:-python}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR/.."

"$PYTHON" manage.py migrate --noinput
exec "$PYTHON" manage.py runserver "$@"
