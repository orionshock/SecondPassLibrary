# Operations

This guide covers maintenance, recovery, and repair for a self-hosted Second
Pass Library instance. The supported deployment is one Docker Compose
application instance backed by SQLite. The operator is responsible for
filesystem permissions, backups, the reverse proxy, and any external scheduler.

See [Deployment](deployment.md) for installation, first setup, environment
configuration, upgrades, and the reverse-proxy trust contract. Tailscale or
another VPN may carry trusted access, but it is outside the product trust
model. Do not expose the Uvicorn port directly to the internet.

## Backup and restore

Back up the complete `/app/userdata` tree as one unit:

- `db/` contains SQLite state;
- `media/` contains EPUBs and covers referenced by that database;
- `imports/` contains temporary and staged import data.

Back up deployment-owned `docker/compose.yml` so
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
docker compose -f docker/compose.yml stop
docker compose -f docker/compose.yml run --rm --no-deps -v ./backups:/backup --entrypoint python server -c "import tarfile; archive=tarfile.open('/backup/secondpass-userdata.tar.gz','w:gz'); archive.add('/app/userdata', arcname='userdata'); archive.close()"
docker compose -f docker/compose.yml start
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

These commands are repeat-safe for the current database state and execute
synchronously without Huey. Registered tasks can also run through the built-in
Maintenance scheduler or Admin **Run now** workflow. Host cron or systemd may
invoke the direct commands when an instance does not run the maintenance
worker. Review Shelf cleanup before applying it.

### Client pairing requests

```bash
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_client_pairing_requests --dry-run
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_client_pairing_requests
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_client_pairing_requests --limit 1000
```

The command preserves active, unexpired requests. Expired pending or approved
requests are immediately eligible; denied, consumed, and explicitly expired
rows are retained for 24 hours. `--dry-run` does not mutate data. `--limit`
bounds one run from 1 through 10,000 rows and defaults to 1,000.

### Marginalia import stages

```bash
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_marginalia_import_stages --dry-run
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_marginalia_import_stages
```

The command removes expired stage records and their protected staged files, and
safe digest-named orphan files left after best-effort post-commit cleanup. It
preserves unexpired stages and imported Marginalia. Runtime access already
expires stages after two hours; cleanup reclaims storage. `--dry-run` reports
expired records without deleting them. This command has no batch-limit option.

### Deleted Marginalia Annotations

```bash
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_deleted_annotations --dry-run
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_deleted_annotations
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_deleted_annotations --limit 1000
```

Soft-deleted Annotation tombstones are permanently deleted according to their
deletion timestamp. Tombstones in closed Reading Sessions are retained for 7
days by default; tombstones in active Sessions are retained for 28 days. The
limits use the existing server-settings storage but are edited on the **Cleanup
Deleted Marginalia Annotations** Maintenance Task page. Both must be
non-negative whole-day values. `--dry-run` reports eligibility without deleting
rows. `--limit` bounds one run from 1 through 10,000 rows and defaults to 1,000.

The registered Maintenance task defaults to Monthly and may also be run
manually with **Run now** in Django Admin. Permanent cleanup deletes only
eligible Annotation rows; it does not delete Reading Sessions or Books.
Each cleanup run reads both retention values directly from the committed
database state, so the separate worker does not rely on its presentation cache.

### Unavailable personal Shelf items

```bash
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_shelves
docker compose -f docker/compose.yml exec -T server python manage.py cleanup_shelves --apply
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

Django Admin is an optional repair tool, disabled by default. Set
`SECOND_PASS_ENABLE_DJANGO_ADMIN=1` and restart the service only when it is
needed. Restrict `/admin/` to trusted LAN/VPN clients or a reverse-proxy
allowlist. Admin is for exceptional repair and inspection, not normal product
workflows; normal authority is documented in [Permissions](permissions.md).

The Admin **Maintenance Tasks** area is superuser-only. Approved task identity,
name, description, and executable are fixed in code. Admin controls only
enabled state and one bounded frequency: Manual only, Hourly, Every 6 hours,
Every 12 hours, Daily, Weekly, or Monthly. Definitions initially synchronize as
enabled; a superuser may still use **Run now** as an explicit override. The run page shows
queued, running, succeeded, failed, or interrupted state and a bounded result; application
logs remain the diagnostic record.

If a process exits after a run is queued or while it is running, the active run
may remain after the worker is gone. A superuser can open that run and choose
**Recover abandoned run**. Recovery requires explicit confirmation that every
Huey worker which could own the run has been stopped and the task is no longer
executing. It marks the run interrupted and frees the task's active slot; it
does not rerun the task or undo partial task work. Run age alone is never used
for recovery. Because the deployment has separate web and worker processes and
no cross-process ownership lease, verifying that the worker is gone remains an
intentional operator responsibility.

No arbitrary command, callable, argument, or schedule expression can be
submitted. Library/Book import and development fixture commands are excluded.
The cleanup management commands and Huey adapters call the same runtime
operations. CLI commands execute synchronously without the worker; scheduled
and Admin runs require `worker`.

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
- **Clean up Catalog Tags:** open a Catalog Tag to review every Book carrying
  it. Mark individual relationships, or mark all displayed relationships, for
  removal and save the tag. This removes only the tag relationships; it does
  not delete Books or reading data. To consolidate redundant tags, select two
  or more tags in the Catalog Tag list and choose **Merge selected Catalog
  Tags**. Review the relationship and overlap counts, choose the surviving tag
  identity, set its final name and sort name, and confirm. The survivor keeps
  its UUID and slug; overlapping Book relationships are collapsed and the
  other selected tags are deleted.

Take a verified backup before structural repair. Do not delete and re-import a
Book merely to restore its file: Book deletion cascades through Shelf,
Group-assignment, Session, and Annotation relationships. Deleting a Reading
Session deletes its Annotations. User, Owner, Group, and membership edits can
change ownership or visibility; prefer Product UI/services and the dedicated
recovery actions. Review Django's affected-object confirmation before any Admin
delete.

The normal owner-facing API may permanently delete one owned Marginalia Session
and its cascading annotations as the single server-owned operation documented
in [Marginalia](marginalia.md#reading-session-lifecycle). That narrow workflow
does not replace or constrain Django Admin's independent destructive repair
authority. Bulk and delete-all Session/history operations remain unsupported.

The Admin **Application Log Level** setting controls Second Pass Library
application namespaces. `INFO` is the normal level; use `DEBUG` temporarily
and return it to `INFO` after diagnosis. A committed change applies immediately
in the process handling the write. A separate process keeps its current level
until its log-level reader next runs after the 30-second cache window, or until
that process restarts; there is no cross-process invalidation channel. It does
not reduce Django security or error logging.

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
  `docker/compose.example.yml` and migration notes.

Inspect bounded container logs with:

```powershell
docker compose -f docker/compose.yml logs --tail 200 server
```

## Troubleshooting

- **Startup rejects settings:** inspect container logs. Production refuses a
  missing/default `DJANGO_SECRET_KEY`; also verify explicit
  `DJANGO_ALLOWED_HOSTS` and the values in `docker/compose.yml`.
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
- **Proxy symptoms:** `400` host failures indicate that `ALLOWED_HOSTS` does not
  include the Second Pass Library server name or IP from the request URL; it does
  not list connecting client addresses. CSRF failures indicate the public origin
  or forwarded scheme; redirect loops
  indicate incorrect forwarded-protocol replacement/trust. Unexpected shared
  login/pairing throttling usually means client-IP forwarding was not configured
  according to [Deployment](deployment.md#reverse-proxy-contract).
