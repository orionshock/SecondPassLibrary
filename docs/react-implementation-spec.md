# React Product UI implementation specification

## Executive summary

This document translates the parked Product UI under
`reference/legacy_product_ui/` into implementation requirements for new React
code. The parked templates and JavaScript are behavioral and visual reference
material, not runtime dependencies or a required component structure. Current
permissions, API contracts, and privacy rules in `docs/` take precedence where
the parked UI is stale.

The React shell, Profile, password change, client pairing, Users,
library Imports, Server Settings, and the Library browse, Book Detail/Edit, and
Author/Series lifecycle slices are substantially rebuilt. Dashboard is a
placeholder, while My Marginalia, Groups, and Shelves remain to be rebuilt.
Library's compact Book row, cover, metadata, Catalog Tag rail, axis state, and
detail conventions are also consumed by Groups and Shelves.

The desired product remains a compact, dark, server-oriented application:
restrained headings, bounded content, rounded bordered rows, muted metadata,
small pills, Material Symbols, explicit page state in the URL, and actions near
the section they affect. React should preserve workflows and semantic detail,
not DOM quirks, inline styles, ad hoc HTML construction, duplicated pagers, or
legacy client-side permission inference.

## Sources and precedence

The audit covered:

- all templates, CSS, and JavaScript under `reference/legacy_product_ui/`;
- `docs/api.md`, `docs/permissions.md`, `docs/reading.md`, `docs/shelves.md`,
  `docs/imports.md`, `docs/ui.md`, `docs/react-ui.md`, and
  `docs/react-ui-rules.md`;
- the React shell and implemented feature branches under `web/react/src/`;
- current shared React UI under `web/react/src/components/` and
  `web/react/src/shared/`;
- all current SDK modules under `web/react/packages/spl-api/src/`.

Use this precedence when sources disagree:

1. current security, permissions, and API documentation;
2. current React rules and established React behavior;
3. this implementation specification;
4. parked UI behavior and visual semantics;
5. parked implementation details.

## Global UI rules to preserve

### Theme and typography

- Preserve the near-black `#0b0f14` background, blue-gray raised surfaces,
  off-white text, muted blue-gray secondary text, cyan links/focus accents,
  green success, and rose danger language already represented by React tokens.
- Keep native dark controls and strong visible keyboard focus. User content is
  plain text; never render metadata or API error HTML.
- Normal Product page titles use the current restrained `1.375rem`-class scale.
  Large type is reserved for Book Detail/Edit identity heroes, where the parked
  UI used a responsive display title beside the cover.
- Supporting labels, counts, timestamps, and metadata are compact. Uppercase
  eyebrow/column labels may use the existing small tracked treatment.

### Width, shell, navigation, and footer

- Keep the centered shell at roughly 72rem with responsive side gutters. Page
  regions use the full shell width only when a list or workspace needs it;
  forms remain bounded.
- The current non-fixed React header is acceptable. Preserve the compact brand,
  horizontally scrollable/wrapping navigation, profile identity, and logout.
- Navigation is capability- and mode-aware:
  - My Marginalia, Library, and Shelves are authenticated-user surfaces.
  - Groups is absent when advanced groups are disabled.
  - Imports is shown only to Librarian, Manager, and Owner.
  - Users is shown only to Manager and Owner.
  - Server Settings is Owner-only.
  Hidden navigation never replaces route-level authorization.
- Keep the server banner below the header and preserve whitespace/newlines.
- Keep the low-emphasis footer with product identity and version. On narrow
  screens it may stack.

Implemented foundation: `AppFrame` derives navigation visibility from stable
SDK role facts. Groups follows advanced-group mode; Imports is Librarian+;
Users is Manager+; and Server Settings is Owner-only. Route-level authorization
remains authoritative.

### Surfaces, rows, and actions

- Cards/surfaces denote meaningful sections or workflows, not every tab panel.
  Tabs sit outside their selected content.
- List items are compact rounded rows/cards with subtle borders and hover/focus
  accents. The Book title is the canonical row link. Do not make secondary
  metadata look like competing navigation.
- Page-heading primary actions align right and wrap below the heading on narrow
  screens. Form actions align right; feedback sits immediately left of the
  buttons. Secondary/Cancel precedes the primary action.
- Disable controls during their own pending mutation. Keep successful feedback
  for about five seconds; keep errors until retry, cancel, or state change.
- Loading, empty, forbidden, not-found, and error states are bounded and
  specific to the current tab/scope. Do not retain broken pager controls for an
  empty result.

### Forms and read-only data

- Use label-left/control-right form rows at desktop widths and a single-column
  layout on narrow screens. Long prose fields may use a vertical label when it
  reads better.
- Read-only facts use a key/value list or restrained definition list. Empty
  values use a muted dash or explicit product phrase, not `null`/`undefined`.
- Validate missing required files and obvious field requirements before an SDK
  call, while treating API validation as authoritative.

### Tabs, filters, pagination, and URL state

- Tabs use real buttons with selected/pressed state and associated panels.
  Tab, filter, ordering, search, page, and page-size state is URL-backed when it
  affects a server query or meaningful workflow context.
- Default values should generally be omitted from the URL. Invalid/hidden tabs,
  scopes, filters, page sizes, and orderings normalize to a safe default.
- A query/filter/tab/order/page-size change resets `page` to 1. Pager navigation
  changes only `page`. Back/Forward and reload restore state.
- Default page size for new Library-style lists is 20, with 20/30/40/50 where
  the legacy list offered those sizes. Marginalia sessions retain 10/20/50 and
  a default of 10.
- Long card lists may show synchronized top and bottom controls. Prefer the
  shared `PagerComponent`; a sticky bottom pager is optional only when it does
  not obscure content. Do not duplicate controller logic to render two pagers.

### Status, danger, help, badges, and icons

- Destructive object deletion uses a collapsed danger zone, consequences,
  typed-name confirmation where the old workflow required it, and a final
  confirmation dialog. Canceling confirmation makes no request.
- Compact detach/remove/revoke operations use `RemoveIconButton` and a focused
  confirmation owned by the feature.
- Use `HelpPopoverComponent`, never a native `title`-only tooltip, for contextual
  explanations. Help is available by hover, focus, and click.
- Pills/badges encode role, state, Public identity, Curator state, visibility,
  group ownership, or Catalog Tags. Keep them compact and wrapping; do not use
  badges for ordinary prose.
- Public/Common Room uses the existing green/public treatment. Danger rows and
  inactive state retain rose borders/backgrounds.
- Use `MaterialIcon` for Material Symbols Outlined. Canonical compact Book
  metadata tokens are `person` for author, `auto_stories` for series, and
  `apartment` for publisher. Decorative icons are hidden from assistive
  technology; icon actions have labels.

### Breadcrumbs and responsive behavior

- Base branch pages do not need breadcrumbs. Child/object/create/edit workflows
  use AppFrame breadcrumbs with explicit navigation context and canonical
  direct-load fallbacks as defined in `docs/react-ui-rules.md`.
- Tables become stacked semantic rows at narrow widths; tabs and action groups
  wrap or scroll locally without causing page-level horizontal scrolling.
- Cover/hero grids collapse to one column, metadata wraps, Catalog Tags become
  a collapsed disclosure below 720px, and action buttons remain keyboard
  reachable. Sticky controls must not cover the final row.

## Route and surface inventory

| Surface | Intended React route(s) | Status | Notes |
| --- | --- | --- | --- |
| App shell | all Product routes | Rebuilt | Capability/mode-aware nav needs tightening. |
| Dashboard | `/` | Still to rebuild | Current React route is a styled placeholder. Retire legacy `/dashboard/`; `/` is canonical. |
| My Marginalia | `/reading` and children below | Still to rebuild | Current `/reading` is a placeholder. |
| Library browse | `/library` | Top-level and selected browse rebuilt | Books/Authors/Series and selected Author/Series Book contexts share URL-backed ordering/search/tag/page state. |
| Book Detail/Edit | `/library/books/:bookId`, `/library/books/:bookId/edit` | Core slices rebuilt | Detail is read-only metadata plus safe EPUB download; Edit owns core bibliographic fields and relationships. |
| Author lifecycle | `/library/authors/new`, `/library/authors/:authorId/edit` | Create/Edit rebuilt | Detail remains selected Author in `/library`; Delete remains deferred. |
| Series lifecycle | `/library/series/new`, `/library/series/:seriesId/edit` | Create/Edit rebuilt | Same model as Authors; Delete remains deferred. |
| Groups | `/groups`, `/groups/new`, `/groups/:groupId`, `/groups/:groupId/edit` | Still to rebuild | Entire branch hidden/unavailable in simple mode. |
| Shelves | `/shelves`, `/shelves/new`, `/shelves/:shelfId`, `/shelves/:shelfId/edit` | Still to rebuild | Available in simple and advanced modes. |
| Library Imports | `/imports` | Rebuilt | Synchronous EPUB/ZIP upload; parked result cap is intentionally retired. |
| Users | `/users`, `/users/new`, `/users/:profileId/edit` | Rebuilt | No separate User Detail route. |
| Profile | `/profile` | Rebuilt | Self profile, memberships, sessions, clients. |
| Password change | `/profile/password` | Rebuilt | Forced-password route restrictions are current contract. |
| Client pairing | `/profile/client-pairing` | Rebuilt | Legacy `/client-api/authorize/` is intentionally retired. |
| Server Settings | `/server` | Rebuilt | Owner-only, URL-backed tabs. |
| Setup/login/logout | `/setup/`, `/login/`, `/logout/` | Retained Django | Not React work. |
| Django Admin | `/admin/` | Retained Django | Gated Service Hatch only. |
| DRF browsable/API auth | old `/api-auth/` UI | Intentionally retired | Do not restore. |

Recommended Marginalia child routes:

- `/reading` — session/book browse entry;
- `/reading/books/:bookId` — all owned sessions for one visible Book context;
- `/reading/books/:bookId/sessions/:sessionId` — session marginalia detail;
- `/reading/import` and `/reading/export`.

These preserve the old sessions-first behavior while using clean React routes.
Owned sessions whose Book is no longer visible remain accessible through
session history with redacted Book context; routes must not leak hidden Book
metadata.

## Dashboard specification

### Purpose and access

Authenticated landing page summarizing recent reading and offering familiar
entry points. All authenticated users can access it.

### Layout and behavior

- Render the server banner through AppFrame, not a second dashboard copy.
- First section: meaningful card titled `Recent reading activity`, a short
  explanation, and `View all sessions` action.
- Preserve a horizontally scrollable strip of up to ten recent session cards:
  compact cover, Book/session title, last activity, and optional progression
  circle. Use current visibility rules and omit open/continue affordances for
  unavailable Books.
- Follow with three responsive action cards: My Marginalia, My Shelves, and
  Browse Library. Groups appears in the Library card only in advanced mode.
- Empty state: `No recent reading activity yet.` The rest of the dashboard stays
  usable if recent activity fails.

### API, SDK, and tests

- Existing API is sufficient. Prefer
  `GET /api/v1/reading/sessions/recent/?limit=10` for continue-reading semantics;
  the parked dashboard used the general sessions list and therefore mixed
  active and closed activity.
- Add `reading.ts` SDK operations and compact session types.
- Tests: recent/empty/failure rendering, inaccessible sessions omitted by the
  API contract, action-card links, Groups mode visibility, and no duplicate
  banner.

Known legacy change: use the purpose-built recent-active endpoint instead of
preserving the parked general-list query. It better matches Dashboard action
semantics and current documentation.

## My Marginalia specifications

### Session and Book browse (`/reading`)

- Purpose: browse owned reading history by individual Session or grouped Book.
- Layout: restrained page header with Import/Export actions, status filters
  (`All`, `Active`, `Closed`), search, view toggle (`By Session`, `By Book`),
  page size, top/bottom pager, and compact session/book cards.
- URL state: `status=active|closed` (omit All), `q`, `view=book` (omit Session),
  `page`, and `page_size=20|50` (omit default 10).
- Server query: `GET /api/v1/reading/sessions/` with `q`, `is_active`, `page`,
  and `page_size`. Search includes owned session name/notes and currently
  visible Book metadata only.
- Session cards show cover when safe, session name or bounded unnamed label,
  visible Book summary or `Book unavailable`, dates, annotation count,
  progression, Active/Closed pill, and links only when `can_open` permits.
- Book view groups the returned page by Book. Preserve the old nuance that the
  server still paginates Sessions, so one Book can span pages; explicitly label
  counts as Books represented by the current Session page. Do not imply Book
  pagination.
- Empty and error copy is specific to current filters. Owned redacted history
  remains visible without open/continue actions.

### Book sessions (`/reading/books/:bookId`)

- Purpose: view all owned Sessions for a visible Book context and open the most
  recent session marginalia.
- Fetch `GET /api/v1/reading/sessions/?book=<bookId>`. Use `context.book` even
  when results are empty. Show a compact Book hero, series/authors, Session rows,
  and the same status/search/page controls where useful.
- Direct malformed/inaccessible Book context produces bounded not-found rather
  than exposing existence.

### Session marginalia (`/reading/books/:bookId/sessions/:sessionId`)

- Purpose: inspect one owned Session, progress, highlights, bookmarks, and
  notes. Current access controls whether the Book can be opened, not whether
  owned history can be inspected.
- Hero: Book cover/title when visible, session identity/status, dates,
  progression, annotation count, and Open/Continue only when `can_open`.
- Controls: annotation kind filters, ordering, and pagination. Highlight cards
  use semantic yellow/green/blue/pink/purple/orange accents; bookmarks and
  comments use Material icons. Never display raw selector/locator internals as
  primary prose; a safe location action may be exposed only when useful.
- Existing endpoints for session detail, progress, and owner-scoped annotation
  filtering are sufficient. Editing note/color or closing a Session remains
  governed by current API writability; read-only history must stay readable.

### Marginalia export (`/reading/export`)

- Complete archive card explains scope and downloads
  `GET /api/v1/reading/export/`, including owned unavailable-Book history.
- Selective archive groups owned Sessions under Book summaries. Support select
  Book, select individual Sessions, select all, clear, expand/collapse Session
  lists, live selection summary, and `POST /api/v1/reading/export/` download.
- Preserve familiar compact cover rows. Do not render raw database IDs;
  unnamed Session disambiguators may use a bounded suffix only when necessary.
- API gap: no dedicated JSON endpoint returns the complete selective-export
  inventory grouped by Book. The SDK can initially aggregate every page of the
  owner-scoped Sessions list, but a focused read-only export-selection summary
  endpoint would avoid a large client crawl. Decide before this slice; do not
  scrape the export file or reintroduce server-rendered context.

### Marginalia import (`/reading/import`)

- This is separate from Library EPUB/ZIP Imports.
- Native JSON file picker posts to
  `POST /api/v1/reading/import/preview/`. Preview creates no reading data.
- Render summary counts, matched/unmatched Books, warnings, malformed-locator
  Sessions, and a download action for the unmatched subset when available.
- Support Book/Session selection, select all/none, and edits to imported Session
  name/notes. Apply selected Sessions through
  `POST /api/v1/reading/import/apply/` using the transient `import_token`.
- Disable Apply until a valid selection exists. Clear staged UI after success
  and show created/skipped summaries. Do not invent jobs/history/polling.
- Existing API is sufficient. Add multipart preview, unmatched download, and
  multipart apply functions to `reading.ts`; preserve export-local Session IDs.

Tests for Marginalia cover URL normalization, status/query restoration,
redaction, `can_open`, pagination, file/selection validation, preview-before-
apply, unmatched download, safe errors, and absence of raw IDs/locators.

## Library implementation plan

### Shared Library state

`/library` has three functional top-level browse axes, selected Author and Series
Book contexts, and one stable Catalog Tag rail:

- `view=books` (safe default), `view=authors`, or `view=series`, with selected
  contexts represented by `view=authors&author=<id>` and
  `view=series&series=<id>`;
- `q`, `tag=<slug>`, `ordering`, `page`, and `page_size`;
- default page size 20; omit default axis/page/order/page size when practical;
- invalid/missing selected Author or Series IDs fall back safely without
  retaining conflicting `author` and `series` parameters.

Every top-level axis button navigates to that axis's canonical base, even when
the axis is already active. It clears selected context, `tag`, `q`, ordering,
and page while retaining non-default page size. Catalog Tag filtering applies
to Books, Authors, and Series.
Rail counts always represent viewer-visible Books; they do not become Author or
Series counts when those axes are active.

The first selected Author/Series browse context is in Library, not a separate
read-only lifecycle page. It reuses compact Book rows and does not fetch entity
metadata: row navigation state supplies an optional safe name, while a
direct load uses a generic heading. Links to Books carry explicit author/series
breadcrumb context through Router location state.

### Books axis

#### Layout and rows

- Header contains `Library`, Search, and no create action for Books. Functional
  Books, Authors, and Series tabs keep the page shell stable.
- Desktop uses a 150–190px Catalog Tag rail and flexible result column. Below
  720px the tag rail becomes a closed disclosure above results.
- Tag rail loads all paginated tag facets, begins with `All tags`, displays
  viewer-scoped `book_count`, toggles the active slug, and degrades independently
  if tags fail.
- The first-slice Book rows use a 52px-class cover, linked title, canonical icon
  metadata (authors, series/index, publisher), and up to six compact Catalog Tag
  pills followed by `+N`. Subtitle, language, published date, and file format
  remain in the app-facing compact object but are not displayed. Metadata wraps
  naturally and remains plain text.
- Compact Book API rows intentionally do not include group assignments.
  Do not preserve the parked JavaScript's attempted group-badge rendering and
  do not add a per-row detail request.
- The title and cover link to Book Detail. Avoid making the entire row a nested
  interactive target when row actions exist.

#### Search, sorting, pagination, and empty states

- Books-axis `q` means title/sort-title search only. Placeholder: `Book title…`.
  Do not claim broad metadata search here.
- Supported ordering: title, author, series and their API-supported directions.
  General/author-filtered default is title; a selected Series defaults to
  `series_index` and displays numeric index order with nulls last.
- `tag`, selected Author/Series, ordering, search, page, and page size compose
  in one server query. Empty copy distinguishes whole Library from selected
  Author, Series, Tag, or search context.
- Well-formed selected Author/Series UUIDs that are missing, deleted, or have no
  caller-visible matching Books produce the same empty paginated Book response.
  React must not infer entity existence from that empty list or expose a
  visibility distinction.
- Render a visible range and shared pager. Correct an out-of-range page to the
  last valid page without an infinite request loop.

### Authors axis

- `view=authors` lists compact Author cards with name, visible `book_count`, and
  a bounded cover preview strip from `include_preview_books=true`. Biography
  prose is reserved for a later lifecycle/detail slice.
- Search placeholder is `Author name…`; supported ordering is name or Book
  count in either direction. Catalog Tag filtering reduces the axis to Authors
  with visible Books carrying the selected tag and adjusts each visible count
  through the backend's axis contract.
- Selecting an Author name moves to `view=authors&author=<id>` and shows a
  restrained context header plus the selected Author's paginated compact Books.
  Biography remains off browse rows; Librarian+ lifecycle actions use the
  canonical create/edit routes.
- Axis header exposes `Create Author` only for Librarian+. Create/Edit links use
  canonical lifecycle routes; Book preview/title links carry Author context.
- Empty states distinguish no Authors, no search matches, and an Author with no
  visible/tagged Books. Management lifecycle still includes unattached Authors;
  ordinary Reader browse does not.

### Series axis

- Mirror Authors with Series name, visible `book_count`, and bounded cover
  previews. Summary prose is reserved for a later lifecycle/detail slice.
- Search placeholder is `Series name…`; ordering is name or Book
  count in either direction. Selected Series Books use `series_index` ordering
  by default and show series indices compactly.
- `Create Series` and Edit are Librarian+ only. Empty and URL-state behavior
  mirrors Authors.
- Selecting a Series name moves to `view=series&series=<id>` and shows a
  restrained context header plus the selected Series' paginated compact Books.
  Summary remains off browse rows; Librarian+ lifecycle actions use the
  canonical create/edit routes.

### Author and Series create/edit

- Bounded form fields: name, sort name, and Biography (Author) or Summary
  (Series). Save feedback belongs beside Cancel/Save.
- Edit loads the entity through the normal role-scoped detail endpoint. Duplicate
  names are legal and do not block saving.
- Create replaces to the returned entity's Edit route. Edit stays in place and
  replaces its draft/baseline from the response. Dirty navigation confirms.
- Delete and its attached-Book conflict workflow remain deferred.
- Do not add quick-create inside Book Edit and do not merge/reassign entities.

### Book Detail (`/library/books/:bookId`)

- All authenticated users with Book visibility may access. Inaccessible Books
  produce bounded not-found.
- The implemented hero uses a large cover column and Book identity column:
  title, subtitle, linked authors and Series/index, publisher, language,
  precision-aware publication date, Catalog Tags, escaped plain-text
  description, and authenticated Download EPUB from `file.download_url`.
- Lightweight local tabs below the hero provide an honest no-fetch Shelves
  placeholder, read-only visible Groups only in advanced mode, and Metadata
  containing publication, identifier, and safe file format/size facts.
- The nested `file` response is a projection of canonical EPUB fields stored on
  Book, not a separate asset record. `file: null` is an exceptional repair state
  shown as an unavailable EPUB; it is not presented as an optional file. A
  checksum is rendered only in the secondary Metadata tab's File panel.
- Real shelf loading, shelf and group relationship actions, Reader/Open,
  deletion, and cover mutation remain out of this read-only slice.
- Cover replace/clear is not available on Detail.

### Book Edit (`/library/books/:bookId/edit`)

- Librarian, Manager, and Owner may access; API remains authoritative.
- The implemented first slice uses a polished two-column workspace: a
  fixed-width read-only cover on the left and identity plus tabbed editing on
  the right, collapsing to one column on narrow screens.
- Its four real local tabs are Book (title, sort title, subtitle, description),
  Catalog (publisher, language, precision-aware publication date, Catalog
  Tags), Authors & Series (existing-entity assignment only), and Identifiers
  (complete scheme/value replacement through the Book PATCH).
- Save sends one explicit transactional PATCH for those edited domains, then
  replaces the draft and dirty baseline from the returned Book Detail while
  remaining on Edit. Dirty cancel/browser unload asks for confirmation.
- Catalog Tags use existing suggestions plus typed creation through Book PATCH;
  there is no standalone Tag lifecycle UI.
- Authors & Series assigns/removes existing Authors, assigns one existing
  Series, and edits Book-specific series index. There is no inline lifecycle
  creation.
- Identifier response ids are not sent in writes; one page-level Save owns the
  replacement alongside the other edited domains.
- Cover replace/clear is implemented as an immediate operation behind one
  Change Cover control and a bounded dialog. Clear confirmation stays inside
  the dialog. It is independent from metadata Save, keeps backend image
  validation authoritative, and updates only the displayed cover from the
  returned Book Detail without resetting the metadata draft or baseline. Local
  image preview remains deferred.
- Groups, shelves, file fields/actions, deletion, and Reader/Open are
  deliberately deferred and have no placeholder tabs.

### Library API, SDK, and tests

Existing APIs are sufficient for browse, detail, metadata writes, cover
mutation, Catalog Tags, Author/Series lifecycle, groups, and shelf relationship
reads/mutations. The initial `library.ts` SDK module owns compact Book list and
Catalog Tag list/all-page operations. Extend it with detail, broad search,
Authors/Series, and cover operations only when those workflows are implemented.
Compact Book wire responses use `catalog_tags`; the SDK maps that field to its
stable app-facing camelCase name. A complete Catalog Tag rail requests up to
200 rows per page and follows the paginated response's `next` links.

Do not add group summaries to compact Book rows. That is a stale legacy
expectation, not a backend gap.

Focused tests:

- query parser/serializer normalization for every axis and Tag composition;
- SDK snake/camel mapping and compact/detail shape separation;
- Books search semantics and selected Series default ordering;
- Author/Series preview, selected context, lifecycle permissions, duplicate
  advisory, attached-delete prevention, and safe deletion;
- Book row accessibility and metadata icons;
- Detail tab/mode behavior, download, safe metadata, and not-found;
- Edit dirty draft, URL tabs, cover workflow, assignment-only relationships,
  identifier validation, mode-hidden Groups, and independent mutation errors.

## Groups implementation plan

### Branch and list

- Entire `/groups` branch is absent from navigation and resolves to a bounded
  unavailable/not-found state when advanced groups are disabled. Public remains
  a backend object but is not exposed as custom-group navigation in simple mode.
- Group list uses paginated rows with group/public badges, current membership or
  Curator badge where safe, description excerpt, visible Book count, bounded
  preview covers, and canonical Group links. Manager/Owner sees `New group`.
- URL state: `page`, `page_size`, and supported `ordering`; default 20/name.
  The parked list did not consistently persist this state; React should.

### Create (`/groups/new`)

- Manager/Owner only. Bounded Name/Description form, Cancel then Create, feedback
  left of actions. Success navigates to Group View or Edit with breadcrumbs.

### Group View (`/groups/:groupId`)

- Read/presentation surface for a visible Group. Header contains identity badges,
  description, and Edit only when current capabilities/group context allow.
- URL-backed `tab=books|members|shelves`, default Books. Each tab owns `page` and
  `page_size`; changing tab resets incompatible paging.
- Books: group Book endpoint, canonical Book rows and Book Detail links, title
  ordering, no mutation actions.
- Members: username-only identities plus Curator indication. Never display name,
  email, raw IDs, or membership IDs.
- Shelves: `owner_group` list with previews, including empty visible group
  shelves; View only on this presentation surface.

### Group Edit (`/groups/:groupId/edit`)

- Tabs: Details, Books, Add Books, Members, Shelves. URL uses
  `tab=details|books|add-books|members|shelves`; accept old `view` only if a
  routing migration explicitly requires it—pre-release React should otherwise
  use one canonical parameter.
- Details:
  - custom Group description is editable by Librarian+, while rename/delete is
    Manager/Owner only according to API capability;
  - Reader curator may edit description only for their exact custom Group;
  - Public is fully read-only here and explains Server Settings ownership;
    Owner gets a same-window Server Settings link;
  - custom delete is collapsed, lists consequences, requires typed name and
    final confirmation. Public has no delete control.
- Books: assigned paginated Book rows with Remove actions and confirmation.
- Add Books: nonblank broad search with `exclude_group`, ordering title, URL
  `q/page/page_size`, Add action, and refresh of both assigned/candidate state.
- Members: Manager/Owner-only mutation controls. Search
  `/accounts/user-choices/?q=&exclude_group=`, choose username, optional Curator
  for custom Groups, add, update Curator, and confirm removal. Public never
  offers Curator and explains fallback behavior.
- Shelves: group-owned shelf list including empty shelves, previews, and
  Create/View/Edit actions according to `can_edit`. Create carries owner-group
  context to Shelf New.

### Groups API, SDK, and tests

Existing API is sufficient: group list/detail/lifecycle, Books, memberships,
user choices, and group shelf filtering. Add `groups.ts`; keep membership
public-profile identifiers internal to SDK calls and app objects.

Tests cover simple-mode branch absence, Public quirks, exact curator authority,
username-only member rendering, tab/query restoration, broad-search exclusion,
fallback-aware removal copy, danger confirmations, empty shelves, and
authoritative 403/404 handling.

## Shelves implementation plan

### Shelf list (`/shelves`)

- Explicit URL-backed scopes: `scope=personal` (default), `shared`, and `group`.
  Do not expose API `all` as a Product tab.
- Header has scope tabs and a separate right-aligned `New shelf` action.
- Shelf cards show name, safe description excerpt, owner/visibility/Public
  badges, viewer-visible item count, bounded cover preview strip, and View/Edit
  according to `can_edit`.
- Personal and Group scopes include empty visible shelves. Shared by Others
  omits empty and hidden-only shelves by API contract. Empty copy names the
  selected scope.
- URL state: `scope`, `ordering`, `page`, `page_size`; default 20/name.

### Shelf create (`/shelves/new`)

- All users can create personal shelves. Name, description, and private/listed
  visibility are bounded fields; listed copy explains that shelves do not grant
  Book access.
- Eligible operators may switch owner type to Group and select only manageable
  Groups derived from current capabilities plus Group list. Group shelves are
  always group-visible/private in API terms; hide irrelevant visibility input.
- In simple mode, Librarian/Manager/Owner may still create Public group shelves.
  Reader curators can create only for their exact custom Groups in advanced mode.
- Accept optional navigation context such as `owner_group` from Group Edit but
  validate against manageable choices.

### Shelf View (`/shelves/:shelfId`)

- Header shows name, subtle ownership/visibility summary, and Edit when
  `can_edit`. Description is restrained prose, not a heavy card.
- Items use canonical Book rows, optional safe Catalog Tags, and Book Detail
  links. URL state: `ordering=position|title|author`, `page`, `page_size`.
- Default ordering is stored position. Show `No visible books.` when all stored
  items are currently unavailable; do not reveal raw item count or hidden data.

### Shelf Edit (`/shelves/:shelfId/edit`)

- URL tabs: `tab=details|books|add-books`, with Books as the familiar default.
- Header summarizes owner, visibility, and viewer-visible item count. Do not add
  redundant View Shelf/View Group buttons; breadcrumbs provide context.
- Details: bounded Name/Description and visibility for personal shelves. Group
  shelf visibility is fixed with explanatory text. Delete is a collapsed danger
  zone and final confirmation; deletion removes ShelfItems, never Books/files.
- Books: paginated canonical Book rows with one-based position label, accessible
  Move up/down, Move to dropdown, and confirmed Remove. Disable impossible
  moves. Reordering uses zero-based API positions and refreshes canonical order.
- Add Books: blank search loads nothing. Use broad search with `exclude_shelf`,
  title ordering, paginated URL-backed `q/page/page_size`, Add, and refresh both
  current/candidate lists.
- A retained unavailable personal item is not rendered by normal reads. If an
  operation races with access loss, show bounded not-found and refresh; never
  reveal hidden Book metadata. The `cleanup_shelves` operator policy has no
  Product UI control.

### Shelves API, SDK, and tests

Existing API is sufficient. Add `shelves.ts` with scope/list/detail/item query
types, owner summaries, preview Books, `canEdit`, `matchedItemId`, and lifecycle/
reorder calls. Add Books uses `library.ts` broad search rather than raw calls.

Tests cover all scope/empty rules, URL state, private/shared/group ownership,
simple-mode Public shelf creation, curator eligibility, `can_edit` affordances,
hidden-item non-disclosure, ordering versus stored position, move boundaries,
blank broad search, exclusion, delete consequences, and 403/404 refresh paths.

## Existing rebuilt surfaces

### Library Imports

Keep the current synchronous EPUB/ZIP upload, transient latest result, no cap,
safe Book summaries, and detailed bounded failure rows. Do not restore the old
50-item cap or add jobs/history/staging/progress.

### Users

Keep the current compact composite columns, role-first default ordering, default
page size 20, hidden impossible role filters, inactive danger treatment, and
advanced-mode membership editing. Do not restore password-change-required list
badges or a separate User Detail page.

### Profile, password, pairing, and Server Settings

Current React behavior and `docs/react-ui-rules.md` are authoritative. The
parked pairing authorization page and `/api-auth/logout/` form are retired.
Setup, login, logout, and gated Admin remain Django surfaces.

## API and SDK gap analysis

| Family | API assessment | Current SDK | Required work or gap |
| --- | --- | --- | --- |
| Dashboard | Sufficient | None | Add recent Sessions mapping in `reading.ts`. |
| Marginalia browse/detail | Sufficient | None | Add Sessions, progress, annotations, activity summary operations. |
| Marginalia import | Sufficient | None | Add preview/unmatched/apply multipart and download operations. |
| Marginalia export | File endpoints sufficient; selection inventory awkward | None | SDK may aggregate paginated Sessions; consider a focused grouped selection-summary read endpoint before implementation. |
| Library browse | Sufficient | None | Add `library.ts` compact list/query mapping. Do not add group data to compact rows. |
| Book Detail/Edit | Sufficient | None | Add detail/PATCH/download metadata/cover/group/shelf adapters. SDK should expose safe file facts while React chooses not to foreground checksum. |
| Authors/Series | Sufficient | Browse plus lifecycle detail/create/update implemented | Delete remains deliberately deferred; normal Librarian+ session reads are catalog-wide. |
| Catalog Tags | Sufficient | None | Add read facets; mutate relationships only through Book PATCH. |
| Groups | Sufficient | User-edit contains narrow membership calls | Add full `groups.ts`; move/reuse API operations rather than duplicating URLs. |
| Shelves | Sufficient | None | Add `shelves.ts` lifecycle, list scopes, items, reorder, previews. |
| Users/Profile/Imports/Server | Sufficient and implemented | Existing modules | No audit-driven server changes. |

Potential response-shape improvement, not a blocker: Marginalia selective export
would benefit from a viewer-safe grouped Book/Session summary endpoint. No other
backend behavior gap blocks Library, Groups, or Shelves.

## Shared React component opportunities

| Candidate | Classification | Use |
| --- | --- | --- |
| `PageHeader`, `Surface`, `Button`, `FormField`, `ErrorPanel`, `Badge`, `KeyValueList` | Already exists | Continue, but avoid wrapping every tab in `Surface`. |
| `ActionRowComponent`, `ActionFeedbackComponent` | Already exists | All mutation forms. |
| `PagerComponent` | Already exists | Server-driven Library, Group, Shelf, and Marginalia lists. Defaults to 20/30/40/50 and accepts deliberate caller-specific sizes. |
| `MaterialIcon`, `RemoveIconButton`, `HelpPopoverComponent` | Already exists | Canonical icons, compact destructive actions, contextual help. |
| `TabListComponent` | Promote soon | Book Detail/Edit, Library axes, Group View/Edit, Shelf scopes/Edit, Marginalia views. It should be server-blind and controlled. |
| `BookCoverComponent` | Built with Library | Shared safe image/fallback and lazy-loading cover box. |
| `BookMetadataComponent` | Built with Library | Shared canonical icon metadata for Library and future Groups/Shelves/Marginalia use. |
| `BookRowComponent` | Built under Library | Compact cover/title/metadata/tag composition with no API or permission knowledge. |
| `CatalogTagRailPageRegion` | Built under Library | Library-owned facet disclosure, counts, selection, and independent failure state. |
| `CoverPreviewStripComponent` | Build with Library | Authors, Series, Groups, Shelves, Dashboard. Likely shared once two consumers land. |
| `SearchFilterToolbarComponent` | Wait | Toolbars differ substantially; reuse small controls/state helpers first. |
| `ModalDialogComponent` | Build with Book Edit | Cover modal establishes accessible dialog behavior; promote when another modal uses it. |
| `DangerZoneComponent` | Promote soon | Group, Shelf, Author, Series deletion with feature-owned copy/confirmation. |
| `MembershipRowComponent` | Wait | User and Group membership surfaces have opposite context and authority; share badges/help, not the whole row yet. |
| `ShelfPreviewComponent` | Build with Shelves | Shelf cards and Group shelf tabs; promote after both shapes stabilize. |
| `GroupBadgeComponent` | Promote soon | Profile, Users, Library Detail/Edit, Groups, Shelf ownership. Accept app-facing display data only. |
| `EmptyStateComponent` | Build with first list | Bounded title/body/action; no API knowledge. Avoid decorative illustration dependency. |
| `DownloadActionComponent` | Wait | Native authenticated links are simple; do not abstract prematurely. |
| Query-state helpers | Promote soon | Typed parse/normalize/write primitives for page/page size/tab/search; domain allow-lists remain feature-local. |

Do not create a generic DataTable or generic upload framework now. Product lists
are responsive card rows with domain metadata, and the two upload workflows
have materially different contracts.

## Suggested implementation order

1. **Library browse foundation (complete):** initial `library.ts`, URL-state
   parser, Book cover/metadata/row, Catalog Tag rail, Books axis, shared pager.
2. **Author and Series browse/lifecycle (complete for current scope):** controlled
   axes, selected contexts, and Librarian+ create/edit are built; Delete remains
   deferred.
3. **Book Detail (complete):** read-only hero, metadata, safe EPUB download,
   repair-state handling, and contextual breadcrumbs.
4. **Book Edit (current scope complete):** the four-tab bibliographic,
   relationship, and identifier editor plus independent cover replace/clear are
   built. File/EPUB editing remains deferred.
5. **Shelves:** SDK, scoped list/create/view/edit. This reuses Book rows and
   broad Library search.
6. **Groups:** SDK, list/create/view/edit. This reuses Book rows, shelf previews,
   badges, tabs, pagers, and broad search.
7. **Dashboard:** recent Sessions plus action cards after destination routes
   exist.
8. **My Marginalia:** browse/detail, export, then preview/apply import. Resolve
   selective-export inventory design before export UI implementation.

### Recommended next slice

Continue with Shelves or Groups while keeping deferred Delete and cover work as
separate mutation boundaries.

## Focused test strategy

- Keep all Vitest files under `web/react/src/__tests__/`.
- Classify API shape/auth/visibility and URL restoration tests as contracts;
  Public/fallback/privacy/non-disclosure tests as invariants; reported visual or
  workflow defects as regressions; isolated render mechanics as implementation
  detail.
- SDK tests assert paths, query omission/default behavior, request method/body,
  snake-to-camel mapping, pagination preservation, and structured errors.
- Query helper tests exercise malformed values, hidden mode-dependent tabs,
  defaults omitted from URLs, page reset rules, and Back/Forward-safe
  serialization.
- Component tests assert semantic labels, link targets, icon accessibility,
  safe fallback content, and absence of forbidden technical fields. Do not use
  snapshots or exact cosmetic pixels.
- Orchestrator tests use SDK mocks for loading, empty, forbidden/not-found,
  recoverable error, mutation pending/success/error, stale-response avoidance,
  and post-mutation refresh.
- Focus backend tests only when an identified API gap is implemented. Existing
  API behavior should otherwise be treated as a contract and not retested from
  React.
- For each future slice run the relevant Vitest files, the React build, SDK-only
  communication boundary check, Django check when routing/API integration
  changes, static hygiene, and `git diff --check`. Playwright is reserved for a
  separately authorized end-to-end pass.
