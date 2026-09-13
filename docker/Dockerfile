# syntax=docker/dockerfile:1

FROM node:22.22.0-bookworm-slim AS frontend-dependencies

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/packages/spl-api/package.json packages/spl-api/package.json

RUN --mount=type=cache,target=/root/.npm \
    npm ci


FROM frontend-dependencies AS frontend-build

COPY frontend/ ./

RUN npm run build -- --outDir /build/product_ui \
    && ! find /build/product_ui -type f -name '*.map' -print -quit | grep -q .


FROM python:3.13-slim AS python-runtime-dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN python -m venv "$VIRTUAL_ENV"

COPY requirements.txt ./

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --disable-pip-version-check --no-compile -r requirements.txt \
    && pip check \
    && pip uninstall --yes pip \
    && find /opt/venv -type d -name __pycache__ -prune -exec rm -rf {} + \
    && rm -rf \
        /opt/venv/lib/python*/site-packages/huey/tests \
        /opt/venv/lib/python*/site-packages/jsonschema/tests \
        /opt/venv/lib/python*/site-packages/jsonschema_specifications/tests \
        /opt/venv/lib/python*/site-packages/referencing/tests


FROM python-runtime-dependencies AS static-collection

ENV DJANGO_SETTINGS_MODULE=secondpass.settings \
    DJANGO_DEBUG=0 \
    DJANGO_SECRET_KEY=static-collection-build-only-secret \
    SECOND_PASS_ENABLE_WHITENOISE=1 \
    SECOND_PASS_USERDATA_DIR=/tmp/secondpass-userdata

WORKDIR /runtime

COPY backend/ ./
COPY --from=frontend-build /build/product_ui/ web/product_ui/

RUN python manage.py collectstatic --noinput --clear \
    && find var/static -type f -name '*.map' -delete \
    && rm -rf web/product_ui/assets web/static


FROM python:3.13-slim AS runtime

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=secondpass.settings \
    SECOND_PASS_ENABLE_WHITENOISE=1 \
    SECOND_PASS_USERDATA_DIR=/app/userdata

WORKDIR /app

RUN groupadd --gid "${APP_GID}" secondpass \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --home-dir /app --shell /usr/sbin/nologin --no-create-home secondpass \
    && apt-get update \
    && apt-get install --yes --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/userdata/db /app/userdata/media /app/userdata/imports \
    && chown -R secondpass:secondpass /app/userdata

# Independent layers keep script, dependency, and application changes isolated.
COPY --link --chmod=755 docker/entrypoint.sh /app/docker/entrypoint.sh
COPY --link docker/healthcheck.py /app/docker/healthcheck.py
COPY --link --from=python-runtime-dependencies /opt/venv/ /opt/venv/
COPY --link --from=static-collection /runtime/ /app/


EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
