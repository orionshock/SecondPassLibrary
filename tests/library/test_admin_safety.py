from __future__ import annotations

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from library.admin import LibraryGroupAdmin, LibraryGroupMembershipAdmin
from library.group_services import ensure_user_public_membership, get_public_group
from library.models import LibraryGroup, LibraryGroupMembership


class _DummySite(AdminSite):
    pass


class LibraryAdminSafetyTest(TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.membership_admin = LibraryGroupMembershipAdmin(
            LibraryGroupMembership, self.site
        )
        self.group_admin = LibraryGroupAdmin(LibraryGroup, self.site)
        self.factory = RequestFactory()

        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="pw", is_staff=True
        )
        ensure_user_public_membership(user=self.staff)

        self.public = get_public_group()
        self.membership = LibraryGroupMembership.objects.get(
            user=self.staff, group=self.public
        )

    def test_public_membership_not_deletable_in_admin(self):
        request = self.factory.get("/admin/library/librarygroupmembership/")
        request.user = self.staff
        self.assertFalse(
            self.membership_admin.has_delete_permission(request, obj=self.membership)
        )

    def test_public_group_not_deletable_in_admin(self):
        request = self.factory.get("/admin/library/librarygroup/")
        request.user = self.staff
        self.assertFalse(self.group_admin.has_delete_permission(request, obj=self.public))

    def test_public_group_slug_is_readonly_in_admin(self):
        request = self.factory.get("/admin/library/librarygroup/")
        request.user = self.staff
        readonly = set(self.group_admin.get_readonly_fields(request, obj=self.public))
        self.assertIn("slug", readonly)

