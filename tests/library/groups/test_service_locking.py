from __future__ import annotations

from unittest.mock import patch

from core.models import ServerSetting
from library.groups import services
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import BookGroupAssignment, LibraryGroupMembership
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase


def _constraint_fields(model, name: str) -> list[str]:
    for constraint in model._meta.constraints:
        if constraint.name == name:
            return list(constraint.fields)
    return []


class LibraryGroupConstraintTests(LibraryGroupServiceTestCase):
    def test_required_uniqueness_constraints_exist(self):
        self.assertEqual(
            _constraint_fields(
                LibraryGroupMembership,
                "unique_user_library_group_membership",
            ),
            ["user", "group"],
        )
        self.assertEqual(
            _constraint_fields(
                BookGroupAssignment,
                "unique_book_library_group_assignment",
            ),
            ["book", "group"],
        )
        self.assertTrue(ServerSetting._meta.get_field("key").unique)


class LibraryGroupServiceLockingTests(LibraryGroupServiceTestCase):
    def test_membership_mutations_lock_target_user(self):
        group = services.create_library_group(name="Lock Room")

        with patch(
            "library.groups.services._lock_user_for_group_mutation",
            wraps=services._lock_user_for_group_mutation,
        ) as lock_user:
            membership = services.add_user_to_group(user=self.user, group=group)
            services.set_group_membership_curator(
                membership=membership,
                is_curator=True,
            )
            services.remove_user_from_group(user=self.user, group=group)

        self.assertEqual(lock_user.call_count, 3)
        self.assertEqual(
            [call.args[0].pk for call in lock_user.call_args_list],
            [self.user.pk, self.user.pk, self.user.pk],
        )

    def test_membership_fallback_paths_lock_target_user_and_keep_noop_behavior(self):
        group = services.create_library_group(name="Missing Membership Room")

        with patch(
            "library.groups.services._lock_user_for_group_mutation",
            wraps=services._lock_user_for_group_mutation,
        ) as lock_user:
            removed = services.remove_user_from_group(user=self.user, group=group)

        self.assertFalse(removed)
        self.assertEqual(lock_user.call_count, 1)
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=self.user,
                group=self.public,
            ).exists()
        )

    def test_book_assignment_mutations_lock_target_book(self):
        group = services.create_library_group(name="Book Lock Room")

        with patch(
            "library.groups.services._lock_book_for_group_assignment",
            wraps=services._lock_book_for_group_assignment,
        ) as lock_book:
            services.add_book_to_group(book=self.book, group=group, actor=self.actor)
            services.remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertEqual(lock_book.call_count, 2)
        self.assertEqual(
            [call.args[0].pk for call in lock_book.call_args_list],
            [self.book.pk, self.book.pk],
        )

    def test_book_assignment_fallback_paths_lock_target_book_and_keep_noop_behavior(self):
        group = services.create_library_group(name="Missing Assignment Room")

        with patch(
            "library.groups.services._lock_book_for_group_assignment",
            wraps=services._lock_book_for_group_assignment,
        ) as lock_book:
            removed = services.remove_book_from_group(
                book=self.book,
                group=group,
                actor=self.actor,
            )

        self.assertFalse(removed)
        self.assertEqual(lock_book.call_count, 1)
        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=self.book,
                group=self.public,
            ).exists()
        )

    def test_public_reassignment_locks_public_group_setting_row(self):
        group = services.create_library_group(name="Next Public")

        with patch(
            "library.groups.services._lock_public_group_setting",
            wraps=services._lock_public_group_setting,
        ) as lock_setting:
            services.set_public_group_identity(group=group)

        lock_setting.assert_called_once_with()
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertEqual(setting.value, str(group.pk))
