# LibraryReWrite2607 Reference

Historical reference for the LibraryReWrite2607 branch. Current architecture is
documented in the normal project docs; prefer those for implementation guidance.

## Original Design Note

Internal design note for a future in-place rewrite of the library/catalog
backend. This is documentation only; it is not an implementation plan for the
current code.

## 1. Purpose and Non-Goals

The current library backend grew from an EPUB-first prototype into catalog,
file storage, import, ACL, group browse, admin repair, and Product UI support.
The next version should make the domain model match the product more directly:
SecondPassLibrary is a self-hosted household library app where a `Book` is one
readable file with catalog metadata.

The redesign should be Calibre-informed, not a Calibre clone. Use metadata
concepts that matter for a household library, keep the API predictable, and
avoid generic systems that will be hard to explain or maintain.

Non-goals:

- Not a Calibre clone.
- No work/edition hierarchy.
- No multi-file-per-book or multi-format-per-book hierarchy.
- No arbitrary custom metadata or facet system.
- No tag namespaces, tag categories, or multiple freeform classification axes.
- No identifiers browse endpoint.
- No webhook/event-bus/custom metadata framework.
- No compatibility layer for old pre-release API semantics unless explicitly
  chosen later.

## 2. Core Domain Model

### Book

A `Book` is the readable file plus catalog metadata.

Fields:

- `id`
- `title`
- `sort_title`
- `subtitle`
- `language`
- `publisher`
- `published_year`
- `published_month`
- `published_day`
- `published_date_precision`
- `description`
- `cover_file`
- `book_file`
- `file_format`: `epub` initially; `cbz` later
- `checksum`
- `file_size`
- `created_at`
- `updated_at`

`file_format` initially supports EPUB only. CBZ is expected later and should fit
the same broad Book-owned-file model.

### Author

Fields:

- `id`
- `name`
- `sort_name`

`name` is display text. `sort_name` is ordering text. Do not split author names
into first/last components.

### BookAuthor

Fields:

- `book`
- `author`
- `position`

Authors are authors. Do not add contributor roles in LibraryReWrite2607. `position` defines
the display/order convention for multi-author books.

### Series

Fields:

- `id`
- `name`
- `sort_name`

### BookSeries

Fields:

- `book`
- `series`
- `series_index`

BookSeries is single-series only: a book belongs to at most one series. Do not
design multi-series support.

### CatalogTag

Fields:

- `id`
- `name`
- `sort_name`
- `normalized_name`

### BookCatalogTag

Fields:

- `book`
- `catalog_tag`

### BookIdentifier

Fields:

- `book`
- `scheme`
- `value`
- `normalized_value`

Identifiers are book metadata for import, detail display, export, and duplicate
handling. They are not a navigation axis and do not get browse endpoints.

Keep the current supported scheme set unless implementation proves one is
obsolete. Prefer uniqueness by `scheme + normalized value`; a given external
identifier should identify one book artifact record.

### Library Groups

Preserve the current ACL model:

- `LibraryGroup`
- `LibraryGroupMembership`
- `BookGroupAssignment`

Public/Common Room identity remains setting/id based, not name based.

## 3. File / Book Ownership Rule

`Book` owns its readable file directly:

- `Book` is the readable file plus catalog metadata.
- `file_format` is simple and product-facing.
- `book_file`, `checksum`, and `file_size` are book fields.
- No `BookFile` model in the current rewrite.
- Repair/import services own file validation and replacement behavior.
- Normal metadata forms do not edit file fields.
- File replacement, repair, and import use dedicated service paths.
- Download/open authorization remains current-access checked.

Checksums are globally unique when present. Treat checksum as content identity.
Duplicate imports are detected by checksum and should be handled in
import/service logic, not view code.

## 4. CatalogTag Rule

`CatalogTag` is the one freeform classification axis.

Imported OPF subjects, Calibre tags, genres, moods, and similar labels all map
into `CatalogTag`. A book can have many tags, and users can browse/filter by
tag.

There is one tag axis at a time. Do not add `CatalogTagA`, `CatalogTagB`, tag
namespaces, tag categories, arbitrary facets, or a custom metadata framework.

## 5. Author and Series Sort Semantics

- `name` is display.
- `sort_name` is ordering.
- Missing sort metadata falls back to `name`.
- Import may use Calibre/OPF sort metadata when present.
- No clever name inversion in migration/import fallback.
- Book ordering by author uses the first/display author `sort_name` according
  to the `BookAuthor.position` convention.
- Book ordering by series uses `Series.sort_name` and `BookSeries.series_index`.
- Sort fields should be editable in Product UI with clear labels.

## 6. Visibility and ACL Query Pipeline

Required query primitives:

- `visible_books_for_user(user, cached=True)`
- `visible_books_for_group(user, group, cached=True)`

ACL/group visibility happens before filters, search, ordering, pagination,
counts, and previews.

Global visible library means all books visible to the requesting user:

- Owner/Manager/Librarian broad access rules may include all books.
- Normal users see books assigned to at least one group intersecting with their
  effective memberships.

Group-scoped visible library means books assigned to that group after confirming
the user can see the group.

Endpoints must not reimplement ACL joins directly. They should ask the query
service for the base visible book universe, then apply endpoint-specific
filters, ordering, pagination, and serialization.

Critical open/download/mutation checks should use uncached/current permission
checks.

Cache policy:

- `visible_books_for_user(user, cached=True)` may cache visible book IDs for 120
  seconds.
- GET/list/browse/search endpoints may use `cached=True`.
- POST/PATCH/DELETE/open/download/security-sensitive checks use `cached=False`.
- No active invalidation is required initially for a self-hosted household app.
- Browse visibility may be stale for up to 120 seconds.
- Cached visibility is a browse optimization, not an authorization source of
  truth.

Public/Common Room behavior:

- No orphaned users.
- No orphaned books.
- If a user has zero library groups, restore Public/Common Room membership.
- If a book has zero library groups, restore Public/Common Room assignment.
- Public/Common Room identity remains setting/id based, not name based.

## 7. Browse Endpoint Shape

This document focuses on browse/read/query shape. Existing mutation endpoints
may be redesigned separately.

Global visible library cluster:

- `GET /api/v1/library/books/`
- `GET /api/v1/library/authors/`
- `GET /api/v1/library/series/`
- `GET /api/v1/library/tags/`

Group-scoped cluster:

- `GET /api/v1/library/groups/<group_id>/books/`
- `GET /api/v1/library/groups/<group_id>/authors/`
- `GET /api/v1/library/groups/<group_id>/series/`
- `GET /api/v1/library/groups/<group_id>/tags/`

Server owns filtering, ordering, and pagination. Client owns presentation mode,
such as List/Grid.

## 8. Query Parameters

Use current DRF-style query params:

- `q`
- `author`
- `series`
- `tag`
- `publisher`
- `ordering`

Rules:

- Query params must make sense for the endpoint context.
- `q` searches inside the selected context.
- `ordering` is explicit and allowlisted.
- No arbitrary model-field ordering.
- No time-based ordering.
- Invalid ordering returns `400` for visible resources.
- Hidden/inaccessible parent resources return `404` before ordering/filter
  validation.

Public browse/filter/order axes should be catalog-meaningful, not implementation
or archival metadata. Allowed public axes are:

- title
- author
- series
- series index
- CatalogTag/tag
- publisher
- language, only when a concrete browse need appears

Do not expose these as normal browse sort/filter axes:

- `file_format`
- checksum/file hash
- `file_size`
- `book_file` path
- cover metadata
- identifier fields such as ISBN/ASIN/DOI
- `created_at` or `updated_at`
- published date fields for now
- arbitrary internal model fields

Book `q` search may match:

- title and subtitle
- author
- series
- CatalogTag/tag
- publisher
- description, as long as the query remains bounded to the visible book context

Ordering uses DRF-style values. Supported book ordering values:

- `title`, `-title`
- `author`, `-author`
- `series`, `-series`
- `series_index`, `-series_index`
- `publisher`, `-publisher`

Author, series, and tag browse endpoints default to `name` and support `name`,
`-name`, `book_count`, and `-book_count`.

Default ordering:

- books default to `title`
- series-filtered books default to `series_index`
- authors/series/tags default to `name`

Author endpoint fields:

- `id`
- `name`
- `sort_name`
- `book_count`

Series endpoint fields:

- `id`
- `name`
- `sort_name`
- `book_count`

Tag endpoint fields:

- `id`
- `name`
- `slug`
- `book_count`

Axis detail endpoints return `404` when the requested author, series, or tag
has no visible books for the requesting user. Axis list/detail payloads do not
embed book lists; clients can use the books endpoint with `author`, `series`, or
`tag` filters.

Examples:

- `/api/v1/library/books/?q=dresden&author=<id>&ordering=-title`
- `/api/v1/library/books/?series=<id>&ordering=series_index`
- `/api/v1/library/books/?publisher=Orbit&ordering=publisher`
- `/api/v1/library/groups/<id>/books/?tag=<slug>&ordering=author`
- `/api/v1/library/authors/?q=butcher&ordering=name`
- `/api/v1/library/tags/?ordering=-book_count`

## 9. Import Mapping

Expected EPUB/OPF/Calibre mapping:

- title -> `Book.title`
- title sort -> `Book.sort_title`
- subtitle -> `Book.subtitle`
- creators/authors -> `Author` + `BookAuthor`
- author sort -> `Author.sort_name`
- series -> `Series` + `BookSeries`
- series sort -> `Series.sort_name`
- series index -> `BookSeries.series_index`
- subjects/tags/genres/moods -> `CatalogTag` + `BookCatalogTag`
- publisher -> `Book.publisher`
- published date -> `Book` partial-date fields
- language -> `Book.language`
- description -> `Book.description`
- cover -> `Book.cover_file`
- file/checksum/size/source filename -> `Book` file fields
- identifiers -> `BookIdentifier` metadata

Import rules:

- Explicit sort metadata wins when present.
- Missing sort metadata falls back to display/name fields.
- No clever name inversion in migration/import fallback.
- Import should preserve actor/provenance where assignments are created.
- Identifier duplicate handling belongs in import/service logic, not view code.

Published dates use partial-precision fields:

- `published_year`
- `published_month`
- `published_day`
- `published_date_precision`

At minimum, preserve year or year-month when that is all the source metadata
provides. Do not force fake UTC datetimes for book publication metadata. Avoid
pretending unknown month/day values are real.

## 10. Query Performance Rules

- Avoid N+1 queries in browse/list/detail serializers.
- Avoid unbounded child queries for previews.
- Use `select_related` and `prefetch_related` intentionally.
- Use `Exists`/indexed queries or cached visible book IDs for ACL base queries.
- Apply ACL before filters/order/pagination.
- Apply ordering before pagination.
- Previews should be bounded per parent.
- Do not fetch all books and trim in Python for parent previews.

## 11. Cross-App Integration Rules

- Shelves consume library query/policy services, not hand-rolled book ACL joins.
- Shelf add-book search for group-owned shelves starts from the owning group's
  visible book universe.
- Reading uses library policy/query services for current book access.
- Reading preserves owned reading history and marginalia after book access loss.
- Product UI and Reader consume the same browse API contracts.
- Admin repair behavior should be rebuilt only as needed after the new model
  exists; do not preserve the old repair UI solely for compatibility.

## 12. Suggested Rewrite Slices

1. Add this design doc and review it.
2. Implement model changes.
3. Implement visibility query helpers and tests.
4. Rebuild global books browse endpoint.
5. Rebuild authors/series/tags browse endpoints.
6. Rebuild group-scoped browse endpoints.
7. Rebuild import mapping.
8. Reconnect shelves.
9. Reconnect reading.
10. Rebuild Product UI catalog calls.
11. Update Reader migration docs.
12. Delete old obsolete library code.

## 13. Resolved Design Decisions and Remaining Open Questions

Resolved decisions:

- BookSeries is single-series only.
  - A book belongs to at most one series.
  - Do not design multi-series support.
- BookAuthor has no role field.
  - Authors are authors.
  - Do not add contributor roles.
  - BookAuthor only needs book, author, and position.
- `file_format` initially supports EPUB only.
  - Do not design exclusively around EPUB internals.
  - CBZ is expected later and should fit the same broad Book-owned-file model.
  - CBZ may need format-specific import/metadata extraction later.
- Checksums are globally unique when present.
  - Treat checksum as content identity.
  - Duplicate imports are detected by checksum.
  - Do not scope checksum uniqueness by `file_format`.
- Identifier schemes remain the current supported set.
  - Keep the current scheme list unless implementation proves one is obsolete.
  - Identifiers are metadata, not a browse axis.
- Identifiers are normalized and stored uniquely.
  - Prefer uniqueness by `scheme + normalized value`.
  - A given external identifier should identify one book artifact record.
  - Duplicate handling belongs in import/service logic, not view code.
- Product UI editability:
  - Most catalog metadata fields are editable.
  - Book id is not editable.
  - File fields are not edited through normal metadata forms.
  - File replacement/repair/import uses dedicated service paths.
  - Sort fields should be editable in Product UI with clear labels.
- Public membership/assignment behavior:
  - No orphaned users.
  - No orphaned books.
  - If a user has zero library groups, restore Public/Common Room membership.
  - If a book has zero library groups, restore Public/Common Room assignment.
  - Public/Common Room identity remains setting/id based, not name based.
- Published date should support partial precision.
  - At minimum, preserve year/month when only year or year-month metadata exists.
  - Do not force fake UTC datetimes for book publication metadata.
  - Avoid pretending unknown month/day values are real.
- Admin repair behavior:
  - Rebuild only what is needed after the new model exists.
  - Do not preserve old repair UI solely for compatibility.
  - Repair should account for Book-owned file fields and validation rules.

Remaining questions:

- Exact LibraryReWrite2607 identifier scheme enum/list copied from current model.
- Exact Product UI placement for editable sort fields.
