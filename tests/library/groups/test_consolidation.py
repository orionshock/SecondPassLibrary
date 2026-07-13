from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core import server_settings
from core.server_settings import set_server_setting
from library.groups import consolidation
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.groups.memberships import add_user_to_group
from library.groups.book_assignments import add_book_to_group
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


class AdvancedGroupsConsolidationTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="owner",
            password="pw",
        )
        self.public = LibraryGroup.objects.create(name="Configured Common Room")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="Public/Common Room group id.",
        )
        server_settings.set_advanced_library_groups_enabled(True)
        add_user_to_group(user=self.owner, group=self.public)

    def _group(self, name="Custom"):
        return LibraryGroup.objects.create(name=name)

    def _book(self, title):
        return create_file_backed_book(title=title, assign_public=False).book

    def _execute(self):
        plan = consolidation.build_advanced_groups_disable_plan()
        return consolidation.execute_advanced_groups_disable_plan(
            actor=self.owner,
            expected_fingerprint=plan.fingerprint,
        )

    def test_shelves_move_before_book_removal_and_preserve_rows_and_item_order(self):
        group = self._group()
        book_a = self._book("A")
        book_b = self._book("B")
        add_book_to_group(book=book_a, group=group)
        add_book_to_group(book=book_b, group=group)
        shelf = Shelf.objects.create(
            name="Favorites",
            description="Keep this",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.owner,
        )
        ShelfItem.objects.create(shelf=shelf, book=book_a, position=4, added_by=self.owner)
        ShelfItem.objects.create(shelf=shelf, book=book_b, position=1, added_by=self.owner)
        Shelf.objects.create(
            name="Custom / Favorites",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.public,
        )
        original_remove = consolidation.remove_book_from_group
        observed_owner_ids = []

        def observe_remove(**kwargs):
            observed_owner_ids.append(
                Shelf.objects.get(pk=shelf.pk).owner_group_id
            )
            return original_remove(**kwargs)

        with patch(
            "library.groups.consolidation.remove_book_from_group",
            side_effect=observe_remove,
        ):
            result = self._execute()

        shelf.refresh_from_db()
        self.assertEqual(observed_owner_ids, [self.public.id, self.public.id])
        self.assertEqual(shelf.owner_group, self.public)
        self.assertEqual(shelf.name, "Custom / Favorites (2)")
        self.assertEqual(result.summary.shelf_name_collisions, 1)
        self.assertEqual(shelf.description, "Keep this")
        self.assertEqual(shelf.created_by, self.owner)
        self.assertEqual(shelf.visibility, Shelf.VISIBILITY_PRIVATE)
        self.assertEqual(
            list(shelf.items.order_by("position").values_list("position", flat=True)),
            [1, 4],
        )

    def test_book_fallback_happens_only_after_last_group_is_removed(self):
        alpha = self._group("Alpha")
        beta = self._group("Beta")
        book = self._book("Shared custom book")
        add_book_to_group(book=book, group=alpha)
        add_book_to_group(book=book, group=beta)
        original_remove = consolidation.remove_book_from_group
        snapshots = []

        def observe_remove(**kwargs):
            result = original_remove(**kwargs)
            snapshots.append(
                set(
                    BookGroupAssignment.objects.filter(book=book).values_list(
                        "group__name", flat=True
                    )
                )
            )
            return result

        with patch(
            "library.groups.consolidation.remove_book_from_group",
            side_effect=observe_remove,
        ):
            self._execute()

        self.assertEqual(snapshots[0], {"Beta"})
        self.assertEqual(snapshots[1], {self.public.name})

    def test_user_fallback_is_public_and_never_curator(self):
        alpha = self._group("Alpha")
        beta = self._group("Beta")
        reader = get_user_model().objects.create_user(username="reader")
        add_user_to_group(user=reader, group=alpha, is_curator=True)
        add_user_to_group(user=reader, group=beta)
        original_remove = consolidation.remove_user_from_group
        snapshots = []

        def observe_remove(**kwargs):
            result = original_remove(**kwargs)
            snapshots.append(
                list(
                    LibraryGroupMembership.objects.filter(user=reader).values_list(
                        "group__name", "is_curator"
                    )
                )
            )
            return result

        with patch(
            "library.groups.consolidation.remove_user_from_group",
            side_effect=observe_remove,
        ):
            self._execute()

        self.assertEqual(snapshots[0], [("Beta", False)])
        self.assertEqual(snapshots[1], [(self.public.name, False)])

    def test_public_curator_state_is_repaired_with_warning(self):
        LibraryGroupMembership.objects.filter(
            user=self.owner,
            group=self.public,
        ).update(is_curator=True)

        with self.assertLogs(consolidation.logger, level="WARNING") as captured:
            result = self._execute()

        membership = LibraryGroupMembership.objects.get(
            user=self.owner,
            group=self.public,
        )
        self.assertFalse(membership.is_curator)
        self.assertEqual(result.public_curators_cleared, 1)
        self.assertIn("invalid curator membership", captured.output[0])

    def test_custom_group_is_deleted_through_service_only_after_emptying(self):
        group = self._group()
        reader = get_user_model().objects.create_user(username="reader")
        book = self._book("Book")
        add_user_to_group(user=reader, group=group)
        add_book_to_group(book=book, group=group)
        Shelf.objects.create(
            name="Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
        )
        original_delete = consolidation.delete_library_group
        observed = []

        def observe_delete(**kwargs):
            target = kwargs["group"]
            observed.append(
                (
                    target.shelves_owned.count(),
                    target.book_assignments.count(),
                    target.memberships.count(),
                )
            )
            return original_delete(**kwargs)

        with patch(
            "library.groups.consolidation.delete_library_group",
            side_effect=observe_delete,
        ):
            self._execute()

        self.assertEqual(observed, [(0, 0, 0)])
        self.assertFalse(LibraryGroup.objects.filter(pk=group.pk).exists())

    def test_stale_fingerprint_is_rejected_without_changes(self):
        group = self._group()
        plan = consolidation.build_advanced_groups_disable_plan()
        Shelf.objects.create(
            name="Changed after preview",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
        )

        with self.assertRaises(consolidation.AdvancedGroupsPlanStale):
            consolidation.execute_advanced_groups_disable_plan(
                actor=self.owner,
                expected_fingerprint=plan.fingerprint,
            )

        self.assertTrue(LibraryGroup.objects.filter(pk=group.pk).exists())
        self.assertTrue(server_settings.advanced_library_groups_enabled())

    def test_mid_process_failure_rolls_back_every_change_and_setting(self):
        group = self._group()
        reader = get_user_model().objects.create_user(username="reader")
        book = self._book("Book")
        add_user_to_group(user=reader, group=group)
        add_book_to_group(book=book, group=group)
        shelf = Shelf.objects.create(
            name="Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
        )
        plan = consolidation.build_advanced_groups_disable_plan()

        with (
            patch(
                "library.groups.consolidation.remove_user_from_group",
                side_effect=RuntimeError("forced failure"),
            ),
            self.assertRaises(consolidation.AdvancedGroupsConsolidationError),
        ):
            consolidation.execute_advanced_groups_disable_plan(
                actor=self.owner,
                expected_fingerprint=plan.fingerprint,
            )

        shelf.refresh_from_db()
        self.assertEqual(shelf.owner_group, group)
        self.assertEqual(shelf.name, "Shelf")
        self.assertTrue(BookGroupAssignment.objects.filter(book=book, group=group).exists())
        self.assertTrue(
            LibraryGroupMembership.objects.filter(user=reader, group=group).exists()
        )
        self.assertTrue(LibraryGroup.objects.filter(pk=group.pk).exists())
        self.assertTrue(server_settings.advanced_library_groups_enabled())

    def test_configured_public_uuid_wins_over_public_like_name(self):
        decoy = LibraryGroup.objects.create(name="Public")
        group = self._group()
        shelf = Shelf.objects.create(
            name="Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
        )

        result = self._execute()

        shelf.refresh_from_db()
        self.assertEqual(result.plan.public_group_id, str(self.public.id))
        self.assertEqual(shelf.owner_group, self.public)
        self.assertFalse(LibraryGroup.objects.filter(pk=decoy.pk).exists())
        self.assertFalse(server_settings.advanced_library_groups_enabled())
