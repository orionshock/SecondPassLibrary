from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import UserProfile
from library.group_services import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from tests.library.utils import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class SeedDevUsersCommandTests(IsolatedMediaRootMixin, TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_when_debug_false_unless_forced(self):
        with patch(
            "accounts.management.commands.seed_dev_users.call_command"
        ) as migrate_command:
            with self.assertRaises(CommandError):
                call_command("seed_dev_users")
        migrate_command.assert_not_called()

        call_command(
            "seed_dev_users",
            force=True,
            users=1,
            groups=1,
            skip_shelves=True,
            verbosity=0,
        )
        self.assertTrue(User.objects.filter(is_superuser=True, is_active=True).exists())

    @override_settings(DEBUG=True)
    def test_applies_migrations_before_seeding(self):
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
    def test_creates_owner_only_when_no_active_superuser_exists(self):
        call_command(
            "seed_dev_users",
            users=1,
            groups=1,
            skip_shelves=True,
            verbosity=0,
        )

        owner = User.objects.get(is_active=True, is_superuser=True)
        self.assertEqual(owner.username, "lorem-admin")
        self.assertTrue(owner.is_staff)
        self.assertTrue(owner.check_password("changeme123"))
        owner_profile = UserProfile.objects.get(user=owner)
        self.assertEqual(owner_profile.role, UserProfile.ROLE_MANAGER)
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=owner,
                group=get_public_group(),
                is_curator=False,
            ).exists()
        )

    @override_settings(DEBUG=True)
    def test_existing_active_superuser_is_left_unchanged(self):
        owner = User.objects.create_superuser(
            username="existing-admin",
            password="private-password",
            email="private@example.test",
        )
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
        self.assertEqual(owner.email, "private@example.test")
        self.assertFalse(owner.is_staff)
        self.assertEqual(owner.password, password_hash)
        self.assertEqual(profile.role, UserProfile.ROLE_READER)
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
        self.assertIn("existing active superuser existing-admin found; skipped", output.getvalue())

    @override_settings(DEBUG=True)
    def test_existing_demo_user_is_not_overwritten(self):
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
        fantasy = LibraryGroup.objects.create(
            name="Fantasy Club",
            description="Existing group description.",
        )
        membership = LibraryGroupMembership.objects.create(
            user=existing,
            group=fantasy,
            is_curator=False,
        )
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
        fantasy.refresh_from_db()
        membership.refresh_from_db()
        shelf.refresh_from_db()
        self.assertEqual(existing.first_name, "Existing")
        self.assertEqual(existing.last_name, "Person")
        self.assertEqual(existing.email, "existing@example.test")
        self.assertFalse(existing.is_active)
        self.assertTrue(existing.is_staff)
        self.assertFalse(existing.is_superuser)
        self.assertEqual(existing.password, password_hash)
        self.assertEqual(profile.role, UserProfile.ROLE_READER)
        self.assertEqual(fantasy.description, "Existing group description.")
        self.assertFalse(membership.is_curator)
        self.assertEqual(shelf.description, "Existing shelf description.")

    @override_settings(DEBUG=True)
    def test_default_world_has_users_groups_and_varied_memberships(self):
        call_command("seed_dev_users", skip_shelves=True, verbosity=0)

        public = get_public_group()
        self.assertEqual(public.name, "Common Room")
        self.assertEqual(
            public.description,
            "Main Public Library Room for everyone",
        )
        self.assertEqual(
            User.objects.filter(username__in=[
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
            ]).count(),
            20,
        )
        self.assertEqual(
            LibraryGroup.objects.filter(
                name__in=[
                    "Fantasy Club",
                    "Mystery Annex",
                    "Kids Books",
                    "Sci-Fi Stack",
                    "History Corner",
                ]
            ).count(),
            5,
        )

        lorem = User.objects.get(username="lorem")
        dolor = User.objects.get(username="dolor")
        manager = User.objects.get(username="consectetur")
        librarian = User.objects.get(username="elit")
        self.assertGreaterEqual(
            LibraryGroupMembership.objects.filter(user=lorem).count(),
            3,
        )
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=lorem,
                is_curator=True,
            ).exists()
        )
        self.assertEqual(
            list(
                LibraryGroupMembership.objects.filter(user=dolor).values_list(
                    "group__name",
                    flat=True,
                )
            ),
            ["Kids Books"],
        )
        self.assertFalse(
            LibraryGroupMembership.objects.filter(user=dolor, group=public).exists()
        )
        self.assertEqual(
            list(
                LibraryGroupMembership.objects.filter(user=manager).values_list(
                    "group_id",
                    "is_curator",
                )
            ),
            [(public.id, False)],
        )
        self.assertEqual(
            list(
                LibraryGroupMembership.objects.filter(user=librarian).values_list(
                    "group_id",
                    "is_curator",
                )
            ),
            [(public.id, False)],
        )
        self.assertFalse(
            LibraryGroupMembership.objects.filter(
                group=public,
                is_curator=True,
            ).exists()
        )
        curator_user_ids = LibraryGroupMembership.objects.filter(
            is_curator=True,
        ).values_list("user_id", flat=True)
        curator_profile_roles = set(
            UserProfile.objects.filter(user_id__in=curator_user_ids).values_list(
                "role",
                flat=True,
            )
        )
        self.assertEqual(curator_profile_roles, {UserProfile.ROLE_READER})
        self.assertFalse(
            LibraryGroupMembership.objects.filter(
                is_curator=True,
                user__profile__role=UserProfile.ROLE_MANAGER,
            ).exists()
        )
        self.assertFalse(
            LibraryGroupMembership.objects.filter(
                is_curator=True,
                user__profile__role=UserProfile.ROLE_LIBRARIAN,
            ).exists()
        )
        self.assertFalse(
            LibraryGroupMembership.objects.filter(
                user__profile__role__in=[
                    UserProfile.ROLE_MANAGER,
                    UserProfile.ROLE_LIBRARIAN,
                ],
                user__is_superuser=False,
            )
            .exclude(group=public)
            .exists()
        )
        self.assertFalse(
            LibraryGroupMembership.objects.filter(
                user__profile__role__in=[
                    UserProfile.ROLE_MANAGER,
                    UserProfile.ROLE_LIBRARIAN,
                ],
                user__is_superuser=False,
                is_curator=True,
            ).exists()
        )
        for group in LibraryGroup.objects.exclude(pk=public.pk):
            with self.subTest(group=group.name):
                self.assertTrue(
                    LibraryGroupMembership.objects.filter(
                        group=group,
                        is_curator=True,
                    ).exists()
                )

    @override_settings(DEBUG=True)
    def test_existing_reader_membership_is_not_promoted_to_curator(self):
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

    @override_settings(DEBUG=True)
    def test_creates_user_group_and_public_shelves_without_books(self):
        output = StringIO()
        call_command(
            "seed_dev_users",
            users=4,
            groups=2,
            verbosity=0,
            stdout=output,
        )

        self.assertEqual(
            Shelf.objects.filter(owner_type=Shelf.OWNER_TYPE_USER).count(),
            8,
        )
        self.assertEqual(
            Shelf.objects.filter(
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group__name__in=["Fantasy Club", "Mystery Annex"],
            ).count(),
            4,
        )
        self.assertEqual(
            Shelf.objects.filter(
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=get_public_group(),
            ).count(),
            2,
        )
        self.assertSetEqual(
            set(
                Shelf.objects.filter(
                    owner_type=Shelf.OWNER_TYPE_GROUP,
                ).values_list("name", flat=True)
            ),
            {
                "Fantasy Club: Staff Picks",
                "Fantasy Club: Current Favorites",
                "Mystery Annex: Staff Picks",
                "Mystery Annex: Current Favorites",
                "Common Room: Welcome Shelf",
                "Common Room: Community Favorites",
            },
        )
        self.assertEqual(ShelfItem.objects.count(), 0)
        self.assertIn("No books found; shelf item population skipped.", output.getvalue())
        self.assertIn("Book population: skipped because no books exist.", output.getvalue())

    @override_settings(DEBUG=True)
    def test_populates_shelves_deterministically_and_reruns_without_duplicates(self):
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

        shelf_ids = list(Shelf.objects.values_list("id", flat=True))
        first_items = set(
            ShelfItem.objects.values_list("shelf_id", "book_id")
        )
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

        self.assertEqual(
            Shelf.objects.count(),
            len(shelf_ids),
        )
        self.assertEqual(
            set(ShelfItem.objects.values_list("shelf_id", "book_id")),
            first_items,
        )
        self.assertEqual(
            LibraryGroupMembership.objects.count(),
            LibraryGroupMembership.objects.values("user_id", "group_id").distinct().count(),
        )
        self.assertIn("Shelf items added: 0", second_output.getvalue())
        self.assertIn("Users: 0 created, 4 existing/skipped", second_output.getvalue())
        self.assertIn("Groups: 0 created, 2 existing/skipped", second_output.getvalue())
