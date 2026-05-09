from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import UserProfile
from accounts.services import get_or_create_profile
from library.group_services import add_book_to_group, ensure_user_public_membership, get_public_group
from library.models import Book, LibraryGroup, LibraryGroupMembership


User = get_user_model()


@dataclass(frozen=True)
class SeedUserSpec:
    username: str
    email: str
    password: str
    is_superuser: bool = False
    is_staff: bool = False
    role: str = UserProfile.ROLE_READER


SEED_USERS: list[SeedUserSpec] = [
    SeedUserSpec(
        username="owner",
        email="owner@example.test",
        password="changeme123",
        is_superuser=True,
        is_staff=True,
        role=UserProfile.ROLE_MANAGER,
    ),
    SeedUserSpec(
        username="manager",
        email="manager@example.test",
        password="changeme123",
        is_superuser=False,
        is_staff=False,
        role=UserProfile.ROLE_MANAGER,
    ),
    SeedUserSpec(
        username="librarian",
        email="librarian@example.test",
        password="changeme123",
        is_superuser=False,
        is_staff=False,
        role=UserProfile.ROLE_LIBRARIAN,
    ),
    SeedUserSpec(
        username="reader",
        email="reader@example.test",
        password="changeme123",
        is_superuser=False,
        is_staff=False,
        role=UserProfile.ROLE_READER,
    ),
    SeedUserSpec(
        username="curator",
        email="curator@example.test",
        password="changeme123",
        is_superuser=False,
        is_staff=False,
        role=UserProfile.ROLE_READER,
    ),
    SeedUserSpec(
        username="outsider",
        email="outsider@example.test",
        password="changeme123",
        is_superuser=False,
        is_staff=False,
        role=UserProfile.ROLE_READER,
    ),
]


class Command(BaseCommand):
    help = "Seed predictable development users/groups for manual UI testing (DEV ONLY)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running even when DEBUG is False (DANGEROUS).",
        )
        parser.add_argument(
            "--assign-books",
            action="store_true",
            help="Optionally assign a few existing books to the non-Public groups.",
        )

    def handle(self, *args, **options):
        force = bool(options.get("force"))
        assign_books = bool(options.get("assign_books"))

        if not getattr(settings, "DEBUG", False) and not force:
            raise CommandError(
                "Refusing to run because DEBUG is False. Use --force only for local development."
            )

        self.stdout.write(
            self.style.WARNING(
                "WARNING: This command is for local development only. It creates predictable users with a known password."
            )
        )

        public = get_public_group()
        self.stdout.write(f"Public group: {public.name} ({public.slug})")

        created_users: list[str] = []
        updated_users: list[str] = []
        users_by_username: dict[str, object] = {}

        for spec in SEED_USERS:
            user, created = User.objects.get_or_create(
                username=spec.username,
                defaults={
                    "email": spec.email,
                    "is_superuser": spec.is_superuser,
                    "is_staff": spec.is_staff,
                    "is_active": True,
                },
            )
            updates: dict[str, object] = {}
            if user.email != spec.email:
                updates["email"] = spec.email
            if bool(getattr(user, "is_superuser", False)) != spec.is_superuser:
                updates["is_superuser"] = spec.is_superuser
            if bool(getattr(user, "is_staff", False)) != spec.is_staff:
                updates["is_staff"] = spec.is_staff
            if bool(getattr(user, "is_active", True)) is not True:
                updates["is_active"] = True

            if updates:
                for k, v in updates.items():
                    setattr(user, k, v)
                user.save(update_fields=[*updates.keys()])

            user.set_password(spec.password)
            user.save(update_fields=["password"])

            profile = get_or_create_profile(user=user)
            if profile.role != spec.role:
                profile.role = spec.role
                profile.save(update_fields=["role", "updated_at"])

            ensure_user_public_membership(user=user)

            users_by_username[spec.username] = user
            (created_users if created else updated_users).append(spec.username)

        self.stdout.write("")
        self.stdout.write("Users (username / password):")
        for spec in SEED_USERS:
            self.stdout.write(f"- {spec.username} / {spec.password} ({spec.email})")

        if created_users:
            self.stdout.write(f"Created users: {', '.join(created_users)}")
        if updated_users:
            self.stdout.write(f"Updated users: {', '.join(updated_users)}")

        fantasy, _fantasy_created = LibraryGroup.objects.update_or_create(
            slug="fantasy-club",
            defaults={
                "name": "Fantasy Club",
                "discoverability": LibraryGroup.DISCOVERABILITY_LISTED,
            },
        )
        kids, _kids_created = LibraryGroup.objects.update_or_create(
            slug="kids-books",
            defaults={
                "name": "Kids Books",
                "discoverability": LibraryGroup.DISCOVERABILITY_UNLISTED,
            },
        )

        self.stdout.write("")
        self.stdout.write("Groups:")
        self.stdout.write(f"- {fantasy.name} ({fantasy.slug}) [{fantasy.discoverability}]")
        self.stdout.write(f"- {kids.name} ({kids.slug}) [{kids.discoverability}]")

        memberships: list[str] = []

        curator_user = users_by_username["curator"]
        reader_user = users_by_username["reader"]

        LibraryGroupMembership.objects.update_or_create(
            user=curator_user,
            group=fantasy,
            defaults={"role": LibraryGroupMembership.ROLE_CURATOR},
        )
        memberships.append("curator -> fantasy-club (curator)")

        LibraryGroupMembership.objects.update_or_create(
            user=reader_user,
            group=fantasy,
            defaults={"role": LibraryGroupMembership.ROLE_READER},
        )
        memberships.append("reader -> fantasy-club (reader)")

        self.stdout.write("")
        self.stdout.write("Memberships ensured:")
        for line in memberships:
            self.stdout.write(f"- {line}")
        self.stdout.write("- all seed users -> public (reader)")

        if assign_books:
            owner_user = users_by_username["owner"]
            books = list(Book.objects.order_by("title", "created_at")[:6])
            if not books:
                self.stdout.write("")
                self.stdout.write("No books found; skipping book assignments.")
            else:
                self.stdout.write("")
                self.stdout.write("Assigning existing books to groups (idempotent):")
                assigned: list[str] = []
                for idx, book in enumerate(books):
                    target_group = fantasy if idx % 2 == 0 else kids
                    assignment = add_book_to_group(actor=owner_user, book=book, group=target_group)
                    assigned.append(f"{book.title} -> {assignment.group.slug}")
                for line in assigned:
                    self.stdout.write(f"- {line}")

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Dev users use password changeme123. Do not use outside local development."
            )
        )

