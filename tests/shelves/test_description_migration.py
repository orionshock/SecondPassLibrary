from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from shelves.models import Shelf


class ShelfDescriptionMigrationTests(TestCase):
    def test_normalizes_existing_shelf_description(self):
        user = get_user_model().objects.create_user(username="owner")
        shelf = Shelf.objects.create(
            name="Dirty Shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=user,
            created_by=user,
        )
        Shelf.objects.filter(pk=shelf.pk).update(
            description='<div><p class="old">Safe <strong>shelf</strong></p></div><style>bad</style>'
        )
        migration = import_module("shelves.migrations.0002_sanitize_shelf_descriptions")

        migration.normalize_shelf_descriptions(apps, schema_editor=None)

        shelf.refresh_from_db()
        self.assertEqual(shelf.description, "<p>Safe <strong>shelf</strong></p>")
