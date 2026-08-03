from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import override_settings

from accounts.models import UserProfile
from core import server_settings
from library.groups.public_group import get_public_group
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from tests.accounts.management.helpers import SeedDevUsersCommandTestCase, User
from tests.utils.books import create_file_backed_book


class SeedDevUsersIdempotencyTests(SeedDevUsersCommandTestCase):
    @override_settings(DEBUG=True)
    def test_existing_demo_user_is_not_overwritten(self):
        self.create_setup_owner()
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
    def test_unrelated_existing_favorites_shelf_is_not_commandeered(self):
        self.create_setup_owner()
        librarian = User.objects.create_user(username="elit", password="private-password")
        profile = UserProfile.objects.get(user=librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        favorites = Shelf.objects.create(
            name="Favorites",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=librarian,
            created_by=librarian,
            visibility=Shelf.VISIBILITY_PRIVATE,
        )

        call_command(
            "seed_dev_users",
            users=8,
            groups=1,
            verbosity=0,
        )

        favorites.refresh_from_db()
        self.assertEqual(favorites.visibility, Shelf.VISIBILITY_PRIVATE)
        self.assertEqual(
            Shelf.objects.filter(
                owner_user=librarian,
                name="Favorites",
                visibility=Shelf.VISIBILITY_LISTED,
            ).count(),
            1,
        )

    @override_settings(DEBUG=True)
    def test_advanced_mode_creates_custom_groups_memberships_shelves_and_assignments(
        self,
    ):
        self.create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        for index in range(12):
            create_file_backed_book(
                title=f"Fixture Book {index:02d}",
                epub_bytes=f"book-{index}".encode(),
                source_filename=f"book-{index}.epub",
                assign_public=False,
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
            self.assertGreaterEqual(len(items), 1)
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
