from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import SimpleTestCase
from unittest.mock import Mock, patch

from library.admin import BookGroupAssignmentAdmin
from library.models import Book, BookGroupAssignment, LibraryGroup


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
