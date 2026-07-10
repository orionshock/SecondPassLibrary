from __future__ import annotations

from django.contrib.auth import get_user_model

from library.imports.dto import ImportAuthor, ImportMetadata


class ImportPersistenceFixtureMixin:
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.actor = User.objects.create_user(username="importer", password="pw")


def sample_metadata(**overrides) -> ImportMetadata:
    values = {
        "title": "Sample Book",
        "sort_title": "Sample Book, The",
        "subtitle": "A Subtitle",
        "authors": [ImportAuthor(name="Sample Author", sort_name="Author, Sample", position=0)],
        "series": None,
        "language": "en",
        "publisher": "Example Press",
        "description": "Example description",
        "published_year": None,
        "published_month": None,
        "published_day": None,
        "published_date_precision": "",
        "tags": [],
        "identifiers": [],
    }
    values.update(overrides)
    return ImportMetadata(**values)
