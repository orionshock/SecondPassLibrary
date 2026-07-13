from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from accounts.models import UserProfile
from accounts.bootstrap import has_active_owner
from accounts.services import get_or_create_profile
from core import server_settings
from library.groups.book_assignments import add_book_to_group
from library.groups.memberships import add_user_to_group, remove_user_from_group
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from library.groups.public_group import get_public_group
from shelves.models import Shelf, ShelfItem
from shelves.services import add_book_to_shelf, create_shelf, update_shelf


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
        users, created_usernames = self._ensure_demo_users(user_specs, counts)
        self._ensure_simple_memberships(users=users, public=public, counts=counts)
        groups: list[LibraryGroup] = []
        if advanced_groups_enabled:
            groups = self._ensure_groups(_expanded_group_specs(group_count), counts)
            self._ensure_advanced_memberships(
                owner=owner,
                users=users,
                created_usernames=created_usernames,
                groups=groups,
                public=public,
                counts=counts,
            )

        no_books = False
        if skip_shelves:
            self.stdout.write("Shelves: skipped by --skip-shelves.")
        else:
            shelves = self._ensure_shelves(
                owner=owner,
                users=users,
                groups=groups,
                public=public,
                counts=counts,
            )
            books = list(Book.objects.order_by("title", "created_at", "id"))
            if books:
                self._populate_shelves(
                    owner=owner,
                    shelves=shelves,
                    books=books,
                    seed=seed,
                    counts=counts,
                )
            else:
                no_books = True
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
        self.stdout.write(f"Book group assignments added: {counts.book_group_assignments_added}")
        self.stdout.write(
            f"Shelves: {counts.shelves_created} created, "
            f"{counts.shelves_existing} existing/skipped"
        )
        self.stdout.write(f"Shelf items added: {counts.shelf_items_added}")
        if no_books:
            self.stdout.write("Book population: skipped because no books exist.")
        elif not skip_shelves:
            self.stdout.write(f"Book population seed: {seed}")
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
        created_usernames: set[str] = set()
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
                created_usernames.add(spec.username)
            else:
                counts.users_existing += 1
            users[spec.username] = user
        return users, created_usernames

    def _ensure_groups(
        self,
        specs: list[DemoGroupSpec],
        counts: SeedCounts,
    ) -> list[LibraryGroup]:
        groups: list[LibraryGroup] = []
        for spec in specs:
            group = (
                LibraryGroup.objects.filter(name=spec.name)
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
        created_usernames: set[str],
        groups: list[LibraryGroup],
        public: LibraryGroup,
        counts: SeedCounts,
    ) -> None:
        user_items = list(users.items())
        profiles = {
            username: UserProfile.objects.get(user=user)
            for username, user in user_items
        }
        reader_users = [
            user
            for username, user in user_items
            if profiles[username].role == UserProfile.ROLE_READER
        ]
        self._ensure_each_group_has_curator(
            owner=owner,
            users=reader_users,
            groups=groups,
            counts=counts,
        )

        for index, (username, user) in enumerate(user_items):
            if profiles[username].role != UserProfile.ROLE_READER:
                continue

            desired: list[tuple[LibraryGroup, bool]] = []
            if index % 4 != 2:
                desired.append((public, False))

            if index % 8 != 7:
                desired.append(
                    (
                        groups[index % len(groups)],
                        False,
                    )
                )
                if index % 3 == 0:
                    desired.append(
                        (
                            groups[(index + 1) % len(groups)],
                            False,
                        )
                    )

            for group, is_curator in desired:
                existing = LibraryGroupMembership.objects.filter(
                    user=user, group=group
                ).first()
                if existing is not None:
                    counts.memberships_existing += 1
                    continue

                add_user_to_group(
                    user=user,
                    group=group,
                    is_curator=is_curator,
                )
                counts.memberships_created += 1

            if username in created_usernames and index % 4 == 2:
                public_membership = LibraryGroupMembership.objects.filter(
                    user=user,
                    group=public,
                ).first()
                if public_membership is not None:
                    remove_user_from_group(user=user, group=public)

    @staticmethod
    def _ensure_each_group_has_curator(
        *,
        owner: Any,
        users: list[Any],
        groups: list[LibraryGroup],
        counts: SeedCounts,
    ) -> None:
        for group_index, group in enumerate(groups):
            if LibraryGroupMembership.objects.filter(
                group=group,
                is_curator=True,
            ).exists():
                continue

            rotated_users = users[group_index:] + users[:group_index]
            for user in rotated_users:
                if LibraryGroupMembership.objects.filter(
                    user=user,
                    group=group,
                ).exists():
                    continue
                add_user_to_group(
                    user=user,
                    group=group,
                    is_curator=True,
                )
                counts.memberships_created += 1
                break

    def _ensure_shelves(
        self,
        *,
        owner: Any,
        users: dict[str, Any],
        groups: list[LibraryGroup],
        public: LibraryGroup,
        counts: SeedCounts,
    ) -> list[Shelf]:
        shelves: list[Shelf] = []
        for user in users.values():
            profile = get_or_create_profile(user=user)
            for shelf_index, name in enumerate(PERSONAL_SHELF_NAMES):
                visibility = (
                    Shelf.VISIBILITY_LISTED
                    if name == "Favorites"
                    and profile.role == UserProfile.ROLE_LIBRARIAN
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
                name = f"{group.name}: {shelf_label}"
                shelf, created = _get_or_create_shelf(
                    actor=owner,
                    name=name,
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
                name=f"{public.name}: {shelf_label}",
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
        books: list[Book],
        seed: str,
        counts: SeedCounts,
    ) -> None:
        for shelf in shelves:
            if shelf.owner_type == Shelf.OWNER_TYPE_USER:
                shelf_owner = shelf.owner_user
                if shelf_owner is None:
                    raise ValueError("User-owned shelf is missing owner_user.")
                owner_key = shelf_owner.username
                actor = shelf_owner
            else:
                shelf_group = shelf.owner_group
                if shelf_group is None:
                    raise ValueError("Group-owned shelf is missing owner_group.")
                owner_key = shelf_group.name
                actor = owner

            rng = _stable_random(
                seed,
                f"{shelf.owner_type}:{owner_key}:{shelf.name}",
            )
            target_count = min(len(books), rng.randint(5, 10))
            selected = rng.sample(books, target_count)

            for book in selected:
                if ShelfItem.objects.filter(shelf=shelf, book=book).exists():
                    continue
                self._ensure_book_access(
                    owner=owner,
                    actor=actor,
                    shelf=shelf,
                    book=book,
                    counts=counts,
                )
                add_book_to_shelf(actor, shelf=shelf, book=book)
                counts.shelf_items_added += 1

    @staticmethod
    def _ensure_book_access(
        *,
        owner: Any,
        actor: Any,
        shelf: Shelf,
        book: Book,
        counts: SeedCounts,
    ) -> None:
        if shelf.owner_type == Shelf.OWNER_TYPE_GROUP:
            shelf_group = shelf.owner_group
            if shelf_group is None:
                raise ValueError("Group-owned shelf is missing owner_group.")
            already_assigned = BookGroupAssignment.objects.filter(
                book=book,
                group=shelf_group,
            ).exists()
            add_book_to_group(actor=owner, book=book, group=shelf_group)
            if not already_assigned:
                counts.book_group_assignments_added += 1
            return

        profile = get_or_create_profile(user=actor)
        if actor.is_superuser or profile.role in {
            UserProfile.ROLE_MANAGER,
            UserProfile.ROLE_LIBRARIAN,
        }:
            return

        membership = (
            LibraryGroupMembership.objects.filter(user=actor)
            .select_related("group")
            .order_by("group__name", "created_at")
            .first()
        )
        if membership is not None:
            already_assigned = BookGroupAssignment.objects.filter(
                book=book,
                group=membership.group,
            ).exists()
            add_book_to_group(actor=owner, book=book, group=membership.group)
            if not already_assigned:
                counts.book_group_assignments_added += 1
