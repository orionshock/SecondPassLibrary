from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from uuid import uuid4

from accounts.services import get_or_create_profile
from core import server_settings
from accounts.models import UserProfile
from library.models import Book
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
        self.assertNotContains(response, "/static/web/js/groups.js")
        self.assertNotContains(response, "/static/web/js/shelves.js")
        self.assertNotContains(response, "/static/web/js/users.js")
        self.assertNotContains(response, "/static/web/js/book_edit.js")
        self.assertContains(response, 'id="ui-global-error"')
        self.assertContains(response, 'id="recent-reading-section"')
        self.assertContains(response, 'id="recent-reading-status"')
        self.assertContains(response, 'id="recent-reading-list"')
        self.assertContains(response, 'href="/reading/sessions/"')
        self.assertContains(response, "All reading sessions")
        self.assertContains(response, 'aria-label="Dashboard actions"')
        self.assertContains(response, 'href="/library/"')
        self.assertContains(response, "Browse library")
        self.assertNotContains(response, "Import books")
        self.assertContains(response, 'href="/shelves/"')
        self.assertContains(response, "View shelves")
        self.assertContains(response, "Reading sessions")
        self.assertContains(response, 'href="/reading/export/"')
        self.assertContains(response, "Export marginalia")
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
        self.assertContains(response, 'id="groups-results"')

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
        self.assertContains(response, 'id="shelves-results"')

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

    def test_unauthenticated_users_redirects_to_login(self):
        response = self.client.get("/users/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/users/")

    def test_unauthenticated_reading_activity_redirects_to_login(self):
        book_id = uuid4()
        response = self.client.get(f"/reading/books/{book_id}/activity/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"/api-auth/login/?next=/reading/books/{book_id}/activity/",
        )

    def test_authenticated_reading_activity_returns_200_and_has_containers(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book
        session = ReadingSession.objects.create(user=self.user, book=book, name="Mine")

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/books/{book.id}/activity/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/reading/sessions/books/{book.id}/{session.id}/")

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
        self.assertContains(response, "Import is future work.")
        self.assertContains(response, 'href="/reading/sessions/"')
        self.assertContains(response, f'href="/api/v1/reading/export/books/{book.id}/"')
        self.assertContains(response, "Export all sessions")

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

    def test_legacy_reading_sessions_redirects_to_canonical(self):
        self.client.force_login(self.user)
        book_id = uuid4()
        response = self.client.get(f"/reading/books/{book_id}/sessions/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/reading/sessions/books/{book_id}/")

    def test_legacy_activity_with_session_redirects_to_canonical(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book

        self.client.force_login(self.user)
        session_id = uuid4()
        response = self.client.get(f"/reading/books/{book.id}/activity/?session={session_id}", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/reading/sessions/books/{book.id}/{session_id}/")

    def test_legacy_activity_without_session_redirects_to_most_recent_session_when_one_exists(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book
        session = ReadingSession.objects.create(user=self.user, book=book, name="Mine")

        self.client.force_login(self.user)
        response = self.client.get(f"/reading/books/{book.id}/activity/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/reading/sessions/books/{book.id}/{session.id}/")

    def test_legacy_activity_without_session_redirects_to_book_sessions_when_none_exist(self):
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        book = create_file_backed_book(title="B1").book
        self.client.force_login(self.user)
        response = self.client.get(f"/reading/books/{book.id}/activity/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/reading/sessions/books/{book.id}/")

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
