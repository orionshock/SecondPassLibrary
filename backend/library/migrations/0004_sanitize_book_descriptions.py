import nh3
from django.db import migrations


BOOK_DESCRIPTION_TAGS = {
    "b",
    "br",
    "em",
    "i",
    "li",
    "ol",
    "p",
    "strong",
    "ul",
}
BOOK_DESCRIPTION_CLEAN_CONTENT_TAGS = {"script", "style"}


def sanitize_book_descriptions(apps, schema_editor):
    Book = apps.get_model("library", "Book")
    cleaner = nh3.Cleaner(
        tags=BOOK_DESCRIPTION_TAGS,
        clean_content_tags=BOOK_DESCRIPTION_CLEAN_CONTENT_TAGS,
        attributes={},
        link_rel=None,
    )
    for book in Book.objects.exclude(description="").iterator(chunk_size=500):
        sanitized = cleaner.clean(book.description or "")
        if sanitized != book.description:
            Book.objects.filter(pk=book.pk).update(description=sanitized)


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0003_bookseries_index_contract"),
    ]

    operations = [
        migrations.RunPython(sanitize_book_descriptions, migrations.RunPython.noop),
    ]
