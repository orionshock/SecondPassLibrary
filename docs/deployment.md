# Deployment

Second Pass Library supports one Docker Compose application instance with
SQLite and persistent Docker storage. The image builds the React Product UI,
collects static assets, applies migrations at web-container startup, and runs
one Uvicorn web process plus one Huey maintenance worker as the non-root
`secondpass` user.

The supported network boundary is a loopback/private application bind behind an
operator-managed reverse proxy. Direct public exposure of the Uvicorn port is
unsupported. HTTPS termination, HTTP-to-HTTPS redirect, HSTS, and public
exposure policy belong to the operator.

See [Operations](operations.md) for backups, cleanup, Admin repair, maintenance,
and troubleshooting.

## Fresh database requirement

The first-party migration history has been flattened into new initial
migrations. Databases created from the earlier migration history are not
compatible with this release. Create a fresh database and apply the current
initial migrations. Do not use `--fake-initial` or mark the initial migrations
as applied to an old database.

Retaining `userdata/media/` does not restore its database records or
relationships. Re-import EPUBs through a supported import path, or restore one
complete, mutually consistent database and userdata backup.

## Docker Compose

The example web service is `secondpasslibrary`;
`secondpasslibrary-maintenance-worker` is its separate background-maintenance
consumer. Both mount the named volume
`secondpass_userdata` at `/app/userdata`, while only the web service publishes
`127.0.0.1:8000:8000`. Do not scale the service or increase its worker count
while it uses SQLite.

The multi-stage image builds only `frontend/`, copies `backend/` into the
runtime tree, places the React artifact at `web/product_ui/`, and runs
`collectstatic`. The final image contains the prepared backend runtime and one
collected static asset tree, not Node, frontend source, tests, docs, or tools.

From the repository root:

```powershell
copy docker\.env.example docker\.env
copy docker\compose.example.yml docker\compose.yml
docker compose -f docker/compose.yml up -d --build
```

Before starting, replace the secret and hostname placeholders:

```text
DJANGO_SECRET_KEY=<generated-secret>
DJANGO_ALLOWED_HOSTS=<exact-hostnames-or-lan-ips>
```

Keep `docker/.env` readable only by the deployment account. Apply similarly
restrictive host permissions to bind-mounted userdata and any deployment-owned
Compose overrides. Optional values and defaults remain documented next to the
configuration in `docker/.env.example`.

The standard image fixes `SECOND_PASS_USERDATA_DIR=/app/userdata`. Its default
UID/GID is `1000:1000`; alternative IDs are Docker build arguments in
`docker/compose.yml`, not runtime environment variables. The entrypoint creates
and verifies the required userdata directories before dropping privileges.

Web startup performs:

1. `python manage.py check --deploy`
2. `python manage.py migrate --noinput`
3. `python -m uvicorn secondpass.asgi:application --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers --no-access-log`

After web health succeeds, `secondpasslibrary-maintenance-worker` runs
`python manage.py run_huey`. Huey's queue uses the separate persistent SQLite
file `/app/userdata/db/huey.sqlite3`, not Django's application database, and
the worker exposes no network port. Keep exactly one maintenance worker for
this SQLite-first deployment.

The container healthcheck calls `/api/v1/health/` with the first allowed host.
Readiness requires the database, built Product UI index, and writable userdata
directories. Startup refuses a missing/default production secret.

Complete first-owner setup through a local or otherwise trusted connection
before enabling remote proxy exposure. The setup wizard configures application
state after migrations; it does not create database tables during a request.
Once an active Owner exists, `/setup/` is disabled.

## Reverse-proxy contract

For HTTPS deployment, use exact public hosts and origins, secure cookies, and
explicit forwarded-protocol trust:

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<generated-secret>
DJANGO_ALLOWED_HOSTS=books.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://books.example.com
DJANGO_TRUST_X_FORWARDED_PROTO=1
DJANGO_SECURE_COOKIES=1
DJANGO_USE_X_FORWARDED_HOST=0
```

Uvicorn proxy-header rewriting is disabled in every supported startup path.
Django owns forwarded-header interpretation. The proxy must discard untrusted
incoming forwarded headers and set its own values; merely passing client values
through is unsafe. Forwarded host trust is normally unnecessary, so
`DJANGO_USE_X_FORWARDED_HOST` should remain disabled.

Pairing and browser-login throttling use the direct ASGI peer by default and
ignore `X-Forwarded-For`. If the application should distinguish client IPs,
enable Django's interpretation and list the exact direct proxy peers:

```text
DJANGO_TRUST_X_FORWARDED_FOR=1
DJANGO_TRUSTED_PROXY_IPS=127.0.0.1,::1
```

For a request received from an exact trusted peer, the application uses the
first address in `X-Forwarded-For`. The proxy must replace that header rather
than append to an untrusted client-supplied value. Do not enable this for an
untrusted, shared, or pass-through proxy.

The reverse proxy should also:

- own HTTPS redirect and HSTS;
- replace forwarded protocol and client-address headers;
- enforce reasonable request-body and header-size limits; the Library import
  request ceiling must permit the documented 256 MiB application limit without
  becoming a general multi-gigabyte upload path (see [Imports](imports.md));
- enforce header/read/idle timeouts that still allow expected synchronous
  imports and exports;
- apply coarse abuse limits to setup, login, and pairing creation without
  caching private authentication responses;
- keep the application port unreachable from untrusted networks.

With redirect and HSTS owned by the proxy, Django `check --deploy` may
legitimately report `security.W004` (`SECURE_HSTS_SECONDS`) and `security.W008`
(`SECURE_SSL_REDIRECT`). Review every warning; do not broadly silence deploy
checks. Secure-cookie warnings are not expected for an HTTPS deployment with
`DJANGO_SECURE_COOKIES=1`.

A VPN such as Tailscale may provide a private path to the proxy, but it is
optional infrastructure and not a Second Pass Library authentication or trust
boundary.

## Storage and served files

Durable state is under `/app/userdata`:

- `db/` contains SQLite;
- `media/` contains EPUBs and covers;
- `imports/` contains temporary or staged imports.

The default named volume needs no host path configuration. To use a bind mount,
change only the deployment-owned volume source while retaining the container
target:

```yaml
volumes:
  - /srv/secondpass/userdata:/app/userdata
```

Ensure the host directory is owned/writable by the configured container UID/GID
without granting broad access. See [Operations](operations.md#backup-and-restore)
for the backup unit and restore precautions.

Never expose `userdata/` or all of `userdata/media/` through the proxy.
WhiteNoise serves packaged assets under `/static/`; Django exposes only
`/media/covers/` as public display media. Stored EPUBs, imports, exports, and
Marginalia remain protected application responses.

## Optional Admin boundary

Django Admin is an intentional repair service hatch. Its route is registered
only when `SECOND_PASS_ENABLE_DJANGO_ADMIN=1`; keep it disabled normally. When
enabled, restrict it to trusted operator networks or a proxy allowlist. See
[Admin and repair workflows](operations.md#admin-and-repair-workflows).

## Upgrades

Before upgrading, take a verified backup as documented in
[Operations](operations.md#backup-and-restore). Then, from the repository root:

```powershell
git pull
docker compose -f docker/compose.yml up -d --build
```

Review changes to `docker/.env.example`, `docker/compose.example.yml`, and
migration requirements before starting the replacement container. The
entrypoint completes deploy checks and migrations before Uvicorn accepts
requests.

For a deliberately clean image rebuild:

```powershell
docker compose -f docker/compose.yml build --no-cache --pull
docker compose -f docker/compose.yml up -d
```

Use `docs/development.md` for the Windows local production-mode helper and
contributor startup commands; those helpers are not production secret or
deployment contracts.
