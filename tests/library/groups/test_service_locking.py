from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import OperationalError, connection
from django.test import TransactionTestCase

from core.models import ServerSetting
from core.server_settings import clear_server_settings_cache
from library.groups.book_assignments import add_book_to_group, remove_book_from_group
from library.groups.memberships import (
    add_user_to_group,
    remove_user_from_group,
    set_group_membership_curator,
)
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.groups.public_services import configure_public_group, set_public_group_identity
from library.groups.services import create_library_group
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase
from tests.testenv.database_connections import orm_worker_connection_scope


User = get_user_model()


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


@skipUnless(connection.vendor == "sqlite", "SQLite concurrency regression")
class LibraryGroupServiceConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        cache.clear()
        clear_server_settings_cache()
        self.actor = User.objects.create_user(username="actor", password="pw")
        self.user = User.objects.create_user(username="reader", password="pw")
        self.book = Book.objects.create(title="Concurrent Group Book")
        self.public = configure_public_group(name="Common Room", description="Shared")

    def test_concurrent_final_membership_removals_never_leave_user_without_group(self):
        first = create_library_group(name="First Room")
        second = create_library_group(name="Second Room")
        add_user_to_group(user=self.user, group=first)
        add_user_to_group(user=self.user, group=second)

        operations = (
            lambda: remove_user_from_group(
                user=self.user,
                group=first,
            ),
            lambda: remove_user_from_group(
                user=self.user,
                group=second,
            ),
        )
        outcomes = self._run_interleaved(
            operations,
            sync_points=((User._meta.db_table, 1),) * 2,
        )

        self.assertIn("retryable-lock", outcomes)
        memberships = LibraryGroupMembership.objects.filter(user=self.user)
        self.assertTrue(memberships.exists())

        self._retry_locked_operations(outcomes, operations)

        memberships = LibraryGroupMembership.objects.filter(user=self.user)
        self.assertFalse(memberships.filter(group__in=[first, second]).exists())
        self.assertEqual(memberships.filter(group=self.public).count(), 1)

    def test_concurrent_final_assignment_removals_never_leave_book_without_group(self):
        first = create_library_group(name="First Collection")
        second = create_library_group(name="Second Collection")
        add_book_to_group(book=self.book, group=first, actor=self.actor)
        add_book_to_group(book=self.book, group=second, actor=self.actor)

        operations = (
            lambda: remove_book_from_group(
                book=self.book,
                group=first,
                actor=self.actor,
            ),
            lambda: remove_book_from_group(
                book=self.book,
                group=second,
                actor=self.actor,
            ),
        )
        outcomes = self._run_interleaved(
            operations,
            sync_points=((Book._meta.db_table, 1),) * 2,
        )

        self.assertIn("retryable-lock", outcomes)
        assignments = BookGroupAssignment.objects.filter(book=self.book)
        self.assertTrue(assignments.exists())

        self._retry_locked_operations(outcomes, operations)

        assignments = BookGroupAssignment.objects.filter(book=self.book)
        self.assertFalse(assignments.filter(group__in=[first, second]).exists())
        self.assertEqual(assignments.filter(group=self.public).count(), 1)

    def test_concurrent_membership_add_and_final_removal_stay_serially_valid(self):
        first = create_library_group(name="Existing Room")
        second = create_library_group(name="Incoming Room")
        add_user_to_group(user=self.user, group=first)

        operations = (
            lambda: add_user_to_group(user=self.user, group=second),
            lambda: remove_user_from_group(user=self.user, group=first),
        )
        outcomes = self._run_interleaved(
            operations,
            sync_points=((User._meta.db_table, 1),) * 2,
        )

        self.assertIn("retryable-lock", outcomes)
        self.assertTrue(LibraryGroupMembership.objects.filter(user=self.user).exists())

        self._retry_locked_operations(outcomes, operations)

        group_ids = set(
            LibraryGroupMembership.objects.filter(user=self.user).values_list(
                "group_id", flat=True
            )
        )
        self.assertIn(group_ids, ({second.pk}, {self.public.pk, second.pk}))

    def test_concurrent_assignment_add_and_final_removal_stay_serially_valid(self):
        first = create_library_group(name="Existing Collection")
        second = create_library_group(name="Incoming Collection")
        add_book_to_group(book=self.book, group=first, actor=self.actor)

        operations = (
            lambda: add_book_to_group(book=self.book, group=second, actor=self.actor),
            lambda: remove_book_from_group(
                book=self.book,
                group=first,
                actor=self.actor,
            ),
        )
        outcomes = self._run_interleaved(
            operations,
            sync_points=((Book._meta.db_table, 1),) * 2,
        )

        self.assertIn("retryable-lock", outcomes)
        self.assertTrue(BookGroupAssignment.objects.filter(book=self.book).exists())

        self._retry_locked_operations(outcomes, operations)

        group_ids = set(
            BookGroupAssignment.objects.filter(book=self.book).values_list(
                "group_id", flat=True
            )
        )
        self.assertIn(group_ids, ({second.pk}, {self.public.pk, second.pk}))

    def test_concurrent_public_identity_changes_leave_valid_setting_and_retry_cleanly(self):
        first = create_library_group(name="First Public Candidate")
        second = create_library_group(name="Second Public Candidate")
        add_user_to_group(user=self.user, group=self.public)
        add_book_to_group(book=self.book, group=self.public, actor=self.actor)

        operations = (
            lambda: set_public_group_identity(group=first),
            lambda: set_public_group_identity(group=second),
        )
        outcomes = self._run_interleaved(
            operations,
            sync_points=((ServerSetting._meta.db_table, 2),) * 2,
        )

        self.assertIn("retryable-lock", outcomes)
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertIn(setting.value, {str(self.public.pk), str(first.pk), str(second.pk)})
        self.assertTrue(LibraryGroup.objects.filter(pk=setting.value).exists())

        self._retry_locked_operations(outcomes, operations)

        setting.refresh_from_db()
        self.assertIn(setting.value, {str(first.pk), str(second.pk)})
        self.assertTrue(LibraryGroup.objects.filter(pk=setting.value).exists())
        self.assertTrue(
            LibraryGroupMembership.objects.filter(user=self.user, group=self.public).exists()
        )
        self.assertTrue(
            BookGroupAssignment.objects.filter(book=self.book, group=self.public).exists()
        )

    def test_public_identity_and_curator_changes_cannot_create_public_curator(self):
        candidate = create_library_group(name="Public Candidate")
        membership = add_user_to_group(user=self.user, group=candidate)
        operations = (
            lambda: set_group_membership_curator(
                membership=LibraryGroupMembership.objects.get(pk=membership.pk),
                is_curator=True,
            ),
            lambda: set_public_group_identity(group=candidate),
        )
        outcomes = self._run_interleaved(
            operations,
            sync_points=(
                (User._meta.db_table, 1),
                (ServerSetting._meta.db_table, 2),
            ),
        )

        self.assertTrue({"retryable-lock", "rejected"}.intersection(outcomes))
        self._assert_public_group_has_no_curators()

        resolved = self._retry_locked_operations(outcomes, operations)

        self.assertIn("rejected", resolved)
        self._assert_public_group_has_no_curators()

    def _run_interleaved(self, operations, *, sync_points) -> list[str]:
        barrier = Barrier(len(operations))

        def execute(item) -> str:
            operation, (table_name, occurrence) = item
            with orm_worker_connection_scope():
                matches = 0

                def synchronize_after_read(execute, sql, params, many, context):
                    nonlocal matches
                    result = execute(sql, params, many, context)
                    if sql.lstrip().upper().startswith("SELECT") and table_name in sql:
                        matches += 1
                        if matches == occurrence:
                            barrier.wait(timeout=5)
                    return result

                with connection.execute_wrapper(synchronize_after_read):
                    try:
                        operation()
                    except ValidationError:
                        return "rejected"
                    except OperationalError as exc:
                        if "locked" not in str(exc).lower():
                            raise
                        return "retryable-lock"
                    return "committed"

        with ThreadPoolExecutor(max_workers=len(operations)) as executor:
            return list(executor.map(execute, zip(operations, sync_points, strict=True)))

    def _retry_locked_operations(self, outcomes, operations) -> list[str]:
        resolved = list(outcomes)
        for index, (outcome, operation) in enumerate(
            zip(outcomes, operations, strict=True)
        ):
            if outcome == "retryable-lock":
                try:
                    operation()
                except ValidationError:
                    resolved[index] = "rejected"
                else:
                    resolved[index] = "committed"
        return resolved

    def _assert_public_group_has_no_curators(self) -> None:
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertFalse(
            LibraryGroupMembership.objects.filter(
                group_id=setting.value,
                is_curator=True,
            ).exists()
        )
