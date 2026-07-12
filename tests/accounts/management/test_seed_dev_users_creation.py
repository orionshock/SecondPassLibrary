from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import override_settings

from accounts.models import UserProfile
from library.groups.public_group import get_public_group
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from tests.accounts.management.helpers import SeedDevUsersCommandTestCase, User
from tests.utils.books import create_file_backed_book


class SeedDevUsersCreationTests(SeedDevUsersCommandTestCase):
    @override_settings(DEBUG=True)
    def test_existing_active_superuser_is_left_unchanged(self):
        owner = self.create_setup_owner(username="existing-admin")
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
        self.assertIn(
            "Owner: existing active superuser existing-admin", output.getvalue()
        )

    @override_settings(DEBUG=True)
    def test_simple_mode_has_users_public_memberships_and_no_custom_groups(self):
        self.create_setup_owner()

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
        self.assertFalse(
            LibraryGroupMembership.objects.filter(is_curator=True).exists()
        )
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
        self.create_setup_owner()
        output = StringIO()

        call_command(
            "seed_dev_users",
            users=4,
            groups=2,
            verbosity=0,
            stdout=output,
        )

        public = get_public_group()
        self.assertEqual(
            Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_USER).count(), 8
        )
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
        self.assertIn(
            "No books found; shelf item population skipped.", output.getvalue()
        )
        self.assertIn(
            "Book population: skipped because no books exist.", output.getvalue()
        )

    @override_settings(DEBUG=True)
    def test_simple_mode_populates_public_and_user_shelves_without_custom_groups(self):
        self.create_setup_owner()
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
