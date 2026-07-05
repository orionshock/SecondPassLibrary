from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import UserProfile
from core import server_settings
from library.groups.public_group import get_public_group
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from tests.library.utils import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class SeedDevUsersCommandTests(IsolatedMediaRootMixin, TestCase):
    def _create_setup_owner(self, username: str = "setup-owner"):
        owner = User.objects.create_superuser(
            username=username,
            password="private-password",
            email=f"{username}@example.test",
        )
        profile = UserProfile.objects.get(user=owner)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])
        return owner

    @override_settings(DEBUG=False)
    def test_refuses_when_debug_false_unless_forced(self):
        with patch(
            "accounts.management.commands.seed_dev_users.call_command"
        ) as migrate_command:
            with self.assertRaises(CommandError):
                call_command("seed_dev_users")
        migrate_command.assert_not_called()

        self._create_setup_owner()
        call_command(
            "seed_dev_users",
            force=True,
            users=1,
            groups=1,
            skip_shelves=True,
            verbosity=0,
        )

        self.assertTrue(User.objects.filter(username="lorem").exists())

    @override_settings(DEBUG=True)
    def test_requires_first_run_setup_owner(self):
        with patch(
            "accounts.management.commands.seed_dev_users.call_command"
        ) as migrate_command:
            with self.assertRaises(CommandError) as cm:
                call_command("seed_dev_users", verbosity=0)

        self.assertIn("Complete setup before running seed_dev_users", str(cm.exception))
        migrate_command.assert_not_called()
        self.assertFalse(User.objects.filter(username="lorem-admin").exists())

    @override_settings(DEBUG=True)
    def test_applies_migrations_before_seeding(self):
        self._create_setup_owner()
        with patch(
            "accounts.management.commands.seed_dev_users.call_command",
            wraps=call_command,
        ) as migrate_command:
            call_command(
                "seed_dev_users",
                users=1,
                groups=1,
                skip_shelves=True,
                verbosity=0,
            )

        migrate_command.assert_called_once_with(
            "migrate",
            interactive=False,
            verbosity=0,
        )

    @override_settings(DEBUG=True)
    def test_existing_active_superuser_is_left_unchanged(self):
        owner = self._create_setup_owner(username="existing-admin")
        owner.first_name = "Existing"
        owner.last_name = "Operator"
        owner.is_staff = False
        owner.save(update_fields=["first_name", "last_name", "is_staff"])
        profile = UserProfile.objects.get(user=owner)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        password_hash = owner.password

        output = StringIO()
        call_command(
            "seed_dev_users",
            users=1,
            groups=1,
            skip_shelves=True,
            verbosity=0,
            stdout=output,
        )

        owner.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(owner.first_name, "Existing")
        self.assertEqual(owner.last_name, "Operator")
        self.assertEqual(owner.email, "existing-admin@example.test")
        self.assertFalse(owner.is_staff)
        self.assertEqual(owner.password, password_hash)
        self.assertEqual(profile.role, UserProfile.ROLE_READER)
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
        self.assertIn("Owner: existing active superuser existing-admin", output.getvalue())

    @override_settings(DEBUG=True)
    def test_existing_demo_user_is_not_overwritten(self):
        self._create_setup_owner()
        existing = User.objects.create_user(
            username="lorem",
            password="private-password",
            first_name="Existing",
            last_name="Person",
            email="existing@example.test",
            is_active=False,
            is_staff=True,
        )
        profile = UserProfile.objects.get(user=existing)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        shelf = Shelf.objects.create(
            name="Reading Queue",
            description="Existing shelf description.",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=existing,
            created_by=existing,
        )
        password_hash = existing.password

        call_command(
            "seed_dev_users",
            users=1,
            groups=1,
            verbosity=0,
        )

        existing.refresh_from_db()
        profile.refresh_from_db()
        shelf.refresh_from_db()
        self.assertEqual(existing.first_name, "Existing")
        self.assertEqual(existing.last_name, "Person")
        self.assertEqual(existing.email, "existing@example.test")
        self.assertFalse(existing.is_active)
        self.assertTrue(existing.is_staff)
        self.assertFalse(existing.is_superuser)
        self.assertEqual(existing.password, password_hash)
        self.assertEqual(profile.role, UserProfile.ROLE_READER)
        self.assertEqual(shelf.description, "Existing shelf description.")

    @override_settings(DEBUG=True)
    def test_simple_mode_has_users_public_memberships_and_no_custom_groups(self):
        self._create_setup_owner()

        call_command("seed_dev_users", skip_shelves=True, verbosity=0)

        public = get_public_group()
        self.assertEqual(public.name, "Common Room")
        self.assertEqual(
            User.objects.filter(
                username__in=[
                    "lorem",
                    "ipsum",
                    "dolor",
                    "sit",
                    "amet",
                    "consectetur",
                    "adipiscing",
                    "elit",
                    "sed",
                    "eiusmod",
                    "tempor",
                    "incididunt",
                    "labore",
                    "dolore",
                    "magna",
                    "aliqua",
                    "enim",
                    "minim",
                    "veniam",
                    "nostrud",
                ]
            ).count(),
            20,
        )
        self.assertEqual(LibraryGroup.objects.exclude(pk=public.pk).count(), 0)
        self.assertEqual(
            LibraryGroupMembership.objects.filter(
                user__username="dolor",
                group=public,
                is_curator=False,
            ).count(),
            1,
        )
        self.assertFalse(LibraryGroupMembership.objects.filter(is_curator=True).exists())
        self.assertEqual(
            list(
                LibraryGroupMembership.objects.filter(
                    user__username="consectetur",
                ).values_list("group_id", "is_curator")
            ),
            [(public.id, False)],
        )

    @override_settings(DEBUG=True)
    def test_simple_mode_creates_user_and_public_shelves_without_books(self):
        self._create_setup_owner()
        output = StringIO()

        call_command(
            "seed_dev_users",
            users=4,
            groups=2,
            verbosity=0,
            stdout=output,
        )

        public = get_public_group()
        self.assertEqual(Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_USER).count(), 8)
        self.assertEqual(
            Shelf.objects.filter(
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=public,
            ).count(),
            2,
        )
        self.assertEqual(LibraryGroup.objects.exclude(pk=public.pk).count(), 0)
        self.assertFalse(
            Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_GROUP)
            .exclude(owner_group=public)
            .exists()
        )
        self.assertSetEqual(
            set(
                Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_GROUP).values_list(
                    "name",
                    flat=True,
                )
            ),
            {
                "Common Room: Welcome Shelf",
                "Common Room: Community Favorites",
            },
        )
        self.assertEqual(ShelfItem.objects.count(), 0)
        self.assertIn("No books found; shelf item population skipped.", output.getvalue())
        self.assertIn("Book population: skipped because no books exist.", output.getvalue())

    @override_settings(DEBUG=True)
    def test_simple_mode_populates_public_and_user_shelves_without_custom_groups(self):
        self._create_setup_owner()
        for index in range(12):
            create_file_backed_book(
                title=f"Fixture Book {index:02d}",
                epub_bytes=f"simple-book-{index}".encode(),
                source_filename=f"simple-book-{index}.epub",
            )

        output = StringIO()
        call_command(
            "seed_dev_users",
            users=4,
            groups=2,
            seed="fixture-seed",
            verbosity=0,
            stdout=output,
        )

        public = get_public_group()
        self.assertEqual(LibraryGroup.objects.exclude(pk=public.pk).count(), 0)
        self.assertFalse(BookGroupAssignment.objects.exclude(group=public).exists())
        self.assertTrue(ShelfItem.objects.exists())
        self.assertIn("Book population seed: fixture-seed", output.getvalue())

    @override_settings(DEBUG=True)
    def test_advanced_mode_creates_custom_groups_memberships_shelves_and_assignments(self):
        self._create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        for index in range(12):
            create_file_backed_book(
                title=f"Fixture Book {index:02d}",
                epub_bytes=f"book-{index}".encode(),
                source_filename=f"book-{index}.epub",
            )

        first_output = StringIO()
        call_command(
            "seed_dev_users",
            users=4,
            groups=2,
            seed="fixture-seed",
            verbosity=0,
            stdout=first_output,
        )

        public = get_public_group()
        self.assertEqual(
            LibraryGroup.objects.filter(
                name__in=["Fantasy Club", "Mystery Annex"],
            ).count(),
            2,
        )
        self.assertTrue(
            LibraryGroupMembership.objects.filter(is_curator=True)
            .exclude(group=public)
            .exists()
        )
        self.assertEqual(
            Shelf.objects.filter(
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group__name__in=["Fantasy Club", "Mystery Annex"],
            ).count(),
            4,
        )
        self.assertTrue(BookGroupAssignment.objects.exclude(group=public).exists())

        shelf_ids = list(Shelf.objects.values_list("id", flat=True))
        first_items = set(ShelfItem.objects.values_list("shelf_id", "book_id"))
        self.assertTrue(first_items)
        for shelf_id in shelf_ids:
            items = list(
                ShelfItem.objects.filter(shelf_id=shelf_id).values_list(
                    "book_id",
                    flat=True,
                )
            )
            self.assertGreaterEqual(len(items), 5)
            self.assertLessEqual(len(items), 10)
            self.assertEqual(len(items), len(set(items)))

        second_output = StringIO()
        call_command(
            "seed_dev_users",
            users=4,
            groups=2,
            seed="fixture-seed",
            verbosity=0,
            stdout=second_output,
        )

        self.assertEqual(Shelf.objects.count(), len(shelf_ids))
        self.assertEqual(
            set(ShelfItem.objects.values_list("shelf_id", "book_id")),
            first_items,
        )
        self.assertEqual(
            LibraryGroupMembership.objects.count(),
            LibraryGroupMembership.objects.values("user_id", "group_id")
            .distinct()
            .count(),
        )
        self.assertIn("Shelf items added: 0", second_output.getvalue())
        self.assertIn("Users: 0 created, 4 existing/skipped", second_output.getvalue())
        self.assertIn("Groups: 0 created, 2 existing/skipped", second_output.getvalue())

    @override_settings(DEBUG=True)
    def test_existing_reader_membership_is_not_promoted_to_curator(self):
        self._create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        existing = User.objects.create_user(
            username="lorem",
            password="private-password",
        )
        profile = UserProfile.objects.get(user=existing)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        fantasy = LibraryGroup.objects.create(name="Fantasy Club")
        membership = LibraryGroupMembership.objects.create(
            user=existing,
            group=fantasy,
            is_curator=False,
        )

        call_command(
            "seed_dev_users",
            users=1,
            groups=1,
            skip_shelves=True,
            verbosity=0,
        )

        membership.refresh_from_db()
        self.assertFalse(membership.is_curator)

    @override_settings(DEBUG=True)
    def test_existing_broad_role_membership_is_preserved(self):
        self._create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        existing = User.objects.create_user(
            username="consectetur",
            password="private-password",
        )
        profile = UserProfile.objects.get(user=existing)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])
        fantasy = LibraryGroup.objects.create(name="Fantasy Club")
        membership = LibraryGroupMembership.objects.create(
            user=existing,
            group=fantasy,
            is_curator=False,
        )

        call_command(
            "seed_dev_users",
            users=6,
            groups=1,
            skip_shelves=True,
            verbosity=0,
        )

        membership.refresh_from_db()
        self.assertFalse(membership.is_curator)
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=existing,
                group=get_public_group(),
                is_curator=False,
            ).exists()
        )
