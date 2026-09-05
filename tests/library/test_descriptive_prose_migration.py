from importlib import import_module

from django.apps import apps
from django.test import TestCase

from library.models import LibraryGroup


class DescriptiveProseMigrationTests(TestCase):
    def test_normalizes_existing_group_description(self):
        group = LibraryGroup.objects.create(name="Dirty Group")
        LibraryGroup.objects.filter(pk=group.pk).update(
            description='<div><p class="old">Safe <em>group</em></p></div><script>bad()</script>'
        )
        migration = import_module(
            "library.migrations.0006_sanitize_group_descriptions_and_validate_prose"
        )

        migration.normalize_library_prose(apps, schema_editor=None)

        group.refresh_from_db()
        self.assertEqual(group.description, "<p>Safe <em>group</em></p>")

    def test_rejects_existing_library_prose_over_limit_without_truncation(self):
        group = LibraryGroup.objects.create(name="Oversized")
        oversized = "x" * 25_001
        LibraryGroup.objects.filter(pk=group.pk).update(description=oversized)
        migration = import_module(
            "library.migrations.0006_sanitize_group_descriptions_and_validate_prose"
        )

        with self.assertRaises(RuntimeError):
            migration.normalize_library_prose(apps, schema_editor=None)

        group.refresh_from_db()
        self.assertEqual(group.description, oversized)
