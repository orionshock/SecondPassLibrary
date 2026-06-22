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
from accounts.services import get_or_create_profile
from library.group_services import (
    add_book_to_group,
    ensure_user_public_membership,
    get_public_group,
)
from library.models import Book, LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from shelves.services import add_book_to_shelf, create_shelf


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


DEMO_USERS = [
    DemoUserSpec("lorem", "Lorem", "Ipsum", UserProfile.ROLE_MANAGER),
    DemoUserSpec("ipsum", "Ipsum", "Dolor", UserProfile.ROLE_MANAGER),
    DemoUserSpec("dolor", "Dolor", "Sit", UserProfile.ROLE_MANAGER),
    DemoUserSpec("sit", "Sit", "Amet", UserProfile.ROLE_LIBRARIAN),
    DemoUserSpec("amet", "Amet", "Consectetur", UserProfile.ROLE_LIBRARIAN),
    DemoUserSpec(
        "consectetur",
        "Consectetur",
        "Adipiscing",
        UserProfile.ROLE_LIBRARIAN,
    ),
    DemoUserSpec("adipiscing", "Adipiscing", "Elit", UserProfile.ROLE_LIBRARIAN),
    DemoUserSpec("elit", "Elit", "Sed", UserProfile.ROLE_READER),
    DemoUserSpec("sed", "Sed", "Eiusmod", UserProfile.ROLE_READER),
    DemoUserSpec("eiusmod", "Eiusmod", "Tempor", UserProfile.ROLE_READER),
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
        owner, owner_created = self._ensure_owner()
        self.stdout.write(f"Public group: {public.name} ({public.id})")

        user_specs = _expanded_user_specs(user_count)
        users, created_usernames = self._ensure_demo_users(user_specs, counts)
        groups = self._ensure_groups(_expanded_group_specs(group_count), counts)
        self._ensure_memberships(
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
        owner_summary = (
            f"created {owner.username}"
            if owner_created
            else f"existing active superuser {owner.username} found; skipped"
        )
        self.stdout.write(f"Owner bootstrap: {owner_summary}")
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

    def _ensure_owner(self) -> tuple[Any, bool]:
        existing = (
            User.objects.filter(is_active=True, is_superuser=True)
            .order_by("date_joined", "pk")
            .first()
        )
        if existing is not None:
            return existing, False

        base_username = "lorem-admin"
        username = base_username
        suffix = 2
        while User.objects.filter(username=username).exists():
            username = f"{base_username}-{suffix}"
            suffix += 1

        owner = User(
            username=username,
            first_name="Lorem",
            last_name="Administrator",
            email=f"{username}@example.test",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        owner.set_password(DEV_PASSWORD)
        owner.full_clean()
        owner.save()

        profile = get_or_create_profile(user=owner)
        profile.role = UserProfile.ROLE_MANAGER
        profile.must_change_password = False
        profile.save(update_fields=["role", "must_change_password", "updated_at"])
        ensure_user_public_membership(user=owner)
        return owner, True

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

    def _ensure_memberships(
        self,
        *,
        users: dict[str, Any],
        created_usernames: set[str],
        groups: list[LibraryGroup],
        public: LibraryGroup,
        counts: SeedCounts,
    ) -> None:
        for index, (username, user) in enumerate(users.items()):
            desired: list[tuple[LibraryGroup, str]] = []
            if index % 4 != 2:
                desired.append((public, LibraryGroupMembership.ROLE_READER))

            if index % 8 != 7:
                desired.append(
                    (
                        groups[index % len(groups)],
                        (
                            LibraryGroupMembership.ROLE_CURATOR
                            if index % 5 == 0
                            else LibraryGroupMembership.ROLE_READER
                        ),
                    )
                )
                if index % 3 == 0:
                    desired.append(
                        (
                            groups[(index + 1) % len(groups)],
                            LibraryGroupMembership.ROLE_READER,
                        )
                    )

            for group, role in desired:
                _membership, created = LibraryGroupMembership.objects.get_or_create(
                    user=user,
                    group=group,
                    defaults={"role": role},
                )
                if created:
                    counts.memberships_created += 1
                else:
                    counts.memberships_existing += 1

            if username in created_usernames and index % 4 == 2:
                LibraryGroupMembership.objects.filter(
                    user=user,
                    group=public,
                ).delete()

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
            for shelf_index, name in enumerate(PERSONAL_SHELF_NAMES):
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
                )
                self._record_shelf(shelf, created, shelves, counts)

        for group in groups:
            for name in GROUP_SHELF_NAMES:
                shelf, created = _get_or_create_shelf(
                    actor=owner,
                    name=name,
                    description=f"A shared {name.lower()} shelf for {group.name}.",
                    owner_type=Shelf.OWNER_TYPE_GROUP,
                    owner_group=group,
                )
                self._record_shelf(shelf, created, shelves, counts)

        for name, description in PUBLIC_SHELVES:
            shelf, created = _get_or_create_shelf(
                actor=owner,
                name=name,
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
            owner_key = (
                shelf.owner_user.username
                if shelf.owner_type == Shelf.OWNER_TYPE_USER
                else shelf.owner_group.name
            )
            rng = _stable_random(
                seed,
                f"{shelf.owner_type}:{owner_key}:{shelf.name}",
            )
            target_count = min(len(books), rng.randint(5, 10))
            selected = rng.sample(books, target_count)
            actor = (
                shelf.owner_user
                if shelf.owner_type == Shelf.OWNER_TYPE_USER
                else owner
            )

            for book in selected:
                if ShelfItem.objects.filter(shelf=shelf, book=book).exists():
                    continue
                self._ensure_book_access(
                    owner=owner,
                    actor=actor,
                    shelf=shelf,
                    book=book,
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
    ) -> None:
        if shelf.owner_type == Shelf.OWNER_TYPE_GROUP:
            add_book_to_group(actor=owner, book=book, group=shelf.owner_group)
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
            add_book_to_group(actor=owner, book=book, group=membership.group)
