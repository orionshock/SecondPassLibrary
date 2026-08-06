from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import logging
import random
import unicodedata
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import UserProfile
from accounts.bootstrap import has_active_owner
from accounts.services import get_or_create_profile
from core import server_settings
from library.groups.memberships import add_user_to_group, remove_user_from_group
from library.groups.book_assignments import remove_book_from_group
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from library.groups.public_group import get_public_group
from library.queries import (
    invalidate_visible_books_cache_on_commit,
    visible_books_for_user,
)
from shelves.models import Shelf, ShelfItem
from shelves.services import create_shelf, update_shelf


User = get_user_model()
DEV_PASSWORD = "changeme123"
DEFAULT_RANDOM_SEED = "second-pass-library"
logger = logging.getLogger(__name__)


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
    tag_keywords: tuple[str, ...] = ()
    shelf_name: str | None = None


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
    shelves_removed: int = 0
    shelf_items_added: int = 0
    shelf_items_removed: int = 0
    book_group_assignments_added: int = 0
    book_group_assignments_existing: int = 0


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
    exclusive_books: list[Book] = field(default_factory=list)
    shared_book_count: int = 0
    matched_theme_group_count: int = 0
    fallback_group_count: int = 0
    public_only_books: list[Book] = field(default_factory=list)
    public_books_reserved_exclusively: int = 0
    themed_groups: dict[object, "ThemedGroupSummary"] = field(default_factory=dict)


@dataclass
class ThemedGroupSummary:
    matching_tag_names: set[str] = field(default_factory=set)
    matching_book_ids: set[object] = field(default_factory=set)
    assignments_added: int = 0
    assignments_existing: int = 0
    shelf_count: int = 0
    shelf_item_count: int = 0


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
    DemoGroupSpec(
        "Fantasy Club",
        "Epic quests, folklore, and imagined worlds.",
        (
            "fantasy",
            "magic",
            "mythology",
            "mythological",
            "folklore",
            "fairy tale",
            "fairies",
            "legend",
            "legendary",
            "arthurian",
            "dragon",
            "witch",
            "imaginary place",
            "wizard of oz",
        ),
        "Myths, Magic, and Legends",
    ),
    DemoGroupSpec(
        "Mystery Annex",
        "Crime, suspense, puzzles, and investigations.",
        (
            "mystery",
            "detective",
            "crime",
            "murder",
            "investigation",
            "private investigator",
            "police procedural",
            "sleuth",
            "suspense",
            "thriller",
            "spy stories",
            "espionage",
            "criminal",
            "burglars",
            "jewelry theft",
        ),
        "Cases Worth Reopening",
    ),
    DemoGroupSpec(
        "Kids Books",
        "Stories and collections for younger readers.",
        (
            "juvenile fiction",
            "children",
            "boys",
            "girls",
            "family",
            "siblings",
            "brothers",
            "sisters",
            "coming of age",
            "young adult",
            "young men",
            "young women",
            "orphans",
            "schools",
            "kindness",
            "courage",
        ),
        "Growing Up",
    ),
    DemoGroupSpec(
        "Sci-Fi Stack",
        "Science fiction from first contact to far futures.",
        (
            "science fiction",
            "space",
            "interplanetary",
            "extraterrestrial",
            "alien contact",
            "life on other planets",
            "mars",
            "martian",
            "space ship",
            "space station",
            "space colony",
            "time travel",
            "future",
            "scientific expedition",
            "nuclear explosion",
            "underwater exploration",
        ),
        "Beyond Earth",
    ),
    DemoGroupSpec(
        "History Corner",
        "History, biography, and primary-source reading.",
        (
            "classics",
            "classical",
            "ancient",
            "history",
            "historical",
            "biography",
            "autobiography",
            "memoirs",
            "diaries",
            "correspondence",
            "rome",
            "greek",
            "greece",
            "trojan war",
            "medieval",
            "renaissance",
            "victorian",
        ),
        "People and Periods",
    ),
    DemoGroupSpec(
        "Horror Vault",
        "Gothic, supernatural, and unsettling reading.",
        (
            "horror",
            "gothic",
            "ghost",
            "haunted",
            "vampire",
            "dracula",
            "frankenstein",
            "monster",
            "supernatural",
            "occult",
            "paranormal",
            "cthulhu",
            "psychic",
            "telepathy",
            "theosophy",
        ),
        "Things in the Dark",
    ),
    DemoGroupSpec(
        "Adventure Society",
        "Travel, exploration, danger, and discovery.",
        (
            "adventure",
            "voyage",
            "travel",
            "exploration",
            "expedition",
            "shipwreck",
            "castaway",
            "pirate",
            "sailing",
            "sea stories",
            "frontier",
            "pioneer",
            "treasure",
            "jungle",
            "antarctica",
            "mississippi river",
            "description and travel",
        ),
        "Routes Less Traveled",
    ),
    DemoGroupSpec(
        "Romance Room",
        "Love, courtship, marriage, and complicated relationships.",
        (
            "romance",
            "love",
            "courtship",
            "marriage",
            "husband and wife",
            "man woman relationships",
            "first loves",
            "unrequited love",
            "elopement",
            "family relationships",
        ),
        "Matters of the Heart",
    ),
]

GROUP_SHELF_NAMES = ("Staff Picks", "Current Favorites")
OPTIONAL_GROUP_SHELF_NAMES = (
    "A Short Introduction",
    "Deep Cuts",
    "Popular Themes",
    "Long Reads",
)
PUBLIC_SHELVES = (
    ("Welcome Shelf", "A librarian-managed starting point for the Common Room."),
    ("Community Favorites", "Popular books shared across the public library space."),
)
PERSONAL_SHELF_NAMES = ("Reading Queue", "Favorites")


def normalize_catalog_tag_match_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(
        "".join(
            character if character.isalnum() else " " for character in normalized
        ).split()
    )


def matching_group_names_for_tag(
    tag_name: str,
    group_specs: list[DemoGroupSpec] | tuple[DemoGroupSpec, ...] = tuple(DEMO_GROUPS),
) -> set[str]:
    normalized_tag = normalize_catalog_tag_match_text(tag_name)
    return {
        spec.name
        for spec in group_specs
        if any(
            normalize_catalog_tag_match_text(keyword) in normalized_tag
            for keyword in spec.tag_keywords
        )
    }


def thematic_catalog_matches(
    books: list[Book],
    group_specs: list[DemoGroupSpec] | tuple[DemoGroupSpec, ...],
) -> dict[str, ThemedGroupSummary]:
    summaries = {spec.name: ThemedGroupSummary() for spec in group_specs}
    normalized_keywords = {
        spec.name: tuple(
            normalize_catalog_tag_match_text(keyword) for keyword in spec.tag_keywords
        )
        for spec in group_specs
    }
    matching_groups_by_tag: dict[object, set[str]] = {}
    for book in books:
        for relation in book.book_catalog_tags.all():
            tag = relation.catalog_tag
            matching_groups = matching_groups_by_tag.get(tag.pk)
            if matching_groups is None:
                normalized_tag = normalize_catalog_tag_match_text(tag.name)
                matching_groups = {
                    group_name
                    for group_name, keywords in normalized_keywords.items()
                    if any(keyword in normalized_tag for keyword in keywords)
                }
                matching_groups_by_tag[tag.pk] = matching_groups
            for group_name in matching_groups:
                summary = summaries[group_name]
                summary.matching_tag_names.add(tag.name)
                summary.matching_book_ids.add(book.pk)
    return summaries


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
                getattr(value, "pk", None) or getattr(value, "username", None) or value
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
            + (
                "enabled; adding demo rooms."
                if advanced_groups_enabled
                else "disabled; simple Public demo only."
            )
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
                "group_assignments",
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
                book_scenario=book_scenario,
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
        self.stdout.write(
            "Public Books reserved for the exclusive fixture: "
            f"{book_scenario.public_books_reserved_exclusively}"
        )
        self.stdout.write(f"Public-only Books: {len(book_scenario.public_only_books)}")
        self.stdout.write(f"Shared Books: {book_scenario.shared_book_count}")
        self.stdout.write(
            "Thematic coverage: "
            f"{book_scenario.matched_theme_group_count} matched profiles, "
            f"{book_scenario.fallback_group_count} deterministic fallbacks"
        )
        self.stdout.write(
            "Book group assignments: "
            f"{counts.book_group_assignments_added} added, "
            f"{counts.book_group_assignments_existing} already present"
        )
        for group in groups:
            themed = book_scenario.themed_groups.get(group.pk)
            if themed is None:
                continue
            self.stdout.write(
                f"Themed Group {group.name}: "
                f"{len(themed.matching_tag_names)} matching tags, "
                f"{len(themed.matching_book_ids)} matching Books, "
                f"{themed.assignments_added} assignments added, "
                f"{themed.assignments_existing} already present, "
                f"{themed.shelf_count} Shelves, "
                f"{themed.shelf_item_count} Shelf items"
            )
            logger.info(
                "Seed demo thematic Group ready: group=%s matching_tags=%d "
                "matching_books=%d assignments_added=%d assignments_existing=%d "
                "shelves=%d shelf_items=%d",
                group.name,
                len(themed.matching_tag_names),
                len(themed.matching_book_ids),
                themed.assignments_added,
                themed.assignments_existing,
                themed.shelf_count,
                themed.shelf_item_count,
            )
        self.stdout.write(
            f"Shelves: {counts.shelves_created} created, "
            f"{counts.shelves_existing} existing/skipped, "
            f"{counts.shelves_removed} stale seed-owned Shelves removed"
        )
        self.stdout.write(
            f"Shelf items: {counts.shelf_items_added} added, "
            f"{counts.shelf_items_removed} removed during refresh"
        )
        if not books:
            self.stdout.write("Book population: skipped because no books exist.")
        self.stdout.write(f"Book population seed: {seed}")
        if membership_scenario.shortfalls:
            self.stdout.write("Scenario shortfalls:")
            for message in membership_scenario.shortfalls:
                self.stdout.write(self.style.WARNING(f"- {message}"))
        else:
            self.stdout.write("Scenario shortfalls: none")
        logger.info(
            "Seed demo world complete: seed=%s users=%d groups=%d memberships_created=%d "
            "assignments_added=%d shelves_created=%d shelf_items_added=%d",
            seed,
            len(users),
            len(groups),
            counts.memberships_created,
            counts.book_group_assignments_added,
            counts.shelves_created,
            counts.shelf_items_added,
        )
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

        overlapping_user = None
        if available and other_groups:
            overlapping_user = next(
                (
                    user
                    for user in available
                    if roles[user.username] == UserProfile.ROLE_READER
                ),
                available[0],
            )
            available.remove(overlapping_user)
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

        safe_public_only = [
            user
            for user in available
            if not LibraryGroupMembership.objects.filter(user=user)
            .exclude(group=public)
            .exists()
        ]
        public_only = next(
            (
                user
                for user in safe_public_only
                if roles[user.username] == UserProfile.ROLE_READER
            ),
            safe_public_only[0] if safe_public_only else None,
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

        multi_private = (
            available.pop(0) if available and len(other_groups) >= 2 else None
        )
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
        self._bulk_ensure_book_assignments(
            owner=owner,
            books_by_group={public.pk: (public, books)},
            counts=counts,
        )
        return BookScenario()

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

        assignments_by_book = {
            book.pk: {
                assignment.group_id for assignment in book.group_assignments.all()
            }
            for book in books
        }
        safe_exclusive = [
            book
            for book in books
            if not assignments_by_book[book.pk]
            or assignments_by_book[book.pk] == {exclusive_group.pk}
        ]

        exclusive_books = _stable_order(
            seed,
            f"exclusive:{exclusive_group.pk}",
            safe_exclusive,
        )[:2]
        public_exclusive_candidates = _stable_order(
            seed,
            "exclusive-from-public",
            [
                book
                for book in books
                if assignments_by_book[book.pk] == {public.pk}
                and book not in exclusive_books
            ],
        )
        converted_from_public = public_exclusive_candidates[
            : min(
                max(0, 2 - len(exclusive_books)),
                max(0, len(public_exclusive_candidates) - 1),
            )
        ]
        exclusive_books.extend(converted_from_public)
        scenario.public_books_reserved_exclusively = len(converted_from_public)
        scenario.exclusive_books = exclusive_books
        if not exclusive_books:
            membership_scenario.shortfalls.append(
                "No unassigned or already-exclusive Books were safe to assign "
                f"exclusively to {exclusive_group.name}; existing assignments "
                "were preserved."
            )

        exclusive_book_ids = {book.pk for book in exclusive_books}
        public_only_candidates = [
            book
            for book in books
            if book.pk not in exclusive_book_ids
            and assignments_by_book[book.pk].issubset({public.pk})
        ]
        public_only_books = _stable_order(
            seed,
            "public-only-book",
            public_only_candidates,
        )[:1]
        scenario.public_only_books = public_only_books
        if not public_only_books:
            membership_scenario.shortfalls.append(
                "No unassigned or Public-only Book was available for the Public-only fixture."
            )

        reserved_book_ids = exclusive_book_ids | {book.pk for book in public_only_books}
        nonexclusive_candidates = [
            book for book in books if book.pk not in reserved_book_ids
        ]
        other_groups = [group for group in groups if group.pk != exclusive_group.pk]
        unique_anchors: dict[object, Book] = {}
        reserved_anchor_ids: set[object] = set()
        for group in other_groups:
            safe_anchors = [
                book
                for book in nonexclusive_candidates
                if book.pk not in reserved_anchor_ids
                and (
                    not assignments_by_book[book.pk]
                    or assignments_by_book[book.pk] == {group.pk}
                )
            ]
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

        reserved_book_ids |= reserved_anchor_ids
        group_specs = {spec.name: spec for spec in DEMO_GROUPS}
        active_specs = tuple(
            spec
            for group in groups
            if (spec := group_specs.get(group.name)) is not None
        )
        thematic_matches = thematic_catalog_matches(books, active_specs)
        desired_by_group: dict[object, tuple[LibraryGroup, list[Book]]] = {
            group.pk: (group, []) for group in groups
        }
        desired_by_group[exclusive_group.pk][1].extend(exclusive_books)
        for group_id, anchor in unique_anchors.items():
            desired_by_group[group_id][1].append(anchor)

        for group in groups:
            summary = thematic_matches.get(group.name, ThemedGroupSummary())
            scenario.themed_groups[group.pk] = summary
            desired_by_group[group.pk][1].extend(
                book
                for book in books
                if book.pk in summary.matching_book_ids
                and book.pk not in reserved_book_ids
            )

            if summary.matching_book_ids:
                scenario.matched_theme_group_count += 1
            else:
                scenario.fallback_group_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Thematic fallback: {group.name} matched no Catalog Tags; "
                        "using deterministic available Books."
                    )
                )
                logger.warning(
                    "Seed demo thematic Group used fallback: group=%s",
                    group.name,
                )

        for group in groups:
            selected = self._deduplicate_books(desired_by_group[group.pk][1])
            unavailable_fixture_ids = reserved_book_ids - {book.pk for book in selected}
            fallback_candidates = [
                book for book in books if book.pk not in unavailable_fixture_ids
            ]
            fallback = _stable_order(
                seed,
                f"thematic-fallback:{group.pk}",
                [book for book in fallback_candidates if book not in selected],
            )[: max(0, 6 - len(selected))]
            selected.extend(fallback)
            desired_by_group[group.pk] = (group, selected)
            if not selected:
                membership_scenario.shortfalls.append(
                    f"No Books were available for {group.name}."
                )

        shared_candidates = _stable_order(
            seed,
            "shared-books",
            [book for book in books if book.pk not in reserved_book_ids],
        )
        shared_candidate = shared_candidates[0] if shared_candidates else None
        shared_groups = _stable_order(seed, "shared-groups", groups)[:2]
        if shared_candidate is not None and len(shared_groups) >= 2:
            for group in shared_groups:
                selected = desired_by_group[group.pk][1]
                if shared_candidate not in selected:
                    selected.append(shared_candidate)
        else:
            membership_scenario.shortfalls.append(
                "Shared-Book scenario requires a non-reserved Book and at least "
                "two non-Public Groups."
            )

        desired_by_group[public.pk] = (public, public_only_books)
        assignment_counts = self._bulk_ensure_book_assignments(
            owner=owner,
            books_by_group=desired_by_group,
            counts=counts,
        )
        for book in converted_from_public:
            remove_book_from_group(book=book, group=public, actor=owner)
            assignments_by_book[book.pk].discard(public.pk)
        for group in groups:
            added, existing = assignment_counts[group.pk]
            summary = scenario.themed_groups[group.pk]
            summary.assignments_added = added
            summary.assignments_existing = existing

        final_assignment_groups = {
            book_id: set(group_ids)
            for book_id, group_ids in assignments_by_book.items()
        }
        for group_id, (_group, selected) in desired_by_group.items():
            for book in selected:
                final_assignment_groups.setdefault(book.pk, set()).add(group_id)
        scenario.shared_book_count = sum(
            len(group_ids) >= 2
            for book_id, group_ids in final_assignment_groups.items()
            if book_id not in reserved_book_ids
        )
        return scenario

    @staticmethod
    def _deduplicate_books(books: list[Book]) -> list[Book]:
        return list({book.pk: book for book in books}.values())

    @staticmethod
    def _bulk_ensure_book_assignments(
        *,
        owner: Any,
        books_by_group: dict[object, tuple[LibraryGroup, list[Book]]],
        counts: SeedCounts,
    ) -> dict[object, tuple[int, int]]:
        desired = {
            (book.pk, group_id): (book, group)
            for group_id, (group, books) in books_by_group.items()
            for book in books
        }
        if not desired:
            return {group_id: (0, 0) for group_id in books_by_group}
        existing = set(
            BookGroupAssignment.objects.filter(
                book_id__in={book_id for book_id, _group_id in desired},
                group_id__in={group_id for _book_id, group_id in desired},
            ).values_list("book_id", "group_id")
        )
        missing = [
            BookGroupAssignment(book=book, group=group, added_by=owner)
            for pair, (book, group) in desired.items()
            if pair not in existing
        ]
        if missing:
            with transaction.atomic():
                BookGroupAssignment.objects.bulk_create(missing)
                invalidate_visible_books_cache_on_commit()
        counts.book_group_assignments_added += len(missing)
        counts.book_group_assignments_existing += len(existing & desired.keys())
        result: dict[object, tuple[int, int]] = {}
        for group_id in books_by_group:
            added = sum(pair not in existing for pair in desired if pair[1] == group_id)
            already_existing = sum(
                pair in existing for pair in desired if pair[1] == group_id
            )
            result[group_id] = (added, already_existing)
        return result

    def _ensure_shelves(
        self,
        *,
        owner: Any,
        users: dict[str, Any],
        groups: list[LibraryGroup],
        public: LibraryGroup,
        seed: str,
        counts: SeedCounts,
        book_scenario: BookScenario,
    ) -> list[Shelf]:
        shelves: list[Shelf] = []
        for user in users.values():
            for shelf_index, name in enumerate(PERSONAL_SHELF_NAMES):
                visibility = (
                    Shelf.VISIBILITY_LISTED
                    if name == "Favorites"
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
                if shelf.visibility != visibility:
                    shelf = update_shelf(
                        user,
                        shelf,
                        visibility=visibility,
                    )
                self._record_shelf(shelf, created, shelves, counts)

        specs_by_name = {spec.name: spec for spec in DEMO_GROUPS}
        for group in groups:
            spec = specs_by_name.get(group.name)
            optional_names = list(OPTIONAL_GROUP_SHELF_NAMES)
            if spec is not None and spec.shelf_name:
                optional_names.insert(0, spec.shelf_name)
            rng = _stable_random(seed, f"group-shelf-templates:{group.pk}")
            rng.shuffle(optional_names)
            shelf_names = [
                *GROUP_SHELF_NAMES,
                *optional_names[: rng.randint(1, min(2, len(optional_names)))],
            ]
            all_managed_names = {
                *GROUP_SHELF_NAMES,
                *OPTIONAL_GROUP_SHELF_NAMES,
                *([spec.shelf_name] if spec is not None and spec.shelf_name else []),
            }
            selected_names = set(shelf_names)
            for stale_shelf in Shelf.objects.filter(
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=group,
                name__in=all_managed_names - selected_names,
            ):
                if stale_shelf.description != (
                    f"A shared {stale_shelf.name.lower()} shelf for {group.name}."
                ):
                    continue
                stale_shelf.delete()
                counts.shelves_removed += 1
            group_shelves = []
            for shelf_label in shelf_names:
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
                group_shelves.append(shelf)
            summary = book_scenario.themed_groups.get(group.pk)
            if summary is not None:
                summary.shelf_count = len(group_shelves)

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
        existing_items_by_shelf: dict[object, list[ShelfItem]] = {
            shelf.pk: [] for shelf in shelves
        }
        for item in ShelfItem.objects.filter(shelf__in=shelves).order_by(
            "shelf_id",
            "position",
            "created_at",
            "id",
        ):
            existing_items_by_shelf[item.shelf_id].append(item)
        visible_books_by_user: dict[object, list[Book]] = {}
        group_books: dict[object, list[Book]] = {
            shelf.owner_group_id: []
            for shelf in shelves
            if shelf.owner_group_id is not None
        }
        for assignment in (
            BookGroupAssignment.objects.filter(group_id__in=group_books)
            .select_related("book")
            .order_by("group_id", "book__title", "book__created_at", "book__id")
        ):
            group_books[assignment.group_id].append(assignment.book)

        for shelf in shelves:
            if shelf.owner_type == Shelf.OWNER_TYPE_USER:
                shelf_owner = shelf.owner_user
                if shelf_owner is None:
                    raise ValueError("User-owned shelf is missing owner_user.")
                owner_key = shelf_owner.username
                if shelf_owner.pk not in visible_books_by_user:
                    visible_books_by_user[shelf_owner.pk] = list(
                        visible_books_for_user(shelf_owner, cached=False).order_by(
                            "title",
                            "created_at",
                            "id",
                        )
                    )
                books = visible_books_by_user[shelf_owner.pk]
            else:
                shelf_group = shelf.owner_group
                if shelf_group is None:
                    raise ValueError("Group-owned shelf is missing owner_group.")
                owner_key = shelf_group.name
                books = group_books[shelf_group.pk]

            if not books:
                message = f"No accessible Books were available for shelf {shelf.name}."
                if message not in shortfalls:
                    shortfalls.append(message)
                continue

            existing_items = existing_items_by_shelf[shelf.pk]
            eligible_book_ids = {book.pk for book in books}
            if existing_items and all(
                item.book_id in eligible_book_ids for item in existing_items
            ):
                now = timezone.now()
                changed_positions = []
                for position, item in enumerate(existing_items):
                    if item.position == position:
                        continue
                    item.position = position
                    item.updated_at = now
                    changed_positions.append(item)
                if changed_positions:
                    ShelfItem.objects.bulk_update(
                        changed_positions,
                        ["position", "updated_at"],
                    )
                if shelf.owner_group_id in book_scenario.themed_groups:
                    book_scenario.themed_groups[
                        shelf.owner_group_id
                    ].shelf_item_count += len(existing_items)
                continue

            rng = _stable_random(
                seed,
                f"{shelf.owner_type}:{owner_key}:{shelf.name}",
            )
            target_count = min(len(books), rng.randint(6, 24))
            selected = rng.sample(books, target_count)
            self._sync_shelf_items(
                shelf=shelf,
                selected=selected,
                existing=existing_items,
                added_by=shelf.owner_user or owner,
                counts=counts,
            )
            if shelf.owner_group_id in book_scenario.themed_groups:
                book_scenario.themed_groups[
                    shelf.owner_group_id
                ].shelf_item_count += len(selected)

    @staticmethod
    def _sync_shelf_items(
        *,
        shelf: Shelf,
        selected: list[Book],
        existing: list[ShelfItem],
        added_by: Any,
        counts: SeedCounts,
    ) -> None:
        desired_positions = {
            book.pk: position for position, book in enumerate(selected)
        }
        existing_by_book = {item.book_id: item for item in existing}
        removed = [item for item in existing if item.book_id not in desired_positions]
        if removed:
            ShelfItem.objects.filter(pk__in=[item.pk for item in removed]).delete()
            counts.shelf_items_removed += len(removed)

        now = timezone.now()
        changed = []
        for book_id, position in desired_positions.items():
            item = existing_by_book.get(book_id)
            if item is not None and item.position != position:
                item.position = position
                item.updated_at = now
                changed.append(item)
        if changed:
            ShelfItem.objects.bulk_update(changed, ["position", "updated_at"])

        missing = [
            ShelfItem(
                shelf=shelf,
                book=book,
                position=desired_positions[book.pk],
                added_by=added_by,
            )
            for book in selected
            if book.pk not in existing_by_book
        ]
        if missing:
            ShelfItem.objects.bulk_create(missing)
            counts.shelf_items_added += len(missing)
