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
and edit `core.ServerSetting(advanced_library_groups_enabled)`. Treat disabling
as recovery work: existing non-Public groups, memberships, assignments, and
group-owned shelves remain data, but Product UI hides advanced management
entry points and normal group mutation endpoints are blocked while disabled.

## BookFile Repair

Normal book creation happens through import. A normal user-facing `Book`
represents one concrete EPUB artifact and should have exactly one `BookFile`.
Fileless `Book` rows, or `BookFile` rows whose physical file is missing on
disk, are repair states.

The admin repair workflow is available from:

```text
/admin/library/book/
```

Open a Book and use **Repair stored EPUB** in the Stored EPUB section, or use
the repair link from the Books changelist.

Repair behavior:

- If the Book has no `BookFile` row, repair creates one for that existing Book.
- If the Book has a `BookFile` row but the stored file is missing, repair
  updates that existing row and preserves `BookFile.id`.
- If the stored file exists, repair is blocked unless the operator checks
  **Replace existing stored file**.
- If the existing `BookFile` has a checksum, repair requires the uploaded EPUB
  checksum to match by default.
- A different checksum is allowed only when the operator checks
  **Allow different checksum**.
- Repair does not update Book title, authors, identifiers, cover, reading
  sessions, progress, or annotations.

Checksum mismatch is intentionally guarded because replacing an EPUB with a
different file can invalidate EPUB CFI anchors used by annotations and reading
progress.

When repairing a missing physical file, preserving `BookFile.id` keeps existing
`Annotation.book_file` references attached to the same file identity row.

## Boundaries

The admin repair workflow is intentionally not exposed through the Product UI or
public API. Product flows should continue to use import for new books and should
not create fileless Books.

The admin can still make destructive edits. Deleting a Book is outside this
repair workflow and may cascade to related records according to the current
schema. Prefer BookFile repair over deleting and re-importing when the goal is
to restore a missing EPUB file while preserving user marginalia.
