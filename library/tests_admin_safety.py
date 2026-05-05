from __future__ import annotations

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from .admin import LibraryGroupMembershipAdmin
from .group_services import get_public_group, ensure_user_public_membership
from .models import LibraryGroupMembership


class _DummySite(AdminSite):
    pass


class LibraryAdminSafetyTest(TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.admin = LibraryGroupMembershipAdmin(LibraryGroupMembership, self.site)
        self.factory = RequestFactory()

        self.staff = User.objects.create_user(username="staff", password="pw", is_staff=True)
        ensure_user_public_membership(user=self.staff)

        self.public = get_public_group()
        self.membership = LibraryGroupMembership.objects.get(user=self.staff, group=self.public)

    def test_public_membership_not_deletable_in_admin(self):
        request = self.factory.get("/admin/library/librarygroupmembership/")
        request.user = self.staff
        self.assertFalse(self.admin.has_delete_permission(request, obj=self.membership))

