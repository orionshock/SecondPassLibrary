# Product UI

This document defines the current browser Product UI contract. Exact API
routes, parameters, and response fields belong in `docs/api.md`; bearer-client
authentication belongs in `docs/client-api-auth.md`; role and visibility rules
belong in `docs/permissions.md`.

## Authentication and navigation

The Product UI is server-rendered by Django and enhanced with page-focused
JavaScript modules. Authenticated pages use Django session authentication. The
UI does not treat client bearer tokens as browser sessions.

Fresh installations begin at `/setup/`. Setup configures server identity, the
designated Public group's display identity, advanced-library-group preference,
and the first Owner. After setup, `/` leads to the authenticated dashboard.

The primary navigation exposes only surfaces appropriate to the current user
and server mode. Django Admin is an operator Service Hatch, not normal product
navigation. Its link appears only through the gated Owner Server Settings
surface when Django Admin is enabled.

Product object routes use stable UUID-backed URLs. Malformed, missing, or
inaccessible objects may return a styled 404 rather than revealing existence.
Logout is POST-based.

## Shared presentation conventions

- Page headings identify the current object or task. Frequent primary actions
  sit on the right side of the heading or relevant section controls and wrap on
  narrow screens.
- Tabs use the shared `.tabs` and `.tab-button` treatment and sit outside the
  selected content. The selected content does not receive a decorative outer
  card solely for being tab content.
- Tab, filter, page, and page-size state is URL-backed where the controller
  supports it. Direct URLs, reload, and browser back/forward restore that state.
- Library-style pagers provide Previous, Next, a visible result range/status,
  and a page-size selector. Long lists may use controls above and below the
  list, with the established sticky bottom pager.
- Changing page size resets the current page to 1. Changing a tab or scope
  resets only incompatible page state.
- Forms use bounded readable widths. Labels and controls align consistently;
  fields do not expand to viewport width without a reason.
- Cards are reserved for meaningful grouping, such as User, Password, and
  Group Memberships. A card is not added merely to wrap a page or list.
- Destructive group and shelf actions use a native collapsed disclosure and a
  final browser confirmation. Canceling confirmation makes no API request.
- Loading, success, and error messages use bounded status surfaces. API errors,
  tracebacks, or returned HTML are not rendered as raw markup.
- User-controlled values are inserted as text or passed through established
  escaping helpers. The UI does not interpret metadata as HTML.
- Compact identity rendering uses username/profile identity only unless a
  self-profile or authorized user-management workflow explicitly exposes more.

Shelf `can_edit` and similar payload hints control affordances, not authority.
The UI still handles authoritative 403 and anti-leakage 404 responses.

## Icons and compact book metadata

Product UI icons use Material Symbols Outlined.

- Decorative icons use `aria-hidden="true"`.
- Interactive icon buttons require visible text or a clear `aria-label` and
  remain keyboard-focusable.
- Shared helpers and styles are preferred over one-off raw icon spans.
- Metadata icons are subdued so they do not compete with the Book title.

Canonical compact Book metadata icons are:

| Field | Material Symbol |
| --- | --- |
| Author | `person` |
| Series | `auto_stories` |
| Publisher | `apartment` |

Compact metadata values are text, not links. The Book title remains the primary
canonical link. Visually hidden labels identify Author, Series, and Publisher
for screen readers while the icons remain decorative. Metadata groups use a
wrapping flex layout and gap spacing; they do not use literal or CSS-generated
dot separators.

The shared metadata treatment is used by Library Book rows, Group View Books,
Group Edit assigned/search rows, Shelf View items, and Shelf Edit item/search
rows. `menu_book` is avoided for Series because it can be confused with the
current Book; `store` is avoided for Publisher because it suggests a retailer.

### Reader-client icon advisory

The reader client uses the following Material Symbols Outlined vocabulary.
Product UI surfaces are not required to use every token. When both clients use
an icon for the same concept, prefer the same token unless the Product UI
meaning is materially different.

| Token | Reader-client context |
| --- | --- |
| `arrow_back` | Return from reader activity or session view |
| `arrow_forward` | Advance to the next book |
| `auto_stories` | Library Series axis and series sorting |
| `bookmark` | Existing bookmark annotation type |
| `bookmark_add` | Add bookmark reader action |
| `bookmark_added` | Current location is bookmarked |
| `border_color` | Highlight annotation type |
| `chat_bubble` | Highlight with note or comment |
| `check` | Confirm edits, saved metadata, or added shelf state |
| `check_circle` | Enabled marginalia layer |
| `chevron_left` | Previous reader page |
| `chevron_right` | Next reader page |
| `close` | Close a drawer, menu, editor, or dialog; cancel an edit |
| `delete` | Delete a shelf, shelf item, highlight, bookmark, or annotation |
| `done` | Finish shelf editing |
| `edit` | Edit shelf or session metadata |
| `edit_note` | Edit an annotation note or generic annotation fallback |
| `expand_more` | Library scope menu disclosure |
| `flag` | Complete reader activity when no next Book exists |
| `format_list_numbered` | Count/order sorting and explicit shelf/series order |
| `groups` | Non-Public Library group scope or shelf ownership |
| `home` | Return to application or Library home from the reader |
| `ink_highlighter` | Open marginalia or highlight controls |
| `keyboard_arrow_down` | Move a shelf item down |
| `keyboard_arrow_up` | Move a shelf item up |
| `library_books` | All Library scope |
| `link` | Start client pairing or linking |
| `local_library` | Connected Library identity in the application header |
| `menu` | Open the reader table of contents |
| `menu_book` | Library Books axis |
| `more_vert` | Open the shelf action menu |
| `my_location` | Navigate to an annotation or bookmark location |
| `open_in_new` | Open pairing authorization or an annotation target |
| `person` | Authors axis, author sorting, or user-owned shelves |
| `public` | Public Library group scope or public group ownership |
| `radio_button_unchecked` | Disabled marginalia layer |
| `search` | Open in-Book search |
| `settings` | Application and reader display settings |
| `sort_by_alpha` | Alphabetical Book, Author, Series, or shelf sorting |

## Library

The Library page has Books, Authors, and Series axes. Catalog Tags appear as a
filter rail rather than a fourth axis.

- Books-axis search matches Book title and sort title only.
- Authors and Series have axis-specific search and ordering.
- Author and Series rows may show bounded cover previews for visible Books.
- Catalog Tag filtering uses the tag slug supplied by the API. Tag rows are
  filter/facet data, not preview-card surfaces.
- Picker workflows use the broad library book search endpoint. Product copy and
  Product UI documentation call this “library search” or “broad library book
  search,” not internal programming shorthand.

Library axis, ordering, filter, pagination, and selected-tab state remain in
the URL. List rows use the shared Book row and metadata treatment.

### Book Detail

Book Detail uses a large-cover identity layout with the Book title and safe
visible metadata. The title/hero area is not replaced with a compact list row.

Its relationship/content tabs are Shelves, optional Groups, and Metadata. The
Groups tab is present only when advanced library groups are enabled. In simple
mode Public/Common Room remains a real backend group, but the Product UI does
not show an advanced Book/group relationship tab.

Visible shelf and group relationships are read-only on Book Detail. EPUB
download uses the authenticated action supplied by Book Detail file metadata.
Cover replacement and clearing are not Book Detail actions.

### Book Edit

Authorized Book Edit uses these tabs:

1. Book Details
2. Catalog
3. Authors & Series
4. Library Groups, when advanced mode exposes group management
5. Shelves
6. Identifiers & File Info

Metadata changes are saved through the Book edit workflow. Catalog Tags and
identifiers are managed with the Book rather than through standalone mutation
pages. Cover replacement/clear lives in Book Edit and uses its separate cover
workflow. Shelf and group relationship controls retain their own mutation
boundaries.

## Library Groups

Simple mode hides advanced group navigation, relationship tabs, and custom
group management. The designated Public/Common Room group still exists and
continues to support applicable group-scoped API reads and shelf ownership.

### Group View

Group View is presentation/read mode with tabs outside the content:

1. Books
2. Members
3. Shelves

Books use Library-style rows and canonical Book Detail links. Members display
compact username identity only. Shelves retain empty visible group shelves and
show safe preview strips without Edit actions. All three lists use URL-backed
Library-style pagination where applicable.

Group View does not add Author, Series, or Catalog Tag axes. It does not render
email, first/last names, raw user IDs, membership IDs, file paths, checksums, or
download metadata.

### Group Edit

Group Edit is management mode with these tabs:

1. Details
2. Books
3. Add Books
4. Members
5. Shelves

Books shows currently assigned Books and Remove actions. Add Books uses broad
library book search with `exclude_group`, then refreshes assigned and candidate
state after a successful add. Both tabs use Library-style rows and pagers.

Members preserves authorized add, curator-update, and remove behavior while
rendering username-only identity. Shelves retains create/view/edit management
actions, empty shelves, preview strips, and pagination.

For a custom group, Details exposes the currently authorized description edit.
Authorized Manager/Owner users may delete a custom group through a collapsed
Delete Group disclosure and final browser confirmation.

The designated Public group has an intentional read-only Details state showing
its current name and description. It explains that Public Library identity is
managed in Server Settings and gives Owner a same-window Server Settings link.
It has no Details Save or Delete Group control. Books, Members, and Shelves
remain available according to their existing authority.

## Shelves

The Shelves page uses explicit scope tabs:

1. Personal
2. Shared by Others
3. Group Shelves

The API also supports omitted/`all` combined scope, but the Product UI uses an
explicit scope so selected state is durable in the URL. Personal and visible
group-owned shelves remain listed when empty. Other users' listed shelves are
omitted when they have no viewer-visible Books, including hidden-only shelves.
Private shelf visibility is unchanged.

The scope header keeps New shelf separate from the tabs. Shelf cards retain
ownership/visibility metadata and safe preview strips. Scope, page, and page
size survive direct URLs and browser history.

### Shelf View

Shelf View presents its description as subtle user text without a separate
heavy card. Items use Library-style Book rows, compact icon metadata, optional
safe Catalog Tag pills, canonical Book Detail links, and top/bottom pagers.
File, storage, checksum, source, and hidden Book metadata are never rendered.

### Shelf Edit

Shelf Edit uses:

1. Details
2. Books
3. Add Books

Breadcrumbs provide navigation context; there are no redundant View Shelf or
View Group buttons. Details uses a bounded vertical form. Delete Shelf is a
collapsed disclosure with a final browser confirmation.

Books retains accessible move-up, move-down, move-to-position, and Remove
controls in a compact action area. Add Books uses broad library book search
with `exclude_shelf`; blank search does not load the whole Library. Both lists
use the shared Book row treatment and pagination where applicable.

User-owned shelf items preserve durable intent when Book access changes.
Unavailable items remain stored until explicit `cleanup_shelves` processing,
but Product UI responses and controls do not reveal the hidden Book data.

## Users

Users management is available according to the current Manager/Owner policy.

- The Users list has role/status filters, sorting, URL-backed pagination, and a
  right-aligned Create User action.
- Create User uses a bounded vertical form and right-aligned Create/Cancel
  actions.
- Edit User remains section-card based and does not use tabs.

Edit User contains three meaningful cards:

1. User
2. Password
3. Group Memberships

The page title includes the edited user's display identity and username. The
User card keeps its main Save separate from password state. “Require Password
Change on next login.” saves asynchronously and is not submitted by the main
User Save. Reset Password reveals the generated temporary password and its
one-time-copy warning only after a successful reset.

Group Memberships uses compact two-cluster rows: destructive remove plus group
badge on the left, and Curator state on the right. For Public, a Public Group
label replaces the curator checkbox. Its keyboard-accessible Product UI help
popover explains: “Only Librarians/Managers may Curate the Public Group.” The
help is available on hover and focus rather than permanently occupying the row.

User Edit and Group Edit are both valid membership-management surfaces. They
use the same authorized membership operations from opposite sides of the
relationship. Neither surface renders raw user IDs, membership IDs, hidden
group data, or unrelated profile internals.

## Imports and reading activity

Library import is a session-authenticated Product UI workflow for Librarian,
Manager, and Owner. EPUB and supported ZIP batches show bounded validation and
result summaries. ZIP OPF sidecars may replace embedded metadata for new Books;
valid referenced JPEG, PNG, or WebP sidecar covers take precedence over the
embedded cover. Missing or invalid sidecar covers fall back safely.

Reading session and Marginalia pages show only the authenticated user's data.
Owned history remains available after Book access loss with redacted Book
context and without open/continue actions. Dashboard continue-reading surfaces
omit inaccessible Books.

Marginalia import/export in the Product UI is session-only. Import uses preview,
selection, and apply steps; export supports the current user's owned sessions.
Detailed data formats and Reading API semantics belong in `docs/reading.md`,
`docs/api.md`, and the marginalia profile specification.

## Server Settings

Server Settings is Owner-only and uses these tabs:

1. General
2. Public Library
3. Library Groups

General contains server name, server description, and banner text. Public
Library manages the designated Public/Common Room name and description; normal
Group Edit does not edit this identity. Library Groups shows advanced-group
status and the enable action.

Enabling advanced groups requires browser confirmation. The normal Product UI
does not provide disable/collapse after enablement. That operation is a
recovery workflow through the Service Hatch.

“Service Hatch” means advanced settings and recovery tools provided through
Django Admin. Help uses the established keyboard-focusable Product UI popover,
not a native `title` tooltip. The Django Admin / Service Hatch action retains
its configured authorization and deployment visibility gates.

## Accessibility, privacy, and responsive behavior

- Tabs and action groups wrap without horizontal page scrolling.
- Sticky pagers do not obscure list content.
- Form controls, disclosures, help affordances, and icon actions are keyboard
  reachable and have accessible names.
- Hover help is also available by focus and through `aria-describedby`.
- Empty states are specific to the selected scope/tab and do not show broken
  pagination controls.
- The UI never renders membership record IDs, raw authentication user IDs,
  tokens, passwords, filesystem paths, source filenames, internal file keys, or
  inaccessible Book/group metadata.
- Email and personal-name fields appear only on authorized self-profile or user
  management surfaces, not compact Group member identity rows.
