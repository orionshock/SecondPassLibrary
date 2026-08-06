from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path, reverse

from library.admin import CatalogTagAdmin, CatalogTagBookInline
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookCatalogTag,
    BookSeries,
    CatalogTag,
    Series,
)


urlpatterns = [path("admin/", admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__)
class CatalogTagAdminTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="owner",
            password="pw",
        )
        self.request = RequestFactory().post("/admin/library/catalogtag/")
        self.request.user = self.owner
        self.model_admin = CatalogTagAdmin(CatalogTag, admin.site)

    def test_layout_and_read_only_identity_fields(self):
        form_class = self.model_admin.get_form(self.request)

        self.assertEqual(
            self.model_admin.get_fields(self.request),
            ["name", "sort_name", "normalized_name", "slug"],
        )
        self.assertEqual(
            set(self.model_admin.get_readonly_fields(self.request)),
            {"normalized_name", "slug"},
        )
        self.assertEqual(list(form_class.base_fields), ["name", "sort_name"])
        self.assertEqual(self.model_admin.inlines, [CatalogTagBookInline])

    def test_submitted_normalized_name_is_ignored(self):
        form_class = self.model_admin.get_form(self.request)
        form = form_class(
            data={
                "name": "  Urban   Fantasy ",
                "sort_name": "Fantasy, Urban",
                "normalized_name": "attacker-controlled",
                "slug": "attacker-controlled",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        tag = form.save()
        self.assertEqual(tag.name, "Urban Fantasy")
        self.assertEqual(tag.normalized_name, "urban fantasy")
        self.assertEqual(tag.slug, "urban-fantasy")

    def test_name_change_recalculates_identity_and_preserves_slug(self):
        tag = CatalogTag.objects.create(
            name="Mystery",
            sort_name="Mystery",
            normalized_name="mystery",
            slug="mystery",
        )
        form_class = self.model_admin.get_form(self.request, tag)
        form = form_class(
            data={"name": "Crime Fiction", "sort_name": "Fiction, Crime"},
            instance=tag,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        tag.refresh_from_db()
        self.assertEqual(tag.normalized_name, "crime fiction")
        self.assertEqual(tag.slug, "mystery")

    def test_sort_name_only_change_preserves_normalized_identity_and_slug(self):
        tag = CatalogTag.objects.create(
            name="Science Fiction",
            sort_name="Science Fiction",
            normalized_name="science fiction",
            slug="science-fiction",
        )
        form_class = self.model_admin.get_form(self.request, tag)
        form = form_class(
            data={"name": tag.name, "sort_name": "Fiction, Science"},
            instance=tag,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        tag.refresh_from_db()
        self.assertEqual(tag.normalized_name, "science fiction")
        self.assertEqual(tag.slug, "science-fiction")

    def test_conflicting_normalized_name_is_a_form_error(self):
        CatalogTag.objects.create(
            name="Urban Fantasy",
            normalized_name="urban fantasy",
            slug="urban-fantasy",
        )
        tag = CatalogTag.objects.create(
            name="Mystery",
            normalized_name="mystery",
            slug="mystery",
        )
        form_class = self.model_admin.get_form(self.request, tag)
        form = form_class(
            data={"name": " URBAN   FANTASY ", "sort_name": ""},
            instance=tag,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["name"],
            ["A Catalog Tag with this normalized name already exists."],
        )

    def test_change_page_lists_linked_books_with_single_and_bulk_remove_controls(self):
        tag = CatalogTag.objects.create(
            name="Imported clutter",
            normalized_name="imported clutter",
            slug="imported-clutter",
        )
        book = Book.objects.create(title="Tagged book")
        secondary = Author.objects.create(name="Secondary author")
        primary = Author.objects.create(name="Primary author")
        BookAuthor.objects.create(book=book, author=secondary, position=2)
        BookAuthor.objects.create(book=book, author=primary, position=1)
        series = Series.objects.create(name="Example series")
        BookSeries.objects.create(book=book, series=series, series_index="2.50")
        BookCatalogTag.objects.create(book=book, catalog_tag=tag)
        self.assertTrue(self.client.login(username="owner", password="pw"))

        response = self.client.get(
            reverse("admin:library_catalogtag_change", args=[tag.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Books carrying this tag")
        self.assertContains(response, "Tagged book")
        self.assertContains(response, "Primary author")
        self.assertNotContains(response, "Secondary author")
        self.assertContains(response, "Example series")
        self.assertContains(response, "#2.50")
        self.assertContains(
            response,
            reverse("admin:library_book_change", args=[book.pk]),
        )
        self.assertContains(
            response,
            reverse("admin:library_author_change", args=[primary.pk]),
        )
        self.assertContains(
            response,
            reverse("admin:library_series_change", args=[series.pk]),
        )
        self.assertContains(response, 'name="book_catalog_tags-0-DELETE"')
        self.assertContains(response, "library/admin/catalog_tag_books.js")
        self.assertContains(response, "library/admin/catalog_tag_books.css")

    def test_save_removes_selected_book_relationships_only(self):
        tag = CatalogTag.objects.create(
            name="Imported clutter",
            normalized_name="imported clutter",
            slug="imported-clutter",
        )
        books = [
            Book.objects.create(title="Keep me"),
            Book.objects.create(title="Remove me"),
        ]
        relationships = [
            BookCatalogTag.objects.create(book=book, catalog_tag=tag)
            for book in books
        ]
        self.assertTrue(self.client.login(username="owner", password="pw"))

        response = self.client.post(
            reverse("admin:library_catalogtag_change", args=[tag.pk]),
            {
                "name": tag.name,
                "sort_name": "",
                "book_catalog_tags-TOTAL_FORMS": "2",
                "book_catalog_tags-INITIAL_FORMS": "2",
                "book_catalog_tags-MIN_NUM_FORMS": "0",
                "book_catalog_tags-MAX_NUM_FORMS": "1000",
                "book_catalog_tags-0-id": str(relationships[0].pk),
                "book_catalog_tags-0-catalog_tag": str(tag.pk),
                "book_catalog_tags-1-id": str(relationships[1].pk),
                "book_catalog_tags-1-catalog_tag": str(tag.pk),
                "book_catalog_tags-1-DELETE": "on",
                "_continue": "Save and continue editing",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Book.objects.count(), 2)
        self.assertEqual(
            list(tag.books.values_list("title", flat=True)),
            ["Keep me"],
        )
