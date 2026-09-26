from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import path, reverse

from library.admin import BookAdmin
from library.models import Author, Book, BookAuthor, BookSeries, Series


urlpatterns = [path("admin/", admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__)
class BookAdminChangelistTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="owner",
            password="pw",
        )
        self.author = Author.objects.create(name="Ursula Le Guin")
        self.series = Series.objects.create(name="Earthsea")
        self.book = Book.objects.create(title="A Wizard of Earthsea", language="eng")
        BookAuthor.objects.create(book=self.book, author=self.author, position=0)
        BookSeries.objects.create(
            book=self.book,
            series=self.series,
            series_index="1.25",
        )
        self.unrelated_book = Book.objects.create(title="Standalone", language="fra")
        self.url = reverse("admin:library_book_changelist")
        self.assertTrue(self.client.login(username="owner", password="pw"))

    def test_rows_show_relationship_context_and_repair_links(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Ursula Le Guin")
        self.assertContains(response, "Earthsea")
        self.assertContains(response, "1.25")
        self.assertContains(response, "Standalone")
        for book in (self.book, self.unrelated_book):
            repair_url = reverse(
                "admin:library_book_repair_stored_epub",
                args=[book.pk],
            )
            self.assertContains(response, repair_url)

    def test_series_language_and_created_at_filters_render_and_filter(self):
        response = self.client.get(self.url)

        filter_titles = [spec.title for spec in response.context["cl"].filter_specs]
        self.assertEqual(set(filter_titles), {"Series", "language", "created at"})

        series_response = self.client.get(
            self.url,
            {"series": str(self.series.pk)},
        )
        self.assertContains(series_response, self.book.title)
        self.assertNotContains(series_response, self.unrelated_book.title)

        language_response = self.client.get(self.url, {"language__exact": "fra"})
        self.assertContains(language_response, self.unrelated_book.title)
        self.assertNotContains(language_response, self.book.title)

    def test_queryset_fetches_row_relationships_without_per_row_growth(self):
        request = RequestFactory().get(self.url)
        request.user = self.owner
        model_admin = BookAdmin(Book, admin.site)

        with CaptureQueriesContext(connection) as captured:
            books = list(model_admin.get_queryset(request))
            for book in books:
                model_admin.authors_display(book)
                model_admin.series_display(book)
                model_admin.series_index_display(book)

        self.assertLessEqual(len(captured), 2)
