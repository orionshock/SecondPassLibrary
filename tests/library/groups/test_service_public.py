from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import ServerSetting
from core.server_settings import set_server_setting
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_NAME,
    PUBLIC_GROUP_ID_SETTING,
    get_public_group,
    is_public_group,
)
from library.groups.public_services import (
    configure_public_group,
    repair_public_group_identity,
)
from library.groups.services import create_library_group, delete_library_group
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase


class LibraryPublicGroupServiceTests(LibraryGroupServiceTestCase):
    def test_public_identity_is_setting_id_based_and_survives_rename(self):
        self.public.name = "Renamed"
        self.public.save(update_fields=["name", "updated_at"])

        self.assertTrue(is_public_group(self.public))
        self.assertEqual(get_public_group().id, self.public.id)

    def test_stale_public_setting_self_heals(self):
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(uuid4()),
            description="Public/Common Room group id.",
        )

        healed = get_public_group()

        self.assertTrue(LibraryGroup.objects.filter(pk=healed.pk).exists())
        self.assertTrue(is_public_group(healed))

    def test_configure_public_group_is_idempotent(self):
        configured = configure_public_group(name="Renamed Public", description="Updated")

        self.assertEqual(configured.id, self.public.id)
        self.assertEqual(LibraryGroup.objects.count(), 1)
        self.assertEqual(configured.name, "Renamed Public")
        self.assertEqual(configured.description, "Updated")
        self.assertTrue(is_public_group(configured))

    def test_configure_public_group_normalizes_name_and_preserves_description_text(self):
        configured = configure_public_group(
            name="  Trimmed Room  ",
            description="  Trimmed description  ",
        )

        self.assertEqual(configured.name, "Trimmed Room")
        self.assertEqual(configured.description, "  Trimmed description  ")

        configured = configure_public_group(name="   ", description="   ")

        self.assertEqual(configured.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(configured.description, "   ")

    def test_configure_public_group_preserves_explicit_blank_description(self):
        configured = configure_public_group(
            name=None,
            description="",
        )

        self.assertEqual(configured.name, DEFAULT_PUBLIC_GROUP_NAME)
        self.assertEqual(configured.description, "")

    def test_configure_public_group_noop_does_not_save_group_or_rewrite_setting(self):
        configured = configure_public_group(name="Stable Public", description="")
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        group_updated_at = configured.updated_at
        setting_updated_at = setting.updated_at

        same = configure_public_group(name="  Stable Public  ", description="")
        setting.refresh_from_db()

        self.assertEqual(same.pk, configured.pk)
        self.assertEqual(same.updated_at, group_updated_at)
        self.assertEqual(setting.updated_at, setting_updated_at)

    def test_configure_public_group_changed_values_persist(self):
        configured = configure_public_group(name="Before", description="")
        original_updated_at = configured.updated_at

        changed = configure_public_group(name="After", description="New description")

        self.assertEqual(changed.pk, configured.pk)
        self.assertEqual(changed.name, "After")
        self.assertEqual(changed.description, "New description")
        self.assertGreater(changed.updated_at, original_updated_at)

    def test_renamed_public_group_cannot_be_deleted(self):
        configure_public_group(name="Library Lobby", description="Still public")
        self.public.refresh_from_db()

        with self.assertRaises(ValidationError):
            delete_library_group(group=self.public)

        self.assertTrue(LibraryGroup.objects.filter(pk=self.public.pk).exists())

    def test_public_repair_restores_only_true_orphan_users_and_books(self):
        other_group = create_library_group(name="Other")
        assigned_book = Book.objects.create(title="Already assigned")
        LibraryGroupMembership.objects.create(user=self.actor, group=other_group)
        BookGroupAssignment.objects.create(book=assigned_book, group=other_group)

        with self.captureOnCommitCallbacks(execute=True):
            result = repair_public_group_identity(
                create_new_common_room=False,
                actor=self.actor,
            )

        self.assertEqual(result.users_restored, 1)
        self.assertEqual(result.books_restored, 1)
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=self.user,
                group=self.public,
                is_curator=False,
            ).exists()
        )
        self.assertFalse(
            LibraryGroupMembership.objects.filter(user=self.actor, group=self.public).exists()
        )
        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=self.book,
                group=self.public,
                added_by=self.actor,
            ).exists()
        )
        self.assertFalse(
            BookGroupAssignment.objects.filter(book=assigned_book, group=self.public).exists()
        )

    def test_public_repair_is_idempotent_and_counts_actual_created_rows(self):
        with self.captureOnCommitCallbacks(execute=True):
            first = repair_public_group_identity(
                create_new_common_room=False,
                actor=self.actor,
            )
        with self.captureOnCommitCallbacks(execute=True):
            second = repair_public_group_identity(
                create_new_common_room=False,
                actor=self.actor,
            )

        self.assertEqual(first.users_restored, 2)
        self.assertEqual(first.books_restored, 1)
        self.assertEqual(second.users_restored, 0)
        self.assertEqual(second.books_restored, 0)
        self.assertEqual(
            LibraryGroupMembership.objects.filter(group=self.public).count(),
            2,
        )
        self.assertEqual(
            BookGroupAssignment.objects.filter(group=self.public).count(),
            1,
        )

    def test_public_repair_registers_one_visibility_cache_invalidation(self):
        with patch("library.queries.invalidate_visible_books_cache") as invalidate:
            with self.captureOnCommitCallbacks(execute=True):
                repair_public_group_identity(
                    create_new_common_room=False,
                    actor=self.actor,
                )

        invalidate.assert_called_once_with()

    def test_public_repair_rolls_back_relationships_on_failure(self):
        with (
            patch(
                "library.groups.public_services._restore_orphan_books_to_public",
                side_effect=RuntimeError("forced failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    repair_public_group_identity(
                        create_new_common_room=False,
                        actor=self.actor,
                    )

        self.assertFalse(LibraryGroupMembership.objects.filter(user=self.actor).exists())
        self.assertFalse(LibraryGroupMembership.objects.filter(user=self.user).exists())
        self.assertFalse(BookGroupAssignment.objects.filter(book=self.book).exists())
