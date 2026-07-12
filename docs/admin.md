# Django Admin

The Django admin is an operator service hatch for recovery, inspection, and
low-level maintenance. It is not the Product UI and should not be treated as a
normal reader or library-management workflow.

`/admin/` is disabled by default unless `SECOND_PASS_ENABLE_DJANGO_ADMIN=1` is
set. This removes the `/admin/` URL route while leaving admin classes and repair
code installed. The local production helper sets this flag to `1` only when the
variable is unset and respects an explicit `0`. To expose admin in a trusted
deployment, set `SECOND_PASS_ENABLE_DJANGO_ADMIN=1`.

For exposed deployments, restrict admin access outside the app where practical:
LAN-only access, VPN, reverse-proxy IP allowlisting, or equivalent network
controls.

## Advanced Library Groups Recovery

Advanced library groups are off by default. An Owner can enable them from
Product UI with an explicit confirmation. Product UI does not offer a normal
disable action after enablement.

If an operator needs to reverse the setting, expose Django admin intentionally
and use the recovery action:

```text
/admin/core/serversetting/advanced-groups-disable/
```

Do not manually flip `core.ServerSetting(advanced_library_groups_enabled)` to
false. The structural setting page shows status and its recovery action instead
of an editable raw value. The superuser-only recovery flow renders a
fingerprinted plan and full counts, requires both a confirmation checkbox and
the typed phrase `DISABLE ADVANCED GROUPS`, rejects stale plans for review, and
runs the confirmed operation inside one database transaction.

The recovery flow:

- renames non-Public group shelves as `<group name> / <shelf name>`
- moves those shelves to the Public/Common Room group while preserving shelf
  rows, shelf items, and item order
- removes non-Public book/group associations through the existing group services
  so orphaned books naturally fall back to Public
- removes non-Public memberships and curator assignments through the existing
  group services so orphaned users naturally fall back to Public
- deletes the now-empty custom group containers
- disables advanced library groups only after consolidation succeeds

Public/Common Room remains a normal access-controlled `LibraryGroup`; moving
state there does not make books universally visible. An already-disabled
setting is presented as a safe no-op. An enabled installation with no custom
groups can complete the setting transition without deleting Public.

`ServerSetting.key` is visible and read-only. The admin does not allow adding
arbitrary `ServerSetting` rows or bulk deletion. Managed structural rows cannot
be deleted.

Server Name, Server Description, and Server Banner Message use semantic labels
and operator-facing help text. Advanced Library Groups exposes status and its
recovery action rather than a raw boolean. Public/Common Room Group uses an
explicit LibraryGroup selector and reassignment confirmation; groups with
curator memberships must be corrected before selection. Its separate recovery
action creates a fresh protected group without deleting the previously
configured group when **Create a new Common Room** is selected. Without that
selection, recovery uses the currently configured Public group. Both paths scan
all users and Books and restore only those with no group assignment to the
resulting Public group.

Books, stored EPUB fields/assets, users, reading sessions, progress,
annotations, Public/Common Room identity, shelves, and shelf items are
preserved.

## Stored Book File Recovery

Normal book creation happens through import. A normal user-facing `Book` owns
its stored EPUB fields directly:

- `book_file`
- `file_format`
- `checksum`
- `file_size`
- `cover_file`

There is no `BookFile` model in the current library catalog schema. If a
legacy/operator mistake leaves a `Book` without `book_file`, with a missing
physical EPUB, or with a file that must be deliberately replaced, open the Book
in Django admin and use **Repair stored EPUB**. This route is restricted to
superusers. The generic Book form keeps `book_file`, `file_format`, `checksum`,
and `file_size` read-only.

The repair page validates a replacement EPUB, reports the current stored-file
state, and requires explicit confirmation before replacing an existing physical
file. A different checksum requires a separate confirmation warning that EPUB
CFI anchors may no longer match. Successful repair returns to the same Book
change page.

Repair preserves the Book UUID, metadata, authors, series, identifiers, Catalog
Tags, cover, groups, shelves, reading sessions, progress, and annotations. It
does not store or display source-file provenance. Do not delete and re-import an
existing Book merely to restore its file when preserving reading data matters.

Checksum mismatch is intentionally guarded because replacing an EPUB with a
different file can invalidate EPUB CFI anchors used by annotations and reading
progress.

## Boundaries

Stored EPUB recovery is intentionally operator-facing. Product flows should
continue to use import for new books and should not create fileless Books.

The admin can still make destructive edits. Deleting a Book is outside this
repair workflow and may cascade to related records according to the current
schema. Prefer explicit operator repair/import planning over deleting and
re-importing when the goal is to restore a missing EPUB file while preserving
user marginalia.
