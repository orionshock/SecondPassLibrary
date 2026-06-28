from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from uuid import uuid4

from accounts.services import get_or_create_profile
from core import server_settings
from accounts.models import UserProfile
from library.group_services import get_public_group
from library.models import LibraryGroupMembership
from reading.models import ReadingSession
from tests.utils.books import create_file_backed_book


User = get_user_model()


class FirstRunProductUiTests(TestCase):
    setup_data = {
        "server_name": "Second Pass Library",
        "server_description": "",
        "public_group_name": "Common Room",
        "public_group_description": "Main Public Library Room for everyone",
        "username": "owner",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "",
        "password1": "Correct-Horse-Battery-47",
        "password2": "Correct-Horse-Battery-47",
    }

    def test_setup_page_is_available_without_active_owner(self):
        response = self.client.get("/setup/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set up your library")
        self.assertContains(response, 'class="setup-layout"')
        self.assertContains(response, "Server")
        self.assertContains(response, "Public Space")
        self.assertContains(response, "Owner Account")
        self.assertContains(response, "Advanced")
        self.assertContains(response, 'name="server_name"')
        self.assertContains(response, 'value="Second Pass Library"')
        self.assertContains(response, 'name="server_description"')
        self.assertContains(response, 'name="public_group_name"')
        self.assertContains(response, 'value="Common Room"')
        self.assertContains(response, 'name="public_group_description"')
        self.assertContains(response, "Main Public Library Room for everyone")
        self.assertContains(response, 'name="advanced_library_groups_enabled"')
        self.assertContains(
            response,
            (
                "Advanced library groups let you create separate curator-managed "
                "library rooms with their own memberships and group-owned shelves. "
                "Leave this off if you only need the Common Room, managed by librarians "
                "as the shared public library space."
            ),
        )
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'name="last_name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')
        self.assertNotContains(
            response,
            'name="advanced_library_groups_enabled" checked',
        )

    @override_settings(DEBUG=False)
    def test_setup_page_is_available_in_production_mode(self):
        response = self.client.get("/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set up your library")

    def test_root_app_and_login_direct_to_setup_without_active_owner(self):
        for path in ("/", "/app/", "/api-auth/login/"):
            with self.subTest(path=path):
                response = self.client.get(path, follow=False)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], "/setup/")

    def test_successful_setup_redirects_to_login_and_login_works(self):
        response = self.client.post("/setup/", self.setup_data, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/")

        owner = User.objects.get(username="owner")
        profile = UserProfile.objects.get(user=owner)
        public_group = get_public_group()
        self.assertTrue(owner.is_active)
        self.assertTrue(owner.is_staff)
        self.assertTrue(owner.is_superuser)
        self.assertEqual(profile.role, UserProfile.ROLE_MANAGER)
        self.assertEqual(server_settings.get_server_name(), "Second Pass Library")
        self.assertEqual(server_settings.get_server_description(), "")
        self.assertEqual(public_group.name, "Common Room")
        self.assertEqual(
            public_group.description,
            "Main Public Library Room for everyone",
        )
        self.assertFalse(server_settings.get_advanced_library_groups_enabled())
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=owner,
                group=public_group,
                is_curator=False,
            ).exists()
        )

        login_response = self.client.post(
            "/api-auth/login/",
            {
                "username": "owner",
                "password": "Correct-Horse-Battery-47",
                "next": "/app/",
            },
            follow=False,
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response["Location"], "/app/")

    def test_setup_redirects_to_login_after_completion(self):
        User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        response = self.client.get("/setup/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/")

    def test_second_setup_post_does_not_create_another_owner(self):
        first = self.client.post("/setup/", self.setup_data, follow=False)
        self.assertEqual(first.status_code, 302)

        second_data = {
            **self.setup_data,
            "username": "owner-two",
            "password1": "Another-Correct-Password-48",
            "password2": "Another-Correct-Password-48",
        }
        second = self.client.post("/setup/", second_data, follow=False)

        self.assertEqual(second.status_code, 302)
        self.assertEqual(second["Location"], "/api-auth/login/")
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)


class ProductUiSmokeTests(TestCase):
    def setUp(self):
        self.bootstrap_owner = User.objects.create_superuser(
            username="bootstrap-owner",
            email="bootstrap-owner@example.com",
            password="pw",
        )
        self.user = User.objects.create_user(
            username="u", email="u@example.com", password="pw"
        )

    def test_root_redirects_to_app(self):
        response = self.client.get("/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/app/")

    def test_unauthenticated_app_redirects_to_login(self):
        response = self.client.get("/app/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/app/")

    def test_unauthenticated_server_settings_redirects_to_login(self):
        response = self.client.get("/server/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/server/")

    def test_owner_server_settings_returns_200_and_has_form_and_service_hatch_link(self):
        owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)
        response = self.client.get("/server/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Server Settings")
        self.assertContains(response, 'id="server-settings-form"')
        self.assertContains(response, 'id="server-settings-public-name-input"')
        self.assertContains(response, 'id="server-settings-public-description-input"')
        self.assertContains(response, 'id="server-settings-advanced-groups-input"')
        self.assertContains(response, 'href="/admin/"')

    def test_manager_server_settings_is_not_allowed(self):
        manager = User.objects.create_user(
            username="manager", email="m@example.com", password="pw"
        )
        profile = get_or_create_profile(user=manager)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])

        self.client.force_login(manager)
        response = self.client.get("/server/", follow=False)
        self.assertEqual(response.status_code, 403)

    def test_login_page_uses_configured_server_identity(self):
        server_settings.set_server_name("My Library")
        server_settings.set_server_description("Private family library.")
        response = self.client.get("/api-auth/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Library")
        self.assertContains(response, "A SecondPass Library")
        self.assertContains(response, "Private family library.")

    def test_base_template_has_no_service_hatch_nav_link(self):
        self.client.force_login(self.user)
        response = self.client.get("/app/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/admin/"')
        self.assertContains(response, 'href="/server/"')
        self.assertContains(response, "Server Settings")

    def test_product_ui_has_themed_controls_and_fixed_header(self):
        css = Path("web/static/web/app.css").read_text(encoding="utf-8")
        base_template = Path("web/templates/web/base.html").read_text(
            encoding="utf-8"
        )
        layout_js = Path("web/static/web/js/layout.js").read_text(
            encoding="utf-8"
        )
        main_js = Path("web/static/web/js/main.js").read_text(encoding="utf-8")

        self.assertIn("--control-bg:", css)
        self.assertIn("--control-text:", css)
        self.assertIn("--control-border:", css)
        self.assertIn("--control-disabled-bg:", css)
        self.assertIn("color-scheme: dark", css)
        self.assertIn('input:not([type="checkbox"])', css)
        self.assertIn("select,", css)
        self.assertIn("textarea", css)
        self.assertIn(":focus-visible", css)
        self.assertIn(":disabled", css)
        self.assertIn("[readonly]", css)
        self.assertIn("select option", css)
        self.assertIn('input[type="file"]::file-selector-button', css)

        self.assertIn(".topbar {", css)
        self.assertIn("position: fixed", css)
        self.assertIn("top: 0", css)
        self.assertIn("right: 0", css)
        self.assertIn("left: 0", css)
        self.assertIn("z-index: 100", css)
        self.assertIn("isolation: isolate", css)
        self.assertIn("border-bottom: 1px solid var(--border)", css)
        self.assertIn("--app-header-height:", css)
        self.assertIn("padding-top: var(--app-header-height)", css)
        self.assertIn(
            "scroll-padding-top: calc(var(--app-header-height) + 8px)",
            css,
        )
        self.assertIn("export function initAppHeaderLayout", layout_js)
        self.assertIn("new ResizeObserver(updateHeaderHeight)", layout_js)
        self.assertIn('"--app-header-height"', layout_js)
        self.assertIn("initAppHeaderLayout();", main_js)
        self.assertIn('<header class="topbar">', base_template)
        self.assertIn('<div class="container topbar__inner">', base_template)

    def test_product_ui_avoids_legacy_decorative_entities(self):
        source_paths = [
            *Path("web/templates/web").rglob("*.html"),
            *Path("web/static/web/js").rglob("*.js"),
        ]
        sources = {
            str(path): path.read_text(encoding="utf-8")
            for path in source_paths
        }
        forbidden = (
            "&middot;",
            "&larr;",
            "&rarr;",
            "&mdash;",
            "&ndash;",
            "\u00c2\u00b7",
            "\u00b7",
            "\u2190",
            "\u2192",
            "\u2014",
            "\u2013",
        )

        for path, text in sources.items():
            for token in forbidden:
                self.assertNotIn(token, text, msg=f"{token!r} remains in {path}")

        template_text = "\n".join(
            text for path, text in sources.items() if path.endswith(".html")
        )
        self.assertIn('class="pill back-link"', template_text)
        self.assertIn(
            '<span class="material-symbols-outlined" aria-hidden="true">arrow_back</span>',
            template_text,
        )

        css = Path("web/static/web/app.css").read_text(encoding="utf-8")
        self.assertIn(".back-link", css)
        self.assertIn(".metadata-piece + .metadata-piece::before", css)
        self.assertIn(
            ".shelf-metadata-piece + .shelf-metadata-piece::before",
            css,
        )

    def test_authenticated_app_returns_200_and_title(self):
        self.client.force_login(self.user)
        response = self.client.get("/app/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Second Pass Library")
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, "fonts.googleapis.com/css2?family=Material+Symbols+Outlined")
        self.assertContains(response, "/static/web/favicon.png")
        self.assertContains(response, 'class="brand__icon"')
        self.assertContains(response, 'aria-hidden="true"')
        self.assertNotContains(response, "/static/web/js/groups.js")
        self.assertNotContains(response, "/static/web/js/shelves.js")
        self.assertNotContains(response, "/static/web/js/users.js")
        self.assertNotContains(response, "/static/web/js/book_edit.js")
        self.assertContains(response, 'id="ui-global-error"')
        self.assertContains(response, 'id="recent-reading-section"')
        self.assertContains(response, 'id="recent-reading-status"')
        self.assertContains(response, 'id="recent-reading-list"')
        self.assertNotContains(response, "All reading sessions")
        self.assertContains(response, 'aria-label="Dashboard actions"')
        self.assertContains(response, 'href="/library/"')
        self.assertContains(response, "Browse library")
        self.assertNotContains(response, "Import books")
        self.assertContains(response, 'href="/shelves/"')
        self.assertContains(response, "View shelves")
        self.assertContains(response, 'href="/reading/sessions/"')
        self.assertContains(response, "Reading Sessions")
        self.assertContains(response, 'href="/reading/import/"')
        self.assertContains(response, "Import SPL Marginalia")
        self.assertContains(response, 'href="/reading/export/"')
        self.assertContains(response, "Export SPL Marginalia")
        self.assertNotContains(response, "Future activity dashboard")
        self.assertNotContains(response, 'id="future-activity-dashboard"')
        self.assertContains(response, 'href="/profile/"')

    def test_favicon_ico_route_works(self):
        response = self.client.get("/favicon.ico", follow=False)
        self.assertIn(response.status_code, (200, 301, 302))
        if response.status_code in (301, 302):
            self.assertIn("/static/web/favicon.png", response["Location"])

    def test_must_change_password_redirects_product_ui_to_profile_password(self):
        profile = get_or_create_profile(user=self.user)
        profile.must_change_password = True
        profile.save(update_fields=["must_change_password", "updated_at"])
        self.client.force_login(self.user)
        response = self.client.get("/app/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/profile/password/")

    def test_must_change_password_allows_profile_password_page(self):
        profile = get_or_create_profile(user=self.user)
        profile.must_change_password = True
        profile.save(update_fields=["must_change_password", "updated_at"])
        self.client.force_login(self.user)
        response = self.client.get("/profile/password/", follow=False)
        self.assertEqual(response.status_code, 200)

    def test_unusable_password_user_is_not_forced_to_local_password_change(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        profile = get_or_create_profile(user=self.user)
        profile.must_change_password = True
        profile.save(update_fields=["must_change_password", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.get("/app/", follow=False)

        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_library_redirects_to_login(self):
        response = self.client.get("/library/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/library/")

    def test_authenticated_library_returns_200(self):
        self.client.force_login(self.user)
        response = self.client.get("/library/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Second Pass Library")
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="library-search"')
        self.assertContains(response, 'id="q"')
        self.assertContains(response, 'id="library-tab-books"')
        self.assertContains(response, 'id="library-tab-authors"')
        self.assertContains(response, 'id="library-tab-series"')
        self.assertContains(response, 'data-view="books"')
        self.assertContains(response, 'data-view="authors"')
        self.assertContains(response, 'data-view="series"')
        self.assertContains(response, 'id="library-filter-summary"')
        self.assertContains(response, 'id="library-page-size"')
        self.assertContains(response, '<option value="20" selected>20</option>')
        self.assertContains(response, '<option value="30">30</option>')
        self.assertContains(response, '<option value="40">40</option>')
        self.assertContains(response, '<option value="50">50</option>')
        self.assertContains(response, 'id="library-range"')
        self.assertContains(response, 'class="pager library-pager library-pager--sticky"')
        self.assertContains(response, 'id="library-results"')
        self.assertContains(response, 'id="ui-global-error"')

    def test_unauthenticated_book_detail_redirects_to_login(self):
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], f"/api-auth/login/?next=/library/books/{book_id}/"
        )

    def test_unauthenticated_book_edit_redirects_to_login(self):
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/edit/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"/api-auth/login/?next=/library/books/{book_id}/edit/",
        )

    def test_authenticated_book_detail_returns_200_and_has_container(self):
        self.client.force_login(self.user)
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="book-detail"')
        self.assertContains(response, f'data-book-id="{book_id}"')
        self.assertContains(response, 'id="book-groups"')
        self.assertContains(response, 'id="book-shelves"')
        self.assertContains(response, 'id="book-edit-link-wrap"')
        self.assertContains(response, 'id="book-download-link"')
        self.assertContains(response, 'id="book-summary-toggle"')
        self.assertContains(response, 'data-tab="shelves"')
        self.assertContains(response, 'data-tab="groups"')
        self.assertContains(response, 'data-tab="metadata"')
        self.assertContains(response, 'data-tab-panel="shelves"')
        self.assertContains(response, 'data-tab-panel="groups"')
        self.assertContains(response, 'data-tab-panel="metadata"')
        self.assertContains(response, 'id="tab-metadata"')
        self.assertContains(
            response, f'href="/library/books/{book_id}/edit/"'
        )

    def test_authenticated_book_edit_returns_200_and_has_form_container(self):
        self.client.force_login(self.user)
        book_id = uuid4()
        response = self.client.get(f"/library/books/{book_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="book-edit-header"')
        self.assertContains(response, 'id="book-edit"')
        self.assertContains(response, f'data-book-id="{book_id}"')
        self.assertContains(response, 'data-tab="metadata"')
        self.assertContains(response, 'data-tab="authors"')
        self.assertContains(response, 'data-tab="groups"')
        self.assertContains(response, 'data-tab="shelves"')
        self.assertContains(response, 'data-tab="idents"')
        self.assertContains(response, 'id="tab-metadata"')
        self.assertContains(response, 'id="tab-authors"')
        self.assertContains(response, 'id="tab-groups"')
        self.assertContains(response, 'id="tab-shelves"')
        self.assertContains(response, 'id="tab-idents"')
        self.assertContains(response, 'id="book-edit-form"')
        self.assertContains(response, 'id="book-edit-authors-selected"')
        self.assertContains(response, 'id="book-edit-author-add-select"')
        self.assertContains(response, 'id="book-edit-author-new-name"')
        self.assertContains(response, 'id="book-edit-series-select"')
        self.assertContains(response, 'id="book-edit-series-new-name"')
        self.assertContains(response, 'id="book-edit-series-index"')
        self.assertContains(response, 'step="0.1"')
        self.assertContains(response, 'id="book-edit-identifiers"')
        self.assertContains(response, 'id="book-edit-file-info"')
        self.assertContains(response, 'id="book-edit-groups"')
        self.assertContains(response, 'id="book-edit-groups-add"')
        self.assertContains(response, 'id="book-edit-shelves"')
        self.assertContains(response, 'id="book-edit-shelves-status"')

    def test_unauthenticated_imports_redirects_to_login(self):
        response = self.client.get("/imports/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/imports/")

    def test_authenticated_imports_returns_200_and_has_upload_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/imports/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="imports-upload"')
        self.assertContains(response, 'id="imports-results"')

    def test_unauthenticated_groups_redirects_to_login(self):
        response = self.client.get("/groups/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/groups/")

    def test_authenticated_groups_returns_200_and_has_containers(self):
        self.client.force_login(self.user)
        response = self.client.get("/groups/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="groups-status"')
        self.assertContains(response, 'id="groups-results"')
        self.assertContains(response, 'id="groups-prev"')
        self.assertContains(response, 'id="groups-next"')

    def test_unauthenticated_group_detail_redirects_to_login(self):
        group_id = uuid4()
        response = self.client.get(f"/groups/{group_id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], f"/api-auth/login/?next=/groups/{group_id}/"
        )

    def test_unauthenticated_group_new_redirects_to_login(self):
        response = self.client.get("/groups/new/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/groups/new/")

    def test_authenticated_group_new_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/groups/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-page="group-new"')
        self.assertContains(response, 'id="group-new-form"')

    def test_authenticated_group_detail_returns_200_and_has_container(self):
        self.client.force_login(self.user)
        group_id = uuid4()
        response = self.client.get(f"/groups/{group_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="group-view-root"')
        self.assertContains(response, f'data-group-id="{group_id}"')
        self.assertContains(response, 'id="group-view-books-results"')
        self.assertContains(response, 'id="group-view-members-results"')
        self.assertContains(response, 'id="group-view-shelves-results"')

    def test_unauthenticated_group_edit_redirects_to_login(self):
        group_id = uuid4()
        response = self.client.get(f"/groups/{group_id}/edit/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], f"/api-auth/login/?next=/groups/{group_id}/edit/"
        )

    def test_authenticated_group_edit_returns_200_and_has_container(self):
        self.client.force_login(self.user)
        group_id = uuid4()
        response = self.client.get(f"/groups/{group_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="group-edit-root"')
        self.assertContains(response, f'data-group-id="{group_id}"')
        self.assertContains(response, 'data-tab="details"')
        self.assertContains(response, 'data-tab="books"')
        self.assertContains(response, 'data-tab="members"')
        self.assertContains(response, 'data-tab="shelves"')
        self.assertContains(response, 'id="group-edit-book-search-form"')
        self.assertContains(response, 'id="group-edit-book-search-results"')
        self.assertContains(response, 'id="group-edit-shelves-results"')
        self.assertContains(response, 'id="group-edit-shelves-actions"')
        self.assertContains(response, 'id="group-delete-root"')
        self.assertContains(
            response,
            "Managers, librarians, and owners can already manage books globally.",
        )
        self.assertContains(response, "Curator identifies members who specifically steward this group")
        self.assertContains(
            response, "group-scoped management access to readers."
        )

    def test_unauthenticated_shelves_redirects_to_login(self):
        response = self.client.get("/shelves/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/shelves/")

    def test_authenticated_shelves_returns_200_and_has_containers(self):
        self.client.force_login(self.user)
        response = self.client.get("/shelves/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, "Personal Shelves")
        self.assertContains(response, "Shared Shelves")
        self.assertContains(response, 'id="personal-shelves-status"')
        self.assertContains(response, 'id="personal-shelves-results"')
        self.assertContains(response, 'id="personal-shelves-prev"')
        self.assertContains(response, 'id="personal-shelves-next"')
        self.assertContains(response, 'id="personal-shelves-page-note"')
        self.assertContains(response, 'id="shared-shelves-status"')
        self.assertContains(response, 'id="shared-shelves-results"')
        self.assertContains(response, 'id="shared-shelves-prev"')
        self.assertContains(response, 'id="shared-shelves-next"')
        self.assertContains(response, 'id="shared-shelves-page-note"')
        self.assertContains(response, 'href="/shelves/new/"')
        self.assertContains(response, "New shelf")

    def test_unauthenticated_shelf_new_redirects_to_login(self):
        response = self.client.get("/shelves/new/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/shelves/new/")

    def test_authenticated_shelf_new_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/shelves/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shelf-new-form"')
        self.assertContains(response, 'id="shelf-new-owner-type"')
        self.assertContains(response, 'id="shelf-new-owner-group"')
        self.assertContains(response, 'id="shelf-new-owner-type-row"')
        self.assertContains(response, 'id="shelf-new-owner-group-row"')

    def test_shelf_create_js_gates_group_owner_controls_by_current_user(self):
        new_js = Path("web/static/web/js/shelves/new.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("const me = await loadMeAndInitShell()", new_js)
        self.assertIn("export function canCreateGroupShelves(me)", new_js)
        self.assertIn("canManageLibrary(me)", new_js)
        self.assertIn("group.is_curator === true", new_js)
        self.assertIn("group.capabilities.can_curate === true", new_js)
        self.assertIn("!group.is_public_group", new_js)
        self.assertNotIn("curated_group_ids", new_js)
        self.assertNotIn("membership_role", new_js)
        self.assertNotIn("can_create_shelf", new_js)
        self.assertIn("export function manageableShelfGroups(me, groups)", new_js)
        self.assertIn("availableGroups.filter", new_js)
        self.assertIn("visible(ownerTypeRow, canCreateGroupShelf)", new_js)
        self.assertIn("visible(ownerGroupRow, canCreateGroupShelf)", new_js)
        self.assertIn('ownerTypeEl.value = "user"', new_js)
        self.assertIn(
            'canCreateGroupShelf && ownerTypeEl.value === "group"',
            new_js,
        )
        self.assertIn("owner_type: ownerType", new_js)
        self.assertIn('if (ownerType === "user")', new_js)

    def test_unauthenticated_shelf_detail_redirects_to_login(self):
        shelf_id = uuid4()
        response = self.client.get(f"/shelves/{shelf_id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/api-auth/login/?next=/shelves/{shelf_id}/")

    def test_authenticated_shelf_detail_returns_200_and_has_container(self):
        self.client.force_login(self.user)
        shelf_id = uuid4()
        response = self.client.get(f"/shelves/{shelf_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-shelf-id="{shelf_id}"')
        self.assertContains(response, 'id="shelf-view-summary"')
        self.assertContains(response, 'id="shelf-view-description"')
        self.assertContains(response, 'id="shelf-view-created-by"')
        self.assertContains(response, 'id="shelf-view-items-results"')
        self.assertContains(response, 'id="shelf-view-items-prev"')
        self.assertContains(response, 'id="shelf-view-items-next"')
        self.assertContains(response, 'id="shelf-view-items-page-note"')
        self.assertContains(response, "arrow_back")
        self.assertContains(response, 'id="shelf-view-edit-link"')
        self.assertNotContains(response, ">Details</h2>")
        self.assertNotContains(response, ">Books</h2>")

    def test_unauthenticated_shelf_edit_redirects_to_login(self):
        shelf_id = uuid4()
        response = self.client.get(f"/shelves/{shelf_id}/edit/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/api-auth/login/?next=/shelves/{shelf_id}/edit/")

    def test_authenticated_shelf_edit_returns_200_and_has_container(self):
        self.client.force_login(self.user)
        shelf_id = uuid4()
        response = self.client.get(f"/shelves/{shelf_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-shelf-id="{shelf_id}"')
        self.assertContains(response, 'id="shelf-edit-owner-context"')
        self.assertContains(response, 'id="shelf-edit-tabs"')
        self.assertContains(response, 'id="shelf-edit-tab-books"')
        self.assertContains(response, 'id="shelf-edit-tab-add"')
        self.assertContains(response, 'id="shelf-edit-tab-details"')
        self.assertContains(response, 'id="shelf-edit-panel-books"')
        self.assertContains(response, 'id="shelf-edit-panel-add"')
        self.assertContains(response, 'id="shelf-edit-panel-details"')
        self.assertContains(response, 'id="shelf-edit-form"')
        self.assertContains(response, 'id="shelf-edit-items-results"')
        self.assertContains(response, 'id="shelf-edit-book-search-form"')
        self.assertContains(response, 'id="shelf-edit-danger"')
        self.assertContains(response, 'id="shelf-edit-delete-btn"')

    def test_shelf_items_js_has_move_controls(self):
        js = Path("web/static/web/js/shelves/items.js").read_text()
        self.assertIn('data-action="move-up"', js)
        self.assertIn('data-action="move-down"', js)
        self.assertIn('data-action="move-to"', js)
        self.assertIn('aria-label="Move ${escapeHtml(title)} to position"', js)
        self.assertIn("patchShelfItemPosition", js)
        self.assertIn("storedPosition >= currentItemTotal - 1", js)

    def test_product_ui_tabs_use_shared_helper(self):
        helper_js = Path("web/static/web/js/ui/tabs.js").read_text(encoding="utf-8")
        book_edit_main_js = Path("web/static/web/js/book_edit/main.js").read_text(encoding="utf-8")
        group_shared_js = Path("web/static/web/js/groups/shared.js").read_text(encoding="utf-8")
        group_edit_js = Path("web/static/web/js/groups/edit.js").read_text(encoding="utf-8")
        group_view_js = Path("web/static/web/js/groups/view.js").read_text(encoding="utf-8")
        book_detail_js = Path("web/static/web/js/library/detail.js").read_text(encoding="utf-8")

        self.assertIn("export function initTabs", helper_js)
        self.assertIn(".tab-button[data-tab]", helper_js)
        self.assertIn("[data-tab-panel]", helper_js)
        self.assertIn("aria-selected", helper_js)
        self.assertIn("aria-hidden", helper_js)
        self.assertIn("is-active", helper_js)
        self.assertIn("is-hidden", helper_js)

        self.assertIn('from "../ui/tabs.js"', book_edit_main_js)
        self.assertIn('defaultTab: "metadata"', book_edit_main_js)
        self.assertNotIn('from "./tabs.js"', book_edit_main_js)
        self.assertNotIn("initTabs", group_shared_js)
        self.assertIn('from "../ui/tabs.js"', group_edit_js)
        self.assertIn('from "../ui/tabs.js"', group_view_js)
        self.assertIn('from "../ui/tabs.js"', book_detail_js)
        self.assertNotIn("function initTabs(root)", book_detail_js)

    def test_product_ui_status_helpers_use_shared_helper(self):
        helper_js = Path("web/static/web/js/ui/status.js").read_text(encoding="utf-8")
        group_shared_js = Path("web/static/web/js/groups/shared.js").read_text(encoding="utf-8")
        group_view_js = Path("web/static/web/js/groups/view.js").read_text(encoding="utf-8")
        shelves_shared_js = Path("web/static/web/js/shelves/shared.js").read_text(encoding="utf-8")
        shelves_view_js = Path("web/static/web/js/shelves/view.js").read_text(encoding="utf-8")
        book_edit_shared_js = Path("web/static/web/js/book_edit/shared.js").read_text(encoding="utf-8")
        book_edit_main_js = Path("web/static/web/js/book_edit/main.js").read_text(encoding="utf-8")
        book_edit_status_modules = [
            Path(path).read_text(encoding="utf-8")
            for path in (
                "web/static/web/js/book_edit/main.js",
                "web/static/web/js/book_edit/author_series_actions.js",
                "web/static/web/js/book_edit/group_actions.js",
                "web/static/web/js/book_edit/identifiers_actions.js",
                "web/static/web/js/book_edit/shelf_actions.js",
                "web/static/web/js/book_edit/shelves.js",
            )
        ]
        migrated_status_modules = [
            Path(path).read_text(encoding="utf-8")
            for path in (
                "web/static/web/js/profile/password.js",
                "web/static/web/js/library/list.js",
                "web/static/web/js/library/detail.js",
                "web/static/web/js/groups/new.js",
                "web/static/web/js/groups/edit.js",
                "web/static/web/js/imports/main.js",
                "web/static/web/js/server/settings.js",
                "web/static/web/js/users/list.js",
                "web/static/web/js/users/edit.js",
                "web/static/web/js/users/new.js",
                "web/static/web/js/users/memberships.js",
                "web/static/web/js/users/password_reset.js",
            )
        ]
        users_shared_js = Path("web/static/web/js/users/shared.js").read_text(encoding="utf-8")

        self.assertIn("export function setStatus", helper_js)
        self.assertIn("export function clearStatus", helper_js)
        self.assertIn("document.querySelector", helper_js)
        self.assertIn("textContent", helper_js)
        self.assertIn("classList.toggle", helper_js)
        self.assertIn("errorClass", helper_js)
        self.assertIn('typeof options === "boolean"', helper_js)

        self.assertIn('from "../ui/status.js"', group_view_js)
        self.assertNotIn("export function setStatus", group_shared_js)
        self.assertNotIn("setSharedStatus", group_shared_js)
        self.assertIn('from "../ui/status.js"', shelves_view_js)
        self.assertNotIn("export function setStatus", shelves_shared_js)
        self.assertNotIn("setSharedStatus", shelves_shared_js)
        self.assertIn('from "../ui/status.js"', book_edit_main_js)
        self.assertNotIn("export function setInlineStatus", book_edit_shared_js)
        self.assertNotIn("setSharedStatus", book_edit_shared_js)
        self.assertNotIn("setInlineStatus", "\n".join(book_edit_status_modules))
        for module_js in migrated_status_modules:
            self.assertIn('from "../ui/status.js"', module_js)
        self.assertNotIn("function setStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("function setSaveStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("function setResetStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("function setMembershipsStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("function setAddStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("setElStatus", users_shared_js)

    def test_shelves_and_groups_use_shared_paged_list_helper(self):
        helper_js = Path("web/static/web/js/ui/paged_list.js").read_text(encoding="utf-8")
        shelves_list_js = Path("web/static/web/js/shelves/list.js").read_text(encoding="utf-8")
        shelves_shared_js = Path("web/static/web/js/shelves/shared.js").read_text(encoding="utf-8")
        groups_list_js = Path("web/static/web/js/groups/list.js").read_text(encoding="utf-8")
        groups_view_js = Path("web/static/web/js/groups/view.js").read_text(encoding="utf-8")
        groups_shared_js = Path("web/static/web/js/groups/shared.js").read_text(encoding="utf-8")
        main_js = Path("web/static/web/js/main.js").read_text(encoding="utf-8")

        self.assertIn("export async function createPagedListController", helper_js)
        self.assertIn("fetchJSON", helper_js)
        self.assertIn("setStatus", helper_js)
        self.assertIn("nextBtn.addEventListener", helper_js)
        self.assertIn("prevBtn.addEventListener", helper_js)
        self.assertIn("reloadFirstPage", helper_js)

        self.assertIn('from "../ui/paged_list.js"', shelves_list_js)
        self.assertIn("createPagedListController", shelves_list_js)
        self.assertNotIn("pagedController", shelves_shared_js)
        self.assertIn('from "../ui/paged_list.js"', groups_list_js)
        self.assertIn('from "../ui/paged_list.js"', groups_view_js)
        self.assertNotIn("pagedListController", groups_shared_js)

        self.assertIn('shelves: { importer: () => import("./shelves/main.js")', main_js)
        self.assertIn('groups: { importer: () => import("./groups/main.js")', main_js)

    def test_shelf_js_has_friendly_ownership_display(self):
        identity_js = Path("web/static/web/js/ui/identity.js").read_text(
            encoding="utf-8"
        )
        group_badge_js = Path("web/static/web/js/ui/groups.js").read_text(
            encoding="utf-8"
        )
        shared_js = Path("web/static/web/js/shelves/shared.js").read_text(encoding="utf-8")
        library_list_js = Path("web/static/web/js/library/list.js").read_text(encoding="utf-8")
        cover_previews_js = Path("web/static/web/js/ui/cover_previews.js").read_text(
            encoding="utf-8"
        )
        users_list_js = Path("web/static/web/js/users/list.js").read_text(
            encoding="utf-8"
        )
        user_memberships_js = Path(
            "web/static/web/js/users/memberships.js"
        ).read_text(encoding="utf-8")
        list_js = Path("web/static/web/js/shelves/list.js").read_text(encoding="utf-8")
        view_js = Path("web/static/web/js/shelves/view.js").read_text(encoding="utf-8")
        edit_js = Path("web/static/web/js/shelves/edit.js").read_text(encoding="utf-8")
        book_edit_shelves_js = Path("web/static/web/js/book_edit/shelves.js").read_text(encoding="utf-8")
        groups_shared_js = Path("web/static/web/js/groups/shared.js").read_text(encoding="utf-8")
        css = Path("web/static/web/app.css").read_text(encoding="utf-8")

        self.assertIn("export function userDisplayName", identity_js)
        self.assertIn("export function userHandle", identity_js)
        self.assertIn("export function userIdentityText", identity_js)
        self.assertIn("export function renderUserIdentity", identity_js)
        self.assertIn('[firstName, lastName].filter(Boolean).join(" ")', identity_js)
        self.assertIn("`<@${username}>`", identity_js)
        self.assertIn('parts.join(", ")', identity_js)
        self.assertIn('"Unknown user"', identity_js)
        self.assertIn("options.includeEmail === true", identity_js)
        self.assertIn("options.includeDisplayName === false", identity_js)
        self.assertIn('icon.textContent = "person"', identity_js)
        self.assertIn("piece.textContent = text", identity_js)
        self.assertIn("document.createElement", identity_js)
        self.assertNotIn("innerHTML", identity_js)
        self.assertNotIn("profile_id", identity_js)
        self.assertNotIn("user.id", identity_js)
        self.assertNotIn("user.pk", identity_js)

        self.assertIn("export function groupDisplayName", group_badge_js)
        self.assertIn("export function groupBadgeText", group_badge_js)
        self.assertIn("export function renderGroupBadge", group_badge_js)
        self.assertIn('"Unknown group"', group_badge_js)
        self.assertIn('badge.classList.add("group-badge--public")', group_badge_js)
        self.assertIn('isPublicGroup ? "public" : "groups"', group_badge_js)
        self.assertIn("name.textContent = groupDisplayName(group)", group_badge_js)
        self.assertIn("document.createElement", group_badge_js)
        self.assertNotIn("innerHTML", group_badge_js)
        self.assertNotIn("group.id", group_badge_js)

        self.assertIn('from "../ui/groups.js"', shared_js)
        self.assertIn('from "../ui/identity.js"', shared_js)
        self.assertIn("renderUserIdentity(shelf.owner_user", shared_js)
        self.assertIn("renderGroupBadge(shelf.owner_group", shared_js)
        self.assertIn("shelfOwnerIdentitySegment", shared_js)
        self.assertIn("shelfMetadataLine", shared_js)
        self.assertIn("renderShelfMetadata", shared_js)
        self.assertIn("groups", shared_js)
        self.assertIn("shelf-metadata-piece", shared_js)
        self.assertNotIn("&middot;", shared_js)
        self.assertNotIn("\u00c2\u00b7", shared_js)
        self.assertIn("profile_id", shared_js)
        self.assertNotIn("Owned by you", shared_js)
        self.assertNotIn("Owned by ", shared_js)
        self.assertNotIn("profile_id}</span>", shared_js)
        self.assertNotIn(".email", shared_js)
        self.assertNotIn("shelfOwnerChip", shared_js)

        self.assertIn('from "../ui/identity.js"', users_list_js)
        self.assertIn("renderUserIdentity(user", users_list_js)
        self.assertIn("userIdentityText", users_list_js)
        self.assertIn("includeEmail: true", users_list_js)
        self.assertIn("group.is_curator === true", users_list_js)
        self.assertNotIn("membership_role", users_list_js)
        self.assertNotIn('<span class="pill">active</span>', users_list_js)
        self.assertIn('<span class="pill">inactive</span>', users_list_js)
        self.assertIn("function titleCaseRole", users_list_js)
        self.assertIn("function userSortName", users_list_js)
        self.assertIn("function roleSortValue", users_list_js)
        self.assertIn("function lastLoginTime", users_list_js)
        self.assertIn("function renderHeader", users_list_js)
        self.assertIn("function sortButton", users_list_js)
        self.assertIn("function sortedUsers", users_list_js)
        self.assertIn('name: "Name"', users_list_js)
        self.assertIn('username: "Username"', users_list_js)
        self.assertIn('email: "Email"', users_list_js)
        self.assertIn('role: "Role"', users_list_js)
        self.assertIn('last_login: "Last Login"', users_list_js)
        self.assertIn('let sortKey = "role"', users_list_js)
        self.assertIn('let sortDirection = "desc"', users_list_js)
        self.assertIn('data-sort="${escapeHtml(key)}"', users_list_js)
        self.assertIn("aria-sort", users_list_js)
        self.assertIn("sortDirection", users_list_js)
        self.assertIn('source.closest("button[data-sort]")', users_list_js)
        self.assertIn('return "Librarian"', users_list_js)
        self.assertIn('return "Manager"', users_list_js)
        self.assertIn('return "Reader"', users_list_js)
        self.assertIn("const roleBadge = isOwner", users_list_js)
        self.assertIn('<span class="pill pill--owner">Owner</span>', users_list_js)
        self.assertIn('class="user-row__identity"', users_list_js)
        self.assertIn('class="user-row__role"', users_list_js)
        self.assertIn('class="user-row__last-login"', users_list_js)
        self.assertIn('class="user-row__memberships"', users_list_js)
        self.assertIn('class="user-row__badge-list"', users_list_js)
        self.assertIn('class="users-header"', users_list_js)
        self.assertIn("Groups / Curates", users_list_js)
        self.assertIn('aria-label="${escapeHtml(editLabel)}"', users_list_js)
        self.assertIn('class="icon-button"', users_list_js)
        self.assertIn(">edit</span>", users_list_js)
        self.assertNotIn("ownerBadge", users_list_js)
        self.assertNotIn("${escapeHtml(username)}", users_list_js)
        self.assertNotIn('href="${escapeHtml(editHref)}">Edit</a>', users_list_js)
        self.assertNotIn("user-row__column-label", users_list_js)

        self.assertIn('from "../ui/groups.js"', library_list_js)
        self.assertIn('from "../ui/cover_previews.js"', library_list_js)
        self.assertIn("renderGroupBadge(group, { compact: true })", library_list_js)
        self.assertIn("renderCoverPreviewStrip(author.preview_books", library_list_js)
        self.assertIn("renderCoverPreviewStrip(series.preview_books", library_list_js)
        self.assertIn('include_preview_books: "true"', library_list_js)
        self.assertEqual(library_list_js.count('include_preview_books: "true"'), 2)
        self.assertIn("function publishedYear", library_list_js)
        self.assertIn("function compactSubtitle", library_list_js)
        self.assertIn("const DEFAULT_PAGE_SIZE = 20", library_list_js)
        self.assertIn("const PAGE_SIZE_OPTIONS = [20, 30, 40, 50]", library_list_js)
        self.assertIn('const VIEWS = new Set(["books", "authors", "series"])', library_list_js)
        self.assertIn("function renderTags", library_list_js)
        self.assertIn("function renderGroups", library_list_js)
        self.assertIn("function visibleBookCountLabel", library_list_js)
        self.assertIn('return `${value} ${value === 1 ? "Book" : "Books"}`', library_list_js)
        self.assertNotIn("visible ${value", library_list_js)
        self.assertNotIn("visible book", library_list_js)
        self.assertIn("function renderAuthors", library_list_js)
        self.assertIn("function renderSeries", library_list_js)
        self.assertIn("function rangeText", library_list_js)
        self.assertIn('return "Showing 0 of 0"', library_list_js)
        self.assertIn("`Showing ${start}-${end} of ${count}`", library_list_js)
        self.assertIn("function apiUrlForState", library_list_js)
        self.assertIn('urlWithParams("/api/v1/library/books/"', library_list_js)
        self.assertIn('urlWithParams("/api/v1/library/authors/"', library_list_js)
        self.assertIn('urlWithParams("/api/v1/library/series/"', library_list_js)
        self.assertIn('page: state.page', library_list_js)
        self.assertIn('page_size: state.pageSize', library_list_js)
        self.assertIn("author: state.authorId", library_list_js)
        self.assertIn("series: state.seriesId", library_list_js)
        self.assertIn('ordering: state.seriesId ? "series_index" : ""', library_list_js)
        self.assertIn("function locationParamsForState", library_list_js)
        self.assertIn("view: state.view", library_list_js)
        self.assertIn("function activeFilter", library_list_js)
        self.assertIn('data-action="clear-library-filter"', library_list_js)
        self.assertIn("state.page = 1", library_list_js)
        self.assertIn('pageSizeSelect.addEventListener("change"', library_list_js)
        self.assertIn("state.page += 1", library_list_js)
        self.assertIn("state.page = Math.max(1, state.page - 1)", library_list_js)
        self.assertIn("for (const tab of viewTabs)", library_list_js)
        self.assertIn('tab.addEventListener("click"', library_list_js)
        self.assertIn('data-action="browse-author"', library_list_js)
        self.assertIn('data-action="browse-series"', library_list_js)
        self.assertIn('aria-label="View books by ${escapeHtml(name)}"', library_list_js)
        self.assertIn('aria-label="View books in ${escapeHtml(name)}"', library_list_js)
        self.assertIn('class="library-browse-row__main library-browse-row__primary"', library_list_js)
        self.assertIn("renderCoverPreviewStrip(author.preview_books", library_list_js)
        self.assertIn("renderCoverPreviewStrip(series.preview_books", library_list_js)
        self.assertIn('source.closest(\'[data-action="browse-author"]\')', library_list_js)
        self.assertIn('source.closest(\'[data-action="browse-series"]\')', library_list_js)
        self.assertIn("state.authorId = authorButton.getAttribute", library_list_js)
        self.assertIn("state.seriesId = seriesButton.getAttribute", library_list_js)
        self.assertIn('state.view = "books"', library_list_js)
        self.assertIn('state.view = VIEWS.has(view) ? view : "books"', library_list_js)
        self.assertIn("payload && payload.next", library_list_js)
        self.assertIn("payload && payload.previous", library_list_js)
        self.assertIn("window.history.pushState", library_list_js)
        self.assertIn("window.history.replaceState", library_list_js)
        self.assertIn("mountCovers(resultsEl)", library_list_js)
        self.assertIn('class="library-browse-row"', library_list_js)
        self.assertIn('class="library-browse-row__title"', library_list_js)
        self.assertIn("author.book_count", library_list_js)
        self.assertIn("series.book_count", library_list_js)
        self.assertIn("</button>\n          ${previews}", library_list_js)
        self.assertIn('class="library-row"', library_list_js)
        self.assertIn('class="library-row__title"', library_list_js)
        self.assertIn('class="library-row__meta"', library_list_js)
        self.assertIn('class="library-row__tags"', library_list_js)
        self.assertIn(">Tags</span>", library_list_js)
        self.assertIn("b.publisher", library_list_js)
        self.assertIn("b.published_date", library_list_js)
        self.assertIn("/library/books/${encodeURIComponent(String(b.id))}/", library_list_js)
        self.assertNotIn("function bookFileHtml", library_list_js)
        self.assertNotIn("Download", library_list_js)
        self.assertNotIn("download_url", library_list_js)
        self.assertNotIn("Language:", library_list_js)
        self.assertNotIn("Genre", library_list_js)
        self.assertNotIn("nextUrl", library_list_js)
        self.assertNotIn("prevUrl", library_list_js)

        self.assertIn("export function renderCoverPreviewStrip", cover_previews_js)
        self.assertIn('class="cover-preview-strip"', cover_previews_js)
        self.assertIn('class="cover-preview-button"', cover_previews_js)
        self.assertIn('type="button"', cover_previews_js)
        self.assertIn('title="${escapeHtml(title)}"', cover_previews_js)
        self.assertIn('aria-label="${escapeHtml(ariaLabel)}"', cover_previews_js)
        self.assertIn("preview includes ${title}", cover_previews_js)
        self.assertIn('data-action="${escapeHtml(action)}"', cover_previews_js)
        self.assertIn('data-id="${escapeHtml(contextId)}"', cover_previews_js)
        self.assertIn('data-name="${escapeHtml(contextName)}"', cover_previews_js)
        self.assertIn('data-cover-url="${escapeHtml(coverUrl)}"', cover_previews_js)
        self.assertIn('data-cover-title="${escapeHtml(title)}"', cover_previews_js)
        self.assertNotIn("/library/books/", cover_previews_js)

        self.assertIn('from "../ui/groups.js"', user_memberships_js)
        self.assertIn("renderGroupBadge(g", user_memberships_js)
        self.assertIn('class="membership-row"', user_memberships_js)
        self.assertIn('class="membership-row__group"', user_memberships_js)
        self.assertIn('class="membership-row__controls"', user_memberships_js)
        self.assertIn('class="membership-row__actions"', user_memberships_js)
        self.assertIn('class="membership-row__status muted"', user_memberships_js)
        self.assertIn('data-action="membership-curator"', user_memberships_js)
        self.assertIn("Public fallback group; curator unavailable.", user_memberships_js)
        self.assertIn("descriptionForGroup", user_memberships_js)
        self.assertIn("titleAttr", user_memberships_js)
        self.assertIn('input[data-action="membership-curator"]', user_memberships_js)
        self.assertIn('method: "PATCH"', user_memberships_js)
        self.assertIn("clearLiveStatusLater", user_memberships_js)
        self.assertIn("5000", user_memberships_js)
        self.assertIn('window.confirm("Remove this user from the group?")', user_memberships_js)
        self.assertIn("icon-button--danger", user_memberships_js)
        self.assertNotIn('data-action="membership-save"', user_memberships_js)
        self.assertNotIn('<span class="pill">Member</span>', user_memberships_js)
        self.assertNotIn('<span class="pill">Curator</span>', user_memberships_js)
        self.assertNotIn('disabled" : ""} />', user_memberships_js)
        self.assertNotIn("Public is the default/fallback group", user_memberships_js)
        self.assertNotIn("membership_role", user_memberships_js)
        self.assertNotIn("curated_group_ids", user_memberships_js)
        self.assertNotIn("me.capabilities", user_memberships_js)
        self.assertNotIn(
            "${escapeHtml(g.name || String(g.id || \"\"))}",
            user_memberships_js,
        )

        self.assertIn("shelfMetadataLine", list_js)
        self.assertIn("renderShelfMetadata", view_js)
        self.assertIn("includeVisibility: false", view_js)
        self.assertIn("renderShelfItem", view_js)
        self.assertIn("document.createElement", view_js)
        self.assertNotIn("innerHTML", view_js)
        self.assertNotIn('"Owner type"', view_js)
        self.assertNotIn('"Metadata"', view_js)
        self.assertNotIn('"User:"', view_js)
        self.assertNotIn('"Group:"', view_js)
        self.assertNotIn("profile_id", view_js)
        self.assertNotIn(".email", view_js)
        self.assertIn("shelfMetadataLine", edit_js)
        self.assertIn("shelfMetadataLine", book_edit_shelves_js)
        self.assertIn("shelfMetadataLine", groups_shared_js)
        self.assertNotIn("shelfOwnerChip", list_js)
        self.assertNotIn("shelfOwnerChip", view_js)
        self.assertNotIn("shelfOwnerChip", edit_js)
        self.assertNotIn("shelfOwnerChip", book_edit_shelves_js)
        self.assertNotIn("shelfOwnerChip", groups_shared_js)
        self.assertIn(".user-identity", css)
        self.assertIn(".user-identity__icon", css)
        self.assertIn(".user-identity__display-name", css)
        self.assertIn(".user-identity__handle", css)
        self.assertIn(".user-identity__email", css)
        self.assertIn(".user-identity__piece + .user-identity__piece::before", css)
        self.assertIn(".group-badge", css)
        self.assertIn(".group-badge__icon", css)
        self.assertIn(".group-badge__name", css)
        self.assertIn(".group-badge--compact", css)
        self.assertIn(".group-badge--public", css)
        self.assertIn(".identity-row", css)
        self.assertIn(".identity-row__main", css)
        self.assertIn(".badge-row", css)
        self.assertIn(".user-row__identity", css)
        self.assertIn(".user-row__role", css)
        self.assertIn(".user-row__last-login", css)
        self.assertIn(".user-row__memberships", css)
        self.assertIn(".user-row__badge-list", css)
        self.assertIn(".users-header", css)
        self.assertIn(".users-header__identity", css)
        self.assertIn(".user-sort-button", css)
        self.assertIn(".user-sort-button__icon", css)
        self.assertIn(".user-row:hover", css)
        self.assertIn(".user-row:focus-within", css)
        self.assertIn(".library-tabs", css)
        self.assertIn(".library-filter-summary", css)
        self.assertIn(".library-browse-row", css)
        self.assertIn(".library-browse-row:hover", css)
        self.assertIn(".library-browse-row:focus-within", css)
        self.assertIn(".library-browse-row__title", css)
        self.assertIn(".library-browse-row__meta", css)
        self.assertIn(".library-browse-row__primary", css)
        self.assertIn(".library-browse-row__primary:hover", css)
        self.assertIn("grid-template-columns: minmax(160px, 0.8fr) minmax(180px, 1fr) auto", css)
        self.assertIn(".cover-preview-strip", css)
        self.assertIn(".cover-preview-button", css)
        self.assertIn(".cover-preview-button:hover", css)
        self.assertIn(".cover-preview-button:focus-visible", css)
        self.assertIn(".cover-preview-cover", css)
        self.assertIn(".library-row", css)
        self.assertIn(".library-row:hover", css)
        self.assertIn(".library-row:focus-within", css)
        self.assertIn(".library-row__meta", css)
        self.assertIn(".library-row__tags", css)
        self.assertIn(".library-row__tag-list", css)
        self.assertIn(".library-results", css)
        self.assertIn(".library-pager", css)
        self.assertIn(".library-pager--sticky", css)
        self.assertIn("position: sticky", css)
        self.assertIn(".library-pager__range", css)
        self.assertIn(".library-pager__page-size", css)
        self.assertIn(".library-pager__actions", css)
        self.assertNotIn(".pager { position: sticky", css)
        self.assertIn("@media (max-width: 920px)", css)
        self.assertIn(".card-row--compact", css)
        self.assertIn(".compact-list", css)
        self.assertIn(".compact-list__item", css)
        self.assertIn(".inline-metadata-row", css)
        self.assertIn(".shelf-owner-identity", css)
        self.assertIn(".shelf-metadata-piece + .shelf-metadata-piece::before", css)
        self.assertIn(".shelf-view-heading", css)
        self.assertIn(".shelf-view-description", css)
        self.assertIn(".membership-row", css)
        self.assertIn(".membership-row__group", css)
        self.assertIn(".membership-row__controls", css)
        self.assertIn(".membership-row__actions", css)
        self.assertIn(".membership-row__status", css)
        self.assertIn(".icon-button--danger", css)
        self.assertIn(".membership-add-tile", css)
        self.assertIn(".membership-add-tile__curator", css)
        self.assertIn(".membership-add-tile__actions", css)
        self.assertIn("@media (max-width: 720px)", css)

    def test_shelves_product_ui_list_uses_visibility_scoped_api(self):
        template = Path("web/templates/web/shelves/shelves.html").read_text(encoding="utf-8")
        list_js = Path("web/static/web/js/shelves/list.js").read_text()

        self.assertIn('id="personal-shelves-results"', template)
        self.assertIn('id="shared-shelves-results"', template)
        self.assertIn('initialUrl: "/api/v1/shelves/?scope=personal"', list_js)
        self.assertIn('initialUrl: "/api/v1/shelves/?scope=shared"', list_js)
        self.assertIn("createShelfSectionController", list_js)
        self.assertIn("createPagedListController", list_js)
        self.assertIn("Promise.all", list_js)
        self.assertIn("shelfMetadataLine", list_js)
        self.assertNotIn('initialUrl: "/api/v1/shelves/"', list_js)
        self.assertNotIn(".filter(", list_js)
        self.assertNotIn("owner_user.profile_id", list_js)
        self.assertNotIn(".email", list_js)
        self.assertNotIn("owner_user__is_staff", list_js)
        self.assertNotIn("is_superuser", list_js)

    def test_product_ui_display_sites_use_shared_identity_helpers(self):
        user_identity_modules = {
            path: Path(path).read_text(encoding="utf-8")
            for path in (
                "web/static/web/js/layout.js",
                "web/static/web/js/profile/main.js",
                "web/static/web/js/users/list.js",
                "web/static/web/js/users/edit.js",
                "web/static/web/js/users/new.js",
                "web/static/web/js/groups/shared.js",
            )
        }
        group_badge_modules = {
            path: Path(path).read_text(encoding="utf-8")
            for path in (
                "web/static/web/js/profile/main.js",
                "web/static/web/js/library/detail.js",
                "web/static/web/js/book_edit/groups.js",
                "web/static/web/js/groups/list.js",
                "web/static/web/js/users/list.js",
                "web/static/web/js/users/memberships.js",
                "web/static/web/js/shelves/shared.js",
            )
        }
        users_shared_js = Path("web/static/web/js/users/shared.js").read_text(
            encoding="utf-8"
        )
        group_memberships_js = Path(
            "web/static/web/js/groups/memberships.js"
        ).read_text(encoding="utf-8")
        user_memberships_js = Path(
            "web/static/web/js/users/memberships.js"
        ).read_text(encoding="utf-8")
        layout_js = user_identity_modules["web/static/web/js/layout.js"]
        library_detail_js = group_badge_modules[
            "web/static/web/js/library/detail.js"
        ]
        book_edit_groups_js = group_badge_modules[
            "web/static/web/js/book_edit/groups.js"
        ]
        groups_list_js = group_badge_modules[
            "web/static/web/js/groups/list.js"
        ]
        groups_shared_js = user_identity_modules[
            "web/static/web/js/groups/shared.js"
        ]
        css = Path("web/static/web/app.css").read_text(encoding="utf-8")

        for module_js in user_identity_modules.values():
            self.assertIn("renderUserIdentity", module_js)
        for module_js in group_badge_modules.values():
            self.assertIn("renderGroupBadge", module_js)

        self.assertIn("includeEmail: true", user_identity_modules["web/static/web/js/users/list.js"])
        self.assertIn("includeEmail: true", groups_shared_js)
        self.assertNotIn("includeEmail: true", layout_js)
        self.assertNotIn("includeEmail: true", user_identity_modules["web/static/web/js/profile/main.js"])
        self.assertNotIn("includeEmail: true", user_identity_modules["web/static/web/js/users/edit.js"])
        self.assertNotIn("includeEmail: true", user_identity_modules["web/static/web/js/users/new.js"])

        self.assertIn("includeDisplayName: false", layout_js)
        self.assertNotIn(
            ".user-identity--shell .user-identity__display-name",
            css,
        )
        self.assertIn("renderShelfMetadata(s)", library_detail_js)
        self.assertNotIn("meta.innerHTML", library_detail_js)
        self.assertNotIn("(user:", library_detail_js)
        self.assertNotIn("(group:", library_detail_js)
        self.assertNotIn('pill pill--owner", "Public"', library_detail_js)
        self.assertNotIn('pill pill--owner", "Public"', book_edit_groups_js)
        self.assertNotIn("pill--owner\">Public", groups_list_js)
        self.assertIn("renderUserIdentity(m, { includeEmail: true })", groups_shared_js)
        self.assertNotIn("Role: <code>", groups_shared_js)
        self.assertIn('class="identity-row"', groups_shared_js)
        self.assertIn('class="book card-row--compact"', groups_shared_js)
        self.assertIn('class="badge-row"', groups_shared_js)
        self.assertIn("remove_circle", groups_shared_js)
        self.assertIn('aria-label="Remove member"', groups_shared_js)
        self.assertIn("remove_circle", book_edit_groups_js)
        self.assertIn('aria-label", "Remove from group"', book_edit_groups_js)
        self.assertIn("remove_circle", user_memberships_js)
        self.assertIn('aria-label="Remove membership"', user_memberships_js)
        self.assertIn('data-action="membership-remove"', user_memberships_js)
        self.assertIn('class="membership-row__status muted"', user_memberships_js)
        self.assertIn("setRowStatus", user_memberships_js)
        self.assertNotIn("membershipsStatus", user_memberships_js)
        self.assertIn('closest("[data-action]")', group_memberships_js)
        self.assertIn('closest("[data-action]")', user_memberships_js)
        self.assertIn('class="identity-row"', groups_list_js)
        self.assertIn('class="badge-row"', groups_list_js)
        self.assertIn('el("ul", "compact-list")', library_detail_js)
        self.assertIn('el("li", "compact-list__item")', library_detail_js)
        self.assertIn('el("ul", "compact-list")', book_edit_groups_js)
        self.assertIn('el("li", "compact-list__item")', book_edit_groups_js)
        self.assertNotIn("groupsSummary", users_shared_js)
        self.assertNotIn("curatedGroupsFromUser", users_shared_js)
        self.assertNotIn("escapeHtml(username)", groups_shared_js)

        # Select controls remain plain text because badges cannot be children of option.
        self.assertIn("opt.textContent", group_memberships_js)
        self.assertIn("opt.textContent", user_memberships_js)

    def test_unauthenticated_users_redirects_to_login(self):
        response = self.client.get("/users/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/users/")

    def test_unauthenticated_reading_sessions_redirects_to_login(self):
        book_id = uuid4()
        response = self.client.get(f"/reading/sessions/books/{book_id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"/api-auth/login/?next=/reading/sessions/books/{book_id}/",
        )

    def test_unauthenticated_reading_sessions_all_redirects_to_login(self):
        response = self.client.get("/reading/sessions/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/reading/sessions/")

    def test_unauthenticated_reading_export_redirects_to_login(self):
        response = self.client.get("/reading/export/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/reading/export/")

    def test_unauthenticated_reading_import_redirects_to_login(self):
        response = self.client.get("/reading/import/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/reading/import/")

    def test_authenticated_reading_export_returns_200(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book
        ReadingSession.objects.create(user=self.user, book=book, name="Mine")

        self.client.force_login(self.user)
        response = self.client.get("/reading/export/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Export Marginalia")
        self.assertContains(response, "Native SPL exports can be previewed and imported")
        self.assertContains(response, 'href="/api/v1/reading/export/"')
        self.assertContains(response, "Export all marginalia")
        self.assertNotContains(response, "Import preview")
        self.assertContains(response, 'href="/reading/sessions/"')
        self.assertContains(response, 'class="sessions-cover"')
        self.assertContains(response, "Cover")
        self.assertContains(response, f'href="/api/v1/reading/export/books/{book.id}/"')
        self.assertContains(response, "Export all sessions")

    def test_authenticated_reading_import_returns_200(self):
        self.client.force_login(self.user)
        response = self.client.get("/reading/import/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import Marginalia")
        self.assertContains(response, "Preview and import SPL native marginalia exports.")
        self.assertContains(response, "SPL native marginalia export")
        self.assertContains(response, "Foreign annotation formats")
        self.assertContains(response, 'id="reading-import-preview-form"')
        self.assertContains(response, 'id="reading-import-file"')
        self.assertContains(response, 'id="reading-import-apply-controls"')
        self.assertContains(response, 'id="reading-import-apply-results"')
        self.assertContains(response, 'id="reading-import-session-modal"')
        self.assertContains(response, 'id="reading-import-session-modal-name"')
        self.assertContains(response, 'id="reading-import-session-modal-notes"')
        self.assertContains(response, 'href="/reading/export/"')

    def test_reading_import_js_wires_apply_after_preview(self):
        js = Path("web/static/web/js/reading/import_preview.js").read_text()
        rendering_js = Path("web/static/web/js/reading/import_rendering.js").read_text()
        selection_js = Path("web/static/web/js/reading/import_selection.js").read_text()
        modal_js = Path("web/static/web/js/reading/import_edit_modal.js").read_text()
        self.assertIn("renderApplyControls", js)
        self.assertIn("Apply import", rendering_js)
        self.assertIn("Select all", rendering_js)
        self.assertIn("Select none", rendering_js)
        self.assertIn("reading-import-select-all-top", rendering_js)
        self.assertIn("import-book-select", rendering_js)
        self.assertIn("import-book-select--large", rendering_js)
        self.assertIn("import-session-select", rendering_js)
        self.assertIn("import-session-edit", rendering_js)
        self.assertIn("reading-import-session-modal", js)
        self.assertIn("bookBox.indeterminate", selection_js)
        self.assertIn("No matched local books can be imported.", rendering_js)
        self.assertIn("import-session-name", modal_js)
        self.assertIn("/api/v1/reading/import/apply/", js)
        self.assertIn('formData.append("import_token", currentImportToken)', js)
        self.assertIn('formData.append("selection"', js)
        self.assertIn("buildSelection", js)
        self.assertIn("clearImportData", js)
        self.assertIn('input.value = ""', js)
        self.assertIn("currentPreview = null", js)
        self.assertIn("target.disabled = true", js)
        self.assertIn("renderApplyResult", js)
        self.assertIn("sessions_created", rendering_js)
        self.assertIn("bookmarks_created", rendering_js)
        self.assertIn("commented_highlights_created", rendering_js)

    def test_authenticated_reading_sessions_scopes_to_user_and_book(self):
        # Make the user a librarian so book visibility is not dependent on group membership setup.
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        other = User.objects.create_user(
            username="u2", email="u2@example.com", password="pw"
        )

        book = create_file_backed_book(title="B1").book
        other_book = create_file_backed_book(title="B2").book

        mine = ReadingSession.objects.create(user=self.user, book=book, name="Mine")
        ReadingSession.objects.create(user=self.user, book=other_book, name="Other book")
        others = ReadingSession.objects.create(user=other, book=book, name="Other user")

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-book-id="{book.id}"')
        self.assertContains(response, "Sessions for")
        self.assertContains(response, "No sessions yet for this book.", count=0)

        # Only the current user's sessions for this book appear.
        self.assertContains(response, str(mine.id))
        self.assertNotContains(response, str(others.id))

        # Sessions link back to marginalia with ?session=.
        self.assertContains(
            response,
            f"/reading/sessions/books/{book.id}/{mine.id}/",
        )
        self.assertContains(response, f"/api/v1/reading/export/books/{book.id}/")
        self.assertContains(response, "Export all sessions")
        self.assertContains(response, 'id="reading-sessions-export-selected"')
        self.assertContains(response, "Export selected")
        self.assertContains(response, "disabled")
        self.assertContains(response, "Select sessions to export a subset.")
        self.assertContains(response, 'class="reading-session-select"')
        self.assertContains(response, f'value="{mine.id}"')

    def test_reading_book_sessions_js_builds_selected_export_query(self):
        js = Path("web/static/web/js/reading/book_sessions.js").read_text()
        self.assertIn("initReadingBookSessions", js)
        self.assertIn("loadMeAndInitShell", js)
        self.assertIn('params.append("session", id)', js)
        self.assertIn("/api/v1/reading/export/books/", js)
        self.assertIn("button.disabled = selectedIds().length === 0", js)

    def test_authenticated_reading_sessions_empty_state(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No sessions yet for this book.")

    def test_authenticated_reading_sessions_all_scopes_to_user_and_visible_books(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        other = User.objects.create_user(username="u2", email="u2@example.com", password="pw")

        book = create_file_backed_book(title="B1").book
        mine = ReadingSession.objects.create(user=self.user, book=book, name="Mine")
        others = ReadingSession.objects.create(user=other, book=book, name="Other user")

        self.client.force_login(self.user)
        response = self.client.get("/reading/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="reading-sessions-all-title">Sessions</h1>')
        self.assertContains(response, 'id="reading-sessions-subtitle"')
        self.assertContains(response, 'class="sessions-controls"')
        self.assertContains(response, 'id="reading-sessions-controls"')
        self.assertContains(response, 'class="tabs sessions-controls__group sessions-status-filters"')
        self.assertContains(response, 'id="reading-sessions-status-filters"')
        self.assertContains(response, 'data-status-filter="all"')
        self.assertContains(response, 'aria-pressed="true"')
        self.assertContains(response, 'data-status-filter="active"')
        self.assertContains(response, 'data-status-filter="closed"')
        self.assertContains(response, 'id="reading-sessions-search-form"')
        self.assertContains(response, 'id="reading-sessions-search"')
        self.assertContains(
            response,
            '<label class="sr-only" for="reading-sessions-search">Search sessions</label>',
        )
        self.assertNotContains(
            response,
            '<label class="search__label" for="reading-sessions-search">Search</label>',
        )
        self.assertContains(
            response,
            'placeholder="Session name, notes, or visible book metadata..."',
        )
        self.assertContains(response, 'id="reading-sessions-search-button"')
        self.assertContains(
            response,
            'id="reading-sessions-search-button" class="button" type="submit">Search</button>',
        )
        self.assertContains(response, 'class="sessions-controls__group sessions-controls__page-size"')
        self.assertContains(response, 'id="reading-sessions-page-size"')
        self.assertContains(response, '<option value="20" selected>20</option>')
        self.assertContains(response, 'id="reading-sessions-results"')
        self.assertContains(response, 'id="reading-sessions-view-toggle"')
        self.assertContains(response, 'data-view-mode="session"')
        self.assertContains(response, 'data-view-mode="book"')
        self.assertContains(
            response,
            'data-view-mode="session" aria-pressed="true">By Session</button>',
        )
        self.assertContains(response, 'id="reading-sessions-view-note"')
        self.assertContains(response, 'id="reading-sessions-status"')
        self.assertContains(response, 'id="reading-sessions-prev"')
        self.assertContains(response, 'id="reading-sessions-next"')

        # Current user's session is present.
        self.assertContains(response, str(mine.id))
        # Other user's session not shown.
        self.assertNotContains(response, str(others.id))

        # Selectable card text is separate from explicit session/book links.
        self.assertContains(response, f"/reading/sessions/books/{book.id}/{mine.id}/")
        self.assertContains(response, 'class="card sessions-row sessions-card"')
        self.assertContains(response, 'class="sessions-card__cover-link"')
        self.assertContains(response, 'class="sessions-card__title"')
        self.assertContains(response, 'aria-label="Open session"')
        self.assertContains(response, 'aria-label="View sessions for this book"')
        self.assertContains(response, "article")
        self.assertContains(response, "auto_stories")
        self.assertContains(response, f"/reading/sessions/?book={book.id}")
        self.assertNotContains(
            response,
            '<a class="card sessions-row sessions-card"',
        )
        self.assertNotContains(response, 'role="link"')
        self.assertNotContains(response, 'tabindex="0"')
        self.assertNotContains(response, "View session marginalia")
        self.assertNotContains(response, ">View book sessions</")
        self.assertContains(response, "Active")

    def test_reading_sessions_js_wires_filters_search_page_size_and_book_context(self):
        js = Path("web/static/web/js/reading/sessions.js").read_text(encoding="utf-8")
        main_js = Path("web/static/web/js/main.js").read_text(encoding="utf-8")
        css = Path("web/static/web/app.css").read_text(encoding="utf-8")

        self.assertIn("const DEFAULT_PAGE_SIZE = 20", js)
        self.assertIn('params.get("book")', js)
        self.assertIn('params.get("q")', js)
        self.assertIn('params.get("status")', js)
        self.assertIn('params.get("page_size")', js)
        self.assertIn('params.get("view")', js)
        self.assertIn('url.searchParams.set("q", state.q)', js)
        self.assertIn('url.searchParams.set("is_active", "true")', js)
        self.assertIn('url.searchParams.set("is_active", "false")', js)
        self.assertIn('url.searchParams.set("page_size", String(state.pageSize))', js)
        self.assertIn('url.searchParams.set("book", state.book)', js)
        self.assertIn('params.set("view", state.view)', js)
        self.assertIn("writeQueryState", js)
        self.assertIn('button.setAttribute("aria-pressed", active ? "true" : "false")', js)
        self.assertIn("Reading sessions for ${String(book.title)}", js)
        self.assertIn("sessionCardTitle(session, bookTitle)", js)
        self.assertIn("appendSeparatedParts", js)
        self.assertIn('el("span", "metadata-piece", part)', js)
        self.assertIn('el("div", "card sessions-row sessions-card")', js)
        self.assertIn('el("a", "sessions-card__cover-link")', js)
        self.assertIn('el("a", "sessions-card__title"', js)
        self.assertNotIn("bindCardInteraction", js)
        self.assertNotIn("window.location.assign", js)
        self.assertNotIn('card.setAttribute("role", "link")', js)
        self.assertNotIn("card.tabIndex", js)
        self.assertIn('label: "Open session"', js)
        self.assertIn('label: "View sessions for this book"', js)
        self.assertIn('icon: "article"', js)
        self.assertIn('icon: "auto_stories"', js)
        self.assertIn("bookSessionsHref", js)
        self.assertIn("groupSessionsByBook", js)
        self.assertIn("renderBookGroup", js)
        self.assertIn("renderCompactSessionRow", js)
        self.assertIn('el("a",', js)
        self.assertIn('"sessions-book-group__session-title"', js)
        self.assertIn("titleLink.href = marginaliaHref", js)
        self.assertIn('state.view === "book"', js)
        self.assertIn("Grouped by book for this page of results.", js)
        self.assertIn('el("div", "muted sessions-row__id", sessionId)', js)
        self.assertIn('session && session.is_active ? "Active" : "Closed"', js)
        self.assertNotIn("View session marginalia", js)
        self.assertNotIn(">View book sessions</", js)
        self.assertIn("No reading sessions for ${String(book.title)} yet.", js)
        self.assertNotIn("/api/v1/library/books/", js)
        self.assertIn('import("./reading/sessions.js")', main_js)
        self.assertIn('initExportName: "initReadingSessions"', main_js)
        self.assertIn(".sessions-controls .sessions-status-filters", css)
        self.assertIn("border-bottom: 0", css)
        self.assertIn(".metadata-piece + .metadata-piece::before", css)

    def test_authenticated_reading_sessions_all_empty_state(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.client.force_login(self.user)
        response = self.client.get("/reading/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No reading sessions yet.")

    def test_authenticated_session_marginalia_returns_200_and_has_containers(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book
        session = ReadingSession.objects.create(user=self.user, book=book, name="Mine")

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/{session.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-book-id="{book.id}"')
        self.assertContains(response, f'data-session-id="{session.id}"')
        self.assertContains(response, 'id="reading-activity-status"')
        self.assertContains(response, 'id="reading-activity-error"')
        self.assertContains(response, 'id="reading-activity-cover"')
        self.assertContains(response, 'id="reading-activity-book-meta"')
        self.assertContains(response, 'id="reading-activity-session-context"')
        self.assertContains(response, 'id="reading-activity-session-display"')
        self.assertContains(response, 'id="reading-activity-session-edit"')
        self.assertContains(response, 'class="material-symbols-outlined"')
        self.assertContains(response, 'id="reading-activity-session-edit-form"')
        self.assertContains(response, 'id="reading-activity-session-cancel"')
        self.assertContains(response, 'id="reading-activity-session-close"')
        self.assertContains(response, 'id="reading-activity-session-close-status"')
        self.assertContains(response, "Close session")
        self.assertContains(response, 'id="reading-activity-session"')
        self.assertContains(response, 'id="reading-activity-progress"')
        self.assertContains(response, 'id="reading-activity-annotations"')
        self.assertContains(response, f"/reading/sessions/books/{book.id}/")
        self.assertContains(
            response,
            f"/api/v1/reading/export/books/{book.id}/{session.id}/",
        )
        self.assertContains(response, "Export this session")

    def test_session_marginalia_404s_for_other_users_session(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        other = User.objects.create_user(username="u2", email="u2@example.com", password="pw")
        book = create_file_backed_book(title="B1").book
        session = ReadingSession.objects.create(user=other, book=book, name="Other")

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{book.id}/{session.id}/", follow=False)
        self.assertEqual(response.status_code, 404)

    def test_session_marginalia_404s_when_book_id_does_not_match(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book
        other_book = create_file_backed_book(title="B2").book
        session = ReadingSession.objects.create(user=self.user, book=book, name="Mine")

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/sessions/books/{other_book.id}/{session.id}/", follow=False)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_profile_redirects_to_login(self):
        response = self.client.get("/profile/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/profile/")

    def test_unauthenticated_profile_password_redirects_to_login(self):
        response = self.client.get("/profile/password/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/profile/password/")

    def test_unauthenticated_user_new_redirects_to_login(self):
        response = self.client.get("/users/new/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/users/new/")

    def test_unauthenticated_user_edit_redirects_to_login(self):
        response = self.client.get(f"/users/{self.user.pk}/edit/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], f"/api-auth/login/?next=/users/{self.user.pk}/edit/"
        )

    def test_authenticated_users_returns_200_and_has_containers(self):
        self.client.force_login(self.user)
        response = self.client.get("/users/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="users-results"')
        self.assertContains(response, 'id="users-filters"')
        self.assertContains(response, 'id="users-create-link"')
        self.assertContains(
            response,
            "Manage local users, roles, and group memberships.",
        )
        self.assertNotContains(response, "Django users")

    def test_authenticated_user_new_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/users/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="user-new-form"')
        self.assertContains(response, 'id="user-new-username"')
        self.assertContains(response, 'id="user-new-created-password"')

    def test_authenticated_user_edit_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/users/{self.user.pk}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="user-edit-form"')
        self.assertContains(response, 'id="user-edit-username"')
        self.assertContains(response, 'id="user-edit-must-change"')
        self.assertContains(response, 'id="user-reset-password-btn"')
        self.assertContains(response, 'id="user-memberships-card"')
        self.assertContains(response, 'id="user-memberships-add-form"')
        self.assertNotContains(response, 'id="user-memberships-status"')
        self.assertContains(response, 'class="membership-add-tile"')
        self.assertContains(response, 'class="membership-add-tile__curator"')
        self.assertContains(
            response,
            "Managers, librarians, and owners can already manage books globally.",
        )
        self.assertContains(response, "Curator identifies members who specifically steward this group")
        self.assertContains(
            response, "group-scoped management access to readers."
        )

    def test_authenticated_profile_returns_200_and_has_containers(self):
        self.client.force_login(self.user)
        response = self.client.get("/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="profile-edit-form"')
        self.assertContains(response, 'id="profile-edit-btn"')
        self.assertContains(response, 'id="profile-save-btn"')
        self.assertContains(response, ">Role</div>")
        self.assertContains(response, 'id="profile-role"')
        self.assertContains(response, ">Owner</div>")
        self.assertContains(response, 'id="profile-owner"')
        self.assertContains(response, 'id="profile-email-input"')
        self.assertContains(response, "Session management")
        self.assertContains(response, 'id="profile-logout-others-btn"')
        self.assertContains(response, "Device/API sessions")
        self.assertContains(response, 'href="/client-api/authorize/"')
        self.assertContains(response, 'id="profile-client-sessions"')
        self.assertContains(response, 'id="profile-client-sessions-status"')
        self.assertContains(response, 'id="profile-groups"')
        self.assertNotContains(response, "Show access details")
        self.assertNotContains(response, 'id="profile-access"')

        profile_js = Path("web/static/web/js/profile/main.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("function titleCaseRole", profile_js)
        self.assertIn("roleEl.textContent = titleCaseRole(me.role)", profile_js)
        self.assertIn('ownerEl.textContent = me.is_owner ? "Yes" : "No"', profile_js)

    def test_authenticated_profile_password_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/profile/password/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="profile-password-form"')
        self.assertContains(response, 'id="profile-password-current"')

    def test_logout_is_post_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/app/")
        self.assertContains(response, '<form class="userbox__logoutform" action="/api-auth/logout/" method="post">')

    def test_post_logout_logs_out_and_redirects(self):
        self.client.force_login(self.user)
        response = self.client.post("/api-auth/logout/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
