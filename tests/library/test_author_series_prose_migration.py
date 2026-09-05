from importlib import import_module

from django.apps import apps
from django.test import TestCase

from library.models import Author, Series


class AuthorSeriesProseMigrationTests(TestCase):
    def test_sanitizes_existing_prose_and_preserves_plain_text(self):
        dirty_author = Author.objects.create(name="Dirty Author")
        plain_author = Author.objects.create(name="Plain Author", biography="Plain biography")
        dirty_series = Series.objects.create(name="Dirty Series")
        Author.objects.filter(pk=dirty_author.pk).update(
            biography='<div><p class="old">Safe <strong>bio</strong></p></div><script>bad()</script>'
        )
        Series.objects.filter(pk=dirty_series.pk).update(
            summary='<ol><li data-index="1">Safe summary</li></ol><style>bad</style>'
        )
        migration = import_module("library.migrations.0005_sanitize_author_series_prose")

        migration.sanitize_author_series_prose(apps, schema_editor=None)

        dirty_author.refresh_from_db()
        plain_author.refresh_from_db()
        dirty_series.refresh_from_db()
        self.assertEqual(dirty_author.biography, "<p>Safe <strong>bio</strong></p>")
        self.assertEqual(plain_author.biography, "Plain biography")
        self.assertEqual(dirty_series.summary, "<ol><li>Safe summary</li></ol>")
