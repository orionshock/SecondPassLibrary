from __future__ import annotations
import importlib

from typing import cast

from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import clear_url_caches, set_urlconf

import secondpass.urls

from accounts.admin import UserProfileAdmin
from accounts.models import ExternalIdentity, UserProfile
from library.models import LibraryGroupMembership


class _DummySite(AdminSite):
    pass


def _reload_project_urls() -> None:
    clear_url_caches()
    set_urlconf(None)
    importlib.reload(secondpass.urls)


class UserProfileAdminRoleRestrictionTest(TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.admin = UserProfileAdmin(UserProfile, self.site)
        self.factory = RequestFactory()

        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="pw", is_staff=True
        )

        self.target = User.objects.create_user(
            username="target", email="target@example.com", password="pw"
        )
        self.profile = UserProfile.objects.get(user=self.target)

    def test_non_owner_cannot_promote_to_manager(self):
        request = self.factory.post("/admin/accounts/userprofile/")
        request.user = self.staff

        Form = self.admin.get_form(request, obj=self.profile)
        form = Form(
            data={
                "user": cast(int, self.target.pk),
                "role": UserProfile.ROLE_MANAGER,
                "external_subject_id": "",
            },
            instance=self.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)

    def test_non_owner_cannot_demote_existing_manager(self):
        self.profile.role = UserProfile.ROLE_MANAGER
        self.profile.save(update_fields=["role", "updated_at"])

        request = self.factory.post("/admin/accounts/userprofile/")
        request.user = self.staff

        Form = self.admin.get_form(request, obj=self.profile)
        form = Form(
            data={
                "user": cast(int, self.target.pk),
                "role": UserProfile.ROLE_READER,
                "external_subject_id": "",
            },
            instance=self.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)

    def test_owner_can_promote_to_manager(self):
        request = self.factory.post("/admin/accounts/userprofile/")
        request.user = self.owner

        Form = self.admin.get_form(request, obj=self.profile)
        form = Form(
            data={
                "user": cast(int, self.target.pk),
                "role": UserProfile.ROLE_MANAGER,
                "external_subject_id": "",
            },
            instance=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_profile_id_is_visible_in_admin(self):
        self.assertIn("profile_id", self.admin.list_display)
        self.assertIn("profile_id", self.admin.readonly_fields)
        self.assertIn("external_subject_id", self.admin.readonly_fields)
        self.assertEqual(self.admin.profile_id(self.profile), self.profile.id)
        self.assertEqual(
            UserProfileAdmin.profile_id.short_description,
            "Profile ID",
        )

    def test_profile_delete_permission_uses_standard_admin_permissions(self):
        owner_request = self.factory.get("/")
        owner_request.user = self.owner
        self.assertTrue(
            self.admin.has_delete_permission(owner_request, self.profile)
        )

        staff_request = self.factory.get("/")
        staff_request.user = self.staff
        self.assertFalse(
            self.admin.has_delete_permission(staff_request, self.profile)
        )

    def test_owner_can_delete_user_through_django_admin(self):
        ExternalIdentity.objects.create(
            user=self.target,
            provider="test",
            issuer="https://issuer.example.test",
            subject="target-subject",
        )
        target_id = self.target.pk
        with override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=True):
            _reload_project_urls()
            self.client.force_login(self.owner)

            confirmation = self.client.post(
                "/admin/auth/user/",
                {
                    "action": "delete_selected",
                    ACTION_CHECKBOX_NAME: [target_id],
                },
            )
            self.assertEqual(confirmation.status_code, 200)
            self.assertContains(confirmation, "Are you sure")

            response = self.client.post(
                "/admin/auth/user/",
                {
                    "action": "delete_selected",
                    ACTION_CHECKBOX_NAME: [target_id],
                    "post": "yes",
                },
                follow=False,
            )

        _reload_project_urls()

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=target_id).exists())
        self.assertFalse(UserProfile.objects.filter(user_id=target_id).exists())
        self.assertFalse(ExternalIdentity.objects.filter(user_id=target_id).exists())
        self.assertFalse(
            LibraryGroupMembership.objects.filter(user_id=target_id).exists()
        )

    def test_username_is_primary_clickable_sort_column(self):
        self.assertEqual(self.admin.list_display[0], "username")
        self.assertEqual(self.admin.list_display_links, ["username"])
        self.assertEqual(self.admin.username(self.profile), "target")
        self.assertEqual(UserProfileAdmin.username.short_description, "Username")
        self.assertEqual(
            UserProfileAdmin.username.admin_order_field,
            "user__username",
        )
