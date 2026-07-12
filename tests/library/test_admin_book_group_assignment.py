from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import SimpleTestCase
from unittest.mock import Mock, patch

from library.admin import (
    BookGroupAssignmentAdmin,
    LibraryGroupMembershipAdmin,
    _sort_library_admin_models,
)
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)


class BookGroupAssignmentAdminTests(SimpleTestCase):
    def setUp(self):
        self.model_admin = BookGroupAssignmentAdmin(BookGroupAssignment, AdminSite())
        self.request = RequestFactory().post("/admin/library/bookgroupassignment/add/")
        self.request.user = get_user_model()(username="operator")

    def test_join_table_is_registered_with_service_backed_operations(self):
        self.assertIsInstance(admin.site._registry[BookGroupAssignment], BookGroupAssignmentAdmin)
        self.assertNotIn("id", self.model_admin.list_display)
        self.assertEqual(self.model_admin.list_display_links, ["book"])
        self.assertEqual(self.model_admin.actions, ["remove_assignments"])
        self.assertFalse(self.model_admin.has_change_permission(None))
        self.assertEqual(
            self.model_admin.readonly_fields,
            ["id", "book", "group", "added_by", "created_at", "updated_at"],
        )

    @patch("library.admin.group_services.add_book_to_group")
    def test_add_uses_group_assignment_service(self, add_book_to_group):
        book = Book(title="Test book")
        group = LibraryGroup(name="Test group")
        saved_assignment = Mock(
            pk="assignment-id",
            added_by=self.request.user,
            created_at=Mock(),
            updated_at=Mock(),
        )
        add_book_to_group.return_value = saved_assignment
        assignment = BookGroupAssignment(book=book, group=group)

        self.model_admin.save_model(self.request, assignment, form=None, change=False)

        add_book_to_group.assert_called_once_with(
            book=book,
            group=group,
            actor=self.request.user,
        )
        self.assertEqual(assignment.pk, saved_assignment.pk)

    @patch("library.admin.group_services.remove_book_from_group")
    def test_delete_uses_group_assignment_service(self, remove_book_from_group):
        assignment = Mock(book=Mock(), group=Mock())

        self.model_admin.delete_model(self.request, assignment)

        remove_book_from_group.assert_called_once_with(
            book=assignment.book,
            group=assignment.group,
            actor=self.request.user,
        )


class LibraryGroupMembershipAdminTests(SimpleTestCase):
    def setUp(self):
        self.model_admin = LibraryGroupMembershipAdmin(
            LibraryGroupMembership,
            AdminSite(),
        )
        self.request = RequestFactory().post(
            "/admin/library/librarygroupmembership/add/"
        )
        self.request.user = get_user_model()(username="operator")

    @patch("library.admin.is_public_group", return_value=False)
    @patch(
        "library.admin.server_settings.advanced_library_groups_enabled",
        return_value=True,
    )
    def test_user_group_assignments_are_registered_with_service_operations(
        self,
        advanced_groups_enabled,
        is_public,
    ):
        self.assertIsInstance(
            admin.site._registry[LibraryGroupMembership],
            LibraryGroupMembershipAdmin,
        )
        self.assertNotIn("id", self.model_admin.list_display)
        self.assertEqual(self.model_admin.list_display_links, ["user"])
        self.assertEqual(self.model_admin.actions, ["remove_assignments"])
        self.assertNotIn("is_curator", self.model_admin.readonly_fields)
        form_class = self.model_admin.get_form(
            self.request,
            obj=LibraryGroupMembership(group=LibraryGroup(name="Room")),
        )
        self.assertEqual(list(form_class.base_fields), ["is_curator"])

    @patch("library.admin.is_public_group", return_value=False)
    @patch(
        "library.admin.server_settings.advanced_library_groups_enabled",
        return_value=False,
    )
    def test_curator_field_is_hidden_when_advanced_groups_are_disabled(
        self,
        advanced_groups_enabled,
        is_public,
    ):
        membership = LibraryGroupMembership(group=LibraryGroup(name="Room"))

        form_class = self.model_admin.get_form(self.request, obj=membership)

        self.assertNotIn("is_curator", form_class.base_fields)

    @patch("library.admin.is_public_group", return_value=True)
    @patch(
        "library.admin.server_settings.advanced_library_groups_enabled",
        return_value=True,
    )
    def test_curator_field_is_hidden_for_public_membership(
        self,
        advanced_groups_enabled,
        is_public,
    ):
        membership = LibraryGroupMembership(group=LibraryGroup(name="Common Room"))

        form_class = self.model_admin.get_form(self.request, obj=membership)

        self.assertNotIn("is_curator", form_class.base_fields)

    @patch("library.admin.group_services.set_group_membership_curator")
    @patch("library.admin.is_public_group", return_value=True)
    @patch(
        "library.admin.server_settings.advanced_library_groups_enabled",
        return_value=True,
    )
    def test_public_membership_edit_cannot_set_curator(
        self,
        advanced_groups_enabled,
        is_public,
        set_group_membership_curator,
    ):
        membership = LibraryGroupMembership(
            group=LibraryGroup(name="Common Room"),
            is_curator=True,
        )

        self.model_admin.save_model(self.request, membership, form=None, change=True)

        set_group_membership_curator.assert_not_called()

    def test_curator_field_is_hidden_on_add(self):
        form_class = self.model_admin.get_form(self.request, obj=None)

        self.assertNotIn("is_curator", form_class.base_fields)

    @patch("library.admin.group_services.add_user_to_group")
    def test_add_uses_membership_service(self, add_user_to_group):
        user = get_user_model()(username="reader")
        group = LibraryGroup(name="Room")
        saved_membership = Mock(
            pk="membership-id",
            is_curator=True,
            created_at=Mock(),
            updated_at=Mock(),
        )
        add_user_to_group.return_value = saved_membership
        membership = LibraryGroupMembership(
            user=user,
            group=group,
            is_curator=True,
        )

        self.model_admin.save_model(self.request, membership, form=None, change=False)

        add_user_to_group.assert_called_once_with(
            user=user,
            group=group,
            is_curator=True,
        )
        self.assertEqual(membership.pk, saved_membership.pk)

    @patch("library.admin.group_services.set_group_membership_curator")
    @patch("library.admin.is_public_group", return_value=False)
    @patch(
        "library.admin.server_settings.advanced_library_groups_enabled",
        return_value=True,
    )
    def test_edit_updates_only_curator_flag_through_service(
        self,
        advanced_groups_enabled,
        is_public,
        set_group_membership_curator,
    ):
        membership = LibraryGroupMembership(
            user=get_user_model()(username="reader"),
            group=LibraryGroup(name="Room"),
            is_curator=False,
        )

        self.model_admin.save_model(self.request, membership, form=None, change=True)

        set_group_membership_curator.assert_called_once_with(
            membership=membership,
            is_curator=False,
        )

    @patch("library.admin.group_services.remove_user_from_group")
    def test_delete_uses_orphan_safe_membership_service(self, remove_user_from_group):
        membership = Mock(user=Mock(), group=Mock())

        self.model_admin.delete_model(self.request, membership)

        remove_user_from_group.assert_called_once_with(
            user=membership.user,
            group=membership.group,
        )

    @patch("library.admin.group_services.remove_user_from_group", return_value=True)
    def test_bulk_remove_uses_orphan_safe_membership_service(
        self,
        remove_user_from_group,
    ):
        membership = Mock(user=Mock(), group=Mock())
        queryset = Mock()
        queryset.select_related.return_value = [membership]
        self.model_admin.message_user = Mock()

        self.model_admin.remove_assignments(self.request, queryset)

        remove_user_from_group.assert_called_once_with(
            user=membership.user,
            group=membership.group,
        )
        self.model_admin.message_user.assert_called_once_with(
            self.request,
            "Removed 1 user-group assignment(s).",
        )


class LibraryAdminMenuOrderTests(SimpleTestCase):
    def test_library_section_uses_requested_labels_and_order(self):
        app = {
            "models": [
                {"object_name": "LibraryGroupMembership", "name": "Memberships"},
                {"object_name": "BookGroupAssignment", "name": "Assignments"},
                {"object_name": "LibraryGroup", "name": "Groups"},
                {"object_name": "Book", "name": "Books"},
                {"object_name": "CatalogTag", "name": "Tags"},
            ]
        }

        _sort_library_admin_models(app)

        self.assertEqual(
            [model["name"] for model in app["models"]],
            [
                "Books",
                "Catalog Tags",
                "Library Groups",
                "User Group Assignments",
                "Book Group Assignments",
            ],
        )


class AdvancedGroupsAssignmentAdminVisibilityTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/library/")
        self.request.user = Mock()
        self.request.user.has_perm.return_value = True
        self.request.user.has_module_perms.return_value = True
        self.memberships = LibraryGroupMembershipAdmin(
            LibraryGroupMembership,
            AdminSite(),
        )
        self.books = BookGroupAssignmentAdmin(BookGroupAssignment, AdminSite())

    @patch(
        "library.admin.server_settings.advanced_library_groups_enabled",
        return_value=False,
    )
    def test_disabled_state_hides_and_denies_assignment_admins(self, enabled):
        for model_admin in [self.memberships, self.books]:
            with self.subTest(model=model_admin.model):
                self.assertEqual(model_admin.get_model_perms(self.request), {})
                self.assertFalse(model_admin.has_module_permission(self.request))
                self.assertFalse(model_admin.has_view_permission(self.request))
                self.assertFalse(model_admin.has_add_permission(self.request))
                self.assertFalse(model_admin.has_delete_permission(self.request))

    @patch(
        "library.admin.server_settings.advanced_library_groups_enabled",
        return_value=True,
    )
    def test_enabled_state_restores_assignment_admins(self, enabled):
        for model_admin in [self.memberships, self.books]:
            with self.subTest(model=model_admin.model):
                self.assertTrue(model_admin.has_module_permission(self.request))
                self.assertTrue(model_admin.has_view_permission(self.request))
                self.assertTrue(model_admin.has_add_permission(self.request))
                self.assertTrue(model_admin.has_delete_permission(self.request))
