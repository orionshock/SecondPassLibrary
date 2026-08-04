# Operations

This document owns recurring operation, maintenance, recovery, and repair for a
self-hosted Second Pass Library instance. The supported shape is one Docker
Compose application instance with SQLite. The operator owns filesystem
permissions, backups, reverse-proxy operation, and any external scheduler.

See [Deployment](deployment.md) for installation, first setup, environment
configuration, upgrades, and the reverse-proxy trust contract. Tailscale or
another VPN may carry trusted access, but it is outside the product trust
boundary. Direct public exposure of the Uvicorn port is unsupported.

## Backup and restore

The canonical runtime backup unit is the complete `/app/userdata` tree:

- `db/` contains SQLite state;
- `media/` contains EPUBs and covers referenced by that database;
- `imports/` contains temporary and staged import data.

Back up deployment-owned `docker/.env` and `docker/compose.yml` separately so
the instance can be reconstructed. Protect configuration and backup archives
with restrictive host permissions; they contain secrets or private reading
data. Generated static output is image/build material and is not part of the
backup unit.

Database and userdata must describe one consistent point in time. Stop the
service before a filesystem-level backup, or use SQLite's online backup tooling
and coordinate its snapshot with media changes. Copying a live `db.sqlite3`
file is unsupported.

For the default named volume, the existing quiesced backup procedure is:

```powershell
New-Item -ItemType Directory -Force backups
docker compose -f docker/compose.yml stop secondpasslibrary
docker compose -f docker/compose.yml run --rm --no-deps -v ./backups:/backup --entrypoint python secondpasslibrary -c "import tarfile; archive=tarfile.open('/backup/secondpass-userdata.tar.gz','w:gz'); archive.add('/app/userdata', arcname='userdata'); archive.close()"
docker compose -f docker/compose.yml start secondpasslibrary
```

Place `backups/` outside any web-served directory and restrict it with the
host's normal permission tools. For a bind mount, stop the service and copy the
complete host userdata directory as one unit.

Restore into a stopped replacement instance, restore the matching deployment
configuration, and ensure the mounted tree is owned and writable by the
configured container UID/GID (`1000:1000` by default). Start the restored
instance on a non-production bind first. Confirm container health, login,
representative EPUB/cover access, and recent data before replacing the current
instance. Never combine an old database with unrelated media files.

## Cleanup and retention commands

These commands are repeat-safe for the current database state. Django does not
schedule them; run them manually or with host cron, systemd timers, or Windows
Task Scheduler. A weekly run is a reasonable home-lab starting point for
pairing and stage cleanup. Review Shelf cleanup before applying it.

### Client pairing requests

```bash
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_client_pairing_requests --dry-run
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_client_pairing_requests
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_client_pairing_requests --limit 1000
```

The command preserves active, unexpired requests. Expired pending or approved
requests are immediately eligible; denied, consumed, and explicitly expired
rows are retained for 24 hours. `--dry-run` does not mutate data. `--limit`
bounds one run from 1 through 10,000 rows and defaults to 1,000.

### Marginalia import stages

```bash
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_marginalia_import_stages --dry-run
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_marginalia_import_stages
```

The command removes expired stage records and their protected staged files, and
safe digest-named orphan files left after best-effort post-commit cleanup. It
preserves unexpired stages and imported Marginalia. Runtime access already
expires stages after two hours; cleanup reclaims storage. `--dry-run` reports
expired records without deleting them. This command has no batch-limit option.

### Unavailable personal Shelf items

```bash
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_shelves
docker compose -f docker/compose.yml exec -T secondpasslibrary python manage.py cleanup_shelves --apply
```

The default invocation is the dry run. `--apply` permanently removes currently
inaccessible items from user-owned shelves and compacts their positions. It
does not modify Group Shelves or accessible items. Visibility returning before
`--apply` preserves the retained item.

The command is idempotent for the current visibility state and has no batch
limit. Review the complete dry-run output before `--apply`, especially after
membership or Group Book-assignment changes. If unexpected unavailable counts
appear, repair visibility first and rerun the dry run; restored access keeps
the original item available for normal Shelf operations.

## Admin and repair workflows

Django Admin is an optional operator service hatch, disabled by default. Set
`SECOND_PASS_ENABLE_DJANGO_ADMIN=1` and restart the service only when it is
needed. Restrict `/admin/` to trusted LAN/VPN clients or a reverse-proxy
allowlist. Admin is for exceptional repair and inspection, not normal product
workflows; normal authority is documented in [Permissions](permissions.md).

Important repair flows are superuser-only:

- **Disable Advanced Library Groups:** use
  `/admin/core/serversetting/advanced-groups-disable/`, not a raw setting edit.
  The confirmed, fingerprinted transaction moves custom Group Shelves into
  Public/Common Room, removes custom-group assignments and memberships through
  their services, deletes the emptied custom Groups, and disables the feature
  only after consolidation succeeds.
- **Repair Public/Common Room identity:** use the action on the Server Settings
  admin. It can verify the configured Group or create a new Common Room, then
  restores only users and Books that have no Group. It does not make Public
  membership universal.
- **Repair stored EPUB:** open the existing Book and choose **Repair stored
  EPUB**. The guarded workflow validates the replacement while preserving the
  Book UUID, metadata, relationships, Shelves, Sessions, progress, and
  annotations. Replacing with a different checksum requires explicit
  confirmation because existing EPUB CFI anchors may no longer match.

Take a verified backup before structural repair. Do not delete and re-import a
Book merely to restore its file: Book deletion cascades through Shelf,
Group-assignment, Session, and Annotation relationships. Deleting a Reading
Session deletes its Annotations. User, Owner, Group, and membership edits can
change ownership or visibility; prefer Product UI/services and the dedicated
recovery actions. Review Django's affected-object confirmation before any Admin
delete.

The Admin **Application Log Level** setting controls Second Pass Library
application namespaces. `INFO` is the normal level; use `DEBUG` temporarily
and return it to `INFO` after diagnosis. It does not reduce Django security or
error logging.

## Routine maintenance

- Check `docker compose -f docker/compose.yml ps` and investigate unhealthy
  containers.
- Monitor free space for the Docker volume, database, media, staged imports,
  logs, and backup destination.
- Verify backups by restoring periodically to an isolated bind and opening
  representative Books and recent Marginalia.
- Run the applicable cleanup dry runs and review unexpected growth before
  applying destructive cleanup.
- Watch database growth and bounded logs for repeated import/export failures,
  cleanup failures, storage errors, or authentication throttling.
- Before upgrading, take and verify a consistent backup and review changes to
  `docker/.env.example`, `docker/compose.example.yml`, and migration notes.

Inspect bounded container logs with:

```powershell
docker compose -f docker/compose.yml logs --tail 200 secondpasslibrary
```

## Troubleshooting

- **Startup rejects settings:** inspect container logs. Production refuses a
  missing/default `DJANGO_SECRET_KEY`; also verify explicit
  `DJANGO_ALLOWED_HOSTS` and the values in `docker/.env`.
- **Migration failure:** the entrypoint stops before Uvicorn. Do not fake an
  incompatible migration. Preserve the failed database, inspect the error, and
  restore the last verified database/userdata pair if recovery is unsafe.
- **Product UI/static unavailable:** `/api/v1/health/` reports the database,
  Product UI index, and userdata checks separately. Rebuild the image through
  the supported Compose build; do not copy frontend artifacts manually into a
  running container.
- **SQLite lock/contention:** confirm there is only one application replica and
  one Uvicorn worker, and that backup or maintenance processes are not holding
  the database. The SQLite deployment is not intended for horizontal scaling.
- **Filesystem failure:** health and startup require writable userdata, DB,
  media, and import directories. Verify the mount target and configured
  UID/GID ownership rather than making the volume broadly writable.
- **Restore mismatch:** missing EPUBs/covers after restore usually means the
  database and media came from different snapshots. Restore one consistent
  backup unit.
- **Proxy symptoms:** `400` host failures indicate `ALLOWED_HOSTS`; CSRF
  failures indicate the public origin or forwarded scheme; redirect loops
  indicate incorrect forwarded-protocol replacement/trust. Unexpected shared
  login/pairing throttling usually means client-IP forwarding was not configured
  according to [Deployment](deployment.md#reverse-proxy-contract).
