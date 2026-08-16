from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from library.models import LibraryGroupMembership
from shelves.unavailable_item_cleanup import cleanup_unavailable_user_shelf_items
from shelves.models import Shelf, ShelfItem
from shelves.services import create_shelf
from tests.shelves.service_helpers import ShelfServiceFixtureMixin


class CleanupShelvesTests(ShelfServiceFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.personal = create_shelf(
            self.reader,
            name="Private\nQueue",
            owner_type=Shelf.OWNER_TYPE_USER,
        )
        self.accessible = ShelfItem.objects.create(
            shelf=self.personal,
            book=self.book_other,
            position=4,
            added_by=self.reader,
        )
        self.unavailable = ShelfItem.objects.create(
            shelf=self.personal,
            book=self.book_in_group,
            position=9,
            added_by=self.reader,
        )
        self.group_shelf = create_shelf(
            self.owner,
            name="Group Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
        )
        self.group_item = ShelfItem.objects.create(
            shelf=self.group_shelf,
            book=self.book_in_group,
            position=7,
            added_by=self.owner,
        )
        LibraryGroupMembership.objects.filter(
            user=self.reader,
            group=self.group,
        ).delete()

    def test_dry_run_reports_without_mutating_and_bounds_names(self):
        output = StringIO()

        call_command("cleanup_shelves", stdout=output)

        text = output.getvalue()
        self.assertIn("Mode: Dry run", text)
        self.assertRegex(text, r"User-owned Shelves affected\s+1")
        self.assertRegex(text, r"Unavailable Shelf items\s+1")
        self.assertIn("Affected Shelves", text)
        self.assertIn("Private Queue", text)
        self.assertNotIn("Private\nQueue", text)
        self.assertIn("Result: Dry run complete; no changes made", text)
        self.assertTrue(ShelfItem.objects.filter(pk=self.unavailable.pk).exists())

    def test_apply_removes_only_unavailable_personal_items_and_canonicalizes(self):
        output = StringIO()

        call_command("cleanup_shelves", apply=True, stdout=output)

        self.assertFalse(ShelfItem.objects.filter(pk=self.unavailable.pk).exists())
        self.assertTrue(ShelfItem.objects.filter(pk=self.accessible.pk).exists())
        self.assertTrue(ShelfItem.objects.filter(pk=self.group_item.pk).exists())
        self.accessible.refresh_from_db()
        self.group_item.refresh_from_db()
        self.assertEqual(self.accessible.position, 0)
        self.assertEqual(self.group_item.position, 7)
        self.assertTrue(Shelf.objects.filter(pk=self.personal.pk).exists())
        text = output.getvalue()
        self.assertIn("Mode: Apply", text)
        self.assertRegex(text, r"Unavailable Shelf items removed\s+1")
        self.assertIn("Result: Succeeded", text)

    def test_plan_escapes_markup_and_bounds_shelf_names(self):
        self.personal.name = f"[red]{'X' * 100}[/red]\nQueue"
        self.personal.save(update_fields=("name", "updated_at"))
        output = StringIO()

        call_command("cleanup_shelves", stdout=output)

        text = output.getvalue()
        self.assertIn("[red]", text)
        self.assertNotIn("\x1b[", text)
        self.assertNotIn("\nQueue", text)

    def test_repeated_apply_is_idempotent(self):
        first = cleanup_unavailable_user_shelf_items()
        second = cleanup_unavailable_user_shelf_items()

        self.assertEqual(first.removed_item_count, 1)
        self.assertEqual(second.removed_item_count, 0)
        self.assertEqual(second.affected_shelf_count, 0)

    def test_cleanup_uses_shelf_owner_access_not_an_operator(self):
        result = cleanup_unavailable_user_shelf_items()

        self.assertEqual(result.removed_item_count, 1)
        self.assertFalse(ShelfItem.objects.filter(pk=self.unavailable.pk).exists())
        self.assertTrue(self.owner.is_superuser)
