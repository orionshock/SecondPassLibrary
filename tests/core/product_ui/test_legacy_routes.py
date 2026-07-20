from pathlib import Path

from django.urls import resolve, reverse

from core import server_settings
from library.models import Book
from tests.core.product_ui.helpers import ProductUiTestCase


class LegacyProductUiRouteContractTests(ProductUiTestCase):
    def setUp(self):
        super().setUp()
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.bootstrap_owner)

    def test_root_mounts_use_the_same_view_and_keep_distinct_dashboard_paths(self):
        current = self.client.get("/", follow=False)
        legacy = self.client.get("/legacy/", follow=False)

        self.assertIs(resolve("/").func, resolve("/legacy/").func)
        self.assertEqual(current.status_code, 302)
        self.assertEqual(current["Location"], "/dashboard/")
        self.assertEqual(legacy.status_code, 302)
        self.assertEqual(legacy["Location"], "/legacy/dashboard/")

    def test_representative_legacy_pages_are_available(self):
        book = Book.objects.create(title="Legacy route fixture")
        paths = [
            "/legacy/dashboard/",
            "/legacy/library/",
            f"/legacy/library/books/{book.id}/",
            f"/legacy/library/books/{book.id}/edit/",
            "/legacy/groups/",
            "/legacy/shelves/",
            "/legacy/users/",
            "/legacy/server/",
            "/legacy/imports/",
        ]

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_existing_product_routes_remain_available(self):
        for path in ("/dashboard/", "/library/", "/groups/", "/shelves/", "/users/", "/server/", "/imports/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_legacy_primary_navigation_stays_in_legacy_mount(self):
        response = self.client.get("/legacy/dashboard/")

        for path in (
            "/legacy/dashboard/",
            "/legacy/reading/sessions/",
            "/legacy/library/",
            "/legacy/shelves/",
            "/legacy/imports/",
            "/legacy/users/",
            "/legacy/server/",
            "/legacy/profile/",
        ):
            self.assertContains(response, f'href="{path}"')

    def test_legacy_catalog_and_book_links_preserve_the_mount(self):
        book = Book.objects.create(title="Legacy link fixture")

        author_form = self.client.get("/legacy/library/authors/new/")
        series_form = self.client.get("/legacy/library/series/new/")
        book_detail = self.client.get(f"/legacy/library/books/{book.id}/")
        book_edit = self.client.get(f"/legacy/library/books/{book.id}/edit/")

        self.assertContains(author_form, 'href="/legacy/library/?view=authors"')
        self.assertContains(series_form, 'href="/legacy/library/?view=series"')
        self.assertContains(book_detail, f'href="/legacy/library/books/{book.id}/edit/"')
        for path in (
            "/legacy/library/?view=authors",
            "/legacy/library/authors/new/",
            "/legacy/library/?view=series",
            "/legacy/library/series/new/",
        ):
            self.assertContains(book_edit, f'href="{path}"')

    def test_library_javascript_uses_the_mount_helper_for_axis_and_return_links(self):
        library_js = Path("web/static/web/js/library/list.js").read_text(encoding="utf-8")
        catalog_js = Path("web/static/web/js/catalog_entities/main.js").read_text(encoding="utf-8")

        self.assertIn("axisCreateEl.href = createKind ? productUiPath(", library_js)
        self.assertIn("? productUiPath(`/library/${filter.kind", library_js)
        self.assertIn("window.location.assign(productUiPath(", catalog_js)

    def test_service_routes_are_not_duplicated_below_legacy(self):
        for path in (
            "/legacy/api/v1/accounts/me/",
            "/legacy/static/web/app.css",
            "/legacy/media/covers/missing.png",
            "/legacy/admin/",
            "/legacy/api-auth/login/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

        self.assertEqual(reverse("accounts:accounts_me"), "/api/v1/accounts/me/")
        self.assertEqual(reverse("login"), "/api-auth/login/")

    def test_both_product_ui_namespaces_reverse_independently(self):
        self.assertEqual(reverse("web:library"), "/library/")
        self.assertEqual(reverse("legacy:library"), "/legacy/library/")
