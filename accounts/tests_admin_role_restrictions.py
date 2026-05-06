from __future__ import annotations

from typing import cast

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from .admin import UserProfileAdmin
from .models import UserProfile


class _DummySite(AdminSite):
    pass


class UserProfileAdminRoleRestrictionTest(TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.admin = UserProfileAdmin(UserProfile, self.site)
        self.factory = RequestFactory()

        self.owner = User.objects.create_superuser(username="owner", email="owner@example.com", password="pw")
        self.staff = User.objects.create_user(username="staff", email="staff@example.com", password="pw", is_staff=True)

        self.target = User.objects.create_user(username="target", email="target@example.com", password="pw")
        self.profile = UserProfile.objects.get(user=self.target)

    def test_non_owner_cannot_promote_to_manager(self):
        request = self.factory.post("/admin/accounts/userprofile/")
        request.user = self.staff

        Form = self.admin.get_form(request, obj=self.profile)
        form = Form(
            data={"user": cast(int, self.target.pk), "role": UserProfile.ROLE_MANAGER, "external_subject_id": ""},
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
            data={"user": cast(int, self.target.pk), "role": UserProfile.ROLE_READER, "external_subject_id": ""},
            instance=self.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)

    def test_owner_can_promote_to_manager(self):
        request = self.factory.post("/admin/accounts/userprofile/")
        request.user = self.owner

        Form = self.admin.get_form(request, obj=self.profile)
        form = Form(
            data={"user": cast(int, self.target.pk), "role": UserProfile.ROLE_MANAGER, "external_subject_id": ""},
            instance=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
