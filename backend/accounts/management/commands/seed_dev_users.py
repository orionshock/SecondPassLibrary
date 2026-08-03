from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import random
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from accounts.models import UserProfile
from accounts.bootstrap import has_active_owner
from accounts.services import get_or_create_profile
from core import server_settings
from library.groups.book_assignments import add_book_to_group
from library.groups.memberships import add_user_to_group, remove_user_from_group
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from library.groups.public_group import get_public_group
from library.queries import visible_books_for_user
from shelves.models import Shelf, ShelfItem
from shelves.item_services import add_book_to_shelf
from shelves.services import create_shelf, update_shelf


User = get_user_model()
DEV_PASSWORD = "changeme123"
DEFAULT_RANDOM_SEED = "second-pass-library"


@dataclass(frozen=True)
class DemoUserSpec:
    username: str
    first_name: str
    last_name: str
    role: str

    @property
    def email(self) -> str:
        return f"{self.username}@example.test"


@dataclass(frozen=True)
class DemoGroupSpec:
    name: str
    description: str


@dataclass
class SeedCounts:
    users_created: int = 0
    users_existing: int = 0
    groups_created: int = 0
    groups_existing: int = 0
    memberships_created: int = 0
    memberships_existing: int = 0
    shelves_created: int = 0
    shelves_existing: int = 0
    shelf_items_added: int = 0
    book_group_assignments_added: int = 0


@dataclass(frozen=True)
class CuratorAssignment:
    group_name: str
    username: str
    role: str


@dataclass
class MembershipScenario:
    mode: str
    exclusive_group: LibraryGroup | None = None
    exclusive_users: list[str] = field(default_factory=list)
    overlapping_user: str | None = None
    curators: list[CuratorAssignment] = field(default_factory=list)
    shortfalls: list[str] = field(default_factory=list)


@dataclass
class BookScenario:
    shelf_books: dict[object, list[Book]] = field(default_factory=dict)
    exclusive_books: list[Book] = field(default_factory=list)
    shared_book_count: int = 0
    metadata_group_count: int = 0
    fallback_group_count: int = 0


DEMO_USERS = [
    DemoUserSpec("lorem", "Lorem", "Ipsum", UserProfile.ROLE_READER),
    DemoUserSpec("ipsum", "Ipsum", "Dolor", UserProfile.ROLE_READER),
    DemoUserSpec("dolor", "Dolor", "Sit", UserProfile.ROLE_READER),
    DemoUserSpec("sit", "Sit", "Amet", UserProfile.ROLE_READER),
    DemoUserSpec("amet", "Amet", "Consectetur", UserProfile.ROLE_READER),
    DemoUserSpec(
        "consectetur",
        "Consectetur",
        "Adipiscing",
        UserProfile.ROLE_MANAGER,
    ),
    DemoUserSpec("adipiscing", "Adipiscing", "Elit", UserProfile.ROLE_MANAGER),
    DemoUserSpec("elit", "Elit", "Sed", UserProfile.ROLE_LIBRARIAN),
    DemoUserSpec("sed", "Sed", "Eiusmod", UserProfile.ROLE_LIBRARIAN),
    DemoUserSpec("eiusmod", "Eiusmod", "Tempor", UserProfile.ROLE_LIBRARIAN),
    DemoUserSpec("tempor", "Tempor", "Incididunt", UserProfile.ROLE_READER),
    DemoUserSpec("incididunt", "Incididunt", "Labore", UserProfile.ROLE_READER),
    DemoUserSpec("labore", "Labore", "Dolore", UserProfile.ROLE_READER),
    DemoUserSpec("dolore", "Dolore", "Magna", UserProfile.ROLE_READER),
    DemoUserSpec("magna", "Magna", "Aliqua", UserProfile.ROLE_READER),
    DemoUserSpec("aliqua", "Aliqua", "Enim", UserProfile.ROLE_READER),
    DemoUserSpec("enim", "Enim", "Minim", UserProfile.ROLE_READER),
    DemoUserSpec("minim", "Minim", "Veniam", UserProfile.ROLE_READER),
    DemoUserSpec("veniam", "Veniam", "Quis", UserProfile.ROLE_READER),
    DemoUserSpec("nostrud", "Nostrud", "Exercitation", UserProfile.ROLE_READER),
]

DEMO_GROUPS = [
    DemoGroupSpec("Fantasy Club", "Epic quests, folklore, and imagined worlds."),
    DemoGroupSpec("Mystery Annex", "Crime, suspense, puzzles, and investigations."),
    DemoGroupSpec("Kids Books", "Stories and collections for younger readers."),
    DemoGroupSpec("Sci-Fi Stack", "Science fiction from first contact to far futures."),
    DemoGroupSpec("History Corner", "History, biography, and primary-source reading."),
]

GROUP_SHELF_NAMES = ("Staff Picks", "Current Favorites")
PUBLIC_SHELVES = (
    ("Welcome Shelf", "A librarian-managed starting point for the Common Room."),
    ("Community Favorites", "Popular books shared across the public library space."),
)
PERSONAL_SHELF_NAMES = ("Reading Queue", "Favorites")


def _expanded_user_specs(count: int) -> list[DemoUserSpec]:
    specs = list(DEMO_USERS[:count])
    for index in range(len(specs), count):
        base = DEMO_USERS[index % len(DEMO_USERS)]
        suffix = index + 1
        specs.append(
            DemoUserSpec(
                username=f"{base.username}{suffix}",
                first_name=base.first_name,
                last_name=f"{base.last_name} {suffix}",
                role=base.role,
            )
        )
    return specs


def _expanded_group_specs(count: int) -> list[DemoGroupSpec]:
    specs = list(DEMO_GROUPS[:count])
    for index in range(len(specs), count):
        suffix = index + 1
        specs.append(
            DemoGroupSpec(
                name=f"Reading Room {suffix}",
                description=f"A separate demo library room for collection {suffix}.",
            )
        )
    return specs


def _stable_random(seed: str, key: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _stable_order(seed: str, key: str, values: list[Any]) -> list[Any]:
    def rank(value: Any) -> bytes:
        if isinstance(value, tuple) and value:
            identity = str(value[0])
        else:
            identity = str(
                getattr(value, "pk", None)
                or getattr(value, "username", None)
                or value
            )
        return hashlib.sha256(f"{seed}:{key}:{identity}".encode()).digest()

    return sorted(values, key=rank)


def _get_or_create_shelf(
    *,
    actor: Any,
    name: str,
    description: str,
    owner_type: str,
    owner_user: Any | None = None,
    owner_group: LibraryGroup | None = None,
    visibility: str = Shelf.VISIBILITY_PRIVATE,
) -> tuple[Shelf, bool]:
    existing = (
        Shelf.objects.filter(
            name=name,
            description=description,
            owner_type=owner_type,
            owner_user=owner_user,
            owner_group=owner_group,
        )
        .order_by("created_at", "id")
        .first()
    )
    if existing is not None:
        return existing, False
    return (
        create_shelf(
            actor,
            name=name,
            description=description,
            owner_type=owner_type,
            owner_user=owner_user,
            owner_group=owner_group,
            visibility=visibility,
        ),
        True,
    )


class Command(BaseCommand):
    help = "Create a non-destructive development/demo library world (DEV ONLY)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running even when DEBUG is False (DANGEROUS).",
        )
        parser.add_argument(
            "--seed",
            default=DEFAULT_RANDOM_SEED,
            help="Deterministic seed used when selecting books for shelves.",
        )
        parser.add_argument(
            "--users",
            type=int,
            default=20,
            help="Number of demo users to ensure (default: 20).",
        )
        parser.add_argument(
            "--groups",
            type=int,
            default=5,
            help="Number of non-public demo groups to ensure (default: 5).",
        )
        parser.add_argument(
            "--skip-shelves",
            action="store_true",
            help="Create users, groups, and memberships without demo shelves.",
        )

    def handle(self, *args, **options):
        force = bool(options.get("force"))
        user_count = int(options.get("users", 20))
        group_count = int(options.get("groups", 5))
        seed = str(options.get("seed") or DEFAULT_RANDOM_SEED)
        skip_shelves = bool(options.get("skip_shelves"))

        if not getattr(settings, "DEBUG", False) and not force:
            raise CommandError(
                "Refusing to run because DEBUG is False. "
                "Use --force only for local development."
            )
        if user_count < 1:
            raise CommandError("--users must be at least 1.")
        if group_count < 1:
            raise CommandError("--groups must be at least 1.")
        if not has_active_owner():
            raise CommandError(
                "First-run setup is incomplete. Complete setup before running seed_dev_users."
            )

        self.stdout.write(
            self.style.WARNING(
                "WARNING: development/demo command only. Newly created accounts "
                f"use the predictable password {DEV_PASSWORD}."
            )
        )
        self.stdout.write("Applying pending database migrations...")
        call_command(
            "migrate",
            interactive=False,
            verbosity=int(options.get("verbosity", 1)),
        )

        counts = SeedCounts()
        public = get_public_group()
        owner = self._get_owner()
        advanced_groups_enabled = server_settings.advanced_library_groups_enabled()
        self.stdout.write(f"Public group: {public.name} ({public.id})")
        self.stdout.write(
            "Advanced library groups: "
            + ("enabled; adding demo rooms." if advanced_groups_enabled else "disabled; simple Public demo only.")
        )

        user_specs = _expanded_user_specs(user_count)
        users, managed_usernames = self._ensure_demo_users(user_specs, counts)
        self._ensure_simple_memberships(users=users, public=public, counts=counts)
        groups: list[LibraryGroup] = []
        membership_scenario = MembershipScenario(mode="simple")
        if advanced_groups_enabled:
            groups = self._ensure_groups(_expanded_group_specs(group_count), counts)
            membership_scenario = self._ensure_advanced_memberships(
                owner=owner,
                users=users,
                managed_usernames=managed_usernames,
                groups=groups,
                public=public,
                seed=seed,
                counts=counts,
            )

        books = list(
            Book.objects.order_by("title", "created_at", "id").prefetch_related(
                "book_catalog_tags__catalog_tag",
                "book_authors__author",
                "book_series__series",
            )
        )
        if advanced_groups_enabled:
            book_scenario = self._ensure_advanced_book_assignments(
                owner=owner,
                books=books,
                groups=groups,
                public=public,
                membership_scenario=membership_scenario,
                seed=seed,
                counts=counts,
            )
        else:
            book_scenario = self._ensure_simple_book_assignments(
                owner=owner,
                books=books,
                public=public,
                counts=counts,
            )

        if skip_shelves:
            self.stdout.write("Shelves: skipped by --skip-shelves.")
        else:
            shelves = self._ensure_shelves(
                owner=owner,
                users=users,
                groups=groups,
                public=public,
                seed=seed,
                counts=counts,
            )
            if books:
                self._populate_shelves(
                    owner=owner,
                    shelves=shelves,
                    book_scenario=book_scenario,
                    seed=seed,
                    counts=counts,
                    shortfalls=membership_scenario.shortfalls,
                )
            else:
                self.stdout.write("No books found; shelf item population skipped.")

        self.stdout.write("")
        self.stdout.write("Demo fixture summary:")
        self.stdout.write(f"Owner: existing active superuser {owner.username}")
        self.stdout.write(
            f"Users: {counts.users_created} created, "
            f"{counts.users_existing} existing/skipped"
        )
        self.stdout.write(
            f"Groups: {counts.groups_created} created, "
            f"{counts.groups_existing} existing/skipped"
        )
        self.stdout.write(
            f"Memberships: {counts.memberships_created} created, "
            f"{counts.memberships_existing} existing/skipped"
        )
        self.stdout.write(f"Mode: {membership_scenario.mode}")
        self.stdout.write(
            "Exclusive Group: "
            + (
                membership_scenario.exclusive_group.name
                if membership_scenario.exclusive_group is not None
                else "not applicable"
            )
        )
        self.stdout.write(
            "Exclusive users: "
            + (", ".join(membership_scenario.exclusive_users) or "none")
        )
        self.stdout.write(
            f"Overlapping user: {membership_scenario.overlapping_user or 'none'}"
        )
        self.stdout.write(
            "Curators: "
            + (
                ", ".join(
                    f"{item.group_name}={item.username} ({item.role})"
                    for item in membership_scenario.curators
                )
                or "none"
            )
        )
        self.stdout.write(f"Exclusive Books: {len(book_scenario.exclusive_books)}")
        self.stdout.write(f"Shared Books: {book_scenario.shared_book_count}")
        self.stdout.write(
            "Book selection: "
            f"{book_scenario.metadata_group_count} metadata pools, "
            f"{book_scenario.fallback_group_count} deterministic fallbacks"
        )
        self.stdout.write(f"Book group assignments added: {counts.book_group_assignments_added}")
        self.stdout.write(
            f"Shelves: {counts.shelves_created} created, "
            f"{counts.shelves_existing} existing/skipped"
        )
        self.stdout.write(f"Shelf items added: {counts.shelf_items_added}")
        if not books:
            self.stdout.write("Book population: skipped because no books exist.")
        elif not skip_shelves:
            self.stdout.write(f"Book population seed: {seed}")
        if membership_scenario.shortfalls:
            self.stdout.write("Scenario shortfalls:")
            for message in membership_scenario.shortfalls:
                self.stdout.write(self.style.WARNING(f"- {message}"))
        else:
            self.stdout.write("Scenario shortfalls: none")
        self.stdout.write(
            self.style.WARNING(
                f"Dev accounts use password {DEV_PASSWORD}. "
                "Do not use this command outside local development/demo environments."
            )
        )

    def _get_owner(self) -> Any:
        existing = (
            User.objects.filter(is_active=True, is_superuser=True)
            .order_by("date_joined", "pk")
            .first()
        )
        if existing is None:
            raise CommandError(
                "First-run setup is incomplete. Complete setup before running seed_dev_users."
            )
        return existing

    def _ensure_demo_users(
        self,
        specs: list[DemoUserSpec],
        counts: SeedCounts,
    ) -> tuple[dict[str, Any], set[str]]:
        users: dict[str, Any] = {}
        managed_usernames: set[str] = set()
        for spec in specs:
            user, created = User.objects.get_or_create(
                username=spec.username,
                defaults={
                    "first_name": spec.first_name,
                    "last_name": spec.last_name,
                    "email": spec.email,
                    "is_active": True,
                },
            )
            if created:
                user.set_password(DEV_PASSWORD)
                user.save(update_fields=["password"])
                profile = get_or_create_profile(user=user)
                profile.role = spec.role
                profile.must_change_password = False
                profile.save(
                    update_fields=["role", "must_change_password", "updated_at"]
                )
                counts.users_created += 1
                managed_usernames.add(spec.username)
            else:
                counts.users_existing += 1
                if self._matches_demo_identity(user=user, spec=spec):
                    managed_usernames.add(spec.username)
            users[spec.username] = user
        return users, managed_usernames

    @staticmethod
    def _matches_demo_identity(*, user: Any, spec: DemoUserSpec) -> bool:
        return (
            user.first_name == spec.first_name
            and user.last_name == spec.last_name
            and user.email == spec.email
        )

    def _ensure_groups(
        self,
        specs: list[DemoGroupSpec],
        counts: SeedCounts,
    ) -> list[LibraryGroup]:
        groups: list[LibraryGroup] = []
        for spec in specs:
            group = (
                LibraryGroup.objects.filter(
                    name=spec.name,
                    description=spec.description,
                )
                .order_by("created_at", "id")
                .first()
            )
            created = group is None
            if group is None:
                group = LibraryGroup.objects.create(
                    name=spec.name,
                    description=spec.description,
                )
            if created:
                counts.groups_created += 1
            else:
                counts.groups_existing += 1
            groups.append(group)
        return groups

    def _ensure_simple_memberships(
        self,
        *,
        users: dict[str, Any],
        public: LibraryGroup,
        counts: SeedCounts,
    ) -> None:
        for user in users.values():
            membership, created = LibraryGroupMembership.objects.get_or_create(
                user=user,
                group=public,
                defaults={"is_curator": False},
            )
            if membership.is_curator:
                membership.is_curator = False
                membership.full_clean()
                membership.save(update_fields=["is_curator", "updated_at"])
            if created:
                counts.memberships_created += 1
            else:
                counts.memberships_existing += 1

    def _ensure_advanced_memberships(
        self,
        *,
        owner: Any,
        users: dict[str, Any],
        managed_usernames: set[str],
        groups: list[LibraryGroup],
        public: LibraryGroup,
        seed: str,
        counts: SeedCounts,
    ) -> MembershipScenario:
        scenario = MembershipScenario(mode="advanced")
        ordered_groups = _stable_order(seed, "group-scenarios", groups)
        exclusive_group = ordered_groups[0]
        other_groups = ordered_groups[1:]
        scenario.exclusive_group = exclusive_group

        roles = {
            username: get_or_create_profile(user=user).role
            for username, user in users.items()
        }
        safe_exclusive = []
        allowed_group_ids = {public.pk, exclusive_group.pk}
        for username in managed_usernames:
            user = users[username]
            existing_group_ids = set(
                LibraryGroupMembership.objects.filter(user=user).values_list(
                    "group_id",
                    flat=True,
                )
            )
            if existing_group_ids.issubset(allowed_group_ids):
                safe_exclusive.append(user)

        ordered_safe = _stable_order(seed, "exclusive-users", safe_exclusive)
        reader_safe = [
            user
            for user in ordered_safe
            if roles[user.username] == UserProfile.ROLE_READER
        ]
        exclusive_users: list[Any] = []
        if reader_safe:
            exclusive_users.append(reader_safe[0])
        exclusive_users.extend(
            user for user in ordered_safe if user not in exclusive_users
        )
        exclusive_users = exclusive_users[:2]

        for user in exclusive_users:
            self._ensure_membership(
                user=user,
                group=exclusive_group,
                counts=counts,
            )
            if LibraryGroupMembership.objects.filter(user=user, group=public).exists():
                remove_user_from_group(user=user, group=public, actor=owner)
        scenario.exclusive_users = [user.username for user in exclusive_users]
        if len(exclusive_users) < 2:
            scenario.shortfalls.append(
                "Exclusive Group needs two seed-managed users without unrelated "
                f"memberships; created {len(exclusive_users)}."
            )

        reserved = {user.username for user in exclusive_users}
        available = _stable_order(
            seed,
            "membership-scenarios",
            [user for user in users.values() if user.username not in reserved],
        )

        overlapping_user = available.pop(0) if available and other_groups else None
        if overlapping_user is not None:
            self._ensure_membership(
                user=overlapping_user,
                group=exclusive_group,
                counts=counts,
            )
            self._ensure_membership(
                user=overlapping_user,
                group=other_groups[0],
                counts=counts,
            )
            scenario.overlapping_user = overlapping_user.username
            reserved.add(overlapping_user.username)
        else:
            scenario.shortfalls.append(
                "Overlapping-user scenario requires another demo user and at "
                "least two non-Public Groups."
            )

        public_only = next(
            (
                user
                for user in available
                if not LibraryGroupMembership.objects.filter(user=user)
                .exclude(group=public)
                .exists()
            ),
            None,
        )
        if public_only is not None:
            available.remove(public_only)
            reserved.add(public_only.username)
        else:
            scenario.shortfalls.append(
                "No demo user remained for the Public-only scenario."
            )

        public_private_group = other_groups[0] if other_groups else None
        public_private = next(
            (
                user
                for user in available
                if public_private_group is not None
                and not LibraryGroupMembership.objects.filter(user=user)
                .exclude(group__in=[public, public_private_group])
                .exists()
            ),
            None,
        )
        if public_private is not None:
            available.remove(public_private)
            self._ensure_membership(
                user=public_private,
                group=public_private_group,
                counts=counts,
            )
            reserved.add(public_private.username)
        else:
            scenario.shortfalls.append(
                "No demo user remained for the Public-plus-private-Group scenario."
            )

        multi_private = available.pop(0) if available and len(other_groups) >= 2 else None
        if multi_private is not None:
            for group in other_groups[:2]:
                self._ensure_membership(
                    user=multi_private,
                    group=group,
                    counts=counts,
                )
            reserved.add(multi_private.username)
        elif len(other_groups) < 2:
            scenario.shortfalls.append(
                "Multiple-private-Group scenario requires at least three "
                "non-Public Groups."
            )
        else:
            scenario.shortfalls.append(
                "No demo user remained for the multiple-private-Group scenario."
            )

        distribution_groups = other_groups or [exclusive_group]
        for index, user in enumerate(available):
            self._ensure_membership(
                user=user,
                group=distribution_groups[index % len(distribution_groups)],
                counts=counts,
            )

        self._ensure_group_curators(
            owner=owner,
            users=users,
            managed_usernames=managed_usernames,
            groups=ordered_groups,
            exclusive_users=exclusive_users,
            scenario_protected_usernames={
                user.username
                for user in (public_only, public_private)
                if user is not None
            },
            roles=roles,
            seed=seed,
            counts=counts,
            scenario=scenario,
        )
        return scenario

    @staticmethod
    def _ensure_membership(
        *,
        user: Any,
        group: LibraryGroup,
        counts: SeedCounts,
        is_curator: bool = False,
    ) -> LibraryGroupMembership:
        existing = LibraryGroupMembership.objects.filter(
            user=user,
            group=group,
        ).first()
        membership = add_user_to_group(
            user=user,
            group=group,
            is_curator=is_curator,
        )
        if existing is None:
            counts.memberships_created += 1
        else:
            counts.memberships_existing += 1
        return membership

    def _ensure_group_curators(
        self,
        *,
        owner: Any,
        users: dict[str, Any],
        managed_usernames: set[str],
        groups: list[LibraryGroup],
        exclusive_users: list[Any],
        scenario_protected_usernames: set[str],
        roles: dict[str, str],
        seed: str,
        counts: SeedCounts,
        scenario: MembershipScenario,
    ) -> None:
        protected_usernames = {
            user.username for user in exclusive_users
        } | scenario_protected_usernames
        preferred_roles = [
            UserProfile.ROLE_READER,
            UserProfile.ROLE_LIBRARIAN,
            UserProfile.ROLE_MANAGER,
        ]
        for index, group in enumerate(groups):
            target_role = preferred_roles[index % len(preferred_roles)]
            if index == 0 and exclusive_users:
                candidates = [
                    user
                    for user in exclusive_users
                    if roles[user.username] == target_role
                ] or exclusive_users
            else:
                candidates = [
                    user
                    for username, user in users.items()
                    if username in managed_usernames
                    and username not in protected_usernames
                    and roles[username] == target_role
                ]
                candidates = _stable_order(
                    seed,
                    f"curator:{group.pk}:{target_role}",
                    candidates,
                )
                if not candidates:
                    candidates = _stable_order(
                        seed,
                        f"curator-fallback:{group.pk}",
                        [
                            user
                            for username, user in users.items()
                            if username not in protected_usernames
                        ],
                    )

            candidate = candidates[0] if candidates else None
            if candidate is None:
                existing = (
                    LibraryGroupMembership.objects.filter(
                        group=group,
                        is_curator=True,
                    )
                    .select_related("user__profile")
                    .order_by("user__username")
                    .first()
                )
                if existing is not None:
                    candidate = existing.user
                else:
                    candidate = owner
                    scenario.shortfalls.append(
                        f"Used the Owner as last-resort curator for {group.name}."
                    )

            self._ensure_membership(
                user=candidate,
                group=group,
                is_curator=True,
                counts=counts,
            )
            actual_role = (
                "owner"
                if candidate.is_superuser
                else get_or_create_profile(user=candidate).role
            )
            scenario.curators.append(
                CuratorAssignment(
                    group_name=group.name,
                    username=candidate.username,
                    role=actual_role,
                )
            )
            if actual_role != target_role and not candidate.is_superuser:
                scenario.shortfalls.append(
                    f"{group.name} curator role fell back from {target_role} "
                    f"to {actual_role}."
                )

    def _ensure_simple_book_assignments(
        self,
        *,
        owner: Any,
        books: list[Book],
        public: LibraryGroup,
        counts: SeedCounts,
    ) -> BookScenario:
        for book in books:
            self._ensure_book_assignment(
                owner=owner,
                book=book,
                group=public,
                counts=counts,
            )
        return BookScenario(shelf_books={public.pk: books})

    def _ensure_advanced_book_assignments(
        self,
        *,
        owner: Any,
        books: list[Book],
        groups: list[LibraryGroup],
        public: LibraryGroup,
        membership_scenario: MembershipScenario,
        seed: str,
        counts: SeedCounts,
    ) -> BookScenario:
        scenario = BookScenario()
        exclusive_group = membership_scenario.exclusive_group
        if exclusive_group is None:
            membership_scenario.shortfalls.append(
                "No exclusive Group was available for Book assignment planning."
            )
            return scenario

        metadata_pools = self._book_metadata_pools(books)
        safe_exclusive = []
        for book in books:
            assigned_group_ids = set(
                BookGroupAssignment.objects.filter(book=book).values_list(
                    "group_id",
                    flat=True,
                )
            )
            if not assigned_group_ids or assigned_group_ids == {exclusive_group.pk}:
                safe_exclusive.append(book)

        exclusive_books, used_metadata = self._select_books(
            seed=seed,
            key=f"exclusive:{exclusive_group.pk}",
            candidates=safe_exclusive,
            metadata_pools=metadata_pools,
            target_count=6,
        )
        self._record_book_strategy(scenario, used_metadata)
        for book in exclusive_books:
            self._ensure_book_assignment(
                owner=owner,
                book=book,
                group=exclusive_group,
                counts=counts,
            )
        scenario.exclusive_books = exclusive_books
        scenario.shelf_books[exclusive_group.pk] = exclusive_books
        if not exclusive_books:
            membership_scenario.shortfalls.append(
                "No unassigned or already-exclusive Books were safe to assign "
                f"exclusively to {exclusive_group.name}; existing assignments "
                "were preserved."
            )

        exclusive_book_ids = {book.pk for book in exclusive_books}
        nonexclusive_candidates = [
            book for book in books if book.pk not in exclusive_book_ids
        ]
        other_groups = [group for group in groups if group.pk != exclusive_group.pk]
        unique_anchors: dict[object, Book] = {}
        reserved_anchor_ids: set[object] = set()
        for group in other_groups:
            safe_anchors = []
            for book in nonexclusive_candidates:
                if book.pk in reserved_anchor_ids:
                    continue
                assigned_group_ids = set(
                    BookGroupAssignment.objects.filter(book=book).values_list(
                        "group_id",
                        flat=True,
                    )
                )
                if not assigned_group_ids or assigned_group_ids == {group.pk}:
                    safe_anchors.append(book)
            ordered_anchors = _stable_order(
                seed,
                f"unique-book:{group.pk}",
                safe_anchors,
            )
            if ordered_anchors:
                unique_anchors[group.pk] = ordered_anchors[0]
                reserved_anchor_ids.add(ordered_anchors[0].pk)
            else:
                membership_scenario.shortfalls.append(
                    f"No Book was safe to reserve uniquely for {group.name}."
                )

        selected_by_group: dict[object, list[Book]] = {}
        for group in other_groups:
            anchor = unique_anchors.get(group.pk)
            group_candidates = [
                book
                for book in nonexclusive_candidates
                if book.pk not in reserved_anchor_ids or book == anchor
            ]
            selected, used_metadata = self._select_books(
                seed=seed,
                key=f"group:{group.pk}",
                candidates=group_candidates,
                metadata_pools=metadata_pools,
                target_count=6,
            )
            if anchor is not None and anchor not in selected:
                selected = [anchor, *selected[:5]]
            self._record_book_strategy(scenario, used_metadata)
            for book in selected:
                self._ensure_book_assignment(
                    owner=owner,
                    book=book,
                    group=group,
                    counts=counts,
                )
            selected_by_group[group.pk] = selected
            scenario.shelf_books[group.pk] = selected
            if not selected:
                membership_scenario.shortfalls.append(
                    f"No non-exclusive Books were available for {group.name}."
                )

        shared_candidates_by_id = {
            book.pk: book
            for selected in selected_by_group.values()
            for book in selected
            if book.pk not in reserved_anchor_ids
        }
        shared_candidates = _stable_order(
            seed,
            "shared-books",
            list(shared_candidates_by_id.values()),
        )
        shared_candidate = shared_candidates[0] if shared_candidates else None
        if shared_candidate is not None and len(other_groups) >= 2:
            for group in other_groups[:2]:
                self._ensure_book_assignment(
                    owner=owner,
                    book=shared_candidate,
                    group=group,
                    counts=counts,
                )
                if shared_candidate not in scenario.shelf_books[group.pk]:
                    scenario.shelf_books[group.pk].append(shared_candidate)
        for book in shared_candidates[:4]:
            self._ensure_book_assignment(
                owner=owner,
                book=book,
                group=public,
                counts=counts,
            )
        if shared_candidate is None:
            membership_scenario.shortfalls.append(
                "Shared-Book scenario requires a non-exclusive Book and at least "
                "one non-exclusive demo Group."
            )

        touched_book_ids = {
            book.pk
            for selected in selected_by_group.values()
            for book in selected
        }
        scenario.shared_book_count = (
            Book.objects.filter(pk__in=touched_book_ids)
            .annotate(group_count=Count("group_assignments__group", distinct=True))
            .filter(group_count__gte=2)
            .count()
        )
        scenario.shelf_books[public.pk] = list(
            Book.objects.filter(group_assignments__group=public)
            .distinct()
            .order_by("title", "created_at", "id")
        )
        return scenario

    @staticmethod
    def _ensure_book_assignment(
        *,
        owner: Any,
        book: Book,
        group: LibraryGroup,
        counts: SeedCounts,
    ) -> None:
        exists = BookGroupAssignment.objects.filter(book=book, group=group).exists()
        add_book_to_group(actor=owner, book=book, group=group)
        if not exists:
            counts.book_group_assignments_added += 1

    @staticmethod
    def _record_book_strategy(scenario: BookScenario, used_metadata: bool) -> None:
        if used_metadata:
            scenario.metadata_group_count += 1
        else:
            scenario.fallback_group_count += 1

    @staticmethod
    def _book_metadata_pools(books: list[Book]) -> dict[str, list[Book]]:
        pools: dict[str, list[Book]] = {}
        for book in books:
            for relation in book.book_catalog_tags.all():
                key = f"tag:{relation.catalog_tag.name.casefold()}"
                pools.setdefault(key, []).append(book)
            for relation in book.book_authors.all():
                key = f"author:{relation.author.name.casefold()}"
                pools.setdefault(key, []).append(book)
            try:
                series_name = book.book_series.series.name
            except ObjectDoesNotExist:
                pass
            else:
                pools.setdefault(f"series:{series_name.casefold()}", []).append(book)
        return pools

    @staticmethod
    def _select_books(
        *,
        seed: str,
        key: str,
        candidates: list[Book],
        metadata_pools: dict[str, list[Book]],
        target_count: int,
    ) -> tuple[list[Book], bool]:
        if not candidates:
            return [], False

        candidate_ids = {book.pk for book in candidates}
        eligible_pools = []
        for pool_key, pool_books in sorted(metadata_pools.items()):
            eligible = [book for book in pool_books if book.pk in candidate_ids]
            if len(eligible) >= 2:
                eligible_pools.append((pool_key, eligible))

        selected: list[Book] = []
        used_metadata = bool(eligible_pools)
        if eligible_pools:
            pool_key, pool_books = _stable_order(
                seed,
                f"metadata-pool:{key}",
                eligible_pools,
            )[0]
            selected.extend(
                _stable_order(seed, f"metadata-books:{key}:{pool_key}", pool_books)[
                    :target_count
                ]
            )

        selected_ids = {book.pk for book in selected}
        remaining = [book for book in candidates if book.pk not in selected_ids]
        selected.extend(
            _stable_order(seed, f"book-fallback:{key}", remaining)[
                : max(0, target_count - len(selected))
            ]
        )
        return selected, used_metadata

    def _ensure_shelves(
        self,
        *,
        owner: Any,
        users: dict[str, Any],
        groups: list[LibraryGroup],
        public: LibraryGroup,
        seed: str,
        counts: SeedCounts,
    ) -> list[Shelf]:
        shelves: list[Shelf] = []
        listed_candidates = [
            user
            for user in users.values()
            if get_or_create_profile(user=user).role == UserProfile.ROLE_LIBRARIAN
        ] or list(users.values())
        listed_owner = _stable_order(
            seed,
            "listed-personal-shelf",
            listed_candidates,
        )[0]
        for user in users.values():
            for shelf_index, name in enumerate(PERSONAL_SHELF_NAMES):
                visibility = (
                    Shelf.VISIBILITY_LISTED
                    if name == "Favorites" and user.pk == listed_owner.pk
                    else Shelf.VISIBILITY_PRIVATE
                )
                shelf, created = _get_or_create_shelf(
                    actor=user,
                    name=name,
                    description=(
                        "Books queued for a future reading session."
                        if shelf_index == 0
                        else "Books worth returning to and recommending."
                    ),
                    owner_type=Shelf.OWNER_TYPE_USER,
                    owner_user=user,
                    visibility=visibility,
                )
                if (
                    visibility == Shelf.VISIBILITY_LISTED
                    and shelf.visibility != Shelf.VISIBILITY_LISTED
                ):
                    shelf = update_shelf(
                        user,
                        shelf,
                        visibility=Shelf.VISIBILITY_LISTED,
                    )
                self._record_shelf(shelf, created, shelves, counts)

        for group in groups:
            for shelf_label in GROUP_SHELF_NAMES:
                shelf, created = _get_or_create_shelf(
                    actor=owner,
                    name=shelf_label,
                    description=(
                        f"A shared {shelf_label.lower()} shelf for {group.name}."
                    ),
                    owner_type=Shelf.OWNER_TYPE_GROUP,
                    owner_group=group,
                )
                self._record_shelf(shelf, created, shelves, counts)

        for shelf_label, description in PUBLIC_SHELVES:
            shelf, created = _get_or_create_shelf(
                actor=owner,
                name=shelf_label,
                description=description,
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=public,
            )
            self._record_shelf(shelf, created, shelves, counts)
        return shelves

    @staticmethod
    def _record_shelf(
        shelf: Shelf,
        created: bool,
        shelves: list[Shelf],
        counts: SeedCounts,
    ) -> None:
        shelves.append(shelf)
        if created:
            counts.shelves_created += 1
        else:
            counts.shelves_existing += 1

    def _populate_shelves(
        self,
        *,
        owner: Any,
        shelves: list[Shelf],
        book_scenario: BookScenario,
        seed: str,
        counts: SeedCounts,
        shortfalls: list[str],
    ) -> None:
        for shelf in shelves:
            if ShelfItem.objects.filter(shelf=shelf).exists():
                continue
            if shelf.owner_type == Shelf.OWNER_TYPE_USER:
                shelf_owner = shelf.owner_user
                if shelf_owner is None:
                    raise ValueError("User-owned shelf is missing owner_user.")
                owner_key = shelf_owner.username
                actor = shelf_owner
                books = list(
                    visible_books_for_user(actor, cached=False).order_by(
                        "title",
                        "created_at",
                        "id",
                    )
                )
            else:
                shelf_group = shelf.owner_group
                if shelf_group is None:
                    raise ValueError("Group-owned shelf is missing owner_group.")
                owner_key = shelf_group.name
                actor = owner
                books = [
                    book
                    for book in book_scenario.shelf_books.get(shelf_group.pk, [])
                    if BookGroupAssignment.objects.filter(
                        book=book,
                        group=shelf_group,
                    ).exists()
                ]

            if not books:
                message = f"No accessible Books were available for shelf {shelf.name}."
                if message not in shortfalls:
                    shortfalls.append(message)
                continue

            rng = _stable_random(
                seed,
                f"{shelf.owner_type}:{owner_key}:{shelf.name}",
            )
            target_count = min(len(books), rng.randint(5, 10))
            selected = rng.sample(books, target_count)

            for book in selected:
                if ShelfItem.objects.filter(shelf=shelf, book=book).exists():
                    continue
                add_book_to_shelf(actor, shelf=shelf, book=book)
                counts.shelf_items_added += 1
