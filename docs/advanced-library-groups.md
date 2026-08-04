# Advanced Library Groups Mode

> **Immutable core policy for AI coding agents.** This file is authoritative and must not be edited, regenerated, consolidated, renamed, or deleted. If an implementation, test, API, SDK, Product UI behavior, or other document disagrees with this policy, stop and adjust the implementation and its dependent boundaries to comply. Do not resolve disagreement by weakening or changing this file.

## Authority and audience

This document owns the meaning of **Advanced Mode** versus **Simple Mode**, including Product UI presentation, normal custom Group API mutation availability, Public Group behavior, retained Group state, and supported transitions. It applies to product, backend/API, SDK/Product UI, test, and operator work involving the Advanced Library Groups setting.

It does not define the canonical Library-visible Book set. That policy belongs to [Library Book Visibility](book-visibility.md). Historical Marginalia behavior belongs to [Marginalia-Linked Books](marginalia-book-visibility.md).

## Core rule

**Advanced Library Groups is a capability and presentation mode. It is not a Book visibility switch.**

Simple Mode reduces custom/private Group management and Group presentation. It preserves existing Group-derived Book visibility and normal downstream Library, Shelf, Marginalia, import, export, and supported Reader behavior.

Use the terms **Advanced Mode** and **Simple Mode**. Avoid “Groups enabled” or “Groups disabled,” because Groups, Public behavior, memberships, assignments, and Group Shelves continue to exist and matter in Simple Mode.

## Stored setting and projection

The mode is a persisted server setting. It defaults to Simple Mode unless setup or an Owner-facing server action enables Advanced Mode. Authenticated bootstrap/server information projects the setting, and the first-party SDK adapts it to the Product UI capability model.

The frontend uses that projection to decide which advanced presentation and management surfaces to expose. The value must not be used to calculate a user's Library-visible Book set or replace backend authorization.

The normal Owner-facing server action is one-way enablement. The supported transition back to Simple Mode is the consolidation workflow described below and operationally owned by [Operations](operations.md).

## Simple Mode frontend restrictions

| Product UI surface | Advanced Mode | Simple Mode |
|---|---|---|
| Primary Groups navigation | Shown | Hidden |
| Direct Group management destinations | Available subject to role | Route-gated and not presented |
| Book Edit custom Group assignments | Available to authorized catalog managers | Hidden |
| User Edit custom Group memberships | Available to authorized user managers | Hidden |
| Shelf create custom Group owner choice | Available according to role/curatorship | Hidden |
| Shelf edit custom Group assignment/owner controls | Available only where the lifecycle supports them | Hidden |
| Profile Group membership presentation | Shown | Hidden |
| Book Detail Group presentation | Shown | Hidden |
| Public Group Shelf context | Available where authorized | Remains available where authorized |

These restrictions are presentation rules. They do not erase relationships, revoke Book visibility, or make existing Group Shelves invalid.

Product UI code must use the authenticated server capability projection. It must not infer Advanced Mode from whether custom Groups happen to exist, whether the current user is a curator, or whether a Group Shelf is present.

## Simple Mode frontend behavior retained

Simple Mode continues to provide:

- Dashboard access to Group Shelves;
- the Group Shelf scope and its navigation state;
- Group Shelf list and detail routes;
- item listing, addition, removal, and ordering for editable Group Shelves;
- metadata editing and deletion of existing custom Group Shelves under normal Shelf authority;
- Public Group Shelf creation/context where the actor is otherwise authorized;
- Public Group-dependent Library behavior;
- Book visibility derived from existing private or Public Group relationships;
- normal Library browsing, Shelves, Marginalia, imports, exports, and supported Reader workflows.

Do not hide Group Shelves because Advanced Mode is off. The Dashboard Group Shelves destination is intentionally discoverable in both modes.

The creation nuance is deliberate:

- the normal Simple Mode Product UI does not offer a custom Group as the owner of a newly created Shelf;
- a custom Group creation context smuggled through stale or manually constructed navigation state must not restore that owner choice;
- Public Group Shelf creation remains available to roles that may create Public-owned Shelves;
- existing custom Group Shelves remain readable and editable by users with normal Shelf authority;
- direct backend Shelf creation follows Shelf authority and may accept a custom Group owner in retained-data states even though the Simple Mode Product UI does not offer that choice.

## Simple Mode backend restrictions

Normal custom Group reads remain available. Normal custom Group management mutations do not.

When the target is a custom/non-Public Group, Simple Mode rejects:

- creation of a custom Group;
- editing its name or description;
- deleting it;
- adding a user membership;
- updating membership or curator state;
- removing a user membership;
- adding a Book assignment;
- removing a Book assignment.

These operations use the existing bounded anti-enumerating behavior, normally not found, so the mutation surface does not become a flag-based discovery mechanism. Role checks still apply in Advanced Mode and to Public operations; enabling Advanced Mode never grants authority by itself.

The restrictions belong at the normal HTTP mutation boundary. They do not block:

- Owner-facing Server Settings behavior;
- the supported Admin consolidation workflow;
- intentional Django Admin repair operations;
- cohesive internal services used by imports, fixtures, fallback, consolidation, or repair for their owning workflow.

Do not move the Simple Mode flag into low-level membership or assignment services in a way that breaks those internal workflows.

## Simple Mode backend behavior retained

| Backend behavior | Advanced Mode | Simple Mode |
|---|---|---|
| Custom Group list/detail reads | Normal authority | Same normal authority |
| Custom Group Book browse and axes | Normal authority | Same normal authority |
| Custom Group membership reads | Normal authority | Same normal authority |
| Custom Group management mutations | Role/curator policy | Rejected regardless of otherwise sufficient role |
| Public Group reads | Active | Active |
| Public Group membership/Book operations | Existing Public and role policy | Same policy |
| Existing memberships and assignments | Effective | Effective |
| Canonical Book visibility | Relationship/role based | Identical relationship/role policy |
| Group Shelf reads and mutations | Shelf authority | Shelf authority |
| `scope=group` | Active | Active |
| Exact-Group curator Shelf authority | Active | Active |
| Marginalia/import/export | Normal domain policy | Normal domain policy |
| Supported Reader catalog behavior | Canonical visibility | Canonical visibility |
| Admin repair | Intentional exception | Intentional exception |

Custom Group reads are not management mutations. A user who can normally see a Group may read its detail, Books, axes, and membership projection in Simple Mode. Downstream domains may use those projections without treating the flag as authorization.

The flag must never filter `visible_books_for_user`, remove a private Group from the user's membership-derived union, or deny a Book solely because its only matching assignment is private.

## Group Shelves are independent

Group Shelves are Shelf-domain objects. They are not Advanced Mode management objects.

Their durable rules are:

- Owners, Managers, and Librarians retain broad Shelf authority according to the normal role policy;
- a Reader curator retains Shelf authority for the exact non-Public Group they curate;
- ordinary Readers do not gain edit authority merely by being members;
- a Group Shelf may contain only Books assigned to its exact owning Group;
- item insertion rechecks actor authority and exact assignment inside the locked atomic boundary;
- Simple Mode neither erases nor invalidates a Group Shelf;
- Group Shelf routes, scope, reads, and mutations remain active;
- a Group Shelf never broadens Book visibility.

Normal Group Shelf presentation necessarily identifies its owner. That is not the same as exposing the advanced Group management destination or placing general Group membership/assignment controls on unrelated screens.

## Public Group

The **Public Group** is a real stored Group selected by configured identity, not by its name or a display label.

Public policy is unchanged between modes:

- Public membership is explicit;
- Public Book assignment is explicit;
- Public is not anonymous, universal, or automatically added alongside every private relationship;
- removing a final membership creates a non-curator Public fallback;
- removing a final Book assignment creates a Public fallback;
- removing one of several relationships does not add unnecessary Public state;
- Public curator status is invalid;
- Public identity is Owner-managed through Server Settings, not ordinary Group metadata mutation;
- Public reads and normal Public behavior remain active in Simple Mode.

Naming a different Group “Public” does not give it Public identity.

## Existing private data in Simple Mode

Simple Mode is robust when private data already exists:

- custom Groups may remain stored;
- memberships and Book assignments remain stored and effective;
- private membership and assignment paths continue granting Library visibility;
- existing custom Group Shelves remain valid;
- Group reads and downstream projections remain available under normal authority;
- custom Group management presentation is hidden;
- normal custom Group mutation APIs are blocked.

This tolerance is necessary both for supported runtime behavior and for diagnosing retained state. It is not permission to treat the flag as a destructive migration switch.

## Supported transition to Simple Mode

The supported Advanced-to-Simple transition is the operator consolidation workflow.

At a high level, consolidation:

1. builds and validates a deterministic plan against the current database state;
2. moves custom Group Shelves to the designated Public Group while preserving Shelf rows and item ordering under the current naming/collision contract;
3. removes custom Book assignments and memberships through their owning services;
4. establishes Public fallback only when the last Group relationship disappears;
5. repairs invalid Public curator state;
6. deletes emptied custom Groups through the Group service;
7. disables Advanced Mode atomically;
8. invalidates relevant caches after commit.

Failure rolls the transition back. Operational execution, preview/fingerprint requirements, destructive cautions, and recovery belong to [Operations](operations.md), not this policy file.

## Unsupported raw database toggle

**Direct database manipulation of the Advanced Mode flag is unsupported. Operators are expected to use Server Settings and the consolidation/Admin tools.**

The application aims not to fail catastrophically if a flag is changed without consolidation, but it does not promise a clean or normalized product state. Retained custom Groups, memberships, assignments, visibility paths, and Group Shelves may coexist with hidden management controls and blocked custom mutations. The application will not automatically repair, erase, consolidate, or reinterpret that state.

Re-enabling may expose retained management surfaces again. Unusual combinations caused by manual database edits are not product-supported states and receive no automatic repair guarantee.

## Re-enabling

Enabling Advanced Mode changes capability presentation and normal custom Group mutation availability. It does not synthesize data.

- After a raw flag-only disable, retained Groups and relationships may become manageable again because they were never removed.
- After supported consolidation, deleted custom Groups, memberships, assignments, and former ownership relationships are not reconstructed.
- Re-enabling does not reverse consolidation or restore a historical snapshot.

## Role and curator matrix

| Actor | Advanced Mode presentation | Simple Mode presentation | Custom Group reads | Custom Group mutations in Simple Mode | Group Shelf authority in either mode |
|---|---|---|---|---|---|
| Owner | Full advanced surfaces | Advanced surfaces hidden | All Groups | Rejected through normal APIs | Broad |
| Manager | Relevant advanced surfaces | Advanced surfaces hidden | All Groups | Rejected through normal APIs | Broad |
| Librarian | Book/Group catalog surfaces as authorized | Advanced surfaces hidden | All Groups | Rejected through normal APIs | Broad |
| Reader curator | Exact-Group management surfaces | Advanced surfaces hidden | Membership-visible Groups | Rejected through normal Group APIs | Exact curated non-Public Group |
| Ordinary Reader | Group reads/navigation when enabled | Group presentation hidden | Membership-visible Groups | No management authority in either mode | Own Shelves; Group Shelves read as allowed |

Advanced Mode never substitutes for role or curator checks. Simple Mode never removes exact-Group curator Shelf authority.

Public curator state is invalid for every role. Broad roles manage Public Shelf behavior through their broad authority, not a curator flag.

## External Reader and Admin boundaries

Supported bearer Reader catalog operations use the canonical Library-visible Book policy in both modes. Custom Group reads follow normal Group visibility. Bearer mutation capabilities remain separately constrained and are never expanded simply because Advanced Mode is enabled.

Django Admin is an optional, trusted repair boundary. It may inspect or repair state hidden from normal Product UI management surfaces. Admin behavior is not the Product UI contract, and destructive Admin changes remain subject to [Operations](operations.md).

## Development fixtures

The development seed command creates a deterministic world appropriate to the current mode.

In a clean Simple Mode fixture it creates or ensures:

- Public memberships needed by the demo users;
- Public Book assignments;
- Public Group Shelves;
- personal Shelves;
- Books usable through normal Public behavior;
- no new advanced private membership/visibility scenario.

In Advanced Mode it additionally creates:

- a deliberate private membership matrix;
- exclusive and overlapping user scenarios;
- exclusive, shared, and metadata-coherent Group Book sets;
- curator assignments distributed across Reader, Librarian, and Manager roles where counts permit;
- Shelves for each demo private Group.

The command is non-destructive. Simple Mode does not authorize it to erase arbitrary pre-existing private Groups, relationships, assignments, or Shelves. Repeated runs converge around seed-managed identities rather than normalizing unrelated operator data.

## Transition comparison

| Situation | Data retained | Visibility | Management presentation | Mutation behavior | Re-enable result |
|---|---|---|---|---|---|
| Advanced Mode | Yes | Canonical policy | Shown by role | Normal role/curator policy | Already enabled |
| Simple Mode from initial setup | Public/simple fixture state | Canonical policy | Custom management hidden | Custom Group mutations blocked | Enables future advanced management |
| Supported consolidation | Custom state moved/removed by plan | Public fallback where required | Custom management hidden | Custom Group mutations blocked | Deleted custom data is not restored |
| Unsupported raw flag disable | Custom state may remain | Retained relationships still apply | Custom management hidden | Custom Group mutations blocked; reads/Shelves continue | Retained state may reappear |

## Related authorities

- [Library Book Visibility](book-visibility.md) owns the canonical visible Book set and cache policy.
- [Marginalia-Linked Books](marginalia-book-visibility.md) owns preservation and openability after Library access changes.
- [Permissions](permissions.md) owns general roles and mutation authority.
- [Operations](operations.md) owns consolidation, repair, and destructive procedures.
- [Frontend](frontend.md) owns SDK/orchestrator/presentation layering.
- [Development](development.md) owns commands and fixture operation.

