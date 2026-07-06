from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from core.admin_widgets import keep_only_user_view_related_control
from library.models import Book


class AdminWidgetControlTests(SimpleTestCase):
    def test_user_related_widget_controls_hide_mutations_and_preserve_view(self):
        widget = SimpleNamespace(
            can_add_related=True,
            can_change_related=True,
            can_delete_related=True,
            can_view_related=True,
        )
        formfield = SimpleNamespace(widget=widget)
        db_field = SimpleNamespace(remote_field=SimpleNamespace(model=get_user_model()))

        keep_only_user_view_related_control(formfield, db_field)

        self.assertFalse(widget.can_add_related)
        self.assertFalse(widget.can_change_related)
        self.assertFalse(widget.can_delete_related)
        self.assertTrue(widget.can_view_related)

    def test_non_user_related_widget_controls_are_unchanged(self):
        widget = SimpleNamespace(
            can_add_related=True,
            can_change_related=True,
            can_delete_related=True,
            can_view_related=True,
        )
        formfield = SimpleNamespace(widget=widget)
        db_field = SimpleNamespace(remote_field=SimpleNamespace(model=Book))

        keep_only_user_view_related_control(formfield, db_field)

        self.assertTrue(widget.can_add_related)
        self.assertTrue(widget.can_change_related)
        self.assertTrue(widget.can_delete_related)
        self.assertTrue(widget.can_view_related)
