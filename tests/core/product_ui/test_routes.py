"""Route and smoke tests for product UI pages."""
from accounts.services import get_or_create_profile
from accounts.models import UserProfile
from core import server_settings
from tests.core.product_ui.helpers import ProductUiTestCase


class ProductUiRouteTests(ProductUiTestCase):
    """Test basic route availability and redirects."""

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
        from django.contrib.auth import get_user_model
        User = get_user_model()
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
        manager = self.user
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
        self.assertContains(response, "<code>.epub</code>")
        self.assertContains(response, "simple <code>.zip</code> files of EPUBs")
        self.assertContains(response, "Calibre-style ZIPs with OPF sidecars")
        self.assertContains(response, "PDF is unsupported")
