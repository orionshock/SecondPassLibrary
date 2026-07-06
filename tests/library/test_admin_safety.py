from __future__ import annotations

from pathlib import Path

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from core import server_settings
from core.admin import ServerSettingAdmin, ServerSettingAdminForm
from core.models import ServerSetting
from library.admin import (
    BookGroupAssignmentInline,
    BookGroupAssignmentAdmin,
    LibraryGroupAdmin,
    LibraryGroupMembershipAdmin,
)
from library.groups.services import ensure_user_public_membership
from library.groups.public_group import get_public_group
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)


class _DummySite(AdminSite):
    pass


class LibraryAdminSafetyTest(TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.membership_admin = LibraryGroupMembershipAdmin(
            LibraryGroupMembership, self.site
        )
        self.group_admin = LibraryGroupAdmin(LibraryGroup, self.site)
        self.book_group_assignment_admin = BookGroupAssignmentAdmin(
            BookGroupAssignment, self.site
        )
        self.factory = RequestFactory()

        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="pw", is_staff=True
        )
        ensure_user_public_membership(user=self.staff)

        self.public = get_public_group()
        self.membership = LibraryGroupMembership.objects.get(
            user=self.staff, group=self.public
        )
        book = Book.objects.create(title="Admin Safety Book")
        self.assignment = BookGroupAssignment.objects.create(
            book=book,
            group=self.public,
            added_by=self.staff,
        )

    def test_library_group_membership_admin_uses_standard_permissions(self):
        request = self.factory.get("/admin/library/librarygroupmembership/")
        request.user = User.objects.create_superuser(
            username="owner-membership-admin",
            email="owner-membership@example.com",
            password="pw",
        )

        self.assertTrue(self.membership_admin.has_add_permission(request))
        self.assertTrue(
            self.membership_admin.has_change_permission(request, obj=self.membership)
        )
        self.assertTrue(
            self.membership_admin.has_delete_permission(request, obj=self.membership)
        )

    def test_library_group_membership_admin_uses_autocomplete_widgets(self):
        self.assertEqual(self.membership_admin.autocomplete_fields, ["user", "group"])
        self.assertEqual(self.membership_admin.raw_id_fields, ())

    def test_public_group_not_deletable_in_admin(self):
        request = self.factory.get("/admin/library/librarygroup/")
        request.user = self.staff
        self.assertFalse(
            self.group_admin.has_delete_permission(request, obj=self.public)
        )

    def test_book_group_assignment_admin_uses_standard_permissions(self):
        request = self.factory.get("/admin/library/bookgroupassignment/")
        request.user = User.objects.create_superuser(
            username="owner-assignment-admin",
            email="owner-assignment@example.com",
            password="pw",
        )

        self.assertTrue(self.book_group_assignment_admin.has_add_permission(request))
        self.assertTrue(
            self.book_group_assignment_admin.has_change_permission(
                request, obj=self.assignment
            )
        )
        self.assertTrue(
            self.book_group_assignment_admin.has_delete_permission(
                request, obj=self.assignment
            )
        )

    def test_book_group_assignment_admin_uses_autocomplete_widgets(self):
        self.assertEqual(
            self.book_group_assignment_admin.autocomplete_fields,
            ["book", "group", "added_by"],
        )
        self.assertEqual(self.book_group_assignment_admin.raw_id_fields, ())

    def test_book_group_assignment_inline_uses_autocomplete_widgets(self):
        inline = BookGroupAssignmentInline(Book, self.site)

        self.assertEqual(inline.autocomplete_fields, ["group", "added_by"])
        self.assertEqual(inline.raw_id_fields, ())

    def assert_user_related_widget_is_view_only(self, widget):
        self.assertFalse(widget.can_add_related)
        self.assertFalse(widget.can_change_related)
        self.assertFalse(widget.can_delete_related)
        self.assertTrue(hasattr(widget, "can_view_related"))

    def test_library_group_membership_admin_user_widget_is_view_only(self):
        request = self.factory.get("/admin/library/librarygroupmembership/")
        request.user = User.objects.create_superuser(
            username="owner-membership-user-widget",
            email="owner-membership-user-widget@example.com",
            password="pw",
        )

        field = LibraryGroupMembership._meta.get_field("user")
        formfield = self.membership_admin.formfield_for_dbfield(field, request)

        self.assert_user_related_widget_is_view_only(formfield.widget)

    def test_book_group_assignment_admin_added_by_widget_is_view_only(self):
        request = self.factory.get("/admin/library/bookgroupassignment/")
        request.user = User.objects.create_superuser(
            username="owner-assignment-user-widget",
            email="owner-assignment-user-widget@example.com",
            password="pw",
        )

        field = BookGroupAssignment._meta.get_field("added_by")
        formfield = self.book_group_assignment_admin.formfield_for_dbfield(
            field, request
        )

        self.assert_user_related_widget_is_view_only(formfield.widget)

    def test_book_group_assignment_inline_added_by_widget_is_view_only(self):
        inline = BookGroupAssignmentInline(Book, self.site)
        request = self.factory.get("/admin/library/book/")
        request.user = User.objects.create_superuser(
            username="owner-inline-user-widget",
            email="owner-inline-user-widget@example.com",
            password="pw",
        )

        field = BookGroupAssignment._meta.get_field("added_by")
        formfield = inline.formfield_for_dbfield(field, request)

        self.assert_user_related_widget_is_view_only(formfield.widget)

    def test_public_group_name_is_readonly_in_admin(self):
        request = self.factory.get("/admin/library/librarygroup/")
        request.user = self.staff
        readonly = set(self.group_admin.get_readonly_fields(request, obj=self.public))
        self.assertIn("name", readonly)


class AdvancedGroupsRecoveryAdminSafetyTest(TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.admin = ServerSettingAdmin(ServerSetting, self.site)
        self.factory = RequestFactory()
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="pw", is_staff=True
        )
        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )

    def _attach_messages(self, request):
        setattr(request, "session", {})
        setattr(request, "_messages", FallbackStorage(request))

    def test_normal_admin_form_cannot_flip_advanced_groups_false(self):
        setting = server_settings.set_server_setting(
            key=server_settings.ADVANCED_LIBRARY_GROUPS_SETTING,
            value=True,
            description="test",
        )

        form = ServerSettingAdminForm(
            data={
                "key": server_settings.ADVANCED_LIBRARY_GROUPS_SETTING,
                "value": "false",
                "description": "test",
            },
            instance=setting,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("recovery flow", str(form.errors))

    def test_advanced_groups_setting_change_page_is_recovery_oriented(self):
        setting = server_settings.set_server_setting(
            key=server_settings.ADVANCED_LIBRARY_GROUPS_SETTING,
            value=True,
            description="test",
        )
        request = self.factory.get(f"/admin/core/serversetting/{setting.pk}/change/")
        request.user = self.owner

        response = self.admin.change_view(request, str(setting.pk))
        fieldsets = self.admin.get_fieldsets(request, obj=setting)
        flattened_fields = [
            field for _title, options in fieldsets for field in options["fields"]
        ]

        self.assertEqual(response.status_code, 200)
        self.assertIn("advanced_groups_status", flattened_fields)
        self.assertIn("advanced_groups_recovery_summary", flattened_fields)
        self.assertIn("advanced_groups_recovery_link", flattened_fields)
        self.assertNotIn("value", flattened_fields)
        self.assertNotIn("description", flattened_fields)
        self.assertFalse(response.context_data["show_save"])
        self.assertFalse(response.context_data["show_save_and_continue"])
        self.assertFalse(response.context_data["show_delete"])
        self.assertIn(
            "Do not edit this database setting directly",
            str(self.admin.advanced_groups_recovery_summary(setting)),
        )

    def test_recovery_view_requires_superuser(self):
        request = self.factory.get("/admin/core/serversetting/advanced-groups-disable/")
        request.user = self.staff

        with self.assertRaises(PermissionDenied):
            self.admin.advanced_groups_disable_view(request)

    def test_recovery_preview_renders_summary_context_for_superuser(self):
        request = self.factory.get("/admin/core/serversetting/advanced-groups-disable/")
        request.user = self.owner

        response = self.admin.advanced_groups_disable_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["plan"].phases[0], "Rename shelves")
        self.assertEqual(response.context_data["display_limit"], 100)

    def test_recovery_post_requires_confirmation(self):
        request = self.factory.post(
            "/admin/core/serversetting/advanced-groups-disable/",
            data={"fingerprint": "anything"},
        )
        request.user = self.owner

        response = self.admin.advanced_groups_disable_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context_data["form"].is_valid())

    def test_recovery_success_renders_completion_without_raw_dict_flash(self):
        server_settings.set_advanced_library_groups_enabled(True)
        preview_request = self.factory.get(
            "/admin/core/serversetting/advanced-groups-disable/"
        )
        preview_request.user = self.owner
        preview = self.admin.advanced_groups_disable_view(preview_request)
        fingerprint = preview.context_data["plan"].fingerprint

        request = self.factory.post(
            "/admin/core/serversetting/advanced-groups-disable/",
            data={
                "fingerprint": fingerprint,
                "confirm": "on",
                "confirmation_text": "DISABLE ADVANCED GROUPS",
            },
        )
        request.user = self.owner
        self._attach_messages(request)

        response = self.admin.advanced_groups_disable_view(request)
        messages = [message.message for message in request._messages._queued_messages]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.template_name,
            "admin/core/serversetting/advanced_groups_disable_complete.html",
        )
        self.assertEqual(
            response.context_data["title"], "Advanced library groups disabled"
        )
        self.assertEqual(response.context_data["plan"].public_group_name, "Common Room")
        self.assertEqual(response.context_data["summary"]["custom_groups"], 0)
        self.assertIn(
            "Advanced library groups disabled and consolidated into Public Library.",
            messages,
        )
        self.assertNotIn("{", "\n".join(messages))
        self.assertFalse(server_settings.advanced_library_groups_enabled())

        template = Path(
            "core/templates/admin/core/serversetting/advanced_groups_disable_complete.html"
        ).read_text(encoding="utf-8")
        self.assertIn("Shelves renamed/moved", template)
        self.assertIn("Book/group associations removed", template)
        self.assertIn("Users restored/expected to Public", template)
        self.assertIn("Advanced groups disabled", template)

    def test_recovery_stale_fingerprint_does_not_execute(self):
        request = self.factory.post(
            "/admin/core/serversetting/advanced-groups-disable/",
            data={
                "fingerprint": "stale",
                "confirm": "on",
                "confirmation_text": "DISABLE ADVANCED GROUPS",
            },
        )
        request.user = self.owner
        self._attach_messages(request)

        response = self.admin.advanced_groups_disable_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(server_settings.advanced_library_groups_enabled() is False)
        self.assertEqual(
            response.context_data["form"].initial["fingerprint"],
            response.context_data["plan"].fingerprint,
        )
