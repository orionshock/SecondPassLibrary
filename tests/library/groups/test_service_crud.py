from __future__ import annotations

from django.core.exceptions import ValidationError

from library.groups.public_group import is_public_group
from library.groups.services import create_library_group, delete_library_group, update_library_group
from library.models import LibraryGroup
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase


class LibraryReWrite2607GroupCrudServiceTests(LibraryGroupServiceTestCase):
    def test_create_group_creates_normal_non_public_group(self):
        group = create_library_group(name="Club", description="Readers")

        self.assertEqual(group.name, "Club")
        self.assertEqual(group.description, "Readers")
        self.assertFalse(is_public_group(group))

    def test_update_group_changes_name_and_description(self):
        group = create_library_group(name="Old", description="Before")

        update_library_group(group=group, name="New", description="After")

        group.refresh_from_db()
        self.assertEqual(group.name, "New")
        self.assertEqual(group.description, "After")

    def test_delete_normal_group_removes_group(self):
        group = create_library_group(name="Temporary")

        deleted = delete_library_group(group=group)

        self.assertTrue(deleted)
        self.assertFalse(LibraryGroup.objects.filter(pk=group.pk).exists())

    def test_delete_public_group_is_refused(self):
        with self.assertRaises(ValidationError):
            delete_library_group(group=self.public)

        self.assertTrue(LibraryGroup.objects.filter(pk=self.public.pk).exists())
