from importlib import import_module

from django.apps import apps
from django.test import TestCase

from library.models import Book


class BookDescriptionMigrationTests(TestCase):
    def test_sanitizes_existing_dirty_descriptions_and_preserves_clean_ones(self):
        dirty = Book.objects.create(title="Dirty")
        clean = Book.objects.create(
            title="Clean",
            description="<p>Already <em>safe</em> &amp; stable</p>",
        )
        Book.objects.filter(pk=dirty.pk).update(
            description=(
                '<div><p class="old">Imported <strong>description</strong></p></div>'
                '<script>alert("no")</script>'
            )
        )
        migration = import_module(
            "library.migrations.0004_sanitize_book_descriptions"
        )

        migration.sanitize_book_descriptions(apps, schema_editor=None)

        dirty.refresh_from_db()
        clean.refresh_from_db()
        self.assertEqual(
            dirty.description,
            "<p>Imported <strong>description</strong></p>",
        )
        self.assertEqual(
            clean.description,
            "<p>Already <em>safe</em> &amp; stable</p>",
        )
