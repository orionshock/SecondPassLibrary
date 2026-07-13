from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase

from core import server_settings
from core.server_settings import set_server_setting
from library.groups import consolidation
from library.groups.book_assignments import add_book_to_group, remove_book_from_group
from library.groups.memberships import (
    add_user_to_group,
    remove_user_from_group,
    set_group_membership_curator,
)
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING, get_public_group
from library.groups.services import (
    create_library_group,
    delete_library_group,
    repair_public_group_identity,
    set_public_group_identity,
    update_library_group,
)
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase


class LibraryGroupOperationalLoggingTests(LibraryGroupServiceTestCase):
    def test_group_create_update_and_delete_logs_safe_info(self):
        with self.assertLogs("library.groups.services", level="INFO") as created:
            with self.captureOnCommitCallbacks(execute=True):
                group = create_library_group(name="Secret Group", description="Private room")

        self.assertIn("Library group created", created.output[0])
        self.assertIn(str(group.pk), created.output[0])
        self.assertNotIn("Secret Group", created.output[0])
        self.assertNotIn("Private room", created.output[0])

        with self.assertLogs("library.groups.services", level="INFO") as updated:
            with self.captureOnCommitCallbacks(execute=True):
                update_library_group(
                    group=group,
                    name="New Secret Group",
                    description="New private room",
                )

        self.assertIn("Library group presentation changed", updated.output[0])
        self.assertIn(str(group.pk), updated.output[0])
        self.assertIn("changed_fields=description,name", updated.output[0])
        self.assertNotIn("New Secret Group", updated.output[0])
        self.assertNotIn("New private room", updated.output[0])

        group_id = str(group.pk)
        with self.assertLogs("library.groups.services", level="INFO") as deleted:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertTrue(delete_library_group(group=group, actor=self.actor))

        self.assertIn("Library group deleted", deleted.output[0])
        self.assertIn(group_id, deleted.output[0])
        self.assertIn(str(self.actor.profile.pk), deleted.output[0])

    def test_membership_add_remove_and_curator_change_logs_uuid_only(self):
        group = create_library_group(name="Members Only", description="Hidden")

        with self.assertLogs("library.groups.memberships", level="INFO") as added:
            with self.captureOnCommitCallbacks(execute=True):
                membership = add_user_to_group(user=self.user, group=group)

        self.assertIn("Library group membership added", added.output[0])
        self.assertIn(str(group.pk), added.output[0])
        self.assertIn(str(self.user.profile.pk), added.output[0])
        self.assertIn("curator=False", added.output[0])
        self.assertNotIn("reader", added.output[0])
        self.assertNotIn("Members Only", added.output[0])

        with self.assertLogs("library.groups.memberships", level="INFO") as curator:
            with self.captureOnCommitCallbacks(execute=True):
                set_group_membership_curator(membership=membership, is_curator=True)

        self.assertIn("Library group membership curator changed", curator.output[0])
        self.assertIn(str(group.pk), curator.output[0])
        self.assertIn(str(self.user.profile.pk), curator.output[0])
        self.assertIn("curator=True", curator.output[0])

        other_group = create_library_group(name="Backup")
        add_user_to_group(user=self.user, group=other_group)
        with self.assertLogs("library.groups.memberships", level="INFO") as removed:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertTrue(remove_user_from_group(user=self.user, group=group))

        self.assertIn("Library group membership removed", removed.output[0])
        self.assertIn(str(group.pk), removed.output[0])
        self.assertIn(str(self.user.profile.pk), removed.output[0])
        self.assertIn("fallback_to_public=False", removed.output[0])

    def test_book_assignment_add_and_remove_logs_uuid_only(self):
        group = create_library_group(name="Book Room")
        other_group = create_library_group(name="Other Room")

        with self.assertLogs("library.groups.book_assignments", level="INFO") as added:
            with self.captureOnCommitCallbacks(execute=True):
                add_book_to_group(book=self.book, group=group, actor=self.actor)

        self.assertIn("Book assigned to library group", added.output[0])
        self.assertIn(str(self.book.pk), added.output[0])
        self.assertIn(str(group.pk), added.output[0])
        self.assertIn(str(self.actor.profile.pk), added.output[0])
        self.assertNotIn("Service Book", added.output[0])
        self.assertNotIn("Book Room", added.output[0])

        add_book_to_group(book=self.book, group=other_group, actor=self.actor)
        with self.assertLogs("library.groups.book_assignments", level="INFO") as removed:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertTrue(remove_book_from_group(book=self.book, group=group, actor=self.actor))

        self.assertIn("Book removed from library group", removed.output[0])
        self.assertIn(str(self.book.pk), removed.output[0])
        self.assertIn(str(group.pk), removed.output[0])
        self.assertIn("fallback_to_public=False", removed.output[0])

    def test_public_identity_reassignment_logs_one_safe_summary(self):
        group = create_library_group(name="Candidate Common Room")

        with self.assertLogs("library.groups.services", level="INFO") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                set_public_group_identity(group=group)

        self.assertEqual(len(logs.output), 1)
        self.assertIn("Public/Common Room identity reassigned", logs.output[0])
        self.assertIn(str(group.pk), logs.output[0])
        self.assertNotIn("Candidate Common Room", logs.output[0])

    def test_public_repair_logs_one_aggregate_summary_without_low_level_rows(self):
        orphan_user = get_user_model().objects.create_user(
            username="orphan-user",
            email="orphan@example.com",
        )
        orphan_book = Book.objects.create(title="Hidden orphan book")

        with self.assertLogs("library.groups.services", level="INFO") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                result = repair_public_group_identity(
                    create_new_common_room=True,
                    actor=self.actor,
                )

        self.assertEqual(len(logs.output), 1)
        self.assertIn("Public/Common Room identity repaired", logs.output[0])
        self.assertIn(str(result.group.pk), logs.output[0])
        self.assertIn(f"users_restored={result.users_restored}", logs.output[0])
        self.assertIn(f"books_restored={result.books_restored}", logs.output[0])
        self.assertNotIn("orphan-user", logs.output[0])
        self.assertNotIn("orphan@example.com", logs.output[0])
        self.assertNotIn("Hidden orphan book", logs.output[0])
        self.assertTrue(
            LibraryGroupMembership.objects.filter(user=orphan_user, group=result.group).exists()
        )
        self.assertTrue(
            BookGroupAssignment.objects.filter(book=orphan_book, group=result.group).exists()
        )

    def test_public_identity_self_heal_logs_warning_without_corrupt_value(self):
        missing_id = uuid4()
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(missing_id),
            description="Public/Common Room group id.",
        )
        server_settings.clear_server_settings_cache()

        with self.assertLogs("library.groups.public_group", level="WARNING") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                repaired = get_public_group()

        self.assertIn("Public/Common Room identity self-healed", logs.output[0])
        self.assertIn(str(repaired.pk), logs.output[0])
        self.assertNotIn(str(missing_id), logs.output[0])

    def test_expected_validation_and_noop_paths_do_not_emit_errors(self):
        group = create_library_group(name="No-op Room")
        add_user_to_group(user=self.user, group=group)
        add_book_to_group(book=self.book, group=group)

        with (
            patch("library.groups.services.logger.error") as group_error_log,
            patch("library.groups.memberships.logger.error") as membership_error_log,
            patch("library.groups.book_assignments.logger.error") as assignment_error_log,
        ):
            with self.assertRaises(ValidationError):
                delete_library_group(group=self.public, actor=self.actor)
            add_user_to_group(user=self.user, group=group)
            add_book_to_group(book=self.book, group=group)
            update_library_group(
                group=group,
                name=group.name,
                description=group.description,
            )

        group_error_log.assert_not_called()
        membership_error_log.assert_not_called()
        assignment_error_log.assert_not_called()

    def test_state_change_info_logs_do_not_fire_when_outer_transaction_rolls_back(self):
        group = create_library_group(name="Rollback Room")

        with patch("library.groups.memberships.logger.info") as info_log:
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    add_user_to_group(user=self.user, group=group)
                    raise RuntimeError("rollback")

        info_log.assert_not_called()

    def test_book_assignment_log_separates_actor_and_added_by(self):
        group = create_library_group(name="Assignment Room")

        with self.assertLogs("library.groups.book_assignments", level="INFO") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                add_book_to_group(
                    book=self.book,
                    group=group,
                    actor=None,
                    added_by=self.actor,
                )

        self.assertIn("actor=none", logs.output[0])
        self.assertIn(f"added_by={self.actor.profile.pk}", logs.output[0])


class AdvancedGroupCollapseLoggingSuppressionTests(TestCase):
    def setUp(self):
        cache.clear()
        server_settings.clear_server_settings_cache()
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

    def test_collapse_logs_only_aggregate_info_from_consolidation_boundary(self):
        group = LibraryGroup.objects.create(name="Custom Room")
        reader = get_user_model().objects.create_user(username="reader")
        book = Book.objects.create(title="Custom Room Book")
        add_user_to_group(user=reader, group=group)
        add_book_to_group(book=book, group=group)
        plan = consolidation.build_advanced_groups_disable_plan()

        with (
            patch("library.groups.services.logger.info") as low_level_info,
            patch("library.groups.memberships.logger.info") as membership_low_level_info,
            patch("library.groups.book_assignments.logger.info") as assignment_low_level_info,
            self.assertLogs("library.groups.consolidation", level="INFO") as logs,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                consolidation.execute_advanced_groups_disable_plan(
                    actor=self.owner,
                    expected_fingerprint=plan.fingerprint,
                )

        low_level_info.assert_not_called()
        membership_low_level_info.assert_not_called()
        assignment_low_level_info.assert_not_called()
        self.assertEqual(len(logs.output), 1)
        self.assertIn("Advanced library groups consolidated", logs.output[0])
