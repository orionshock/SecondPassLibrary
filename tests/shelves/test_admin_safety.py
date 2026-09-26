from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path

from library.models import Book, LibraryGroup
from shelves.admin import (
    ShelfAdmin,
    ShelfAdminForm,
    ShelfItemAdmin,
    ShelfItemInline,
)
from shelves.models import Shelf, ShelfItem


urlpatterns = [path("admin/", admin.site.urls)]


class _DummySite(AdminSite):
    pass


@override_settings(ROOT_URLCONF=__name__)
class ShelfAdminSafetyTests(TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.shelf_admin = ShelfAdmin(Shelf, self.site)
        self.shelf_item_admin = ShelfItemAdmin(ShelfItem, self.site)
        self.shelf_item_inline = ShelfItemInline(Shelf, self.site)
        self.factory = RequestFactory()
        self.request = self.factory.get("/admin/shelves/shelf/")
        self.user = User.objects.create_user(
            username="owner", email="owner@example.com", password="pw"
        )
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        self.group = LibraryGroup.objects.create(name="Test Group")
        self.book = Book.objects.create(title="Inline Book")

    def test_owner_user_shelf_requires_owner_user_and_rejects_owner_group(self):
        form = ShelfAdminForm(
            data={
                "name": "User Shelf",
                "owner_type": Shelf.OWNER_TYPE_USER,
                "owner_group": str(self.group.pk),
                "visibility": Shelf.VISIBILITY_PRIVATE,
            },
            instance=Shelf(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("owner_user", form.errors)
        self.assertIn("owner_group", form.errors)

    def test_owner_group_shelf_requires_owner_group_and_rejects_owner_user(self):
        form = ShelfAdminForm(
            data={
                "name": "Group Shelf",
                "owner_type": Shelf.OWNER_TYPE_GROUP,
                "owner_user": str(self.user.pk),
                "visibility": Shelf.VISIBILITY_PRIVATE,
            },
            instance=Shelf(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("owner_group", form.errors)
        self.assertIn("owner_user", form.errors)

    def test_group_shelf_rejects_non_private_visibility(self):
        form = ShelfAdminForm(
            data={
                "name": "Group Shelf",
                "owner_type": Shelf.OWNER_TYPE_GROUP,
                "owner_group": str(self.group.pk),
                "visibility": Shelf.VISIBILITY_LISTED,
            },
            instance=Shelf(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("visibility", form.errors)

    def test_shelf_description_admin_uses_shared_sanitizer_and_limit(self):
        shelf = Shelf(
            name="Formatted",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.user,
            visibility=Shelf.VISIBILITY_PRIVATE,
        )
        valid = ShelfAdminForm(
            data={
                "name": shelf.name,
                "description": '<p class="no">Safe <em>shelf</em></p><script>bad()</script>',
                "owner_type": Shelf.OWNER_TYPE_USER,
                "owner_user": str(self.user.pk),
                "visibility": Shelf.VISIBILITY_PRIVATE,
            },
            instance=shelf,
        )
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.cleaned_data["description"], "<p>Safe <em>shelf</em></p>")

        invalid = ShelfAdminForm(
            data={
                "name": shelf.name,
                "description": "x" * 25_001,
                "owner_type": Shelf.OWNER_TYPE_USER,
                "owner_user": str(self.user.pk),
                "visibility": Shelf.VISIBILITY_PRIVATE,
            },
            instance=shelf,
        )
        self.assertFalse(invalid.is_valid())
        self.assertIn("description", invalid.errors)

    def test_system_fields_are_readonly(self):
        self.request.user = self.user
        readonly = self.shelf_admin.get_readonly_fields(
            self.request, obj=Shelf(owner_type=Shelf.OWNER_TYPE_USER)
        )

        self.assertIn("id", readonly)
        self.assertIn("created_at", readonly)
        self.assertIn("updated_at", readonly)
        self.assertIn("created_by", readonly)
    def test_shelf_item_inline_is_readonly_diagnostic(self):
        self.request.user = self.superuser

        self.assertEqual(
            self.shelf_item_inline.template,
            "admin/shelves/shelf/edit_inline/shelf_items_tabular.html",
        )
        self.assertFalse(self.shelf_item_inline.has_add_permission(self.request))
        self.assertFalse(self.shelf_item_inline.has_change_permission(self.request))
        self.assertTrue(self.shelf_item_inline.can_delete)
        self.assertTrue(self.shelf_item_inline.has_delete_permission(self.request))
        self.assertFalse(self.shelf_item_inline.show_change_link)
        self.assertNotIn("book", self.shelf_item_inline.fields)
        for field in ["book_link", "position", "added_by", "created_at", "updated_at"]:
            self.assertIn(field, self.shelf_item_inline.readonly_fields)

    def test_shelf_item_inline_book_display_links_to_book_admin_only(self):
        shelf = Shelf.objects.create(
            name="Shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.user,
            created_by=self.user,
        )
        item = ShelfItem.objects.create(
            shelf=shelf,
            book=self.book,
            position=0,
            added_by=self.user,
        )

        html = str(self.shelf_item_inline.book_link(item))

        self.assertIn("Inline Book", html)
        self.assertIn(f"/admin/library/book/{self.book.pk}/change/", html)
        self.assertNotIn("Shelf:", html)

    def test_shelf_item_inline_delete_canonicalizes_positions(self):
        self.request.user = self.superuser
        shelf = Shelf.objects.create(
            name="Shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.user,
            created_by=self.user,
        )
        books = [
            Book.objects.create(title="A"),
            Book.objects.create(title="B"),
            Book.objects.create(title="C"),
        ]
        items = [
            ShelfItem.objects.create(
                shelf=shelf,
                book=book,
                position=position,
                added_by=self.user,
            )
            for position, book in enumerate(books)
        ]
        formset_class = self.shelf_item_inline.get_formset(self.request, obj=shelf)
        prefix = formset_class.get_default_prefix()
        data = {
            f"{prefix}-TOTAL_FORMS": "3",
            f"{prefix}-INITIAL_FORMS": "3",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
        for index, item in enumerate(items):
            data[f"{prefix}-{index}-id"] = str(item.pk)
        data[f"{prefix}-1-DELETE"] = "on"

        formset = formset_class(data=data, instance=shelf)

        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual(
            list(
                ShelfItem.objects.filter(shelf=shelf)
                .order_by("position")
                .values_list("book__title", "position")
            ),
            [("A", 0), ("C", 1)],
        )

    def test_standalone_shelf_item_admin_is_hidden_but_does_not_block_shelf_deletes(
        self,
    ):
        self.request.user = self.user

        self.assertFalse(self.shelf_item_admin.has_add_permission(self.request))
        self.assertFalse(self.shelf_item_admin.has_change_permission(self.request))
        self.assertFalse(self.shelf_item_admin.has_delete_permission(self.request))
        self.assertFalse(self.shelf_item_admin.has_module_permission(self.request))

        self.request.user = self.superuser
        self.assertTrue(self.shelf_item_admin.has_delete_permission(self.request))
        self.assertFalse(self.shelf_item_admin.has_module_permission(self.request))

    def assert_user_related_widget_is_view_only(self, widget):
        self.assertFalse(widget.can_add_related)
        self.assertFalse(widget.can_change_related)
        self.assertFalse(widget.can_delete_related)
        self.assertTrue(hasattr(widget, "can_view_related"))

    def assert_library_group_related_widget_is_view_only(self, widget):
        self.assertFalse(widget.can_add_related)
        self.assertFalse(widget.can_change_related)
        self.assertFalse(widget.can_delete_related)
        self.assertTrue(hasattr(widget, "can_view_related"))

    def test_shelf_admin_user_widgets_keep_only_view_related_control(self):
        self.request.user = self.superuser

        for field_name in ["owner_user", "created_by"]:
            field = Shelf._meta.get_field(field_name)
            formfield = self.shelf_admin.formfield_for_dbfield(field, self.request)
            self.assert_user_related_widget_is_view_only(formfield.widget)

    def test_shelf_admin_group_widget_keeps_only_view_related_control(self):
        self.request.user = self.superuser

        field = Shelf._meta.get_field("owner_group")
        formfield = self.shelf_admin.formfield_for_dbfield(field, self.request)

        self.assert_library_group_related_widget_is_view_only(formfield.widget)
