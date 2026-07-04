FROM python:3.13-slim

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=secondpass.settings \
    SECOND_PASS_USERDATA_DIR=/app/userdata

WORKDIR /app

RUN groupadd --gid "${APP_GID}" secondpass \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --home-dir /app --shell /usr/sbin/nologin --no-create-home secondpass

RUN python -m pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/userdata /app/var/static \
    && chown -R secondpass:secondpass /app/userdata /app/var

USER secondpass

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
