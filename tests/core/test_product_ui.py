from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from uuid import uuid4

from accounts.services import get_or_create_profile
from core import server_settings
from accounts.models import UserProfile
from reading.models import ReadingSession
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ProductUiSmokeTests(TestCase):
    def setUp(self):
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
        self.assertContains(response, 'id="shelves-status"')
        self.assertContains(response, 'id="shelves-results"')
        self.assertContains(response, 'id="shelves-prev"')
        self.assertContains(response, 'id="shelves-next"')
        self.assertContains(response, 'id="shelves-page-note"')

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
        self.assertContains(response, 'id="shelf-view-items-results"')

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
        self.assertIn('parts.join(" • ")', identity_js)
        self.assertIn('"Unknown user"', identity_js)
        self.assertIn("options.includeEmail === true", identity_js)
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
        self.assertIn('icon.textContent = "groups"', group_badge_js)
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
        self.assertIn("groups", shared_js)
        self.assertIn("&middot;", shared_js)
        self.assertNotIn("\u00c2\u00b7", shared_js)
        self.assertIn("profile_id", shared_js)
        self.assertNotIn("Owned by you", shared_js)
        self.assertNotIn("Owned by ", shared_js)
        self.assertNotIn("profile_id}</span>", shared_js)
        self.assertNotIn(".email", shared_js)
        self.assertNotIn("shelfOwnerChip", shared_js)

        self.assertIn('from "../ui/identity.js"', users_list_js)
        self.assertIn("renderUserIdentity(user", users_list_js)
        self.assertIn("includeEmail: true", users_list_js)
        self.assertNotIn("${escapeHtml(username)}", users_list_js)

        self.assertIn('from "../ui/groups.js"', user_memberships_js)
        self.assertIn("renderGroupBadge(g", user_memberships_js)
        self.assertNotIn(
            "${escapeHtml(g.name || String(g.id || \"\"))}",
            user_memberships_js,
        )

        self.assertIn("shelfMetadataLine", list_js)
        self.assertIn("shelfMetadataLine", view_js)
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
        self.assertIn(".shelf-owner-identity", css)
        self.assertIn(".shelf-meta-separator", css)

    def test_shelves_product_ui_list_uses_visibility_scoped_api(self):
        template = Path("web/templates/web/shelves/shelves.html").read_text(encoding="utf-8")
        list_js = Path("web/static/web/js/shelves/list.js").read_text()

        self.assertIn('id="shelves-results"', template)
        self.assertIn('initialUrl: "/api/v1/shelves/"', list_js)
        self.assertNotIn("owner_user__is_staff", list_js)
        self.assertNotIn("is_superuser", list_js)

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
        self.assertContains(response, "Reading Sessions")

        # Current user's session is present.
        self.assertContains(response, str(mine.id))
        # Other user's session not shown.
        self.assertNotContains(response, str(others.id))

        # Session row links to marginalia and per-book sessions.
        self.assertContains(response, f"/reading/sessions/books/{book.id}/{mine.id}/")
        self.assertContains(response, f"/reading/sessions/books/{book.id}/")

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

    def test_authenticated_profile_returns_200_and_has_containers(self):
        self.client.force_login(self.user)
        response = self.client.get("/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="profile-edit-form"')
        self.assertContains(response, 'id="profile-edit-btn"')
        self.assertContains(response, 'id="profile-save-btn"')
        self.assertContains(response, 'id="profile-email-input"')
        self.assertContains(response, "Session management")
        self.assertContains(response, 'id="profile-logout-others-btn"')
        self.assertContains(response, "Device/API sessions")
        self.assertContains(response, 'href="/client-api/authorize/"')
        self.assertContains(response, 'id="profile-client-sessions"')
        self.assertContains(response, 'id="profile-client-sessions-status"')

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
