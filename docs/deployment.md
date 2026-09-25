# Deployment

Second Pass Library supports one Docker Compose application instance with
SQLite and persistent Docker storage. CI builds the React Product UI, collects
static assets, and publishes the production image. A deployment host only
pulls that image. At startup it applies migrations and runs one Uvicorn web
process plus one Huey maintenance worker as the non-root `secondpass` user.

Run the application behind a reverse proxy connected to the Compose network.
Do not publish the Uvicorn port on the host or expose it directly to the
internet. The operator's proxy handles HTTPS, HTTP-to-HTTPS redirects, HSTS,
and public access.

The Compose example enables secure cookies and Django's trust of the forwarded
HTTPS protocol for this deployment. The reverse proxy must replace incoming
`X-Forwarded-Proto` before forwarding requests. Forwarded client-IP and host
trust remain disabled unless separately configured.

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

The Compose project is `secondpasslibrary`. Its web service is `server`;
`worker` is its separate background-maintenance consumer. Both mount the named volume
`secondpass_userdata` at `/app/userdata`. The web service exposes port `8000`
only to containers on its Compose network; it does not publish a host port. The
reverse proxy should connect to `http://server:8000` on that network. Do not
scale the service or increase its worker count while it uses SQLite.

The multi-stage image uses Python 3.14, builds only `frontend/`, copies
`backend/` into the runtime tree, places the React artifact at
`web/product_ui/`, and runs `collectstatic`. The final image contains the
prepared backend runtime and one collected static asset tree, not Node,
frontend source, tests, docs, or tools.
The image also omits dependency test suites and the virtualenv's pip and
bytecode caches. The `seed_dev_users` command remains included. Runtime package
metadata, migrations, templates, translations, and schemas remain available.
The final script, dependency, and application copies use independent BuildKit
layers so changes to one do not invalidate the others.

The workflow in `.github/workflows/ci.yml` derives the version with
`git describe --tags --always --dirty` and the release date from the commit with
`git log -1 --format=%cs`. It passes both values to the existing Dockerfile
build arguments. The build replaces `secondpass/version.py` only in the image
staging tree before running `collectstatic`; it does not modify the checkout or
require Git in the runtime image.

Images are published at
`git.zcaprica.duckdns.org/orionshock/secondpasslibrary`. Every published build
has an immutable `sha-<full-commit-sha>` tag. Builds from `main` also update the
moving `main` integration tag, and Git tags add a same-named image tag. Use an
immutable SHA tag, a deliberate release tag, or a digest for deployments; do
not use `main` as a production deployment identity.

The canonical homelab deployment receives an already-published image identity
and does not pull source or build on NewCaprica:

```powershell
ssh NewCaprica "cd ~/projects/SecondPassLibrary/ && ./tools/redeploy-homelab.sh sha-<full-commit-sha>"
```

VS Code exposes this command as `Deploy: Homelab` and prompts for the immutable
tag or full image reference. `Deploy: Homelab Status` is the read-only
post-deployment status check.

From the repository root:

```powershell
copy docker\compose.example.yml docker\compose.yml
```

Before starting, edit the shared application environment in `docker/compose.yml`
and replace the secret, allowed-host, HTTPS origin, and Library URL placeholders:

```yaml
DJANGO_SECRET_KEY: <generated-secret>
DJANGO_ALLOWED_HOSTS: <library-server-hostnames-or-ips>
DJANGO_CSRF_TRUSTED_ORIGINS: https://books.example.com
SECOND_PASS_LIBRARY_URLS: https://books.example.com
```

Start the deployment after editing the file:

```powershell
docker compose -f docker/compose.yml pull
docker compose -f docker/compose.yml up -d --no-build
```

`docker/compose.yml` is the deployment configuration and contains the secret.
Keep it readable only by the deployment account. Optional values and defaults
are documented beside their entries in `docker/compose.example.yml`.
Set `SECOND_PASS_IMAGE` for a one-off immutable image selection, or replace the
example's `image:` value with the chosen release tag or digest. The default
`main` tag is intended only for integration deployments. The supported example
is self-contained and does not require a project `.env` file.

The standard image fixes `SECOND_PASS_USERDATA_DIR=/app/userdata`. Its default
UID/GID is `1000:1000`. The entrypoint creates and verifies the required
userdata directories before dropping privileges.

If the registry requires authentication, log in with a pull-only token before
running Compose. For the homelab tool, either rely on Docker's existing
credential store or set `SECOND_PASS_REGISTRY_USERNAME` and
`SECOND_PASS_REGISTRY_TOKEN_FILE`. The token file is read through
`docker login --password-stdin`; do not place tokens in Compose or command-line
arguments.

Web startup performs:

1. `python manage.py check --deploy`
2. `python manage.py migrate --noinput`
3. `python manage.py sync_deployment_server_settings`
4. `python -m uvicorn secondpass.asgi:application --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers --no-access-log`

After web health succeeds, `worker` runs
`python manage.py run_huey`. Huey's queue uses the separate persistent SQLite
file `/app/userdata/db/huey.sqlite3`, not Django's application database, and
the worker exposes no network port. Keep exactly one maintenance worker for
this SQLite-first deployment.

The container healthcheck calls `/api/v1/health/` with the first allowed host.
Readiness requires the database, built Product UI index, and writable userdata
directories. Startup refuses a missing/default production secret.

The deploy check also refuses `DJANGO_DEBUG=1`, an empty or wildcard
`DJANGO_ALLOWED_HOSTS`, the packaged hostname placeholder, malformed host
entries, and overlapping static/media roots. Host entries are hostnames or IP
addresses used to reach the Second Pass Library server, not addresses belonging
to connecting client devices. They are not URLs: omit schemes, paths, and ports.
Localhost, loopback addresses, private addresses, and Docker service names
remain valid server addresses.

Complete first-owner setup through a local or otherwise trusted connection
before enabling remote proxy exposure. The setup wizard configures application
state after migrations; it does not create database tables during a request.
Once an active Owner exists, `/setup/` is disabled.

### Optional command-line setup

Headless and disposable deployments may run the same first-owner setup workflow
with `setup_server` instead of using `/setup/`. The command accepts the Owner's
username plus optional account, server, Public/Common Room, and Advanced Library
Groups fields; run `python manage.py setup_server --help` for the complete list.

For an interactive terminal, omit the password options. The command prompts
twice without echoing the password:

```powershell
docker compose -f docker/compose.yml exec server python manage.py setup_server --username owner --server-name "Family Library"
```

For automation, pipe one raw password through stdin. It receives the same
Django password-strength validation as browser setup:

```sh
printf '%s' "$PASSWORD" | docker compose -f docker/compose.yml exec -T server python manage.py setup_server --username owner --password-stdin
```

An operator may instead pipe an already encoded Django password:

```sh
cat /run/secrets/owner-password-hash | docker compose -f docker/compose.yml exec -T server python manage.py setup_server --username owner --encoded-password-stdin
```

Encoded mode verifies that the configured Django hasher recognizes the value
and stores it unchanged. Plaintext strength validation is impossible in this
mode and remains the operator's responsibility. Treat the encoded value as a
secret: do not place either password form in process arguments or logs.

Both stdin modes read exactly one value and are mutually exclusive. The command
is atomic, refuses an already initialized server without changing it, and has
no force or reset mode. Migrations must already be complete, as they are during
normal container startup.

## Second Pass Reader web client URL

The optional `second_pass_reader_web_client_url` Server Setting is the base URL
used to open Books in the Second Pass Reader web client. It can be
edited in Django Admin as a single-line URL field, or fixed by deployment in
the shared Compose environment with:

```yaml
SECOND_PASS_READER_WEB_CLIENT_URL: https://reader.example.com
```

The value must be an absolute `http` or `https` URL. Localhost, private-network
hosts, and explicit ports are supported. Startup preserves the scheme, host,
and explicit port while removing any path, query string, fragment, and trailing
slash, then synchronizes the normalized value into the Server Setting row.
Runtime code reads that stored row rather than reading the environment directly.

## Optional LAN discovery

The optional `discovery` Compose profile advertises the Library on the host LAN
through mDNS/DNS-SD. Declare the externally reachable Library base URLs in
preferred order in the shared Compose environment. Put the first URL in the
`secondpass_discovery_service` TXT record and set its external SRV port in the
same Compose file:

```yaml
SECOND_PASS_LIBRARY_URLS: https://library.home.example,https://library.public.example
```

In `secondpass_discovery_service`:

```xml
<port>443</port>
<txt-record>url=https://library.home.example</txt-record>
```

Then start the normal deployment with discovery enabled:

```powershell
docker compose -f docker/compose.yml --profile discovery up -d
```

The sidecar uses host networking and publishes service type
`_secondpass._tcp` with the single Second Pass TXT property
`url=<first SECOND_PASS_LIBRARY_URLS entry>`. The operator keeps the TXT value
in sync with the first URL; Compose does not derive one from the other. Compose
mounts the inline declaration read-only, and the sidecar copies it into an
isolated temporary service directory before starting Avahi. This hides the
image's packaged SSH and SFTP declarations. Clients
use that URL directly; SRV host and port fields are publication plumbing. The
record contains no Server ID,
Library name, description, version, capability, authentication, or user data.
The server and worker do not depend on the sidecar and continue normally when
the profile is disabled or the sidecar fails.

Operators with their own Avahi, Bonjour, or compatible DNS-SD infrastructure
do not need the container. Publish `_secondpass._tcp` with exactly the `url=`
TXT property pointing to the client-facing Library URL. Multiple Libraries may
publish the same service type; clients obtain identity and display metadata
from each discovered URL's normal public HTTP endpoint.

`SECOND_PASS_LIBRARY_URLS` is also returned by authenticated server info as
`server_urls`. Values are comma-separated absolute HTTP(S) base URLs. The server
trims surrounding whitespace and a root trailing slash, removes duplicate
origins without changing the order, and rejects empty entries, credentials,
paths, queries, fragments, and malformed hosts or ports. An empty value yields
an empty list. Configure at least one URL and copy its first entry into the TXT
record before enabling discovery. The URLs are declarations,
not routing configuration. Operators must separately configure DNS, TLS, reverse
proxy routes, `DJANGO_ALLOWED_HOSTS`, CSRF trusted origins, and proxy trust.

## Reverse-proxy contract

For HTTPS deployment, use exact public hosts and origins, secure cookies, and
explicit forwarded-protocol trust:

```yaml
DJANGO_SECRET_KEY: <generated-secret>
DJANGO_ALLOWED_HOSTS: books.example.com
DJANGO_CSRF_TRUSTED_ORIGINS: https://books.example.com
DJANGO_TRUST_X_FORWARDED_PROTO: "1"
DJANGO_SECURE_COOKIES: "1"
DJANGO_USE_X_FORWARDED_HOST: "0"
```

Uvicorn proxy-header rewriting is disabled in every supported startup path, so
Django interprets forwarded headers. The proxy must discard untrusted
incoming forwarded headers and set its own values; merely passing client values
through is unsafe. Forwarded host trust is normally unnecessary, so
`DJANGO_USE_X_FORWARDED_HOST` should remain disabled.

Pairing and browser-login throttling use the direct ASGI peer by default and
ignore `X-Forwarded-For`. If the application should distinguish client IPs,
enable Django's interpretation and list the direct proxy peers as exact IP
addresses or bounded CIDR networks:

```yaml
DJANGO_TRUST_X_FORWARDED_FOR: "1"
DJANGO_TRUSTED_PROXY_IPS: 127.0.0.1,::1
```

For a request received from a trusted peer, the application uses the first
address in `X-Forwarded-For`. Invalid entries, an enabled trust setting with no
trusted peers, and trust-all networks fail the configuration check. Duplicate
networks produce a warning. Broad but bounded networks remain an operator
choice; prefer the narrowest range that describes the direct proxy peers. The
proxy must replace the header rather than append to an untrusted client-supplied
value. Do not enable this for an untrusted, shared, or pass-through proxy.

The reverse proxy should also:

- own HTTPS redirect and HSTS;
- set baseline response headers at the proxy, including a restrictive
  `Referrer-Policy`, `X-Content-Type-Options: nosniff`, and an appropriate
  framing policy; add CSP only after validating the built Product UI;
- replace forwarded protocol and client-address headers;
- enforce reasonable request-body and header-size limits; the Library import
  request ceiling must permit the documented 128 MiB application limit without
  becoming a general multi-gigabyte upload path (see [Imports](imports.md));
- enforce header/read/idle timeouts that still allow expected synchronous
  imports and exports;
- apply coarse abuse limits to setup, login, and pairing creation without
  caching private authentication responses;
- keep the application port unreachable from untrusted networks.

With redirect and HSTS owned by the proxy, Django `check --deploy` may
legitimately report `security.W004` (`SECURE_HSTS_SECONDS`) and `security.W008`
(`SECURE_SSL_REDIRECT`). Review every warning; do not broadly silence deploy
checks. Second Pass Library raises a deploy-check error when forwarded HTTPS
trust is enabled without secure session and CSRF cookies. Local direct HTTP
remains supported because that check applies only to forwarded HTTPS trust.
Forwarded host trust remains available for proxies that replace
`X-Forwarded-Host`, but produces an advisory warning because the normal and
safer deployment leaves `DJANGO_USE_X_FORWARDED_HOST=0`.

A VPN such as Tailscale can provide a private route to the proxy, but it does
not replace Second Pass Library authentication.

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

Django owns cover response caching. It serves only canonical content-addressed
cover paths and marks them public and immutable for one year. A reverse proxy
may cache `/media/covers/`, but must preserve the application's `Cache-Control`
and `Last-Modified` headers. It must not expose noncanonical cover names or any
sibling media path.

## Optional Admin boundary

Django Admin is an optional repair tool. Its route is registered
only when `SECOND_PASS_ENABLE_DJANGO_ADMIN=1`; keep it disabled normally. When
enabled, restrict it to trusted operator networks or a proxy allowlist. See
[Admin and repair workflows](operations.md#admin-and-repair-workflows).

## Upgrades

Before upgrading, take a verified backup as documented in
[Operations](operations.md#backup-and-restore). Select the immutable image
identity produced by a successful CI run, review changes to the distributable
Compose example and migration requirements, then pull and start it:

```powershell
$env:SECOND_PASS_IMAGE = "git.zcaprica.duckdns.org/orionshock/secondpasslibrary:sha-<full-commit-sha>"
docker compose -f docker/compose.yml pull
docker compose -f docker/compose.yml up -d --no-build
```

The homelab command is `tools/redeploy-homelab.sh <tag-or-reference>`. It pulls
first, stops the old deployment, starts the selected image without building,
waits for server health, checks the worker and discovery sidecar, and reports
the running version and image identity. It intentionally does not roll back:
if the replacement is broken, the deployment remains visibly broken until the
underlying problem is fixed. The entrypoint completes deploy checks and
migrations before Uvicorn accepts requests.

Use `docs/development.md` for the Windows local production-mode helper and
contributor startup commands; those helpers are not production secret or
deployment contracts.
