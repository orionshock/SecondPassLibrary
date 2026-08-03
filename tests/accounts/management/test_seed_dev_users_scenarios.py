from __future__ import annotations

from io import StringIO
import re

from django.core.management import call_command
from django.db.models import Count
from django.test import override_settings

from accounts.models import UserProfile
from core import server_settings
from library.groups.public_group import get_public_group
from library.models import (
    Book,
    BookCatalogTag,
    BookGroupAssignment,
    CatalogTag,
    LibraryGroup,
    LibraryGroupMembership,
)
from shelves.models import Shelf, ShelfItem
from tests.accounts.management.helpers import SeedDevUsersCommandTestCase, User
from tests.utils.books import create_file_backed_book


class SeedDevUsersScenarioTests(SeedDevUsersCommandTestCase):
    @staticmethod
    def _create_books(count: int, *, assign_public: bool) -> list[Book]:
        return [
            create_file_backed_book(
                title=f"Scenario Book {index:02d}",
                epub_bytes=f"scenario-book-{index}".encode(),
                source_filename=f"scenario-book-{index}.epub",
                assign_public=assign_public,
            ).book
            for index in range(count)
        ]

    @staticmethod
    def _summary_value(output: str, label: str) -> str:
        match = re.search(rf"^{re.escape(label)}: (.+)$", output, re.MULTILINE)
        if match is None:
            raise AssertionError(f"Missing summary label: {label}")
        return match.group(1)

    @override_settings(DEBUG=True)
    def test_advanced_world_has_exclusive_overlap_curators_and_valid_group_shelves(
        self,
    ):
        self.create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        books = self._create_books(18, assign_public=False)
        tag = CatalogTag.objects.create(
            name="Fixture Speculative Fiction",
            sort_name="Fixture Speculative Fiction",
            normalized_name="fixture speculative fiction",
            slug="fixture-speculative-fiction",
        )
        for book in books[:8]:
            BookCatalogTag.objects.create(book=book, catalog_tag=tag)
        output = StringIO()

        call_command(
            "seed_dev_users",
            users=10,
            groups=3,
            seed="scenario-seed",
            verbosity=0,
            stdout=output,
        )

        summary = output.getvalue()
        public = get_public_group()
        exclusive_group = LibraryGroup.objects.get(
            name=self._summary_value(summary, "Exclusive Group")
        )
        exclusive_usernames = self._summary_value(
            summary,
            "Exclusive users",
        ).split(", ")
        overlapping_username = self._summary_value(summary, "Overlapping user")

        self.assertGreaterEqual(len(exclusive_usernames), 2)
        for username in exclusive_usernames:
            self.assertEqual(
                list(
                    LibraryGroupMembership.objects.filter(
                        user__username=username
                    ).values_list("group_id", flat=True)
                ),
                [exclusive_group.pk],
            )

        overlapping_group_ids = set(
            LibraryGroupMembership.objects.filter(
                user__username=overlapping_username,
            ).values_list("group_id", flat=True)
        )
        self.assertIn(exclusive_group.pk, overlapping_group_ids)
        self.assertTrue(
            overlapping_group_ids
            - {
                exclusive_group.pk,
                public.pk,
            }
        )

        demo_user_memberships = [
            set(
                LibraryGroupMembership.objects.filter(user=user).values_list(
                    "group_id",
                    flat=True,
                )
            )
            for user in User.objects.filter(is_superuser=False)
        ]
        self.assertIn({public.pk}, demo_user_memberships)
        self.assertTrue(
            any(
                public.pk in memberships
                and len(memberships - {public.pk}) == 1
                for memberships in demo_user_memberships
            )
        )
        self.assertTrue(
            any(
                len(memberships - {public.pk}) >= 2
                for memberships in demo_user_memberships
            )
        )

        exclusive_books = Book.objects.annotate(
            assignment_count=Count("group_assignments__group", distinct=True)
        ).filter(
            group_assignments__group=exclusive_group,
            assignment_count=1,
        )
        self.assertTrue(exclusive_books.exists())
        self.assertFalse(
            BookGroupAssignment.objects.filter(book__in=exclusive_books)
            .exclude(group=exclusive_group)
            .exists()
        )

        demo_groups = LibraryGroup.objects.exclude(pk=public.pk)
        self.assertFalse(
            demo_groups.exclude(memberships__is_curator=True).exists()
        )
        curator_roles = set(
            LibraryGroupMembership.objects.filter(
                group__in=demo_groups,
                is_curator=True,
            ).values_list("user__profile__role", flat=True)
        )
        self.assertTrue(
            {
                UserProfile.ROLE_READER,
                UserProfile.ROLE_LIBRARIAN,
                UserProfile.ROLE_MANAGER,
            }.issubset(curator_roles)
        )

        shared_books = (
            Book.objects.annotate(
                assignment_count=Count("group_assignments__group", distinct=True)
            )
            .filter(assignment_count__gte=2)
            .count()
        )
        self.assertGreaterEqual(shared_books, 1)
        for group in demo_groups.exclude(pk=exclusive_group.pk):
            self.assertTrue(
                Book.objects.annotate(
                    assignment_count=Count(
                        "group_assignments__group",
                        distinct=True,
                    )
                )
                .filter(
                    group_assignments__group=group,
                    assignment_count=1,
                )
                .exists()
            )

        for item in ShelfItem.objects.filter(
            shelf__owner_type=Shelf.OWNER_TYPE_GROUP
        ).select_related("shelf__owner_group"):
            self.assertTrue(
                BookGroupAssignment.objects.filter(
                    book=item.book,
                    group=item.shelf.owner_group,
                ).exists()
            )
        self.assertFalse(Shelf.objects.filter(name__contains=":").exists())
        self.assertRegex(
            summary,
            r"Book selection: [1-9][0-9]* metadata pools",
        )
        self.assertIn("Scenario shortfalls: none", summary)

    @override_settings(DEBUG=True)
    def test_same_seed_rerun_converges_without_new_relationships(self):
        self.create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        self._create_books(18, assign_public=False)
        options = {
            "users": 10,
            "groups": 3,
            "seed": "repeatable-world",
            "verbosity": 0,
        }

        first_output = StringIO()
        call_command("seed_dev_users", stdout=first_output, **options)
        first_state = {
            "memberships": set(
                LibraryGroupMembership.objects.values_list(
                    "user_id",
                    "group_id",
                    "is_curator",
                )
            ),
            "assignments": set(
                BookGroupAssignment.objects.values_list("book_id", "group_id")
            ),
            "shelves": set(
                Shelf.objects.values_list(
                    "id",
                    "name",
                    "owner_user_id",
                    "owner_group_id",
                )
            ),
            "items": set(ShelfItem.objects.values_list("shelf_id", "book_id")),
        }

        second_output = StringIO()
        call_command("seed_dev_users", stdout=second_output, **options)

        self.assertEqual(
            first_state["memberships"],
            set(
                LibraryGroupMembership.objects.values_list(
                    "user_id",
                    "group_id",
                    "is_curator",
                )
            ),
        )
        self.assertEqual(
            first_state["assignments"],
            set(BookGroupAssignment.objects.values_list("book_id", "group_id")),
        )
        self.assertEqual(
            first_state["shelves"],
            set(
                Shelf.objects.values_list(
                    "id",
                    "name",
                    "owner_user_id",
                    "owner_group_id",
                )
            ),
        )
        current_items = set(ShelfItem.objects.values_list("shelf_id", "book_id"))
        self.assertEqual(
            first_state["items"],
            current_items,
        )
        self.assertIn("Shelf items added: 0", second_output.getvalue())
        self.assertIn("Book group assignments added: 0", second_output.getvalue())

    @override_settings(DEBUG=True)
    def test_simple_world_uses_only_public_books_and_public_group_shelves(self):
        self.create_setup_owner()
        self._create_books(8, assign_public=False)

        call_command(
            "seed_dev_users",
            users=4,
            groups=3,
            seed="simple-world",
            verbosity=0,
        )

        public = get_public_group()
        self.assertFalse(LibraryGroup.objects.exclude(pk=public.pk).exists())
        self.assertFalse(BookGroupAssignment.objects.exclude(group=public).exists())
        public_shelves = Shelf.objects.filter(
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=public,
        )
        self.assertSetEqual(
            set(public_shelves.values_list("name", flat=True)),
            {"Welcome Shelf", "Community Favorites"},
        )
        self.assertFalse(
            ShelfItem.objects.filter(shelf__in=public_shelves)
            .exclude(book__group_assignments__group=public)
            .exists()
        )
        self.assertTrue(ShelfItem.objects.filter(shelf__in=public_shelves).exists())

    @override_settings(DEBUG=True)
    def test_small_world_reports_shortfalls_instead_of_failing(self):
        self.create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        output = StringIO()

        call_command(
            "seed_dev_users",
            users=1,
            groups=1,
            seed="small-world",
            verbosity=0,
            stdout=output,
        )

        summary = output.getvalue()
        self.assertIn("Scenario shortfalls:", summary)
        self.assertIn("Exclusive Group needs two", summary)
        self.assertIn("Overlapping-user scenario", summary)
        self.assertIn("No unassigned or already-exclusive Books", summary)
        self.assertEqual(
            LibraryGroupMembership.objects.filter(is_curator=True).count(),
            1,
        )

    @override_settings(DEBUG=True)
    def test_unrelated_memberships_and_book_assignments_are_preserved(self):
        self.create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        public = get_public_group()
        unrelated_group = LibraryGroup.objects.create(
            name="Operator Group",
            description="Not managed by the demo command.",
        )
        existing = User.objects.create_user(username="lorem", password="private")
        unrelated_membership = LibraryGroupMembership.objects.create(
            user=existing,
            group=unrelated_group,
        )
        public_membership = LibraryGroupMembership.objects.create(
            user=existing,
            group=public,
        )
        operator_book = create_file_backed_book(
            title="Operator Book",
            epub_bytes=b"operator-book",
            source_filename="operator-book.epub",
        ).book
        unrelated_assignment = BookGroupAssignment.objects.create(
            book=operator_book,
            group=unrelated_group,
        )
        self._create_books(8, assign_public=False)

        call_command(
            "seed_dev_users",
            users=6,
            groups=3,
            seed="preserve-world",
            skip_shelves=True,
            verbosity=0,
        )

        self.assertTrue(
            LibraryGroupMembership.objects.filter(pk=unrelated_membership.pk).exists()
        )
        self.assertTrue(
            LibraryGroupMembership.objects.filter(pk=public_membership.pk).exists()
        )
        self.assertTrue(
            BookGroupAssignment.objects.filter(pk=unrelated_assignment.pk).exists()
        )
        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=operator_book,
                group=public,
            ).exists()
        )
        self.assertFalse(Shelf.objects.exists())
