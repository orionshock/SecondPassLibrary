from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core import server_settings
from library.groups.consolidation import (
    AdvancedGroupsConsolidationError,
    AdvancedGroupsPlanStale,
    build_advanced_groups_disable_plan,
    execute_advanced_groups_disable_plan,
)
from library.groups.public_group import get_public_group
from library.groups.services import ensure_user_public_membership
from library.models import (
    BookFile,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from reading.models import Annotation, ReadingProgress, ReadingSession
from shelves.models import Shelf, ShelfItem
from tests.utils.books import create_file_backed_book
from tests.testenv.filesystem import IsolatedMediaRootMixin


User = get_user_model()


class AdvancedGroupsConsolidationPlanTest(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.public = get_public_group()
        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.owner)
        server_settings.set_advanced_library_groups_enabled(True)

    def test_plan_identifies_custom_group_state_only(self):
        group = LibraryGroup.objects.create(name="Bedroom")
        public_shelf = Shelf.objects.create(
            name="Bedroom / Favorites",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.public,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.owner,
        )
        custom_shelf = Shelf.objects.create(
            name="Favorites",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.owner,
        )
        book = create_file_backed_book(title="Hidden Book", assign_public=False).book
        BookGroupAssignment.objects.create(book=book, group=group, added_by=self.owner)
        member = User.objects.create_user(username="member", password="pw")
        LibraryGroupMembership.objects.create(user=member, group=group, is_curator=True)
        LibraryGroupMembership.objects.filter(user=member, group=self.public).delete()

        plan = build_advanced_groups_disable_plan()

        self.assertEqual(plan.summary["custom_groups"], 1)
        self.assertEqual(plan.summary["shelves_moved"], 1)
        self.assertEqual(plan.shelf_moves[0].shelf_id, str(custom_shelf.id))
        self.assertEqual(plan.shelf_moves[0].new_name, "Bedroom / Favorites")
        self.assertTrue(plan.shelf_moves[0].name_collision)
        self.assertEqual(plan.book_public_fallbacks[0].title, "Hidden Book")
        self.assertEqual(plan.user_public_fallbacks[0].username, "member")
        self.assertEqual(plan.group_deletions[0].name, "Bedroom")
        self.assertNotEqual(plan.shelf_moves[0].shelf_id, str(public_shelf.id))
        self.assertEqual(
            plan.phases,
            (
                "Rename shelves",
                "Move shelves to Public Library",
                "Remove non-Public book/group associations and restore orphaned books to Public",
                "Remove group users/memberships/curators and restore orphaned users to Public",
                "Delete custom groups",
                "Disable advanced groups",
            ),
        )

    def test_blank_group_name_gets_defensive_display_name(self):
        group = LibraryGroup.objects.create(name=" ")
        Shelf.objects.create(
            name="Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.owner,
        )

        plan = build_advanced_groups_disable_plan()

        self.assertTrue(plan.shelf_moves[0].new_name.startswith("Unnamed group "))


class AdvancedGroupsConsolidationExecutionTest(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.public = get_public_group()
        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.owner)
        server_settings.set_advanced_library_groups_enabled(True)

    def _custom_group_fixture(self):
        group = LibraryGroup.objects.create(name="Bedroom")
        member = User.objects.create_user(username="member", password="pw")
        ensure_user_public_membership(user=member)
        LibraryGroupMembership.objects.create(user=member, group=group, is_curator=True)
        LibraryGroupMembership.objects.filter(user=member, group=self.public).delete()

        backed = create_file_backed_book(title="Only Custom", assign_public=False)
        book = backed.book
        BookGroupAssignment.objects.create(book=book, group=group, added_by=self.owner)

        session = ReadingSession.objects.create(user=member, book=book)
        ReadingProgress.objects.create(
            session=session,
            current_location={"cfi": "/6/2"},
            progression=0.25,
        )
        annotation = Annotation.objects.create(
            session=session,
            book=book,
            book_file=backed.book_file,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            anchor_kind=Annotation.ANCHOR_KIND_BOOKMARK,
            selector_value="epubcfi(/6/2)",
        )

        shelf = Shelf.objects.create(
            name="Favorites",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.owner,
        )
        item = ShelfItem.objects.create(
            shelf=shelf, book=book, position=7, added_by=self.owner
        )
        return group, member, backed.book_file, session, annotation, shelf, item

    def test_execute_consolidates_by_phase_and_preserves_user_value(self):
        group, member, book_file, session, annotation, shelf, item = (
            self._custom_group_fixture()
        )
        plan = build_advanced_groups_disable_plan()

        with self.assertLogs("library.groups.consolidation", level="INFO") as logs:
            result = execute_advanced_groups_disable_plan(
                actor=self.owner,
                expected_fingerprint=plan.fingerprint,
            )

        self.assertEqual(result.summary["custom_groups"], 1)
        output = "\n".join(logs.output)
        self.assertIn("advanced groups recovery started", output)
        self.assertIn("advanced groups recovery shelves moved count=1", output)
        self.assertIn(
            "book assignments removed count=1 books_public_fallback=1", output
        )
        self.assertIn(
            "memberships removed count=1 curator_assignments_removed=1 users_public_fallback=1",
            output,
        )
        self.assertIn("advanced groups recovery groups deleted count=1", output)
        self.assertIn("advanced groups recovery completed duration_ms=", output)
        self.assertFalse(server_settings.advanced_library_groups_enabled())
        self.assertFalse(LibraryGroup.objects.filter(pk=group.pk).exists())
        self.assertFalse(BookGroupAssignment.objects.filter(group_id=group.pk).exists())
        self.assertFalse(
            LibraryGroupMembership.objects.filter(group_id=group.pk).exists()
        )

        shelf.refresh_from_db()
        self.assertEqual(shelf.name, "Bedroom / Favorites")
        self.assertEqual(shelf.owner_group_id, self.public.id)
        self.assertEqual(shelf.owner_type, Shelf.OWNER_TYPE_GROUP)
        self.assertIsNone(shelf.owner_user_id)
        self.assertTrue(
            ShelfItem.objects.filter(pk=item.pk, shelf=shelf, position=7).exists()
        )

        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=book_file.book, group=self.public
            ).exists()
        )
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=member, group=self.public
            ).exists()
        )
        self.assertTrue(BookFile.objects.filter(pk=book_file.pk).exists())
        self.assertTrue(ReadingSession.objects.filter(pk=session.pk).exists())
        self.assertTrue(ReadingProgress.objects.filter(session=session).exists())
        self.assertTrue(Annotation.objects.filter(pk=annotation.pk).exists())

    def test_execute_aborts_on_stale_fingerprint(self):
        self._custom_group_fixture()

        with self.assertRaises(AdvancedGroupsPlanStale):
            execute_advanced_groups_disable_plan(
                actor=self.owner,
                expected_fingerprint="stale",
            )

        self.assertTrue(server_settings.advanced_library_groups_enabled())

    def test_late_failure_rolls_back_consolidation(self):
        group, member, _book_file, _session, _annotation, shelf, item = (
            self._custom_group_fixture()
        )

        with (
            patch(
                "library.groups.consolidation.delete_library_group",
                side_effect=AdvancedGroupsConsolidationError("boom"),
            ),
            patch(
                "library.groups.consolidation_logging.logger.exception"
            ) as log_failure,
        ):
            with self.assertRaises(AdvancedGroupsConsolidationError):
                execute_advanced_groups_disable_plan(actor=self.owner)

        log_failure.assert_called_once_with("advanced groups recovery failed")
        self.assertTrue(server_settings.advanced_library_groups_enabled())
        shelf.refresh_from_db()
        self.assertEqual(shelf.name, "Favorites")
        self.assertEqual(shelf.owner_group_id, group.id)
        self.assertTrue(ShelfItem.objects.filter(pk=item.pk, shelf=shelf).exists())
        self.assertTrue(BookGroupAssignment.objects.filter(group=group).exists())
        self.assertTrue(
            LibraryGroupMembership.objects.filter(user=member, group=group).exists()
        )
        self.assertTrue(LibraryGroup.objects.filter(pk=group.pk).exists())
