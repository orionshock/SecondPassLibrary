from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from uuid import uuid4

from accounts.services import get_or_create_profile


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

    def test_authenticated_app_returns_200_and_title(self):
        self.client.force_login(self.user)
        response = self.client.get("/app/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Second Pass Library")
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="ui-global-error"')
        self.assertContains(response, 'id="app-greeting"')
        self.assertContains(response, 'id="app-sections"')
        self.assertContains(response, 'href="/profile/"')

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

    def test_authenticated_group_detail_returns_200_and_has_container(self):
        self.client.force_login(self.user)
        group_id = uuid4()
        response = self.client.get(f"/groups/{group_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="group-summary"')
        self.assertContains(response, f'data-group-id="{group_id}"')
        self.assertContains(response, 'id="group-members"')
        self.assertContains(response, 'id="group-members-results"')

    def test_unauthenticated_users_redirects_to_login(self):
        response = self.client.get("/users/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/users/")

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
        self.assertContains(response, 'id="profile-summary"')
        self.assertContains(response, 'id="profile-edit-form"')
        self.assertContains(response, 'id="profile-edit-email"')

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
