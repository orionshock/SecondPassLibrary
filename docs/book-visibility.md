# Library Book Visibility

> **Immutable core policy for AI coding agents.** This file is authoritative and must not be edited, regenerated, consolidated, renamed, or deleted. If an implementation, test, API, SDK, Product UI behavior, or other document disagrees with this policy, stop and adjust the implementation and its dependent boundaries to comply. Do not resolve disagreement by weakening or changing this file.

## Authority and audience

This document owns the definition and enforcement of current Library Book visibility. It applies to backend, API, SDK, Product UI, and test work involving Library Books, Groups, Shelves, downloads, imports, or Marginalia. It does not own Advanced Mode presentation policy or the lifecycle of historical Marginalia; those belong to [Advanced Library Groups Mode](advanced-library-groups.md) and [Marginalia-Linked Books](marginalia-book-visibility.md).

The canonical terms are:

- A **Library-visible Book** is a Book currently available to a user through the canonical Library visibility policy.
- A user's **Library-visible Book set** is the complete current set of those Books.
- A **Group-visible Book** is assigned to a particular Group and visible through the user's relationship to that Group.
- An **available personal Shelf item** references a currently Library-visible Book. An **unavailable personal Shelf item** is retained after that Book ceases to be Library-visible.

Do not use `BookVerse` as the product term for this boundary. It is an implementation-specific search name, not the domain vocabulary.

## Scope and core distinction

Book visibility is a current, authorization-bearing property. The backend's canonical visibility query and the services that consume it decide what the user may currently browse, open, mutate, or download. React rendering, remembered client state, and possession of an object identifier are not authorization.

None of the following grants current Library visibility by itself:

- a Book appearing on any Shelf;
- a historical Reading Session or annotation;
- metadata inside a staged Marginalia import;
- a UUID retained from an earlier response;
- a previously rendered page or cached client model;
- a public cover URL;
- curatorship without the necessary Group membership.

Those references may retain narrowly documented historical or display context. They do not make the Book openable or downloadable.

## Canonical visibility definition

For an authenticated user:

- Owner, Manager, and Librarian see all Books.
- Readers, including Reader curators, see the distinct union of Books assigned to Groups for which they have explicit membership.
- A Book assigned to several Groups is visible if any one assignment matches one of the Reader's memberships.
- Duplicate matching paths produce one Book in the result.
- A Reader with no memberships sees no Books.
- Anonymous users see no Books.
- Supported session and bearer authentication boundaries reject inactive users before normal domain access.
- Advanced Mode versus Simple Mode does not participate in this calculation.

In compact notation, for active user `u`:

```text
LibraryVisible(u) = AllBooks                         when u is Librarian-or-higher
LibraryVisible(u) = union AssignedBooks(group)       for every explicit membership of u
LibraryVisible(u) = empty                            for anonymous access
```

The canonical implementation is `visible_books_for_user`. Authorization-sensitive callers use its uncached form. Helpers that accept a user object assume the caller has already passed a user accepted by the supported authentication boundary; they are not a substitute for authentication.

### Canonical-query discipline

All Book-bearing domains must derive their candidate set from the canonical visibility boundary or from a narrower query proven to be an intersection with it. Do not reproduce the role, membership, and assignment rules in serializers, React utilities, SDK adapters, or ad hoc view filters. A locally equivalent query is a drift risk because Public fallback, broad roles, distinct multi-Group results, and cache choice are easy to handle differently.

An exact Group projection is narrower than the user's general set:

```text
GroupVisible(user, group) = LibraryVisible(user) intersect AssignedBooks(group)
```

The user must also be allowed to see the Group itself. This matters for Group browse, Group axes, and Group Shelf candidates. A Book visible through Group A does not become eligible for a Shelf owned by Group B merely because the same user can see both Groups.

Code that already holds a `Book` instance must still recheck authority at the mutation or attachment boundary. Object retrieval during an earlier request phase, preview, serializer validation, or browser fetch is not durable authorization. When a workflow separates preview from apply, or validation from insertion, the final check belongs inside the transaction that performs the write.

## Role and membership matrix

| User state | Library-visible Book set | Important distinction |
|---|---|---|
| Owner | All Books | Broad role authority; membership is not required |
| Manager | All Books | Broad role authority; membership is not required |
| Librarian | All Books | Broad role authority; membership is not required |
| Reader | Union of Books assigned to explicitly joined Groups | No implicit visibility |
| Reader curator | Same membership-derived union as any Reader | Curatorship adds exact-Group management authority, not Books |
| Public-only Reader | Books assigned to the designated Public Group | Public membership must exist |
| Private-Group-only Reader | Books assigned to that private Group | Public membership is not required in addition |
| Multi-Group Reader | Distinct union across every joined Group | Any matching Group is sufficient |
| Reader with no memberships | Empty | A Shelf or remembered UUID cannot compensate |
| Anonymous user | Empty | Public Group does not mean anonymous access |
| Inactive user | Rejected by supported authentication boundaries | Domain queries are not an alternate login path |

Broad role authority and Group-derived visibility are separate concepts. A Reader curator does not become a Librarian. A Librarian does not need to join every Group to see its Books. Permission to manage a Group or Shelf must still be checked separately from Book visibility.

## Public Group and graceful fallback

The **Public Group** is the real stored Group designated by server settings identity. It is not selected by its current name, and it is not an anonymous or universal audience.

Public relationships are explicit:

- a Reader sees a Public-assigned Book because the Reader has Public membership and the Book has a Public assignment;
- a user may legitimately have only private memberships;
- a Book may legitimately have only private assignments;
- private relationships do not require a duplicate Public relationship.

Removal services preserve the no-orphan Group relationship invariant:

- removing a user's final membership establishes a non-curator Public membership;
- removing a Book's final assignment establishes a Public assignment;
- removing one of several relationships does not add an unnecessary Public relationship;
- Group deletion and Advanced-to-Simple consolidation apply the same fallback principle as relationships are removed;
- stale Public identity is repaired through the Public Group service rather than inferred from a display name.

This fallback is graceful continuity, not a rule that every user and Book must always be Public.

## Sources of visibility

| Source or fact | Grants Book visibility? | Rule |
|---|---:|---|
| Owner, Manager, or Librarian role | Yes | Every Book is visible |
| Explicit Public membership plus Public Book assignment | Yes | Both sides of the relationship are required for Readers |
| Matching private membership plus assignment | Yes | Works in Advanced Mode and Simple Mode |
| Several matching Groups | Yes | Union semantics; result remains distinct |
| Curator status alone | No | Curatorship is management authority for an exact Group |
| Membership alone, without Book assignment | No | The Book must be assigned to that Group |
| Book assignment alone, without membership | No for Readers | Broad roles remain a separate source |
| A personal or Group Shelf | No | Shelves organize already-authorized Books |
| Historical Marginalia | No | It preserves owned history, not current Library authority |
| Staged import metadata | No | Matching and apply recheck current authority |
| An unassigned Book | Only for broad roles | Readers have no matching assignment path |
| Stale or guessed UUID | No | Detail and attachment boundaries recheck |
| Django Admin access | Operator repair authority | Not a normal Product UI visibility projection |

### Unassigned and newly imported Books

Normal Library import assigns a successfully imported Book to the designated Public Group through the owning assignment service. Group mutation services also establish Public fallback when the final assignment is removed. These workflows make relationship-orphaned Books unusual without pretending they are impossible.

If repair, direct database manipulation, or incomplete operator work leaves a Book with no assignments:

- broad roles still see it because their visibility source is all Books;
- Readers do not see it because there is no matching Group path;
- a Shelf or Marginalia reference does not substitute for the missing assignment;
- normal repair should use the Public/assignment services rather than special-casing the visibility query.

Do not silently treat all unassigned Books as Public. That would turn a data-integrity condition into an implicit authorization grant.

## Read, projection, mutation, and download boundaries

| Boundary | Visibility behavior | Hidden-object behavior |
|---|---|---|
| Book list and routine browse | Canonical set; may use the browse cache | Hidden Books are omitted |
| Book detail | Uncached canonical check | Missing and hidden Books converge on not found |
| Broad Book search | Current uncached canonical set | Hidden Books are omitted |
| EPUB/file download | Uncached check immediately before opening storage | Missing and hidden Books converge on not found |
| Book metadata mutation | Current uncached Book resolution plus role authority | Hidden Books are not exposed; visible but unauthorized mutations are denied |
| Cover mutation | Current uncached Book resolution plus role authority | Hidden Books are not exposed |
| Author projection | Derived only from visible Books | An Author with no visible Books is omitted/not found |
| Series projection | Derived only from visible Books | A Series with no visible Books is omitted/not found |
| Catalog Tag projection | Derived only from visible Books | A Tag with no visible Books is omitted/not found |
| Supported external Reader catalog reads | Same canonical Book set | Bearer scope may be narrower, but visibility is not broader |

List and axis projections must agree with the same Book set even when their query shapes differ. Detail, mutation, attachment, and related-object paths must not fetch an unrestricted Book and then trust React to hide it.

Authenticated downloads recheck authority at download time. A stale SDK object, cached list row, old download link, or guessed UUID never authorizes access to the EPUB. The application does not expose raw storage paths as a substitute for the controlled download route.

Cover assets are the deliberate exception. Generated public cover URLs are display assets and may remain retrievable when the URL is known. That exposure does not grant access to the Book record, EPUB, Group assignments, Shelves, or Marginalia belonging to another user.

## Accepted cache policy

The canonical visibility cache exists to reduce repeated database work during normal navigation. Its configured lifetime is 120 seconds.

The accepted product policy is:

- ordinary cached Book lists, Group browse projections, and Author/Series/Tag axes may remain stale for up to 120 seconds after a rare membership, assignment, or role change;
- immediate invalidation is not promised for every possible role or relationship transition;
- service-driven membership and assignment changes may invalidate cached projections, but callers must not treat that as a universal synchronous guarantee;
- this bounded browse staleness is acceptable for the self-hosted, single-instance target environment;
- authorization-sensitive detail and mutation boundaries must use current uncached checks;
- EPUB/file download is the strictest asset boundary and remains uncached;
- client state cannot turn a cached browse result into mutation or attachment authority.

Do not redesign the cache merely to eliminate the accepted browse window. Do not expand the cache into authorization-sensitive operations.

## Shelf relationship

Shelves organize Books; they never grant Book visibility.

### Personal Shelves

- Adding a Book requires the actor's current uncached Library visibility.
- The final actor-authority and Book-eligibility checks occur inside the locked atomic insertion boundary immediately before creation.
- A Book validly added while visible may remain stored after later access loss.
- Routine Shelf lists, detail rows, counts, and previews omit unavailable personal items.
- An authorized Shelf editor may receive a bounded unavailable placeholder sufficient to remove the retained item. That placeholder must not expose hidden Book metadata or identifiers beyond the controlled item operation.
- Restoring visibility can make the retained item available again unless an operator cleanup has removed it.
- Cleanup policy and commands belong to [Operations](operations.md).

### Group Shelves

- Adding a Book requires assignment to the exact owning Group, not merely visibility through some other Group.
- The actor must still have authority over that exact Shelf when the insertion transaction reaches its mutation boundary.
- Both exact assignment and actor authority are rechecked after the Shelf and its items are locked.
- Removing a Book's assignment from a Group removes it from that Group's Shelves through the Group-assignment workflow.
- A Group Shelf does not make its Books visible to a user who lacks normal Group-derived visibility.
- Advanced Mode does not control whether existing Group Shelves are valid; see [Advanced Library Groups Mode](advanced-library-groups.md).

Positions remain contiguous after normal Shelf mutations. The race-safe eligibility check must not weaken duplicate prevention, position canonicalization, unavailable-item retention, or cleanup behavior.

## Lifecycle transition matrix

| Transition | Current visibility effect | Cached browse effect | Related behavior |
|---|---|---|---|
| Membership added | Matching assigned Books become visible | May wait for invalidation or expiry | Curatorship remains separate |
| Membership removed | Books disappear unless another matching path remains | May remain stale for up to 120 seconds | Historical Marginalia remains |
| Book assignment added | Matching members gain visibility | May wait for invalidation or expiry | Exact Group Shelf eligibility begins |
| Book assignment removed | Visibility ends unless another path remains | May remain stale for up to 120 seconds | Exact owning-Group Shelf items are removed |
| Final membership removed | Public fallback is established | Normal cache policy applies | Public membership is non-curator |
| Final Book assignment removed | Public fallback is established | Normal cache policy applies | Book does not become relationship-orphaned |
| One of several relationships removed | Remaining paths continue | Normal cache policy applies | No unnecessary Public fallback |
| Role promoted | Broad-role all-Book visibility applies | Browse may be temporarily underinclusive | Strict boundaries use current role/query state |
| Role demoted | Membership-derived union applies | Browse may be temporarily overinclusive | Detail/download/mutations remain uncached |
| Group deleted through services | Its paths disappear; final relationships fall back to Public | Normal cache policy applies | Group Shelves follow deletion/consolidation workflow |
| Advanced Mode toggled only | No visibility change | No visibility-specific effect | Presentation and custom mutation policy changes |
| User disabled | Supported authentication rejects access | Cached IDs do not authenticate the user | Existing data is not itself deleted |
| Book deleted | Book ceases to exist | Cache cannot authorize a missing object | Cascades may remove dependent data, including Marginalia |
| Access restored | Book becomes visible again | Browse may wait for invalidation or expiry | Retained Shelf items and `can_open` can recover |

## Anti-enumeration and privacy

Backend query and service boundaries own authorization. React route guards, hidden controls, and conditional rendering are presentation only.

The durable privacy rules are:

- hidden and missing Books should converge on the same not-found behavior at detail and download boundaries;
- list, search, related-object, selected-ID, Shelf, and attachment operations must not reveal hidden existence through distinguishable responses;
- foreign identifiers must not disclose another user's authority or data;
- a guessed UUID is never a capability;
- bounded Shelf placeholders and owned Marginalia projections are explicit exceptions with narrow purposes;
- Marginalia import may expose the generic `book_inaccessible` classification while returning only user-supplied staged metadata;
- error responses must not contain storage paths, Group assignments, hidden metadata, credentials, or internal exception text.

Use 403 when the object is legitimately visible or owned but the requested action is outside the actor's authority. Use anti-enumerating not-found behavior when acknowledging the object would itself disclose hidden state.

## Consistency requirements for new features

Any new feature that lists, selects, previews, mutates, or downloads Books must answer these questions explicitly:

1. Is the operation a routine browse projection or an authorization-sensitive boundary?
2. Does it use the canonical Library-visible Book set or a documented narrower intersection?
3. If it caches results, can possession of a stale result cause a mutation or asset disclosure?
4. Does detail behavior agree with list/search behavior without revealing hidden existence?
5. Are attachment and file bytes authorized again immediately before storage is opened?
6. If the feature persists a reference, what bounded behavior remains after later access loss?
7. Does a broad role, Reader curator, Public-only Reader, private-only Reader, and user with overlapping Groups receive the correct result?
8. Does Simple Mode leave the visibility result unchanged?

Tests should protect those outcomes at the query or service boundary. React tests may verify presentation, but they cannot replace backend visibility coverage. Prefer representative role/membership matrices over endpoint-by-endpoint duplication.

When a feature intentionally preserves context after access loss, define that exception narrowly. Personal Shelf placeholders and owned Marginalia projections have explicit contracts. They are not precedents for returning unrestricted Book serializers, download URLs, Group assignments, or fresh hidden metadata.

## Browser, bearer, and Admin boundaries

Browser session authentication and supported bearer catalog operations use the same canonical Library-visible Book policy. Bearer clients may have fewer allowed mutations or routes, but they do not receive a broader Book set unless a future immutable policy explicitly says otherwise.

The Product UI and SDK must consume backend-filtered data. They may suppress actions or adapt wire shapes, but they must not reconstruct Group visibility rules locally.

Django Admin is an optional operator repair surface. It may expose and mutate state outside normal Product UI projections. Admin access is not evidence that an ordinary user should see a Book, and destructive Admin operations must respect the cautions in [Operations](operations.md).

## Related authorities

- [Advanced Library Groups Mode](advanced-library-groups.md) owns Advanced/Simple presentation and custom Group mutation policy.
- [Marginalia-Linked Books](marginalia-book-visibility.md) owns historical ownership, `can_open`, import, export, and preservation behavior.
- [Permissions](permissions.md) owns general role and mutation authority.
- [Library Imports](imports.md) owns import metadata and archive safety.
- [Operations](operations.md) owns cleanup, consolidation, repair, and destructive procedures.
