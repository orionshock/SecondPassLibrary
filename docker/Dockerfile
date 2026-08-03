# syntax=docker/dockerfile:1

FROM node:22.22.0-bookworm-slim AS frontend-dependencies

WORKDIR /build/web/react

COPY web/react/package.json web/react/package-lock.json ./
COPY web/react/packages/spl-api/package.json packages/spl-api/package.json

RUN --mount=type=cache,target=/root/.npm \
    npm ci


FROM frontend-dependencies AS frontend-build

COPY web/react/ ./

RUN npm run build \
    && ! find dist -type f -name '*.map' -print -quit | grep -q .


FROM python:3.13-slim AS python-runtime-dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN python -m venv "$VIRTUAL_ENV"

COPY requirements.txt ./

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --disable-pip-version-check -r requirements.txt


FROM python-runtime-dependencies AS static-collection

ENV DJANGO_SETTINGS_MODULE=secondpass.settings \
    DJANGO_DEBUG=0 \
    DJANGO_SECRET_KEY=static-collection-build-only-secret \
    SECOND_PASS_ENABLE_WHITENOISE=1 \
    SECOND_PASS_USERDATA_DIR=/tmp/secondpass-userdata

WORKDIR /runtime

COPY manage.py ./
COPY accounts/ accounts/
COPY core/ core/
COPY library/ library/
COPY marginalia/ marginalia/
COPY secondpass/ secondpass/
COPY shelves/ shelves/
COPY templates/ templates/
COPY web/*.py web/
COPY web/static/ web/static/
COPY web/templates/ web/templates/
COPY --from=frontend-build /build/web/react/dist/ web/react/dist/

RUN python manage.py collectstatic --noinput --clear \
    && find var/static -type f -name '*.map' -delete \
    && mv web/react/dist/index.html /tmp/react-index.html \
    && rm -rf web/react/dist web/static \
    && mkdir -p web/react/dist \
    && mv /tmp/react-index.html web/react/dist/index.html


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

COPY --from=python-runtime-dependencies /opt/venv/ /opt/venv/
COPY --chmod=755 docker/entrypoint.sh /app/docker/entrypoint.sh
COPY --from=static-collection /runtime/ /app/


EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
