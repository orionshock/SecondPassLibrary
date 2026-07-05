"""Route and smoke tests for product UI pages."""
from django.test import override_settings
from django.utils.html import escape

from accounts.services import get_or_create_profile
from accounts.models import UserProfile
from core import server_settings
from tests.core.product_ui.helpers import ProductUiTestCase


class ProductUiRouteTests(ProductUiTestCase):
    """Test basic route availability and redirects."""

    def test_root_redirects_to_dashboard(self):
        response = self.client.get("/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/")

    def test_unauthenticated_dashboard_redirects_to_login(self):
        response = self.client.get("/dashboard/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/dashboard/")

    def test_app_route_is_not_registered(self):
        response = self.client.get("/app/", follow=False)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_server_settings_redirects_to_login(self):
        response = self.client.get("/server/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/server/")

    def test_owner_server_settings_returns_200_and_has_enable_action_without_service_hatch_link_by_default(self):
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
        self.assertContains(response, 'role="tablist"')
        self.assertContains(response, 'id="server-settings-tab-identity"')
        self.assertContains(response, 'id="server-settings-panel-identity"')
        self.assertContains(response, 'id="server-settings-tab-dashboard"')
        self.assertContains(response, 'id="server-settings-panel-dashboard"')
        self.assertContains(response, 'id="server-settings-tab-public"')
        self.assertContains(response, 'id="server-settings-panel-public"')
        self.assertContains(response, 'id="server-settings-tab-library-groups"')
        self.assertContains(response, 'id="server-settings-panel-library-groups"')
        self.assertContains(response, "Identity")
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Public Library")
        self.assertContains(response, "Library Groups")
        self.assertContains(response, "Save")
        self.assertContains(response, "Cancel")
        self.assertContains(response, "Server name")
        self.assertContains(response, "Server Description")
        self.assertContains(response, "Banner Text")
        self.assertContains(response, "material-symbols-outlined server-settings-info-icon")
        self.assertContains(response, "Shows on Login page and Client Discovery")
        self.assertContains(response, "Server's Message for the Dashboard")
        self.assertContains(response, 'id="server-settings-banner-input"')
        self.assertContains(response, "server-settings-control--banner")
        self.assertNotContains(response, "Shown to reader clients via discovery (optional).")
        self.assertNotContains(response, "Shown at the top of the dashboard. Leave blank to hide.")
        self.assertContains(response, 'data-tab-panel="dashboard"')
        self.assertContains(response, 'data-tab-panel="public-library"')
        self.assertContains(response, 'id="server-settings-public-name-input"')
        self.assertContains(response, 'id="server-settings-public-description-input"')
        self.assertContains(response, "Public group name")
        self.assertContains(response, "Public group description")
        self.assertContains(response, 'data-tab-panel="library-groups"')
        self.assertContains(response, "Advanced library groups")
        self.assertContains(response, 'id="server-settings-advanced-groups-display"')
        self.assertContains(response, 'id="server-settings-enable-advanced-groups-btn"')
        self.assertContains(response, "Enable advanced library groups")
        self.assertContains(response, "Product UI does not normally offer a way to turn this off again")
        self.assertNotContains(response, 'id="server-settings-advanced-groups-input"')
        self.assertNotContains(response, 'href="/admin/"')

    def test_owner_server_settings_enabled_status_has_no_disable_control(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        server_settings.enable_advanced_library_groups()
        owner = User.objects.create_user(
            username="owner-groups-enabled",
            email="owner-groups-enabled@example.com",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)
        response = self.client.get("/server/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Disabling this later is an operator recovery action")
        self.assertNotContains(response, 'id="server-settings-advanced-groups-input"')
        self.assertNotContains(response, "Disable advanced library groups")

    @override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=True)
    def test_owner_server_settings_has_service_hatch_link_when_admin_enabled(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        owner = User.objects.create_user(
            username="owner-admin-enabled",
            email="owner-admin-enabled@example.com",
            password="pw",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(owner)
        response = self.client.get("/server/")
        self.assertEqual(response.status_code, 200)
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
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/admin/"')
        self.assertContains(response, 'href="/server/"')
        self.assertContains(response, "Server Settings")

    def test_authenticated_dashboard_returns_200_and_title(self):
        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Second Pass Library")
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, "fonts.googleapis.com/css2?family=Material+Symbols+Outlined")
        self.assertContains(response, "/static/web/favicon.png")
        self.assertContains(response, 'class="brand__icon"')
        self.assertContains(response, 'aria-hidden="true"')
        self.assertContains(response, '<a class="brand" href="/dashboard/">', html=False)
        self.assertContains(response, '<h1 class="sr-only">Dashboard</h1>', html=False)
        self.assertNotContains(response, '<h1 class="page-title">Dashboard</h1>', html=False)
        self.assertNotContains(response, "/static/web/js/groups.js")
        self.assertNotContains(response, "/static/web/js/shelves.js")
        self.assertNotContains(response, "/static/web/js/users.js")
        self.assertNotContains(response, "/static/web/js/book_edit.js")
        self.assertContains(response, 'id="ui-global-error"')
        self.assertContains(response, 'id="recent-reading-section"')
        self.assertContains(response, 'id="recent-reading-status"')
        self.assertContains(response, 'id="recent-reading-list"')
        self.assertNotContains(response, 'id="dashboard-server-banner"')
        self.assertNotContains(response, "All reading sessions")
        self.assertContains(response, 'aria-label="Dashboard actions"')
        self.assertContains(response, "Recent reading activity")
        self.assertContains(response, "No recent reading activity yet.", count=0)
        self.assertContains(response, "View all sessions")
        self.assertContains(response, "Browse Library")
        self.assertContains(response, "Explore the collection by different views.")
        self.assertContains(response, 'href="/library/?view=books"')
        self.assertContains(response, "Books")
        self.assertContains(response, 'href="/library/?view=authors"')
        self.assertContains(response, "Authors")
        self.assertContains(response, 'href="/library/?view=series"')
        self.assertContains(response, "Series")
        self.assertNotContains(response, 'href="/groups/"')
        self.assertNotContains(response, "Import books")
        self.assertContains(response, "My Shelves")
        self.assertContains(response, "Organize books into personal and shared shelves.")
        self.assertContains(response, 'href="/shelves/"')
        self.assertContains(response, "View shelves")
        self.assertContains(response, 'href="/shelves/new/"')
        self.assertContains(response, "Create shelf")
        self.assertContains(response, "My Marginalia")
        self.assertContains(
            response,
            '<a class="nav__item" href="/reading/sessions/" data-nav="marginalia">My Marginalia</a>',
            html=False,
        )
        self.assertContains(
            response,
            "Review your reading sessions, highlights, bookmarks, notes, progress, imports, and exports.",
        )
        self.assertContains(response, 'href="/reading/sessions/"')
        self.assertContains(response, "Browse by Session")
        self.assertContains(response, 'href="/reading/sessions/?view=book"')
        self.assertContains(response, "Browse by Book")
        self.assertContains(response, 'href="/reading/import/"')
        self.assertContains(response, "Import Marginalia")
        self.assertContains(response, 'href="/reading/export/"')
        self.assertContains(response, "Export Marginalia")
        self.assertNotContains(response, "Reading data")
        self.assertNotContains(response, "Reading Data")
        self.assertNotContains(response, "Reading Sessions")
        self.assertNotContains(response, "Import SPL Marginalia")
        self.assertNotContains(response, "Export SPL Marginalia")
        content = response.content.decode("utf-8")
        self.assertLess(content.index("My Marginalia"), content.index("My Shelves"))
        self.assertLess(content.index("My Shelves"), content.index("Browse Library"))
        self.assertNotContains(response, "Future activity dashboard")
        self.assertNotContains(response, 'id="future-activity-dashboard"')
        self.assertContains(response, 'href="/profile/"')

    def test_dashboard_shows_groups_link_when_advanced_groups_enabled(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/groups/"')
        self.assertContains(response, "Groups")

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
        response = self.client.get("/dashboard/", follow=False)
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

        response = self.client.get("/dashboard/", follow=False)

        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_configured_server_banner_message(self):
        server_settings.set_server_banner_message("Maintenance tonight.")
        self.client.force_login(self.user)

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="dashboard-server-banner"')
        self.assertContains(response, 'aria-label="Server message"')
        self.assertContains(response, "Maintenance tonight.")

    def test_dashboard_escapes_server_banner_message(self):
        raw_message = "<strong>Maintenance</strong>"
        server_settings.set_server_banner_message(raw_message)
        self.client.force_login(self.user)

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, escape(raw_message), html=False)
        self.assertNotContains(response, raw_message, html=False)

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
        self.assertContains(response, 'id="imports-submit"')
        self.assertContains(response, 'id="imports-results"')
        self.assertContains(response, "Latest Result")
        self.assertContains(response, "No import has been run in this browser session.")
        self.assertContains(response, "<code>.epub</code>")
        self.assertContains(response, "simple <code>.zip</code> files of EPUBs")
        self.assertContains(response, "Calibre-style ZIPs with OPF sidecars")
        self.assertContains(response, "PDF is unsupported")
