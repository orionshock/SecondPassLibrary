"""Tests for breadcrumb rendering and back links."""
from django.contrib.auth import get_user_model

from tests.core.product_ui.helpers import ProductUiTestCase
from uuid import uuid4


User = get_user_model()


class ProductUiBreadcrumbTests(ProductUiTestCase):
    """Test breadcrumb rendering across static product UI pages."""

    def test_static_product_pages_render_breadcrumbs(self):
        owner = User.objects.create_user(
            username="owner-breadcrumb",
            email="owner-breadcrumb@example.com",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)

        cases = [
            (
                "/library/",
                ('<a class="breadcrumbs__link" href="/library/">Library</a>', "Books"),
                "breadcrumbs--trail",
            ),
            ("/groups/", ("Groups",), "breadcrumbs--single"),
            (
                "/groups/new/",
                ('<a class="breadcrumbs__link" href="/groups/">Groups</a>', "New"),
                "breadcrumbs--trail",
            ),
            ("/shelves/", ("Shelves",), "breadcrumbs--single"),
            (
                "/shelves/new/",
                ('<a class="breadcrumbs__link" href="/shelves/">Shelves</a>', "New"),
                "breadcrumbs--trail",
            ),
            ("/users/", ("Users",), "breadcrumbs--single"),
            (
                "/users/new/",
                ('<a class="breadcrumbs__link" href="/users/">Users</a>', "New"),
                "breadcrumbs--trail",
            ),
            ("/imports/", ("Imports",), "breadcrumbs--single"),
            ("/server/", ("Server", "Settings"), "breadcrumbs--trail"),
            ("/profile/", ("Profile",), "breadcrumbs--single"),
            (
                "/profile/password/",
                ('<a class="breadcrumbs__link" href="/profile/">Profile</a>', "Password"),
                "breadcrumbs--trail",
            ),
            (
                "/reading/sessions/",
                (
                    '<a class="breadcrumbs__link" href="/reading/sessions/">My Marginalia</a>',
                    "By Session",
                ),
                "breadcrumbs--trail",
            ),
            (
                "/reading/import/",
                (
                    '<a class="breadcrumbs__link" href="/reading/sessions/">My Marginalia</a>',
                    "Import",
                ),
                "breadcrumbs--trail",
            ),
            (
                "/reading/export/",
                (
                    '<a class="breadcrumbs__link" href="/reading/sessions/">My Marginalia</a>',
                    "Export",
                ),
                "breadcrumbs--trail",
            ),
            (
                "/client-api/authorize/",
                (
                    '<a class="breadcrumbs__link" href="/profile/">Profile</a>',
                    "Authorize Reader Client",
                ),
                "breadcrumbs--trail",
            ),
        ]

        for path, expected_parts, expected_class in cases:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "breadcrumbs")
                self.assertContains(response, expected_class)
                self.assertContains(response, 'aria-label="Breadcrumb"')
                self.assertContains(response, '<ol class="breadcrumbs__list">')
                self.assertContains(response, 'aria-current="page"')
                for expected in expected_parts:
                    self.assertContains(response, expected, html=False)

    def test_static_breadcrumb_pages_do_not_render_redundant_back_links(self):
        owner = User.objects.create_user(
            username="owner-no-back",
            email="owner-no-back@example.com",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)

        cases = [
            ("/shelves/", ("Back to Dashboard", "arrow_back")),
            ("/groups/new/", ("Back to Groups", "arrow_back")),
            ("/shelves/new/", ("Back to Shelves", "arrow_back")),
            ("/users/new/", ("Back to users",)),
            ("/profile/password/", ("Back to profile",)),
            ("/client-api/authorize/", ("Back to profile",)),
            ("/reading/sessions/", ("Back to Dashboard", "arrow_back")),
            ("/reading/import/", ("Back to Dashboard", "arrow_back")),
            ("/reading/export/", ("Back to Dashboard", "arrow_back")),
        ]

        for path, removed_tokens in cases:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'aria-label="Breadcrumb"')
                for token in removed_tokens:
                    self.assertNotContains(response, token)

    def test_dashboard_still_omits_breadcrumbs(self):
        self.client.force_login(self.user)
        response = self.client.get("/app/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'aria-label="Breadcrumb"')

    def test_book_object_pages_render_breadcrumbs_and_no_back_links(self):
        self.client.force_login(self.user)
        book_id = uuid4()

        response = self.client.get(f"/library/books/{book_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, '<ol class="breadcrumbs__list">')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(
            response, '<a class="breadcrumbs__link" href="/library/">Library</a>', html=False
        )
        self.assertContains(
            response, '<a class="breadcrumbs__link" href="/library/?view=books">Books</a>', html=False
        )
        self.assertContains(response, "Book")
        self.assertNotContains(response, "Back to Library")

        response = self.client.get(f"/library/books/{book_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, '<ol class="breadcrumbs__list">')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(
            response, '<a class="breadcrumbs__link" href="/library/">Library</a>', html=False
        )
        self.assertContains(
            response, '<a class="breadcrumbs__link" href="/library/?view=books">Books</a>', html=False
        )
        self.assertContains(
            response,
            f'<a class="breadcrumbs__link" href="/library/books/{book_id}/">Book</a>',
            html=False,
        )
        self.assertContains(response, "Edit")
        self.assertNotContains(response, "Back to Book")

    def test_group_object_pages_render_breadcrumbs_and_no_back_links(self):
        self.client.force_login(self.user)
        group_id = uuid4()

        response = self.client.get(f"/groups/{group_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, '<ol class="breadcrumbs__list">')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/groups/">Groups</a>',
            html=False,
        )
        self.assertContains(response, "Group")
        self.assertNotContains(response, "Back to Groups")

        response = self.client.get(f"/groups/{group_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, '<ol class="breadcrumbs__list">')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/groups/">Groups</a>',
            html=False,
        )
        self.assertContains(
            response,
            f'<a class="breadcrumbs__link" href="/groups/{group_id}/">Group</a>',
            html=False,
        )
        self.assertContains(response, "Edit")
        self.assertNotContains(response, "Back to Group")

    def test_shelf_object_pages_render_breadcrumbs_and_no_back_links(self):
        self.client.force_login(self.user)
        shelf_id = uuid4()

        response = self.client.get(f"/shelves/{shelf_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, '<ol class="breadcrumbs__list">')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/shelves/">Shelves</a>',
            html=False,
        )
        self.assertContains(response, "Shelf")
        self.assertNotContains(response, "Back to Shelves")

        response = self.client.get(f"/shelves/{shelf_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, '<ol class="breadcrumbs__list">')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/shelves/">Shelves</a>',
            html=False,
        )
        self.assertContains(
            response,
            f'<a class="breadcrumbs__link" href="/shelves/{shelf_id}/">Shelf</a>',
            html=False,
        )
        self.assertContains(response, "Edit")
        self.assertNotContains(response, "Back to Shelf")

    def test_user_edit_page_renders_breadcrumbs_and_no_back_link(self):
        self.client.force_login(self.user)
        profile_id = self.user.profile.id

        response = self.client.get(f"/users/{profile_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, '<ol class="breadcrumbs__list">')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/users/">Users</a>',
            html=False,
        )
        self.assertContains(response, "User")
        self.assertContains(response, "Edit")
        self.assertNotContains(response, "Back to users")
