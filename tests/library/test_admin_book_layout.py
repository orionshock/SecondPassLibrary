from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path, reverse

from core import server_settings
from library.admin import (
    BookAdmin,
    BookGroupAssignmentInline,
    BookIdentifierInline,
    BookSeriesInline,
)
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookCatalogTag,
    BookSeries,
    CatalogTag,
    Series,
)
from tests.library.imports.helpers import image_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin


urlpatterns = [path("admin/", admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__)
class BookAdminLayoutTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="owner",
            password="pw",
        )
        self.book = Book.objects.create(title="Admin Repair Target")
        self.model_admin = BookAdmin(Book, admin.site)
        self.request = RequestFactory().get("/")
        self.request.user = self.owner

    def test_author_selector_is_writable_and_preserves_current_through_rows(self):
        existing = Author.objects.create(name="Existing Author")
        added = Author.objects.create(name="Added Author")
        BookAuthor.objects.create(book=self.book, author=existing, position=3)
        form_class = self.model_admin.get_form(self.request, self.book)
        form = form_class(
            data={
                "title": self.book.title,
                "subtitle": "",
                "description": "",
                "publisher": "",
                "language": "",
                "published_date_precision": "",
                "selected_authors": [existing.pk, added.pk],
                "selected_catalog_tags": [],
            },
            instance=self.book,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertEqual(
            list(self.book.authors.order_by("name").values_list("name", flat=True)),
            ["Added Author", "Existing Author"],
        )
        self.assertEqual(
            BookAuthor.objects.get(book=self.book, author=existing).position,
            3,
        )
        self.assertIn("RelatedFieldWidgetWrapper", type(form.fields["selected_authors"].widget).__name__)

    def test_book_description_is_sanitized_by_admin_form(self):
        form_class = self.model_admin.get_form(self.request, self.book)
        form = form_class(
            data={
                "title": self.book.title,
                "subtitle": "",
                "description": (
                    '<p class="admin">Safe <i>description</i></p>'
                    '<img src="bad"><script>alert("no")</script>'
                ),
                "publisher": "",
                "language": "",
                "published_date_precision": "",
                "selected_authors": [],
                "selected_catalog_tags": [],
            },
            instance=self.book,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.book.refresh_from_db()
        self.assertEqual(
            self.book.description,
            "<p>Safe <i>description</i></p>",
        )

    def test_series_uses_current_relationship_inline(self):
        series = Series.objects.create(name="Current Series")
        BookSeries.objects.create(book=self.book, series=series, series_index="2.50")

        self.assertEqual(BookSeriesInline.model, BookSeries)
        self.assertEqual(BookSeriesInline.fields, ["series", "series_index"])
        self.assertNotIn("series", self.model_admin.get_form(self.request).base_fields)

    def test_cover_upload_and_clear_use_separate_admin_controls(self):
        form_class = self.model_admin.get_form(self.request, self.book)
        upload_form = form_class(
            data={
                "title": self.book.title,
                "subtitle": "",
                "description": "",
                "publisher": "",
                "language": "",
                "published_date_precision": "",
                "selected_authors": [],
                "selected_catalog_tags": [],
            },
            files={
                "cover_upload": SimpleUploadedFile(
                    "cover.jpg",
                    image_bytes("JPEG"),
                    content_type="image/jpeg",
                )
            },
            instance=self.book,
        )
        self.assertTrue(upload_form.is_valid(), upload_form.errors)
        upload_form.save()
        self.book.refresh_from_db()
        self.assertTrue(self.book.cover_file.name.endswith(".jpg"))

        clear_form = form_class(
            data={
                "title": self.book.title,
                "subtitle": "",
                "description": "",
                "publisher": "",
                "language": "",
                "published_date_precision": "",
                "selected_authors": [],
                "selected_catalog_tags": [],
                "clear_cover": "on",
            },
            instance=self.book,
        )
        self.assertTrue(clear_form.is_valid(), clear_form.errors)
        clear_form.save()
        self.book.refresh_from_db()
        self.assertFalse(self.book.cover_file)

    def test_change_page_renders_cover_bibliographic_epub_and_current_identifiers(self):
        tag = CatalogTag.objects.create(
            name="Mystery",
            normalized_name="mystery",
            slug="mystery",
        )
        BookCatalogTag.objects.create(book=self.book, catalog_tag=tag)
        self.book.cover_file.save(f"{'a' * 64}.png", ContentFile(b"cover"), save=True)
        self.assertTrue(self.client.login(username="owner", password="pw"))

        response = self.client.get(
            reverse("admin:library_book_change", args=[self.book.pk])
        )

        self.assertEqual(response.status_code, 200)
        for text in (
            "Book identity",
            "Authors",
            "Series",
            "Cover",
            "Bibliographic",
            "Catalog tags",
            "Stored EPUB",
            "Repair stored EPUB",
            "Book Identifiers",
            "Timestamps",
        ):
            self.assertContains(response, text)
        self.assertContains(response, 'alt="Current cover"')
        self.assertContains(response, 'name="cover_upload"')
        self.assertContains(response, 'name="clear_cover"')
        self.assertEqual(
            BookIdentifierInline.fields,
            ["scheme", "value", "normalized_value"],
        )
        self.assertNotContains(response, "is_primary")
        self.assertNotContains(response, "identifier-source")

    def test_related_selectors_render_only_view_shortcuts(self):
        Author.objects.create(name="Selectable Author")
        Series.objects.create(name="Selectable Series")
        self.assertTrue(self.client.login(username="owner", password="pw"))

        response = self.client.get(
            reverse("admin:library_book_change", args=[self.book.pk])
        )

        self.assertContains(response, "related-widget-wrapper-link view-related")
        self.assertNotContains(response, "related-widget-wrapper-link add-related")
        self.assertNotContains(response, "related-widget-wrapper-link change-related")
        self.assertNotContains(response, "related-widget-wrapper-link delete-related")

    def test_top_level_related_model_admin_pages_remain_available(self):
        self.assertTrue(self.client.login(username="owner", password="pw"))

        for route_name in (
            "admin:library_author_changelist",
            "admin:library_series_changelist",
            "admin:library_librarygroup_changelist",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_stored_epub_and_timestamps_are_read_only(self):
        readonly = set(self.model_admin.get_readonly_fields(self.request, self.book))

        self.assertTrue(
            {
                "book_file",
                "file_format",
                "checksum",
                "file_size",
                "created_at",
                "updated_at",
            }.issubset(readonly)
        )

    def test_group_assignment_inline_tracks_advanced_groups_setting(self):
        server_settings.set_advanced_library_groups_enabled(False)
        self.assertNotIn(
            BookGroupAssignmentInline,
            self.model_admin.get_inlines(self.request, self.book),
        )

        server_settings.set_advanced_library_groups_enabled(True)
        self.assertIn(
            BookGroupAssignmentInline,
            self.model_admin.get_inlines(self.request, self.book),
        )
